from fastapi.testclient import TestClient
from workbench.api import create_app
from workbench.config import Settings


def test_workspace_persistence_and_boundaries(tmp_path):
    settings=Settings(db=str(tmp_path/'app.db'),tokens={'a'*32:'alice','b'*32:'bob'})
    headers={'Authorization':'Bearer '+'a'*32}
    with TestClient(create_app(settings)) as client:
        assert client.get('/').status_code==200
        assert client.get('/static/app.js').status_code==200
        assert client.post('/actions/todo_create',json={'title':'Denied'}).status_code==401
        def invoke(name,args={}):return client.post('/actions/'+name,headers=headers,json=args).json()
        task=invoke('todo_create',{'title':'Ship project'})['output']
        assert invoke('todo_complete',{'id':task['id']})['output']['completed']
        assert client.post('/actions/todo_list',headers={'Authorization':'Bearer '+'b'*32},json={}).json()['output']==[]
        assert client.post('/actions/todo_complete',headers={'Authorization':'Bearer '+'b'*32},json={'id':task['id']}).json()['status']=='blocked'
        invoke('documents_add',{'title':'Guide','text':'Install the workspace locally.'})
        assert invoke('documents_search',{'query':'workspace'})['output'][0]['title']=='Guide'
        proposal=invoke('todo_delete',{'id':task['id']})
        assert proposal['status']=='approval_required'
        assert len(invoke('todo_list')['output'])==1
        assert client.post('/approvals/'+proposal['approval_id'],headers=headers,json={'approve':True}).json()['status']=='executed'
        assert invoke('todo_list')['output']==[]
    with TestClient(create_app(settings)) as client:
        assert len(client.post('/actions/documents_list',headers=headers,json={}).json()['output'])==1


def test_local_config_and_environment_precedence(tmp_path,monkeypatch):
    import json
    path=tmp_path/'config.json'
    path.write_text(json.dumps({'tokens':{'x'*32:'local'}}))
    monkeypatch.setenv('WORKBENCH_CONFIG',str(path))
    monkeypatch.delenv('WORKBENCH_TOKENS',raising=False)
    assert Settings.from_env().tokens=={'x'*32:'local'}
    monkeypatch.setenv('WORKBENCH_TOKENS',json.dumps({'y'*32:'other'}))
    assert Settings.from_env().tokens=={'y'*32:'other'}
