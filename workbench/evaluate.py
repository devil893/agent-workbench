"""SafeLabs transport adapter. Framework verdicts are never recalculated here."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time
import uuid

from .agent import Agent
from .config import Settings
from .execution import Executor
from .storage import Store
from .tools import Catalog

EVALUATOR_COMMIT='1fb34b83b154170551be677df3b350289edf6dcd'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


async def evaluate(output,smoke=False):
    from safelabs import __version__ as evaluator_version
    from safelabs.runner import run_eval
    from safelabs.prompts.loader import get_library
    from safelabs.agents.schemas import AgentResponse, ToolCall
    library=get_library()
    prompts=library.by_category('ASI05')
    if (evaluator_version,library.version,library.schema_version,len(prompts))!=('0.11.2','1.13.0','1.1.0',30):
        raise RuntimeError('Evaluator/prompt versions differ from the pinned pilot. Refusing to silently change the test set.')
    if not smoke and not (os.getenv('ANTHROPIC_API_KEY') and os.getenv('ANTHROPIC_MODEL')):
        raise RuntimeError('Real evaluation requires ANTHROPIC_API_KEY and ANTHROPIC_MODEL. --smoke tests transport only.')
    output=Path(output)
    # New directory per run, so a previous baseline is never overwritten.
    output.mkdir(parents=True,exist_ok=False)
    current={}; records=[]
    def on_start(entry): current['id']=entry.id
    with tempfile.TemporaryDirectory(prefix='workbench-eval-') as tmp:
        settings=Settings(db=str(Path(tmp)/'isolated.sqlite3'),backend='demo' if smoke else 'anthropic',
                          model='' if smoke else os.environ['ANTHROPIC_MODEL'],
                          anthropic_key='' if smoke else os.environ['ANTHROPIC_API_KEY'])
        store=Store(settings.db); catalog=Catalog(store); executor=Executor(store,catalog)
        agent=Agent(settings,store,catalog,executor)
        async def transport(prompt):
            # New tenant per attempt, including framework retries. No state
            # from a previous adversarial prompt can contaminate this one.
            tenant='synthetic-'+uuid.uuid4().hex
            store.add(tenant,'note',{'title':'Synthetic meeting','text':'Discuss the demo on Friday.'})
            start=time.perf_counter()
            result=await agent.run(tenant,prompt)
            events=result['events']
            records.append({'prompt_id':current.get('id'),'run_id':result['run_id'],'tenant':tenant,'events':events,
                            'no_tool_calls':not any(e['type']=='tool_requested' for e in events)})
            # Persist after each prompt, even if a later request fails.
            (output/'tool-events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
            errors=[e['reason'] for e in events if e['type']=='model_error']
            failed=bool(errors)
            calls=[ToolCall.from_arguments(e['tool'],e.get('arguments'),call_id=e.get('call_id')) for e in events if e['type']=='tool_requested']
            return AgentResponse(output='' if failed else result['reply'],
                                 error=errors[0] if failed else None,
                                 tool_calls=calls,provenance={'tool_calls':'inferred'},latency_ms=(time.perf_counter()-start)*1000,
                                 metadata={'run_id':result['run_id'],'smoke_only':smoke})
        result=await run_eval(transport,categories=['ASI05'],on_start=on_start,max_attempts=1)
        # Serialize the framework's own returned object without editing verdicts.
        baseline=output/'framework-baseline.json'
        baseline.write_text(result.model_dump_json(indent=2),encoding='utf-8')
        manifest={'target':'Agent Workbench (fresh implementation)','smoke_only':smoke,
                  'model':settings.model or None,'python':platform.python_version(),
                  'evaluator_version':evaluator_version,'required_evaluator_commit':EVALUATOR_COMMIT,
                  'prompt_library':library.version,'prompt_schema':library.schema_version,
                  'prompt_count':len(prompts),'completed_records':len(result.records),
                  'baseline_sha256':digest(baseline),'tools':catalog.manifest(),
                  'outbound_services':['api.anthropic.com'] if not smoke else [],
                  'dependencies':sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions()),
                  'source_sha256':{str(p.relative_to(Path(__file__).parent)):digest(p) for p in Path(__file__).parent.rglob('*.py')}}
        try:
            root=Path(__file__).resolve().parent.parent
            manifest['agent_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
            manifest['working_tree_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip())
        except (OSError,subprocess.CalledProcessError): manifest['agent_commit']=None
        manifest['limitations']=['External tools simulated; browser is a state machine, not Playwright.',
                                'SQLite, not PostgreSQL; no claims about PostgreSQL role isolation.',
                                'Tool arguments are redacted for common credential patterns; traces are not a guarantee of absence of secrets.',
                                'No actual image-generation, voice, Google OAuth, or external web integrations.',
                                'A smoke run uses deterministic commands and is not an LLM safety evaluation.']
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        comparison=[]
        for r in result.records:
            matching=[x for x in records if x['prompt_id']==r.prompt_id]
            outcomes=[e.get('status') for x in matching for e in x['events'] if e['type']=='tool_outcome']
            comparison.append({'prompt_id':r.prompt_id,'framework_verdict':r.verdict.value if r.verdict else None,
                               'tool_outcomes':outcomes,'no_tool_calls':all(x['no_tool_calls'] for x in matching) if matching else None,
                               'interpretation':'Supplementary evidence only; no safety verdict inferred from action count.'})
        (output/'comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
        return manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,help='A new, non-existing directory; treat results as private')
    parser.add_argument('--smoke',action='store_true',help='Transport check only; no LLM or meaningful safety score')
    args=parser.parse_args()
    manifest=asyncio.run(evaluate(args.output,args.smoke))
    print(json.dumps({'smoke_only':manifest['smoke_only'],'records':manifest['completed_records'],'output':args.output}))


if __name__=='__main__': main()
