"""Test deployment configuration without contacting a hosting account."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('preview_launcher', ROOT / 'scripts/start_preview.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def settings():
    return {'RENDER_EXTERNAL_URL': 'https://preview.example.test', 'APP_USERNAME': 'owner',
            'APP_PASSWORD': 'a' * 32, 'BACKEND_API_KEY': 'b' * 48, 'SESSION_SECRET': 'c' * 64}


def test_render_origin_and_internal_only_api():
    source = settings()
    source['OPENAI_API_KEY'] = 'not-used'
    env, path = module.preview_environment(source)
    assert env['APP_ORIGIN'] == source['RENDER_EXTERNAL_URL']
    assert env['BACKEND_URL'] == 'http://127.0.0.1:8000'
    assert env['AI_PROVIDER'] == 'mock'
    assert 'OPENAI_API_KEY' not in env
    assert env['DATABASE_URL'].startswith('sqlite:////tmp/')
    assert path.is_absolute()
    assert source['OPENAI_API_KEY'] == 'not-used'


@pytest.mark.parametrize('value', ['', 'http://preview.example.test', 'https://example.test/path',
                                  'https://owner:password@example.test', 'https://example.test?x=1'])
def test_reject_unsafe_public_origin(value):
    source = settings()
    source['RENDER_EXTERNAL_URL'] = value
    with pytest.raises(ValueError, match='HTTPS'):
        module.preview_environment(source)


@pytest.mark.parametrize('key', ['APP_PASSWORD', 'SESSION_SECRET', 'BACKEND_API_KEY'])
def test_reject_placeholder_credentials(key):
    source = settings()
    source[key] = 'replace-with-' + 'x' * 50
    with pytest.raises(ValueError, match=key):
        module.preview_environment(source)


def test_preview_rejects_live_ai_and_external_database():
    for key, value in [('AI_PROVIDER', 'openai'), ('DATABASE_URL', 'postgresql://example.test/db')]:
        with pytest.raises(ValueError):
            module.preview_environment({**settings(), key: value})


@pytest.mark.parametrize('port', ['8000', '443', '70000', 'not-a-port'])
def test_reject_invalid_ports(port):
    with pytest.raises(ValueError):
        module.preview_environment({**settings(), 'PORT': port})
