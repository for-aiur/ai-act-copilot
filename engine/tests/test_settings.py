import pytest
from aiact.settings import load_settings


def test_precedence_and_secret_redaction(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text('AIACT_MODEL="from file"\nGEMINI_API_KEY=private-test-value\n')
    settings = load_settings({"model": "flag"}, env={"AIACT_MODEL": "environment"}, dotenv=dotenv)
    assert settings.model == "flag"
    assert "private-test-value" not in repr(settings)
    assert load_settings(env={}, dotenv=dotenv).model == "from file"
    assert load_settings(env={"AIACT_PROVIDER": "ollama"}, dotenv=None).model == "qwen2.5:3b"


def test_cloud_requires_consent_and_key_and_storage_is_explicit():
    settings = load_settings(env={}, dotenv=None)
    with pytest.raises(ValueError, match="consent"):
        settings.require_cloud()
    with pytest.raises(ValueError, match="missing"):
        settings.require_cloud(True)
    assert load_settings(env={"DATABASE_URL": "postgresql://local/db"}, dotenv=None).database_url.get_secret_value().startswith("postgresql")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        load_settings(env={"DATABASE_URL": "mysql://local/db"}, dotenv=None)
    with pytest.raises(ValueError):
        load_settings(env={"LANGFUSE_HOST": "https://untrusted.example"}, dotenv=None)
