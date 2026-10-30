import base64
import hashlib
import hmac
import json
from fastapi.testclient import TestClient
from workbench.api import create_app
from workbench.config import Settings


A='a'*32
B='b'*32


def test_authenticated_chat_and_trace_isolation(tmp_path):
    app=create_app(Settings(db=str(tmp_path/'api.db'),tokens={A:'alice',B:'bob'}))
    with TestClient(app) as c:
        assert c.post('/chat',json={'message':'hello'}).status_code==401
        assert c.post('/chat',headers={'Authorization':'Bearer wrong'},json={'message':'hello'}).status_code==401
        result=c.post('/chat',headers={'Authorization':'Bearer '+A},json={'message':'remember hello'}).json()
        assert c.get('/runs/'+result['run_id'],headers={'Authorization':'Bearer '+B}).status_code==404
        assert c.get('/runs/'+result['run_id'],headers={'Authorization':'Bearer '+A}).status_code==200
        manifest=c.get('/tools',headers={'Authorization':'Bearer '+A}).json()
        assert len({r['specialist'] for r in manifest})==12
        assert c.post('/chat',headers={'Authorization':'Bearer '+A},content=b'x'*70000).status_code==413


def test_http_human_approval(tmp_path):
    app=create_app(Settings(db=str(tmp_path/'a.db'),tokens={A:'a'}))
    h={'Authorization':'Bearer '+A}
    with TestClient(app) as c:
        r=c.post('/chat',headers=h,json={'message':'/tool tasks_create {"title":"Review"}'}).json()
        p=json.loads(r['reply'])
        assert p['status']=='approval_required'
        assert len(c.get('/approvals',headers=h).json())==1
        r=c.post('/approvals/'+p['approval_id'],headers=h,json={'approve':True}).json()
        assert r['status']=='simulated'
        assert c.post('/approvals/'+p['approval_id'],headers=h,json={'approve':True}).json()['status']=='blocked'


def test_twilio_signature_allowlist_and_replay(tmp_path):
    cfg=Settings(db=str(tmp_path/'w.db'),twilio_token='synthetic-token',twilio_url='https://assistant.example.invalid/whatsapp',twilio_phones=('+12025550123',))
    app=create_app(cfg)
    data={'From':'whatsapp:+12025550123','Body':'remember webhook note','MessageSid':'synthetic-sid','NumMedia':'0'}
    def signed(data):
        value=cfg.twilio_url+''.join(k+data[k] for k in sorted(data))
        return {'X-Twilio-Signature':base64.b64encode(hmac.new(cfg.twilio_token.encode(),value.encode(),hashlib.sha1).digest()).decode()}
    with TestClient(app) as c:
        assert c.post('/whatsapp',data=data).status_code==403
        first=c.post('/whatsapp',data=data,headers=signed(data))
        assert first.status_code==200 and '<Response>' in first.text
        again=c.post('/whatsapp',data=data,headers=signed(data))
        assert again.text==first.text
        assert len(app.state.store.list('whatsapp:+12025550123','note'))==1
        data['From']='whatsapp:+12025550124'
        assert c.post('/whatsapp',data=data,headers=signed(data)).status_code==403


def test_unconfigured_channel_disabled(tmp_path):
    with TestClient(create_app(Settings(db=str(tmp_path/'off.db')))) as c:
        assert c.post('/whatsapp',data={}).status_code==503
