import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]

def alembic(db_url, *args):
    result = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=BACKEND_DIR,
        env={**os.environ, 'DATABASE_URL': db_url}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_clean_database_upgrade_and_downgrade(tmp_path):
    url = 'sqlite:///' + str(tmp_path / 'migration_test.db')
    alembic(url, 'upgrade', 'head')
    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    assert {'inbox_messages','tasks','approvals','audit_events','workflow_execution_runs','workflow_execution_steps','alembic_version'} <= names
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0001_initial'
    alembic(url, 'upgrade', 'head')
    alembic(url, 'downgrade', 'base')
    assert 'inbox_messages' not in inspect(engine).get_table_names()
    engine.dispose()
