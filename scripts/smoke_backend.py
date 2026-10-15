"""Live HTTP smoke test using a temporary migrated SQLite DB and fictional input only."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

backend = Path(__file__).resolve().parents[1] / 'backend'
with tempfile.TemporaryDirectory(prefix='ai-workflow-smoke-') as tmp:
    env = os.environ.copy()
    env.update({
        'DATABASE_URL': 'sqlite:///' + str(Path(tmp) / 'smoke.db'),
        'BACKEND_API_KEY': 'smoke-test-secret-not-for-deployment',
        'AI_PROVIDER': 'mock',
        'PYTHONPATH': str(backend),
    })
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=backend, env=env, check=True, capture_output=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=backend, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        root = f'http://127.0.0.1:{port}'
        headers = {'X-API-Key': env['BACKEND_API_KEY']}
        with httpx.Client(timeout=2) as c:
            for _ in range(40):
                try:
                    if c.get(root + '/api/health').status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(.15)
            else:
                raise RuntimeError('server did not start')
            assert c.get(root + '/api/inbox').status_code == 401
            assert c.get(root + '/api/ready', headers=headers).json()['ready'] is True
            payload = {'sender':'customer@example.test','subject':'Urgent repair', 'body':'Please schedule the urgent repair.', 'source_id':'smoke-unique-1'}
            response = c.post(root+'/api/inbox/sample', headers=headers, json=payload)
            assert response.status_code == 201, response.text
            message_id = response.json()['id']
            response = c.post(root+f'/api/inbox/{message_id}/process', headers=headers)
            assert response.status_code == 200, response.text
            task_id = response.json()['task']['id']
            approval = next(a for a in c.get(root+'/api/approvals',headers=headers).json() if a['task_id']==task_id)
            assert c.patch(root+f"/api/approvals/{approval['id']}",headers=headers,json={'decision':'approved'}).status_code == 200
            assert c.get(root+'/api/dashboard/summary',headers=headers).json()['processed'] == 1
            print('PASS: live HTTP smoke test (migration, readiness, auth, intake, process, approval, dashboard)')
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
