"""Real browser checks against production Next.js + FastAPI on loopback HTTPS.

Each scenario uses a fresh migrated SQLite database and generated credentials.
Secure cookies are stored by the browser normally: no injected cookies, mocked
API calls, or disabled authentication. A temporary self-signed TLS bridge models
a hosting TLS terminator. Only the test browser ignores this certificate error.
Screenshots contain synthetic fixtures only; credentials and traces are not saved.
"""
import json
import os
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright
from smoke_fullstack import ROOT, free_port, wait_ready

ARTIFACTS = ROOT / 'browser-artifacts'


@contextmanager
def application():
    processes = []
    bridge = None
    with tempfile.TemporaryDirectory(prefix='awa-browser-') as directory:
        tmp = Path(directory)
        ports = set()
        while len(ports) < 3:
            ports.add(free_port())
        api_port, web_port, tls_port = sorted(ports)
        api = f'http://127.0.0.1:{api_port}'
        upstream = f'http://127.0.0.1:{web_port}'
        origin = f'https://127.0.0.1:{tls_port}'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(tmp / 'test.db'),
               'APP_ORIGIN': origin, 'BACKEND_URL': api,
               'BACKEND_API_KEY': secrets.token_hex(24), 'APP_USERNAME': 'browser-test-owner',
               'APP_PASSWORD': secrets.token_hex(24), 'SESSION_SECRET': secrets.token_hex(32),
               'AI_PROVIDER': 'mock', 'NODE_ENV': 'production',
               'NEXT_TELEMETRY_DISABLED': '1', 'PYTHONPATH': str(ROOT / 'backend')}
        env.pop('OPENAI_API_KEY', None)
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                       cwd=ROOT / 'backend', env=env, check=True, timeout=30)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(tmp / 'key.pem'), '-out', str(tmp / 'cert.pem'),
                        '-days', '1', '-subj', '/CN=localhost',
                        '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)

        class Bridge(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def relay(self):
                ignored = {'host', 'connection', 'accept-encoding', 'content-length'}
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ignored}
                headers['X-Forwarded-Proto'] = 'https'
                data = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                try:
                    with httpx.Client(timeout=35, trust_env=False) as client:
                        result = client.request(self.command, upstream + self.path,
                                                headers=headers, content=data)
                    self.send_response(result.status_code)
                    for key, value in result.headers.multi_items():
                        if key.lower() not in {'content-length', 'content-encoding', 'transfer-encoding', 'connection'}:
                            self.send_header(key, value)
                    self.send_header('Content-Length', str(len(result.content)))
                    self.end_headers()
                    if self.command != 'HEAD':
                        self.wfile.write(result.content)
                except (httpx.HTTPError, BrokenPipeError, ConnectionResetError):
                    self.close_connection = True

            do_GET = do_POST = do_PATCH = do_HEAD = relay

        try:
            processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                '--host', '127.0.0.1', '--port', str(api_port)], cwd=ROOT / 'backend', env=env))
            processes.append(subprocess.Popen(['node', str(ROOT / 'frontend/node_modules/next/dist/bin/next'),
                'start', '--hostname', '127.0.0.1', '--port', str(web_port)], cwd=ROOT / 'frontend', env=env))
            with httpx.Client(timeout=10, trust_env=False) as client:
                wait_ready(client, api + '/api/health', processes)
                wait_ready(client, upstream + '/login', processes)
            bridge = ThreadingHTTPServer(('127.0.0.1', tls_port), Bridge)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(tmp / 'cert.pem', tmp / 'key.pem')
            bridge.socket = tls.wrap_socket(bridge.socket, server_side=True)
            threading.Thread(target=bridge.serve_forever, daemon=True).start()
            yield origin, env
        finally:
            if bridge is not None:
                bridge.shutdown()
                bridge.server_close()
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def scenario(playwright, name, engine, options):
    checks = []
    browser = getattr(playwright, engine).launch()
    try:
        with application() as (origin, env):
            context = browser.new_context(ignore_https_errors=True, **options)
            page = context.new_page()
            page.set_default_timeout(15000)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            # Scope app alerts to main; Next.js also has a route-announcer alert.
            app_alert = page.locator('main [role="alert"]')
            try:
                page.goto(origin + '/')
                expect(page).to_have_url(origin + '/login')
                page.get_by_label('Username').fill(env['APP_USERNAME'])
                page.get_by_label('Password').fill('incorrect-password')
                page.get_by_role('button', name='Sign in', exact=True).click()
                expect(app_alert).to_contain_text('Sign-in failed')
                page.get_by_label('Password').fill(env['APP_PASSWORD'])
                page.get_by_role('button', name='Sign in', exact=True).click()
                expect(page.get_by_role('heading', name='Overview', exact=True)).to_be_visible()
                expect(page.get_by_role('status')).to_contain_text('Backend ready')
                cookie = next(c for c in context.cookies() if c['name'] == 'awa_session')
                assert cookie['httpOnly'] and cookie['secure'] and cookie['sameSite'] == 'Strict'
                checks.append('login, wrong-password rejection and real Secure cookie')

                page.get_by_role('button', name='Load sample inbox', exact=True).click()
                expect(page.locator('.metrics article').first.locator('strong')).to_have_text('3')
                page.screenshot(path=str(ARTIFACTS / f'{name}-overview.png'), full_page=True)
                page.get_by_role('button', name='Smart Inbox', exact=True).click()
                expect(page.locator('.record')).to_have_count(3)
                page.get_by_role('button', name='Load samples', exact=True).click()
                expect(page.locator('.record')).to_have_count(3)
                inquiry = page.locator('.record').filter(has_text='Urgent leak in the office')
                inquiry.get_by_role('button', name='Process', exact=True).click()
                expect(inquiry.get_by_role('button', name='Processed', exact=True)).to_be_disabled()
                expect(inquiry.locator('.tag')).to_contain_text('service request')
                checks.append('sample import, repeat import and message processing')

                page.get_by_role('button', name='Tasks', exact=True).click()
                page.locator('.record select').select_option('done')
                expect(app_alert).to_contain_text('approved review')
                page.get_by_role('button', name='Approvals', exact=True).click()
                page.get_by_role('button', name='Approve', exact=True).click()
                expect(page.locator('.record .tag')).to_have_text('approved')
                page.screenshot(path=str(ARTIFACTS / f'{name}-approval.png'), full_page=True)
                page.get_by_role('button', name='Tasks', exact=True).click()
                page.locator('.record select').select_option('done')
                expect(page.locator('.record .tag')).to_have_text('done')
                checks.append('unapproved task blocked, human approval and task completion')

                page.get_by_role('button', name='Smart Inbox', exact=True).click()
                invoice = page.locator('.record').filter(has_text='Invoice question')
                invoice.get_by_role('button', name='Process', exact=True).click()
                expect(invoice.get_by_role('button', name='Processed', exact=True)).to_be_disabled()
                page.get_by_role('button', name='Approvals', exact=True).click()
                page.get_by_role('button', name='Reject', exact=True).click()
                expect(page.locator('.record .tag').filter(has_text='rejected')).to_have_count(1)
                page.get_by_role('button', name='Tasks', exact=True).click()
                page.locator('.record').filter(has_text='Invoice question').locator('select').select_option('done')
                expect(app_alert).to_contain_text('approved review')
                checks.append('rejection prevents task completion')

                page.get_by_role('button', name='Workflows', exact=True).click()
                expect(page.locator('.flow-card')).to_have_count(8)
                page.get_by_role('button', name='Inspect run', exact=True).first.click()
                expect(page.locator('.trace')).to_have_count(8)
                page.screenshot(path=str(ARTIFACTS / f'{name}-workflow.png'), full_page=True)
                checks.append('workflow diagram and execution trace')

                for tab in ['Overview', 'Smart Inbox', 'Workflows', 'Tasks', 'Approvals', 'Activity']:
                    page.get_by_role('button', name=tab, exact=True).click()
                    expect(page.get_by_role('heading', name=tab, level=1, exact=True)).to_be_visible()
                    assert page.evaluate('Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) <= window.innerWidth + 2'), f'{name}: horizontal overflow in {tab}'
                checks.append('all six screens navigate without document overflow')
                page.reload()
                expect(page.locator('.metrics article').first.locator('strong')).to_have_text('3')
                page.get_by_role('button', name='Sign out', exact=True).click()
                expect(page).to_have_url(origin + '/login')
                assert context.request.get(origin + '/api/proxy/api/inbox').status == 401
                page.goto(origin + '/')
                expect(page).to_have_url(origin + '/login')
                assert not errors, errors
                checks.append('reload persistence, logout and anonymous access blocked')
                print(f'PASS: {name} ({engine}): ' + '; '.join(checks), flush=True)
                return {'profile': name, 'engine': engine, 'passed': True, 'checks': checks}
            except Exception:
                page.screenshot(path=str(ARTIFACTS / f'{name}-failure.png'), full_page=True)
                raise
            finally:
                context.close()
    finally:
        browser.close()


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        for name, engine, options in [
            ('desktop-chromium', 'chromium', {'viewport': {'width': 1280, 'height': 900}}),
            ('mobile-webkit', 'webkit', {'viewport': {'width': 390, 'height': 844},
                                        'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2}),
        ]:
            results.append(scenario(playwright, name, engine, options))
    (ARTIFACTS / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: desktop Chromium and mobile-sized WebKit browser scenarios', flush=True)


if __name__ == '__main__':
    main()
