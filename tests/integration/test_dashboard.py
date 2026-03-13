import pytest


@pytest.mark.asyncio
async def test_dashboard_index_loads(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "NetVault" in response.text


@pytest.mark.asyncio
async def test_dashboard_devices_loads(client):
    response = await client.get("/devices")
    assert response.status_code == 200
    assert "devices" in response.text.lower()


@pytest.mark.asyncio
async def test_dashboard_audit_loads(client):
    response = await client.get("/audit")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_settings_loads(client):
    response = await client.get("/settings")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_device_detail_loads(client, seed_device):
    response = await client.get(f"/devices/{seed_device}")
    assert response.status_code == 200
    text = response.text.lower()
    assert "device" in text or "device_detail" in text


@pytest.mark.asyncio
async def test_dashboard_agents_loads(client):
    response = await client.get("/agents")
    assert response.status_code == 200
