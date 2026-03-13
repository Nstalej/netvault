import pytest


@pytest.mark.asyncio
async def test_create_credential_ssh(client, api_prefix):
    response = await client.post(
        f"{api_prefix}/credentials",
        json={
            "name": "cred-ssh",
            "type": "ssh",
            "data": {"username": "admin", "password": "pass123", "port": 22},
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_credential_rest(client, api_prefix):
    response = await client.post(
        f"{api_prefix}/credentials",
        json={
            "name": "cred-rest",
            "type": "rest",
            "data": {"auth_type": "bearer", "token": "tok-123"},
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_credential_snmp_v2c(client, api_prefix):
    response = await client.post(
        f"{api_prefix}/credentials",
        json={
            "name": "cred-snmp",
            "type": "snmp_v2c",
            "data": {"community": "public"},
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_list_credentials(client, api_prefix):
    await client.post(
        f"{api_prefix}/credentials",
        json={
            "name": "cred-list",
            "type": "ssh",
            "data": {"username": "admin", "password": "pass123"},
        },
    )
    response = await client.get(f"{api_prefix}/credentials")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_credential_by_name(client, api_prefix):
    name = "cred-get"
    await client.post(
        f"{api_prefix}/credentials",
        json={
            "name": name,
            "type": "ssh",
            "data": {"username": "admin", "password": "super-secret"},
        },
    )

    response = await client.get(f"{api_prefix}/credentials/{name}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == name
    assert "data" in data
    assert "masked_fields" in data
    assert "password" in data["masked_fields"]


@pytest.mark.asyncio
async def test_update_credential(client, api_prefix):
    name = "cred-update"
    await client.post(
        f"{api_prefix}/credentials",
        json={
            "name": name,
            "type": "ssh",
            "data": {"username": "admin", "password": "oldpass"},
        },
    )

    updated = await client.put(
        f"{api_prefix}/credentials/{name}",
        json={
            "type": "ssh",
            "data": {"username": "admin", "password": "newpass"},
        },
    )
    assert updated.status_code == 200

    response = await client.get(f"{api_prefix}/credentials/{name}")
    assert response.status_code == 200
    assert response.json()["data"]["password"] == "newpass"


@pytest.mark.asyncio
async def test_delete_credential(client, api_prefix):
    name = "cred-delete"
    await client.post(
        f"{api_prefix}/credentials",
        json={
            "name": name,
            "type": "ssh",
            "data": {"username": "admin", "password": "to-delete"},
        },
    )

    deleted = await client.delete(f"{api_prefix}/credentials/{name}")
    assert deleted.status_code == 200

    response = await client.get(f"{api_prefix}/credentials/{name}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_credential_no_usage_count_phantom(client, api_prefix):
    response = await client.get(f"{api_prefix}/credentials")
    assert response.status_code == 200
    for item in response.json():
        if "usage_count" in item:
            assert isinstance(item["usage_count"], int)
