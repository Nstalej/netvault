import pytest

from connectors.base import ConnectionTestResult
from connectors.ssh_connector.ssh_connector import SSHConnector


@pytest.mark.asyncio
async def test_create_device_returns_201(client, api_prefix):
    response = await client.post(
        f"{api_prefix}/devices",
        json={
            "name": "API-Create-Device",
            "type": "mikrotik",
            "ip": "10.10.10.10",
            "port": 22,
            "connector_type": "ssh",
            "config_json": {"credential_name": "non-existent"},
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_device_config_json_persists(client, api_prefix):
    create = await client.post(
        f"{api_prefix}/devices",
        json={
            "name": "ConfigJson-Device",
            "type": "mikrotik",
            "ip": "10.10.10.11",
            "port": 22,
            "connector_type": "ssh",
            "config_json": {"credential_name": "x"},
        },
    )
    device_id = create.json()["id"]

    detail = await client.get(f"{api_prefix}/devices/{device_id}")
    assert detail.status_code == 200
    assert detail.json()["config_json"].get("credential_name") == "x"


@pytest.mark.asyncio
async def test_create_device_config_alias_persists(client, api_prefix):
    create = await client.post(
        f"{api_prefix}/devices",
        json={
            "name": "ConfigAlias-Device",
            "type": "mikrotik",
            "ip": "10.10.10.12",
            "port": 22,
            "connector_type": "ssh",
            "config": {"credential_name": "alias-x"},
        },
    )
    device_id = create.json()["id"]

    detail = await client.get(f"{api_prefix}/devices/{device_id}")
    assert detail.status_code == 200
    assert detail.json()["config_json"].get("credential_name") == "alias-x"


@pytest.mark.asyncio
async def test_list_devices(client, api_prefix):
    response = await client.get(f"{api_prefix}/devices")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_device_by_id(client, api_prefix, seed_device):
    response = await client.get(f"{api_prefix}/devices/{seed_device}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == seed_device
    assert data["name"] == "Test-MikroTik"


@pytest.mark.asyncio
async def test_get_device_not_found(client, api_prefix):
    response = await client.get(f"{api_prefix}/devices/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_device(client, api_prefix, seed_device):
    response = await client.put(
        f"{api_prefix}/devices/{seed_device}",
        json={"name": "Updated-Device-Name"},
    )
    assert response.status_code == 200

    detail = await client.get(f"{api_prefix}/devices/{seed_device}")
    assert detail.json()["name"] == "Updated-Device-Name"


@pytest.mark.asyncio
async def test_delete_device(client, api_prefix):
    created = await client.post(
        f"{api_prefix}/devices",
        json={
            "name": "Delete-Device",
            "type": "mikrotik",
            "ip": "10.10.10.13",
            "port": 22,
            "connector_type": "ssh",
            "config_json": {},
        },
    )
    device_id = created.json()["id"]

    deleted = await client.delete(f"{api_prefix}/devices/{device_id}")
    assert deleted.status_code == 200

    detail = await client.get(f"{api_prefix}/devices/{device_id}")
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_no_trailing_slash_redirect(client, api_prefix):
    response = await client.post(
        f"{api_prefix}/devices",
        json={
            "name": "No-Redirect-Device",
            "type": "mikrotik",
            "ip": "10.10.10.14",
            "port": 22,
            "connector_type": "ssh",
            "config_json": {},
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 201)
    assert response.status_code != 307


@pytest.mark.asyncio
async def test_test_device_endpoint_exists(client, api_prefix, seed_device):
    response = await client.post(f"{api_prefix}/devices/{seed_device}/test")
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_test_device_no_credential(client, api_prefix):
    created = await client.post(
        f"{api_prefix}/devices",
        json={
            "name": "NoCred-Device",
            "type": "mikrotik",
            "ip": "192.0.2.10",
            "port": 22,
            "connector_type": "ssh",
            "config_json": {},
        },
    )
    device_id = created.json()["id"]

    result = await client.post(f"{api_prefix}/devices/{device_id}/test")
    assert result.status_code == 200
    body = result.json()
    assert body["success"] is False
    assert body.get("error")


@pytest.mark.asyncio
async def test_device_status_after_test(client, api_prefix, seed_device, monkeypatch):
    async def _fake_test_connection(self):
        return ConnectionTestResult(success=True, latency_ms=50.0, error_message=None)

    monkeypatch.setattr(SSHConnector, "test_connection", _fake_test_connection)

    test_result = await client.post(f"{api_prefix}/devices/{seed_device}/test")
    assert test_result.status_code == 200

    detail = await client.get(f"{api_prefix}/devices/{seed_device}")
    status_value = detail.json().get("status")
    assert status_value in ("online", "offline")
