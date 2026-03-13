import asyncio
import os

import pytest

from connectors.ssh_connector.ssh_connector import SSHConnector

pytestmark = pytest.mark.e2e


@pytest.fixture
def live_credentials():
    host = os.getenv("MIKROTIK_HOST", "192.168.2.3")
    user = os.getenv("MIKROTIK_USER", "admin")
    password = os.getenv("MIKROTIK_PASS")
    port = int(os.getenv("MIKROTIK_PORT", "22"))

    if not password:
        pytest.skip("MIKROTIK_PASS not set")

    return {
        "host": host,
        "username": user,
        "password": password,
        "port": port,
        "timeout": 10,
    }


@pytest.mark.asyncio
async def test_ssh_connection(live_credentials):
    connector = SSHConnector(
        device_id="e2e-1",
        device_ip=live_credentials["host"],
        credentials={
            "username": live_credentials["username"],
            "password": live_credentials["password"],
            "port": live_credentials["port"],
            "device_type": "mikrotik",
            "timeout": live_credentials["timeout"],
        },
    )
    try:
        connected = await asyncio.wait_for(connector.connect(), timeout=15)
        assert connected is True
        assert connector.is_connected is True
    finally:
        await connector.disconnect()


@pytest.mark.asyncio
async def test_ssh_test_connection(live_credentials):
    connector = SSHConnector(
        device_id="e2e-2",
        device_ip=live_credentials["host"],
        credentials={
            "username": live_credentials["username"],
            "password": live_credentials["password"],
            "port": live_credentials["port"],
            "device_type": "mikrotik",
            "timeout": live_credentials["timeout"],
        },
    )
    result = await asyncio.wait_for(connector.test_connection(), timeout=15)
    assert result.success is True
    assert result.latency_ms < 5000


@pytest.mark.asyncio
async def test_ssh_system_info(live_credentials):
    connector = SSHConnector(
        device_id="e2e-3",
        device_ip=live_credentials["host"],
        credentials={
            "username": live_credentials["username"],
            "password": live_credentials["password"],
            "port": live_credentials["port"],
            "device_type": "mikrotik",
            "timeout": live_credentials["timeout"],
        },
    )
    try:
        await asyncio.wait_for(connector.connect(), timeout=15)
        info = await asyncio.wait_for(connector.get_system_info(), timeout=15)
        assert isinstance(info, dict)
        assert "model" in info
        assert "os_version" in info
        assert "uptime" in info
    finally:
        await connector.disconnect()


@pytest.mark.asyncio
async def test_ssh_interfaces(live_credentials):
    connector = SSHConnector(
        device_id="e2e-4",
        device_ip=live_credentials["host"],
        credentials={
            "username": live_credentials["username"],
            "password": live_credentials["password"],
            "port": live_credentials["port"],
            "device_type": "mikrotik",
            "timeout": live_credentials["timeout"],
        },
    )
    try:
        await asyncio.wait_for(connector.connect(), timeout=15)
        interfaces = await asyncio.wait_for(connector.get_interfaces(), timeout=15)
        assert interfaces
        assert any(item.status == "up" for item in interfaces)
    finally:
        await connector.disconnect()


@pytest.mark.asyncio
async def test_ssh_arp_table(live_credentials):
    connector = SSHConnector(
        device_id="e2e-5",
        device_ip=live_credentials["host"],
        credentials={
            "username": live_credentials["username"],
            "password": live_credentials["password"],
            "port": live_credentials["port"],
            "device_type": "mikrotik",
            "timeout": live_credentials["timeout"],
        },
    )
    try:
        await asyncio.wait_for(connector.connect(), timeout=15)
        arp_table = await asyncio.wait_for(connector.get_arp_table(), timeout=15)
        assert isinstance(arp_table, list)
    finally:
        await connector.disconnect()


@pytest.mark.asyncio
async def test_ssh_routes(live_credentials):
    connector = SSHConnector(
        device_id="e2e-6",
        device_ip=live_credentials["host"],
        credentials={
            "username": live_credentials["username"],
            "password": live_credentials["password"],
            "port": live_credentials["port"],
            "device_type": "mikrotik",
            "timeout": live_credentials["timeout"],
        },
    )
    try:
        await asyncio.wait_for(connector.connect(), timeout=15)
        routes = await asyncio.wait_for(connector.get_routes(), timeout=15)
        assert len(routes) >= 1
    finally:
        await connector.disconnect()


@pytest.mark.asyncio
async def test_ssh_device_type_detection(live_credentials):
    connector = SSHConnector(
        device_id="e2e-7",
        device_ip=live_credentials["host"],
        credentials={
            "username": live_credentials["username"],
            "password": live_credentials["password"],
            "port": live_credentials["port"],
            "device_type": "auto",
            "timeout": live_credentials["timeout"],
        },
    )
    try:
        connected = await asyncio.wait_for(connector.connect(), timeout=15)
        assert connected is True
        assert connector.device_type == "mikrotik"
    finally:
        await connector.disconnect()
