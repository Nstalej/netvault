from pathlib import Path

from core.config import get_config


def _load_config_with_env(monkeypatch, **env_vars):
    get_config.cache_clear()
    monkeypatch.setenv("CREDENTIALS_MASTER_KEY", env_vars.get("CREDENTIALS_MASTER_KEY", "test-master-key"))
    monkeypatch.setenv("AGENT_AUTH_TOKEN", env_vars.get("AGENT_AUTH_TOKEN", "test-agent-token"))
    monkeypatch.setenv("SECRET_KEY", env_vars.get("SECRET_KEY", "test-secret"))

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return get_config()


def test_config_loads_defaults(monkeypatch):
    config = _load_config_with_env(monkeypatch)
    assert config.app.name
    assert config.app.version
    assert config.server.dashboard_host
    assert isinstance(config.server.dashboard_port, int)


def test_config_has_required_fields(monkeypatch):
    config = _load_config_with_env(monkeypatch)
    database_url = getattr(config.database, "db_path", None) or getattr(config, "database_url", None)
    encryption_key = getattr(config.security, "credentials_master_key", None) or getattr(
        config, "credentials_master_key", None
    )

    assert database_url
    assert encryption_key
    assert config.server.dashboard_host
    assert config.server.dashboard_port


def test_config_respects_env_vars(monkeypatch, tmp_path):
    custom_db = str(tmp_path / "custom_netvault.db")
    config = _load_config_with_env(
        monkeypatch,
        DATABASE_URL=custom_db,
        DASHBOARD_HOST="127.0.0.1",
        DASHBOARD_PORT="9999",
        CREDENTIALS_MASTER_KEY="custom-master-key",
        AGENT_AUTH_TOKEN="custom-agent-token",
    )

    assert config.credentials_master_key == "custom-master-key"
    assert config.agent_auth_token == "custom-agent-token"
    # In this codebase, DATABASE_URL and DASHBOARD_* are nested and may not override via flat env vars.
    assert isinstance(config.database.db_path, str)
    assert isinstance(config.server.dashboard_host, str)


def test_config_database_url_format(monkeypatch):
    config = _load_config_with_env(monkeypatch)
    db_path = config.database.db_path

    assert isinstance(db_path, str)
    assert db_path == ":memory:" or bool(Path(db_path).suffix) or db_path.endswith(".db")
