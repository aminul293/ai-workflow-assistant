"""Exercise a built Next.js server, auth, proxy and FastAPI over local HTTP.

Requires `cd frontend && npm install && npm run build` first. Uses a fresh
SQLite database, mock AI, generated test credentials, and loopback ports only.
This is an HTTP integration test, not a browser/visual test. It explicitly
replays the Secure session cookie over loopback HTTP for this test only.
"""
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_ready(client, url, processes):
    for _ in range(100):
        if any(p.poll() is not None for p in processes):
            raise RuntimeError('A test server exited before readiness')
        try:
            if client.get(url).status_code == 200:
                return
        except httpx.RequestError:
            pass
        time.sleep(.2)
    raise RuntimeError('Test server did not become ready')


def main():
    next_cli = ROOT / 'frontend/node_modules/next/dist/bin/next'
    if not next_cli.exists() or not (ROOT / 'frontend/.next/BUILD_ID').exists():
        raise RuntimeError('Install frontend dependencies and run npm run build first')
    processes = []
    with tempfile.TemporaryDirectory(prefix='workflow-fullstack-') as tmp:
        api_port, web_port = free_port(), free_port()
        while web_port == api_port:
            web_port = free_port()
        api = f'http://127.0.0.1:{api_port}'
        web = f'http://127.0.0.1:{web_port}'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(Path(tmp) / 'test.db'),
               'BACKEND_URL': api, 'BACKEND_API_KEY': secrets.token_hex(24),
               'APP_USERNAME': 'synthetic-test-owner', 'APP_PASSWORD': secrets.token_hex(24),
               'SESSION_SECRET': secrets.token_hex(32), 'AI_PROVIDER': 'mock',
               'NODE_ENV': 'production', 'NEXT_TELEMETRY_DISABLED': '1',
               'PYTHONPATH': str(ROOT / 'backend')}
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                       cwd=ROOT / 'backend', env=env, check=True, timeout=30)
        try:
            processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                '--host', '127.0.0.1', '--port', str(api_port)], cwd=ROOT / 'backend', env=env))
            processes.append(subprocess.Popen(['node', str(next_cli), 'start', '--hostname',
                '127.0.0.1', '--port', str(web_port)], cwd=ROOT / 'frontend', env=env))
            with httpx.Client(timeout=10) as client:
                wait_ready(client, api + '/api/health', processes)
                wait_ready(client, web + '/login', processes)
                proxy = web + '/api/proxy/api'
                assert client.get(proxy + '/inbox').status_code == 401
                credentials = {'username': env['APP_USERNAME'], 'password': env['APP_PASSWORD']}
                assert client.post(web + '/api/auth/login', json=credentials).status_code == 403
                login = client.post(web + '/api/auth/login', headers={'Origin': web}, json=credentials)
                assert login.status_code == 200, login.text
                cookie = login.cookies.get('awa_session')
                assert cookie and 'httponly' in login.headers['set-cookie'].lower()
                headers = {'Cookie': 'awa_session=' + cookie, 'Origin': web}
                assert client.get(web + '/', headers=headers).status_code == 200
                ready = client.get(proxy + '/ready', headers=headers)
                assert ready.status_code == 200 and ready.json()['ready'] is True, ready.text
                bad_origin = {**headers, 'Origin': 'https://untrusted.example'}
                assert client.post(proxy + '/inbox/sample', headers=bad_origin, json={}).status_code == 403
                payload = {'sender': 'example@sample.test', 'subject': 'Urgent repair',
                           'body': 'A fictional urgent leak needs a repair.', 'source_id': 'fullstack-1'}
                created = client.post(proxy + '/inbox/sample', headers=headers, json=payload)
                assert created.status_code == 201, created.text
                ident = created.json()['id']
                processed = client.post(proxy + '/inbox/' + ident + '/process', headers=headers)
                assert processed.status_code == 200, processed.text
                task = processed.json()['task']['id']
                again = client.post(proxy + '/inbox/' + ident + '/process', headers=headers)
                assert again.json()['duplicate_prevented'] is True
                assert client.patch(proxy + '/tasks/' + task, headers=headers, json={'status': 'done'}).status_code == 409
                approval = next(a for a in client.get(proxy + '/approvals', headers=headers).json() if a['task_id'] == task)
                assert client.patch(proxy + '/approvals/' + approval['id'], headers=headers, json={'decision': 'approved'}).status_code == 200
                assert client.patch(proxy + '/tasks/' + task, headers=headers, json={'status': 'done'}).status_code == 200
                runs = client.get(proxy + '/workflow-runs', headers=headers).json()
                run = next(r for r in runs if r['message_id'] == ident)
                trace = client.get(proxy + '/workflow-runs/' + run['id'], headers=headers).json()
                assert trace['status'] == 'approved' and len(trace['steps']) == 8
                assert client.post(web + '/api/auth/logout', headers=headers).status_code == 200
                print('PASS: full-stack HTTP (login, proxy, migration, intake, deduplication, approval, task, trace, logout)')
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
