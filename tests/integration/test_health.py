import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client, health_path):
    response = await client.get(health_path)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_components(client, health_path):
    response = await client.get(health_path)
    payload = response.json()
    assert "components" in payload
    assert "database" in payload["components"]
    assert "vault" in payload["components"]
    assert "device_manager" in payload["components"]


@pytest.mark.asyncio
async def test_health_all_components_healthy(client, health_path):
    response = await client.get(health_path)
    components = response.json()["components"]
    assert components["database"] is True
    assert components["vault"] is True
    assert components["device_manager"] is True


@pytest.mark.asyncio
async def test_health_status_healthy(client, health_path):
    response = await client.get(health_path)
    assert response.json()["status"] == "healthy"
