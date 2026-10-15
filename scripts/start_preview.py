"""Launch one login-protected, mock-only preview behind a hosting TLS terminator.

This deliberately uses disposable local SQLite, not a production database.
The backend listens only on loopback; only Next.js binds to the hosting PORT.
Never log environment values or pass credentials in process command lines.
"""
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]


def preview_environment(source):
    env = dict(source)
    raw_origin = env.get('APP_ORIGIN') or env.get('RENDER_EXTERNAL_URL', '')
    parsed = urlsplit(raw_origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or raw_origin != raw_origin.strip()):
        raise ValueError('Configure a valid HTTPS APP_ORIGIN or RENDER_EXTERNAL_URL')
    env['APP_ORIGIN'] = raw_origin.rstrip('/')
    for key, minimum in [('APP_PASSWORD', 20), ('SESSION_SECRET', 32), ('BACKEND_API_KEY', 32)]:
        value = env.get(key, '')
        if len(value) < minimum or any(marker in value.lower() for marker in
                                      ('replace-with', 'change-me', 'ci-only', 'not-production')):
            raise ValueError(f'Configure a unique strong {key}; placeholder values are rejected')
    if not env.get('APP_USERNAME', '').strip():
        raise ValueError('Configure APP_USERNAME')
    if env.get('AI_PROVIDER', 'mock') != 'mock':
        raise ValueError('This preview launcher permits only AI_PROVIDER=mock')
    if env.get('DATABASE_URL'):
        raise ValueError('This disposable preview uses DATA_DIR, not an external DATABASE_URL')
    port = int(env.get('PORT', '10000'))
    if not 1024 <= port <= 65535 or port == 8000:
        raise ValueError('PORT must be 1024-65535, excluding the internal API port 8000')
    data_dir = Path(env.get('DATA_DIR', '/tmp/awa-preview'))
    if not data_dir.is_absolute():
        raise ValueError('DATA_DIR must be an absolute writable path')
    env.update(DATABASE_URL='sqlite:///' + str(data_dir / 'preview.db'),
               BACKEND_URL='http://127.0.0.1:8000', AI_PROVIDER='mock',
               NODE_ENV='production', NEXT_TELEMETRY_DISABLED='1',
               PYTHONPATH=str(ROOT / 'backend'), PORT=str(port))
    env.pop('OPENAI_API_KEY', None)
    return env, data_dir


def main():
    try:
        env, data_dir = preview_environment(os.environ)
    except (TypeError, ValueError) as exc:
        print(f'Preview configuration rejected: {exc}', file=sys.stderr)
        return 1
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    processes = []
    try:
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                       cwd=ROOT / 'backend', env=env, check=True, timeout=60)
        processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
            '--host', '127.0.0.1', '--port', '8000', '--workers', '1'],
            cwd=ROOT / 'backend', env=env))
        with httpx.Client(timeout=2, trust_env=False) as client:
            ready = False
            for _ in range(100):
                if stop.is_set() or processes[0].poll() is not None:
                    raise RuntimeError('Backend stopped during startup')
                try:
                    response = client.get(env['BACKEND_URL'] + '/api/ready',
                                          headers={'X-API-Key': env['BACKEND_API_KEY']})
                    ready = response.status_code == 200 and response.json().get('ready') is True
                except (httpx.HTTPError, ValueError):
                    ready = False
                if ready:
                    break
                time.sleep(.2)
            if not ready:
                raise RuntimeError('Backend database did not become ready')
        processes.append(subprocess.Popen(['node', str(ROOT / 'frontend/node_modules/next/dist/bin/next'),
            'start', '--hostname', '0.0.0.0', '--port', env['PORT']],
            cwd=ROOT / 'frontend', env=env))
        print('Mock-only preview started. Local records are disposable; no external integrations.', flush=True)
        while not stop.wait(.5):
            if any(process.poll() is not None for process in processes):
                raise RuntimeError('A preview server exited; stopping its companion')
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
