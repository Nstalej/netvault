import pytest

from connectors.base import ConnectionTestResult
from connectors.ssh_connector.ssh_connector import SSHConnector
from core.database import crud
from core.database.models import DeviceModel


@pytest.mark.asyncio
async def test_device_manager_initializes(test_device_manager):
    assert test_device_manager is not None


@pytest.mark.asyncio
async def test_device_manager_not_none_after_init(test_device_manager):
    assert test_device_manager.db is not None
    assert test_device_manager.vault is not None


@pytest.mark.asyncio
async def test_load_devices(test_device_manager, test_db):
    await crud.create_device(
        test_db,
        DeviceModel(
            name="dm-r1",
            type="router",
            ip="10.20.0.1",
            connector_type="ssh",
            config_json={},
        ),
    )
    await crud.create_device(
        test_db,
        DeviceModel(
            name="dm-r2",
            type="router",
            ip="10.20.0.2",
            connector_type="ssh",
            config_json={},
        ),
    )

    await test_device_manager.load_devices()
    assert len(test_device_manager._devices) >= 2


@pytest.mark.asyncio
async def test_get_connector_ssh(test_device_manager, test_db, test_vault):
    await test_vault.store_credential(
        name="dm-ssh-cred",
        credential_type="ssh",
        data={"username": "admin", "password": "pass123", "device_type": "mikrotik"},
    )
    device_id = await crud.create_device(
        test_db,
        DeviceModel(
            name="dm-ssh-device",
            type="mikrotik",
            ip="10.20.0.3",
            port=22,
            connector_type="ssh",
            config_json={"credential_name": "dm-ssh-cred"},
        ),
    )

    await test_device_manager.load_devices()
    connector = await test_device_manager.get_connector(device_id)
    assert isinstance(connector, SSHConnector)


@pytest.mark.asyncio
async def test_get_connector_missing_credential(test_device_manager, test_db):
    device_id = await crud.create_device(
        test_db,
        DeviceModel(
            name="dm-missing-cred",
            type="mikrotik",
            ip="10.20.0.4",
            port=22,
            connector_type="ssh",
            config_json={"credential_name": "does-not-exist"},
        ),
    )

    await test_device_manager.load_devices()
    connector = await test_device_manager.get_connector(device_id)
    assert connector is None


@pytest.mark.asyncio
async def test_get_connector_empty_config_json(test_device_manager, test_db):
    device_id = await crud.create_device(
        test_db,
        DeviceModel(
            name="dm-empty-config",
            type="mikrotik",
            ip="10.20.0.5",
            port=22,
            connector_type="ssh",
            config_json={},
        ),
    )

    await test_device_manager.load_devices()
    connector = await test_device_manager.get_connector(device_id)
    assert connector is None


@pytest.mark.asyncio
async def test_test_device_with_mock_ssh(test_device_manager, test_db, test_vault, monkeypatch):
    await test_vault.store_credential(
        name="dm-test-cred",
        credential_type="ssh",
        data={"username": "admin", "password": "pass123", "device_type": "mikrotik"},
    )
    device_id = await crud.create_device(
        test_db,
        DeviceModel(
            name="dm-test-device",
            type="mikrotik",
            ip="10.20.0.6",
            port=22,
            connector_type="ssh",
            config_json={"credential_name": "dm-test-cred"},
        ),
    )

    async def _fake_test_connection(self):
        return ConnectionTestResult(success=True, latency_ms=12.3, error_message=None)

    monkeypatch.setattr(SSHConnector, "test_connection", _fake_test_connection)

    await test_device_manager.load_devices()
    result = await test_device_manager.test_device(device_id)
    assert result.success is True
