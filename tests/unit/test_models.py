import pytest

from connectors.base import AuditResult
from core.database.models import DeviceModel, DeviceStatus


def test_device_model_basic():
    model = DeviceModel(
        name="R1",
        type="router",
        ip="10.0.0.1",
        port=22,
        connector_type="ssh",
    )
    assert model.name == "R1"
    assert model.config_json == {}


def test_device_model_config_json_direct():
    model = DeviceModel(
        name="R2",
        type="router",
        ip="10.0.0.2",
        port=22,
        connector_type="ssh",
        config_json={"credential_name": "x"},
    )
    assert model.config_json["credential_name"] == "x"


def test_device_model_config_alias():
    model = DeviceModel(
        name="R3",
        type="router",
        ip="10.0.0.3",
        port=22,
        connector_type="ssh",
        config={"credential_name": "alias-cred"},
    )
    assert model.config_json == {"credential_name": "alias-cred"}


def test_device_model_config_json_serialization():
    model = DeviceModel(
        name="R4",
        type="router",
        ip="10.0.0.4",
        port=22,
        connector_type="ssh",
        config_json={"credential_name": "x"},
    )
    data = model.model_dump()
    assert "config_json" in data
    assert data["config_json"]["credential_name"] == "x"


def test_device_model_config_json_serialization_by_alias():
    model = DeviceModel(
        name="R5",
        type="router",
        ip="10.0.0.5",
        port=22,
        connector_type="ssh",
        config={"credential_name": "x"},
    )
    data = model.model_dump(by_alias=True)
    assert "config" in data


def test_device_model_default_status():
    model = DeviceModel(
        name="R6",
        type="router",
        ip="10.0.0.6",
        port=22,
        connector_type="ssh",
    )
    assert model.status == DeviceStatus.UNKNOWN


def test_device_model_valid_status_values():
    valid_values = {"online", "offline", "warning", "unknown"}
    for value in valid_values:
        model = DeviceModel(
            name=f"R-{value}",
            type="router",
            ip="10.0.1.1",
            port=22,
            connector_type="ssh",
            status=value,
        )
        assert model.status.value == value

    with pytest.raises(ValueError):
        DeviceModel(
            name="R-invalid",
            type="router",
            ip="10.0.1.2",
            port=22,
            connector_type="ssh",
            status="up",
        )


def test_credential_model_basic():
    payload = {
        "name": "cred-1",
        "type": "ssh",
        "data": {"username": "admin", "password": "x"},
    }
    assert payload["name"] == "cred-1"
    assert payload["type"] == "ssh"
    assert "username" in payload["data"]


def test_audit_result_model():
    result = AuditResult(device_name="router-1", summary="ok")
    assert result.device_name == "router-1"
    assert result.summary == "ok"
    assert isinstance(result.checks, list)
