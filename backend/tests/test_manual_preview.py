"""Isolated synthetic-only intake and edited-draft regression coverage."""
import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.main import app, Base, get_db, Approval, Audit, Task

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('BACKEND_API_KEY', 'isolated-preview-test-key')
    monkeypatch.setenv('AI_PROVIDER', 'mock')
    engine = create_engine('sqlite:///' + str(tmp_path / 'preview.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    def isolated_db():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app, headers={'X-API-Key': 'isolated-preview-test-key'}) as c:
            yield c, engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def payload(**changes):
    return dict(sender='invented@sample.test', subject='Fictional appointment',
                body='Please schedule a fictional visit.', source_id='manual-' + uuid4().hex,
                synthetic_ack=True, **changes) if not changes else {**payload(), **changes}


def processed(client):
    c, engine = client
    m = c.post('/api/inbox/fictional', json=payload())
    assert m.status_code == 201
    r = c.post('/api/inbox/' + m.json()['id'] + '/process')
    assert r.status_code == 200
    approval = c.get('/api/approvals').json()[0]
    return m.json()['id'], r.json()['task']['id'], approval


def test_manual_input_normalized_and_retry_safe(client):
    c, _ = client
    data = payload(subject='  Fictional appointment  ', body='  Schedule a fictional visit.  ')
    first = c.post('/api/inbox/fictional', json=data)
    again = c.post('/api/inbox/fictional', json=data)
    assert first.status_code == again.status_code == 201
    assert first.json()['id'] == again.json()['id']
    assert first.json()['subject'] == 'Fictional appointment'
    assert first.json()['body'] == 'Schedule a fictional visit.'
    assert len(c.get('/api/inbox').json()) == 1
    assert c.get('/api/tasks').json() == []
    assert len(c.get('/api/audit-events').json()) == 1

@pytest.mark.parametrize('ack', [False, None, 'true', 1])
def test_explicit_fictional_confirmation_required(client, ack):
    c, _ = client
    assert c.post('/api/inbox/fictional', json=payload(synthetic_ack=ack)).status_code == 422
    assert c.get('/api/inbox').json() == []

@pytest.mark.parametrize('sender', ['person@example.com', 'no-address', 'fake@test.evil', 'a@.test'])
def test_only_test_domain_sender_accepted(client, sender):
    c, _ = client
    assert c.post('/api/inbox/fictional', json=payload(sender=sender)).status_code == 422

@pytest.mark.parametrize('field,value', [('subject','   '), ('body',' \n '), ('source_id',''),
    ('subject','x'*256), ('body','x'*10001), ('source_id','x'*81)])
def test_manual_length_and_blank_validation(client, field, value):
    c, _ = client
    assert c.post('/api/inbox/fictional', json=payload(**{field:value})).status_code == 422
    assert c.get('/api/inbox').json() == []


def test_reusing_identifier_with_changed_input_is_conflict(client):
    c, _ = client
    data = payload()
    assert c.post('/api/inbox/fictional', json=data).status_code == 201
    assert c.post('/api/inbox/fictional', json={**data, 'body':'Different fictional message.'}).status_code == 409
    assert len(c.get('/api/inbox').json()) == 1


def test_anonymous_manual_intake_is_blocked(client):
    c, _ = client
    assert c.post('/api/inbox/fictional', json=payload(), headers={'X-API-Key':''}).status_code == 401


def test_edited_draft_is_saved_with_decision_and_not_sent(client):
    c, _ = client
    mid, tid, a = processed(client)
    edited = 'Thank you. This is an edited fictional response; no visit is booked.'
    r = c.patch('/api/approvals/' + a['id'], json={'decision':'approved','draft':edited,'expected_draft':a['draft']})
    assert r.status_code == 200 and r.json()['draft'] == edited
    assert c.get('/api/approvals').json()[0]['draft'] == edited
    assert c.get('/api/tasks').json()[0]['status'] == 'open'
    assert c.get('/api/inbox/' + mid).json()['status'] == 'approved'
    assert c.get('/api/agents').json()['outbound_actions_enabled'] is False
    assert any(e['event'] == 'approval_decided' and '(no external action)' in e['note'] for e in c.get('/api/audit-events').json())
    assert c.patch('/api/tasks/' + tid, json={'status':'done'}).status_code == 200
    assert c.patch('/api/approvals/' + a['id'], json={'decision':'rejected','draft':'Overwrite'}).status_code == 409
    assert c.get('/api/approvals').json()[0]['draft'] == edited

@pytest.mark.parametrize('draft', ['', '   ', 'x'*2001])
def test_invalid_edited_draft_keeps_review_pending(client, draft):
    c, _ = client
    _, _, a = processed(client)
    assert c.patch('/api/approvals/' + a['id'], json={'decision':'approved','draft':draft}).status_code == 422
    current = c.get('/api/approvals').json()[0]
    assert current['decision'] == 'pending' and current['draft'] == a['draft']


def test_stale_draft_cannot_overwrite_another_review(client):
    c, engine = client
    _, _, a = processed(client)
    with Session(engine) as db:
        db.get(Approval, a['id']).draft = 'A newer fictional draft.'
        db.commit()
    r = c.patch('/api/approvals/' + a['id'], json={'decision':'approved','draft':'Stale overwrite','expected_draft':a['draft']})
    assert r.status_code == 409
    current = c.get('/api/approvals').json()[0]
    assert current['decision'] == 'pending' and current['draft'] == 'A newer fictional draft.'
    assert not any(e['event']=='approval_decided' for e in c.get('/api/audit-events').json())


def test_task_with_missing_approval_fails_closed(client):
    c, engine = client
    _, tid, a = processed(client)
    with Session(engine) as db:
        db.delete(db.get(Approval, a['id'])); db.commit()
    assert c.patch('/api/tasks/' + tid, json={'status':'done'}).status_code == 409


def test_rejection_does_not_apply_unsubmitted_edits(client):
    c, _ = client
    _, tid, a = processed(client)
    r = c.patch('/api/approvals/' + a['id'], json={'decision':'rejected','expected_draft':a['draft']})
    assert r.status_code == 200 and r.json()['draft'] == a['draft']
    assert c.patch('/api/tasks/' + tid, json={'status':'done'}).status_code == 409
