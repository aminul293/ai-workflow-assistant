"""Test the built Docker image on loopback without creating cloud resources.

The browser suite independently exercises native Secure cookies over HTTPS.
This packaging-only probe forwards its test session explicitly over loopback HTTP.
Generated test credentials never appear in command lines, logs, or artifacts.
"""
import json
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def docker(*arguments):
    return subprocess.check_output(['docker', *arguments], text=True, timeout=30).strip()


def main():
    name = 'awa-test-' + secrets.token_hex(5)
    origin = 'https://preview.example.test'
    env = {'APP_ORIGIN': origin, 'APP_USERNAME': 'container-owner',
           'APP_PASSWORD': secrets.token_hex(24), 'BACKEND_API_KEY': secrets.token_hex(32),
           'SESSION_SECRET': secrets.token_hex(32), 'AI_PROVIDER': 'mock'}
    started = False
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with tempfile.TemporaryDirectory(prefix='awa-container-') as tmp:
        env_file = Path(tmp) / 'test.env'
        env_file.write_text(''.join(f'{key}={value}\n' for key, value in env.items()))
        os.chmod(env_file, 0o600)
        try:
            docker('run', '-d', '--name', name, '--memory=512m', '--env-file', str(env_file),
                   '-p', '127.0.0.1::10000', 'awa-preview:ci')
            started = True
            port = docker('inspect', '--format',
                '{{(index (index .NetworkSettings.Ports "10000/tcp") 0).HostPort}}', name)
            base = 'http://127.0.0.1:' + port

            def request(path, method='GET', data=None, cookie=None):
                headers = {'Accept': 'application/json'}
                if method != 'GET':
                    headers.update({'Origin': origin, 'Content-Type': 'application/json'})
                if cookie:
                    headers['Cookie'] = cookie
                body = json.dumps(data).encode() if data is not None else None
                req = Request(base + path, data=body, headers=headers, method=method)
                try:
                    response = opener.open(req, timeout=5)
                except HTTPError as error:
                    response = error
                with response:
                    return response.status, response.headers, response.read().decode()

            for _ in range(100):
                if docker('inspect', '--format', '{{.State.Running}}', name) != 'true':
                    raise RuntimeError('Preview container exited during startup')
                try:
                    if request('/login')[0] == 200:
                        break
                except (URLError, TimeoutError, ConnectionError):
                    pass
                time.sleep(.5)
            else:
                raise RuntimeError('Preview did not become ready')
            assert docker('exec', name, 'id', '-u') != '0', 'Container must not run as root'
            status, headers, _ = request('/')
            assert status in (302, 307) and headers['Location'] == origin + '/login'
            assert request('/api/proxy/api/inbox')[0] == 401
            assert request('/api/auth/login', 'POST', {'username': env['APP_USERNAME'], 'password': 'wrong'})[0] == 401
            status, headers, _ = request('/api/auth/login', 'POST',
                {'username': env['APP_USERNAME'], 'password': env['APP_PASSWORD']})
            assert status == 200, 'Container login failed'
            raw_cookie = headers.get('Set-Cookie', '')
            assert 'HttpOnly' in raw_cookie and 'Secure' in raw_cookie
            cookie = raw_cookie.split(';', 1)[0]
            status, _, body = request('/api/proxy/api/ready', cookie=cookie)
            assert status == 200 and json.loads(body)['ready'] is True
            status, _, body = request('/api/proxy/api/inbox/sample', 'POST',
                {'sender': 'fictional@example.test', 'subject': 'Preview sample',
                 'body': 'Please review this fictional invoice.'}, cookie)
            assert status == 201
            message = json.loads(body)
            status, _, body = request('/api/proxy/api/inbox/' + message['id'] + '/process', 'POST', {}, cookie)
            assert status == 200 and json.loads(body)['task']['status'] == 'pending_review'
            assert request('/api/auth/logout', 'POST', {}, cookie)[0] == 200
            print('PASS: 512 MB Docker preview: non-root startup, migrated database, login, proxy and mock processing')
        except Exception:
            if started:
                subprocess.run(['docker', 'logs', '--tail', '60', name], check=False, timeout=10)
            raise
        finally:
            if started:
                subprocess.run(['docker', 'rm', '-f', name], check=False,
                               stdout=subprocess.DEVNULL, timeout=20)


if __name__ == '__main__':
    main()
