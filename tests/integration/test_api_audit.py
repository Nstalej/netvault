import asyncio
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.database import crud
from core.database.models import AuditLogModel


@pytest_asyncio.fixture
async def seed_audit_data(test_db):
    rows = [
        AuditLogModel(
            device_id=1,
            audit_type="device",
            result_json={"ok": True},
            status="completed",
            completed_at=datetime.now(timezone.utc),
        ),
        AuditLogModel(
            device_id=1,
            audit_type="device",
            result_json={"ok": False},
            status="failed",
            completed_at=datetime.now(timezone.utc),
        ),
        AuditLogModel(
            device_id=2,
            audit_type="network",
            result_json={"ok": True},
            status="completed",
            completed_at=datetime.now(timezone.utc),
        ),
        AuditLogModel(
            device_id=3,
            audit_type="device",
            result_json={"ok": True},
            status="completed",
            completed_at=datetime.now(timezone.utc),
        ),
    ]
    ids = []
    for row in rows:
        ids.append(await crud.create_audit_log(test_db, row))
    return ids


@pytest.mark.asyncio
async def test_list_audit_results(client, api_prefix, seed_audit_data):
    response = await client.get(f"{api_prefix}/audit/results")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_audit_with_limit(client, api_prefix, seed_audit_data):
    response = await client.get(f"{api_prefix}/audit/results?limit=2")
    assert response.status_code == 200
    assert len(response.json()) <= 2


@pytest.mark.asyncio
async def test_list_audit_with_type_filter(client, api_prefix, seed_audit_data):
    response = await client.get(f"{api_prefix}/audit/results?audit_type=device")
    assert response.status_code == 200
    for item in response.json():
        assert item["audit_type"] == "device"


@pytest.mark.asyncio
async def test_list_audit_with_status_filter(client, api_prefix, seed_audit_data):
    response = await client.get(f"{api_prefix}/audit/results?status=completed")
    assert response.status_code == 200
    for item in response.json():
        assert item["status"] == "completed"


@pytest.mark.asyncio
async def test_list_audit_combined_filters(client, api_prefix, seed_audit_data):
    response = await client.get(f"{api_prefix}/audit/results?audit_type=device&status=completed&limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) <= 5
    for item in payload:
        assert item["audit_type"] == "device"
        assert item["status"] == "completed"


@pytest.mark.asyncio
async def test_get_audit_by_id(client, api_prefix, seed_audit_data):
    audit_id = seed_audit_data[0]
    response = await client.get(f"{api_prefix}/audit/results/{audit_id}")
    assert response.status_code == 200
    assert response.json()["id"] == audit_id


@pytest.mark.asyncio
async def test_get_audit_by_id_not_found(client, api_prefix):
    response = await client.get(f"{api_prefix}/audit/results/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_audit(client, api_prefix, test_app, test_db, seed_device, monkeypatch):
    async def _fake_run_device_audit(device_id):
        await crud.create_audit_log(
            test_db,
            AuditLogModel(
                device_id=device_id,
                audit_type="device",
                result_json={"triggered": True},
                status="completed",
                completed_at=datetime.now(timezone.utc),
            ),
        )
        return None

    monkeypatch.setattr(test_app.state.audit_engine, "run_device_audit", _fake_run_device_audit)

    before = await client.get(f"{api_prefix}/audit/results")
    before_count = len(before.json())

    response = await client.post(f"{api_prefix}/audit/run?device_id={seed_device}&audit_type=device")
    assert response.status_code == 202

    await asyncio.sleep(0.05)
    after = await client.get(f"{api_prefix}/audit/results")
    assert len(after.json()) >= before_count + 1


@pytest.mark.asyncio
async def test_audit_schedule_endpoint_exists(client, api_prefix):
    response = await client.get(f"{api_prefix}/audit/schedule")
    assert response.status_code != 404
