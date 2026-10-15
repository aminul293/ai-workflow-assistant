import os
os.environ.setdefault("BACKEND_API_KEY", "test-backend-secret")
from app.agents import run_agents, AGENTS
from app.ai_processor import Extraction, ProcessorError
from app.main import app
from fastapi.testclient import TestClient
import pytest

def test_agent_catalog():
    catalog=TestClient(app, headers={'X-API-Key':'test-backend-secret'}).get('/api/agents').json()
    assert len(catalog['agents'])==4
    assert catalog['outbound_actions_enabled'] is False
    assert catalog['human_approval_required'] is True

def test_mock_agents_produce_trace_and_manual_review():
    r=run_agents('demo@example.test','Urgent leak','Emergency leak in synthetic building')
    assert len(r.trace)==4
    assert r.requires_review is True
    assert r.provider=='mock'
    assert r.task_title.startswith('Service Request:')

def test_no_model_call_for_invalid_input():
    def forbidden(*args): raise AssertionError('should not call model')
    with pytest.raises(ProcessorError,match='Intake'):
        run_agents('demo@example.test','','body',classifier=forbidden)

def test_high_confidence_normal_still_has_human_approval():
    def classifier(*args):
        return Extraction(category='billing',urgency='normal',summary='Question',draft='Thanks',confidence=0.99),'test'
    r=run_agents('demo@example.test','Invoice','Can you help?',classifier=classifier)
    assert not r.requires_review
    assert len(r.trace)==4
