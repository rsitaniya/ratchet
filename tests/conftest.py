import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """Shared TestClient instance for the session."""
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True, scope="session")
def isolate_usage_log(tmp_path_factory):
    """Redirect usage_log.jsonl to a temp file for the test session.

    Prevents test traffic (including the 422 from test_invalid_op_returns_422)
    from polluting the real usage_log.jsonl that the feature-suggester reads.
    """
    import app.main as m
    original = m.USAGE_LOG
    m.USAGE_LOG = tmp_path_factory.mktemp("logs") / "test_usage.jsonl"
    yield
    m.USAGE_LOG = original
