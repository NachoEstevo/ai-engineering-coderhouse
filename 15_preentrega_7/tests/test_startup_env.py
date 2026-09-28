import os

from app.config import Settings
from app.main import create_app


def test_native_factory_loads_tracing_env_without_overriding_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr('app.main.BASE_DIR', tmp_path)
    monkeypatch.setenv('LANGSMITH_PROJECT', 'temporary-before-delete')
    monkeypatch.setenv('LANGSMITH_TRACING', 'temporary-before-delete')
    monkeypatch.delenv('LANGSMITH_PROJECT', raising=False)
    monkeypatch.delenv('LANGSMITH_TRACING', raising=False)
    monkeypatch.setenv('LANGSMITH_ENDPOINT', 'https://runtime.example.test')
    # monkeypatch tracks these keys and restores the original environment after the test.
    (tmp_path / '.env').write_text(
        'LANGSMITH_PROJECT=synthetic-test-project\n'
        'LANGSMITH_TRACING=true\n'
        'LANGSMITH_ENDPOINT=https://file.example.test\n', encoding='utf-8')
    settings = Settings(api_key='synthetic-api-key-123', approval_key='synthetic-approver-123', _env_file=None)
    create_app(settings=settings, model=object(), start_workers=False)
    assert os.environ['LANGSMITH_PROJECT'] == 'synthetic-test-project'
    assert os.environ['LANGSMITH_TRACING'] == 'true'
    assert os.environ['LANGSMITH_ENDPOINT'] == 'https://runtime.example.test'
