"""Code-level policy checks and action outcomes, independent of model prose."""
import json
import re
import uuid
from jsonschema import Draft202012Validator
from .tools import Denied


def safe_log(value):
    if isinstance(value,dict):
        return {str(k):('[redacted]' if any(x in str(k).lower() for x in ['token','password','secret','authorization','api_key']) else safe_log(v)) for k,v in value.items()}
    if isinstance(value,list): return [safe_log(v) for v in value[:100]]
    if isinstance(value,str):
        value=re.sub(r'(?i)(bearer\s+|sk-ant-|sk-)[A-Za-z0-9_\-]{12,}', '[redacted]', value)
        return value[:16000]
    return value


class Executor:
    def __init__(self,store,catalog):
        self.store,self.catalog=store,catalog

    def invoke(self,tenant,run_id,name,args):
        call_id=uuid.uuid4().hex
        self.store.event(tenant,run_id,{'type':'tool_requested','call_id':call_id,'tool':name,'arguments':safe_log(args)})
        tool=self.catalog.tools.get(name)
        try:
            if tool is None: raise Denied('Unknown or unavailable capability')
            errors=list(Draft202012Validator(tool.parameters).iter_errors(args))
            if errors: raise Denied('Arguments do not match the tool schema')
            if tool.approval:
                key=self.store.propose(tenant,name,args)
                result={'status':'approval_required','approval_id':key,'tool':name,'arguments':args,'expires_in_seconds':600}
            else:
                result=self._perform(tool,tenant,args)
        except Denied as e:
            result={'status':'blocked','reason':str(e)}
        except Exception:
            result={'status':'error','reason':'The tool could not complete; no success is claimed'}
        self.store.event(tenant,run_id,{'type':'tool_outcome','call_id':call_id,'tool':name,**safe_log(result)})
        return result

    def _perform(self,tool,tenant,args):
        output=tool.handler(tenant,args)
        return {'status':'simulated' if tool.effect=='simulated' else 'executed','effect':tool.effect,'output':output}

    def decide(self,tenant,key,approve,run_id):
        # This method is exposed only on the authenticated human API/channel,
        # never in the model's tool definitions or delegation interface.
        row=self.store.consume(tenant,key,approve)
        if not row:
            result={'status':'blocked','reason':'Approval missing, expired, or already consumed'}
        elif not approve:
            result={'status':'rejected'}
        else:
            try:
                result=self._perform(self.catalog.tools[row['tool']],tenant,json.loads(row['arguments']))
            except Denied as e:
                result={'status':'blocked','reason':str(e)}
            except Exception:
                result={'status':'error','reason':'Action failed; approval was consumed and must not be retried automatically'}
            self.store.finish_approval(tenant,key,result['status'])
        self.store.event(tenant,run_id,{'type':'human_decision','approval_id':key,'approved':approve,**safe_log(result)})
        return result
