from fastapi.testclient import TestClient
from app.main import app

def test_fail_closed(monkeypatch):
    monkeypatch.setenv('BACKEND_API_KEY', 'test-backend-secret')
    client=TestClient(app)
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/inbox').status_code == 401
    assert client.get('/api/inbox',headers={'X-API-Key':'wrong'}).status_code == 401
    correct=client.get('/api/inbox',headers={'X-API-Key':'test-backend-secret'})
    assert correct.status_code == 200
    assert correct.headers.get('X-Request-ID')

def test_missing_server_secret_denies_everyone(monkeypatch):
    monkeypatch.delenv('BACKEND_API_KEY',raising=False)
    assert TestClient(app).get('/api/inbox').status_code == 401
