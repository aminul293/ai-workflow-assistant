import os
os.environ.setdefault("BACKEND_API_KEY", "test-backend-secret")
import os
from pathlib import Path
os.environ['DATABASE_URL']='sqlite:///'+str(Path(__file__).parent/'test_workflow.db')
from fastapi.testclient import TestClient
from app.main import app, Base, engine

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
client=TestClient(app, headers={"X-API-Key":"test-backend-secret"})

def test_demo_flow():
    assert client.get('/api/health').json()['mode']=='synthetic_only'
    message=client.post('/api/inbox/sample',json={'sender':'sample@example.test','subject':'Urgent repair needed','body':'There is an emergency leak in our sample building','source_id':'test-message-1'}).json()
    message2=client.post('/api/inbox/sample',json={'sender':'sample@example.test','subject':'Urgent repair needed','body':'There is an emergency leak in our sample building','source_id':'test-message-1'}).json()
    assert message['id']==message2['id']
    processed=client.post(f"/api/inbox/{message['id']}/process").json()
    assert processed['message']['category']=='service_request'
    assert processed['message']['urgency']=='high'
    assert client.post(f"/api/inbox/{message['id']}/process").json()['duplicate_prevented']
    a=client.get('/api/approvals').json()[0]
    assert client.patch('/api/approvals/'+a['id'],json={'decision':'approved'}).json()['decision']=='approved'
    assert client.patch('/api/approvals/'+a['id'],json={'decision':'approved'}).status_code==409
    assert client.get('/api/dashboard/summary').json()['tasks']==1


def test_batch_import_is_idempotent_and_atomic():
    payload={'messages':[
        {'sender':'alpha@example.test','subject':'Appointment request','body':'Can I schedule a visit?','source_id':'batch-1'},
        {'sender':'beta@example.test','subject':'Billing issue','body':'Payment question','source_id':'batch-2'}
    ]}
    first=client.post('/api/inbox/sample-batch',json=payload)
    assert first.status_code==200
    assert first.json()['inserted']==2
    second=client.post('/api/inbox/sample-batch',json=payload).json()
    assert second['inserted']==0 and second['existing']==2
    duplicate=client.post('/api/inbox/sample-batch',json={'messages':[payload['messages'][0],payload['messages'][0]]})
    assert duplicate.status_code==422
    assert client.get('/api/dashboard/summary').json()['messages']==3

def test_classifier_word_boundaries_and_category_analytics():
    from app.main import classify
    assert classify('Unbroken item; normal business situation')==('general_inquiry','normal')
    assert classify('ASAP: schedule appointment')==('scheduling','high')
    assert classify('We have invoices to review')==('billing','normal')
    msg=client.get('/api/inbox').json()
    billing=next(m for m in msg if m['source_id']=='batch-2')
    client.post('/api/inbox/'+billing['id']+'/process')
    a=client.get('/api/analytics/categories').json()
    assert any(x['name']=='billing' and x['count']==1 for x in a['categories'])
    assert a['high_urgency']>=1

def test_validation_and_approval_transitions():
    assert client.post('/api/inbox/sample',json={'sender':'x','subject':'hey','body':'hi'}).status_code==422
    assert client.patch('/api/tasks/nonexistent',json={'status':'done'}).status_code==404
    assert client.patch('/api/approvals/nonexistent',json={'decision':'sent'}).status_code==422

def test_processor_mock_schema_and_missing_key(monkeypatch):
    from app.ai_processor import extract, ProcessorError
    monkeypatch.setenv('AI_PROVIDER','mock')
    result,provider=extract('Schedule visit','Need an urgent appointment')
    assert provider=='mock' and result.category=='scheduling' and result.urgency=='high'
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    import pytest
    with pytest.raises(ProcessorError,match='OPENAI_API_KEY'):
        extract('Subject','Body')

def test_optional_openai_provider_with_mocked_http(monkeypatch):
    from app.ai_processor import extract
    import httpx, json
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.setenv('OPENAI_API_KEY','fake-test-key')
    class FakeClient:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def post(self,url,**kwargs):
            assert url=='https://api.openai.com/v1/chat/completions'
            assert kwargs['headers']['Authorization']=='Bearer fake-test-key'
            return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'message':{'content':json.dumps({'category':'billing','urgency':'normal','summary':'Invoice request','draft':'Thanks for your inquiry.','confidence':0.95})}}]})
    monkeypatch.setattr(httpx,'Client',FakeClient)
    result,provider=extract('Invoice','Can I get an invoice?')
    assert result.confidence==0.95 and provider=='openai'

def test_provider_failure_creates_no_partial_task(monkeypatch):
    from app.ai_processor import ProcessorError
    monkeypatch.setattr('app.main.extract',lambda *args: (_ for _ in ()).throw(ProcessorError('AI processing failed; no task or approval was created')))
    m=client.post('/api/inbox/sample',json={'sender':'test@example.test','subject':'Processing failure','body':'A fictional question','source_id':'provider-failure'}).json()
    old=client.get('/api/dashboard/summary').json()['tasks']
    response=client.post('/api/inbox/'+m['id']+'/process')
    assert response.status_code==502
    assert client.get('/api/dashboard/summary').json()['tasks']==old
    assert client.get('/api/inbox/'+m['id']).json()['status']=='new'
