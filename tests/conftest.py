import pytest


@pytest.fixture(autouse=True, scope="session")
def isolate_usage_log(tmp_path_factory):
    """Redirect usage_log.jsonl to a temp file for the test session.

    Prevents test traffic from polluting the real usage_log.jsonl that the
    feature-suggester reads.
    """
    import engagements.madi_onboarding.app.main as m
    original = m.USAGE_LOG
    m.USAGE_LOG = tmp_path_factory.mktemp("logs") / "test_usage.jsonl"
    yield
    m.USAGE_LOG = original
