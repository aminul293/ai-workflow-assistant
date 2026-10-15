"""Authorization and state-transition regression coverage using fictional data."""
import os
from uuid import uuid4
os.environ.setdefault('BACKEND_API_KEY','test-backend-secret')
from fastapi.testclient import TestClient
from app.main import Base,app,engine
client=TestClient(app,headers={'X-API-Key':os.environ['BACKEND_API_KEY']})
def _make():
    Base.metadata.create_all(engine)
    m=client.post('/api/inbox/sample',json={'sender':'demo@example.test','subject':'Synthetic task','body':'Please review sample invoice','source_id':'guard-'+uuid4().hex})
    assert m.status_code==201
    processed=client.post('/api/inbox/'+m.json()['id']+'/process')
    assert processed.status_code==200
    task_id=processed.json()['task']['id']
    approval=next(a for a in client.get('/api/approvals').json() if a['task_id']==task_id)
    return task_id,approval['id']
def test_unapproved_task_cannot_be_progressed():
    task,approval=_make()
    for state in ('open','in_progress','done'):
        assert client.patch('/api/tasks/'+task,json={'status':state}).status_code==409
    assert client.patch('/api/approvals/'+approval,json={'decision':'approved'}).status_code==200
    assert client.patch('/api/tasks/'+task,json={'status':'in_progress'}).status_code==200
    assert client.patch('/api/tasks/'+task,json={'status':'done'}).status_code==200
def test_rejected_task_cannot_be_marked_done():
    task,approval=_make()
    assert client.patch('/api/approvals/'+approval,json={'decision':'rejected'}).status_code==200
    assert client.patch('/api/tasks/'+task,json={'status':'done'}).status_code==409
def test_empty_approval_draft_does_not_change_decision():
    task,approval=_make()
    assert client.patch('/api/approvals/'+approval,json={'decision':'approved','draft':'   '}).status_code==422
    current=next(a for a in client.get('/api/approvals').json() if a['id']==approval)
    assert current['decision']=='pending'
