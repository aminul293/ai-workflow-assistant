"""Synthetic-data HTTP integration checks: every stage through a human decision."""
import os
from uuid import uuid4
os.environ.setdefault('BACKEND_API_KEY', 'test-backend-secret')
from fastapi.testclient import TestClient
from app.main import Base, engine, app

client=TestClient(app, headers={'X-API-Key':os.environ['BACKEND_API_KEY']})

def test_full_synthetic_approval_flow():
    Base.metadata.create_all(engine)
    source='release-'+uuid4().hex
    payload={'sender':'case@sample.test','subject':'Urgent service request',
             'body':'Please fix the urgent issue tomorrow.','source_id':source}
    before=client.get('/api/dashboard/summary')
    assert before.status_code==200
    new=client.post('/api/inbox/sample',json=payload)
    assert new.status_code==201
    ident=new.json()['id']
    assert client.post('/api/inbox/sample',json=payload).json()['id']==ident
    processed=client.post(f'/api/inbox/{ident}/process')
    assert processed.status_code==200
    assert processed.json()['duplicate_prevented'] is False
    repeated=client.post(f'/api/inbox/{ident}/process')
    assert repeated.status_code==200 and repeated.json()['duplicate_prevented'] is True
    task_id=processed.json()['task']['id']
    approval=next(a for a in client.get('/api/approvals').json() if a['task_id']==task_id)
    run=next(r for r in client.get('/api/workflow-runs').json() if r['message_id']==ident)
    trace=client.get('/api/workflow-runs/'+run['id'])
    assert trace.status_code==200 and len(trace.json()['steps'])==8
    decision=client.patch('/api/approvals/'+approval['id'],json={'decision':'approved'})
    assert decision.status_code==200
    assert client.patch('/api/approvals/'+approval['id'],json={'decision':'approved'}).status_code==409
    assert client.get('/api/workflow-runs/'+run['id']).json()['status']=='approved'
    assert next(m for m in client.get('/api/inbox').json() if m['id']==ident)['status']=='approved'
    assert next(t for t in client.get('/api/tasks').json() if t['id']==task_id)['status']=='open'
    assert any(e['event']=='approval_decided' and e['reference_id']==approval['id'] for e in client.get('/api/audit-events').json())

def test_api_key_rejected():
    response=TestClient(app).get('/api/inbox')
    assert response.status_code==401
