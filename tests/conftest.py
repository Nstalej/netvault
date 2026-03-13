import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from core.api.app import create_app
from core.config import Settings
from core.database.db import DatabaseManager
from core.engine.audit_engine import AuditEngine
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import DeviceManager, get_device_manager

# API prefix discovery note:
# Devices and credentials routes are registered under /api (not /api/v1).
API_PREFIX = "/api"
HEALTH_PATH = "/health"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def api_prefix() -> str:
    return API_PREFIX


@pytest.fixture(scope="session")
def health_path() -> str:
    return HEALTH_PATH


@pytest.fixture(autouse=True)
def isolate_sensitive_env(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_MASTER_KEY", raising=False)
    monkeypatch.delenv("AGENT_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(
        credentials_master_key="dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5n",
        agent_auth_token="test-agent-token",
        secret_key="test-secret-key",
        database={"db_path": "data/test-fixture.db"},
        logging={"file": None},
        modules={"mcp_server": False, "scheduler": False},
    )


@pytest_asyncio.fixture()
async def test_db(tmp_path):
    db = DatabaseManager(str(tmp_path / "test_netvault.db"))
    await db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


@pytest_asyncio.fixture()
async def test_vault(test_db):
    return CredentialVault(
        db=test_db,
        master_key="dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5n",
    )


@pytest_asyncio.fixture()
async def test_device_manager(test_db, test_vault):
    import core.engine.device_manager as dm_module

    dm_module._DEVICE_MANAGER_INSTANCE = None
    DeviceManager._instance = None

    # Ensure connector registry is populated.
    import connectors  # noqa: F401

    manager = get_device_manager(test_db, test_vault)
    yield manager

    dm_module._DEVICE_MANAGER_INSTANCE = None
    DeviceManager._instance = None


@pytest_asyncio.fixture()
async def test_app(test_settings, test_db, test_vault, test_device_manager):
    import core.engine.audit_engine as ae_module

    ae_module._AUDIT_ENGINE_INSTANCE = None
    AuditEngine._instance = None

    app = create_app(test_settings)

    @asynccontextmanager
    async def _no_lifespan(_app):
        yield

    app.router.lifespan_context = _no_lifespan

    app.state.db = test_db
    app.state.vault = test_vault
    app.state.device_manager = test_device_manager
    app.state.audit_engine = AuditEngine(test_db, test_device_manager)
    app.state.start_time = datetime.now(timezone.utc)
    app.state.local_ip = "127.0.0.1"

    yield app


@pytest_asyncio.fixture()
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def seed_ssh_credential(test_vault):
    name = "test-mikrotik-ssh"
    await test_vault.store_credential(
        name=name,
        credential_type="ssh",
        data={
            "username": "admin",
            "password": "testpass123",
            "port": 22,
            "timeout": 10,
            "device_type": "mikrotik",
        },
    )
    yield name


@pytest_asyncio.fixture()
async def seed_device(client, api_prefix, seed_ssh_credential):
    response = await client.post(
        f"{api_prefix}/devices",
        json={
            "name": "Test-MikroTik",
            "type": "mikrotik",
            "ip": "192.168.2.3",
            "port": 22,
            "connector_type": "ssh",
            "config_json": {"credential_name": seed_ssh_credential},
        },
    )
    response.raise_for_status()
    yield response.json()["id"]
