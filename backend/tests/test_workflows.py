import os
os.environ.setdefault("BACKEND_API_KEY", "test-backend-secret")
from app.main import app, Base, engine
from fastapi.testclient import TestClient

client=TestClient(app, headers={"X-API-Key":"test-backend-secret"})

def test_graph_and_trace():
    Base.metadata.create_all(engine)
    graph=client.get('/api/workflows/diagram')
    assert graph.status_code==200 and len(graph.json()['nodes'])==8
    payload={'sender':'flow@example.test','subject':'Schedule sample','body':'Please schedule this demo','source_id':'flow-test-id'}
    message=client.post('/api/inbox/sample',json=payload).json()
    result=client.post('/api/inbox/'+message['id']+'/process')
    assert result.status_code==200
    runs=client.get('/api/workflow-runs').json()
    run=next(x for x in runs if x['message_id']==message['id'])
    detail=client.get('/api/workflow-runs/'+run['id']).json()
    assert detail['status']=='awaiting_approval'
    assert [s['node_id'] for s in detail['steps']]==[x['id'] for x in graph.json()['nodes']]
    again=client.post('/api/inbox/'+message['id']+'/process').json()
    assert again['duplicate_prevented'] is True
    assert len([r for r in client.get('/api/workflow-runs').json() if r['message_id']==message['id']])==1
    approval=next(a for a in client.get('/api/approvals').json() if a['task_id']==result.json()['task']['id'])
    assert client.patch('/api/approvals/'+approval['id'],json={'decision':'approved'}).status_code==200
    assert client.get('/api/workflow-runs/'+run['id']).json()['status']=='approved'
    assert client.get('/api/workflow-runs/not-found').status_code==404
