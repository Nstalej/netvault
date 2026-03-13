"""
NetVault - Device management routes
"""
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.database.models import DeviceModel, DeviceStatus
from core.database import crud
from core.database.db import DatabaseManager
from core.engine.device_manager import DeviceManager

router = APIRouter(tags=["devices"])


class DeviceDataFixPayload(BaseModel):
    mikrotik_device_id: int = 3
    mikrotik_real_ip: Optional[str] = None


_SENSITIVE_CONFIG_KEYS = {
    "password",
    "passphrase",
    "secret",
    "token",
    "private_key",
    "api_key",
    "auth_key",
    "priv_key",
}


def _sanitize_config_json(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: Dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in _SENSITIVE_CONFIG_KEYS or (
                ("password" in lowered or "secret" in lowered or "token" in lowered)
                and lowered != "credential_name"
            ):
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_config_json(value)
        return sanitized

    if isinstance(payload, list):
        return [_sanitize_config_json(item) for item in payload]

    return payload


def _normalize_device_family(device: Dict[str, Any]) -> str:
    device_type = str(device.get("type") or "").strip().lower()
    connector_type = str(device.get("connector_type") or "").strip().lower()
    name = str(device.get("name") or "").strip().lower()

    if "mikrotik" in device_type:
        return "mikrotik"
    if device_type in {"ap", "access_point", "access point"} or "ruckus" in device_type or "ruckus" in name:
        return "ap"
    if device_type == "switch" or connector_type == "snmp":
        return "switch"
    return "generic"


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _extract_key_values(raw: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # key: value
        if ":" in line:
            left, right = line.split(":", 1)
            key = left.strip().lower().replace(" ", "_").replace("-", "_")
            value = right.strip()
            if key:
                data[key] = value

        # key=value tokens
        for key, value in re.findall(r"([A-Za-z0-9_\-]+)=([^\s]+)", line):
            data[key.strip().lower().replace("-", "_")] = value.strip()

    return data


def _parse_human_size_to_bytes(value: str) -> Optional[float]:
    if not value:
        return None

    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGTP]?i?B)?", str(value), re.IGNORECASE)
    if not match:
        return None

    number = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    factor = {
        "B": 1,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
    }.get(unit)
    if factor is None:
        return None
    return number * factor


def _percent(used: Optional[float], total: Optional[float]) -> Optional[str]:
    if used is None or total is None or total <= 0:
        return None
    return f"{round((used / total) * 100)}%"


def _parse_mikrotik_ip_addresses(raw: str) -> List[Dict[str, str]]:
    ip_addresses: List[Dict[str, str]] = []
    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    for line in lines:
        # format: address=192.168.2.3/24 interface=bridge1
        kv = dict(re.findall(r"([A-Za-z0-9_\-]+)=([^\s]+)", line))
        address = kv.get("address")
        interface = kv.get("interface")

        if not address:
            addr_match = re.search(r"address\s*[:=]\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3}/\d{1,2})", line, re.IGNORECASE)
            if addr_match:
                address = addr_match.group(1)
        if not interface:
            int_match = re.search(r"interface\s*[:=]\s*([A-Za-z0-9_.\-]+)", line, re.IGNORECASE)
            if int_match:
                interface = int_match.group(1)

        if address:
            ip_addresses.append({"address": address, "interface": interface or "unknown"})

    return ip_addresses


def _parse_ruckus_wlan_list(raw: str) -> List[Dict[str, Any]]:
    wlans: List[Dict[str, Any]] = []

    for line in raw.splitlines():
        original_line = line
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if any(marker in lower for marker in ["wlan list", "radio", "ssid", "status", "----"]):
            continue

        wlan_match = re.search(r"\b(wlan\d+)\b", line, re.IGNORECASE)
        if not wlan_match:
            continue

        wlan_name = wlan_match.group(1).lower()
        bssid_match = re.search(r"([0-9a-f]{2}(?::[0-9a-f]{2}){5})", line, re.IGNORECASE)
        bssid = bssid_match.group(1).lower() if bssid_match else None

        quoted = re.findall(r'"([^"]+)"', original_line)
        ssid = quoted[0] if quoted else None
        if not ssid:
            ssid_match = re.search(r"ssid\s*[:=]\s*([^,;]+)", line, re.IGNORECASE)
            if ssid_match:
                ssid = ssid_match.group(1).strip()

        status = "unknown"
        if re.search(r"\b(up|enabled)\b", lower):
            status = "up"
        elif re.search(r"\b(down|disabled)\b", lower):
            status = "down"

        security_match = re.search(r"(WPA3?[\-A-Z0-9/]*|WEP|OPEN)", line, re.IGNORECASE)
        security = security_match.group(1).upper() if security_match else "unknown"

        wlans.append(
            {
                "name": wlan_name,
                "ssid": ssid or wlan_name,
                "status": status,
                "security": security,
                "radio": "2.4/5G",
                "bssid": bssid,
            }
        )

    # Deduplicate by WLAN name, keep first parsed
    dedup: Dict[str, Dict[str, Any]] = {}
    for wlan in wlans:
        if wlan["name"] not in dedup:
            dedup[wlan["name"]] = wlan
    return list(dedup.values())


def _parse_ruckus_security(raw: str) -> str:
    if not raw:
        return "unknown"
    upper = raw.upper()
    labels: List[str] = []
    if "WPA3" in upper:
        labels.append("WPA3")
    if "WPA2" in upper:
        labels.append("WPA2")
    if "WPA" in upper and not labels:
        labels.append("WPA")
    if "AES" in upper:
        labels.append("AES")
    if "TKIP" in upper:
        labels.append("TKIP")
    if "OPEN" in upper and not labels:
        labels.append("OPEN")
    if "WEP" in upper and not labels:
        labels.append("WEP")
    if not labels:
        return "unknown"
    return "-".join(labels)


def _parse_airtime(raw: str) -> Dict[str, Optional[int]]:
    metrics = {"total": None, "busy": None, "tx": None, "rx": None}
    if not raw:
        return metrics

    for key in metrics.keys():
        match = re.search(rf"{key}\s*[:=]\s*([0-9]+)", raw, re.IGNORECASE)
        if match:
            metrics[key] = int(match.group(1))

    # fallback for loose token parsing, e.g. "tx 40"
    for key in metrics.keys():
        if metrics[key] is not None:
            continue
        match = re.search(rf"\b{key}\b\s+([0-9]+)", raw, re.IGNORECASE)
        if match:
            metrics[key] = int(match.group(1))

    return metrics


async def _fetch_mikrotik_live_data(connector: Any) -> Dict[str, Any]:
    try:
        if not await connector.connect():
            raise ConnectionError("Could not connect to MikroTik device")

        identity_raw = await connector._execute_command("/system identity print")
        resource_raw = await connector._execute_command("/system resource print")
        ip_raw = await connector._execute_command("/ip address print detail without-paging")
        interfaces = await connector.get_interfaces()

        identity_map = _extract_key_values(identity_raw)
        resource_map = _extract_key_values(resource_raw)

        identity = identity_map.get("name") or resource_map.get("identity") or "unknown"
        version = resource_map.get("version", "unknown")
        uptime = resource_map.get("uptime", "unknown")

        cpu_load = resource_map.get("cpu_load") or resource_map.get("cpu") or "unknown"
        if cpu_load.isdigit():
            cpu_load = f"{cpu_load}%"

        total_memory = _parse_human_size_to_bytes(resource_map.get("total_memory", ""))
        free_memory = _parse_human_size_to_bytes(resource_map.get("free_memory", ""))
        used_memory = (total_memory - free_memory) if (total_memory is not None and free_memory is not None) else None
        memory_used = _percent(used_memory, total_memory) or "unknown"

        parsed_interfaces = [
            {
                "name": getattr(item, "name", None),
                "status": getattr(item, "status", "unknown"),
                "mac": getattr(item, "mac", None),
                "rx_bytes": getattr(item, "rx_bytes", 0),
                "tx_bytes": getattr(item, "tx_bytes", 0),
            }
            for item in interfaces
        ]

        return {
            "identity": identity,
            "version": version,
            "uptime": uptime,
            "cpu_load": cpu_load,
            "memory_used": memory_used,
            "board_info": {
                "board_name": resource_map.get("board_name"),
                "architecture_name": resource_map.get("architecture_name"),
                "cpu": resource_map.get("cpu"),
            },
            "interfaces": parsed_interfaces,
            "ip_addresses": _parse_mikrotik_ip_addresses(ip_raw),
        }
    finally:
        if connector.is_connected:
            await connector.disconnect()


async def _fetch_ruckus_live_data(connector: Any, device: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not await connector.connect():
            raise ConnectionError("Could not connect to Ruckus AP")

        cmd = connector._execute_command

        version_raw = await cmd("get version")
        board_raw = await cmd("get boarddata")
        ip_raw = await cmd("get ipaddr wan")
        uptime_raw = await cmd("get uptime")
        wlan_raw = await cmd("get wlanlist")

        version_map = _extract_key_values(version_raw)
        board_map = _extract_key_values(board_raw)
        ip_map = _extract_key_values(ip_raw)
        uptime_map = _extract_key_values(uptime_raw)

        wlans = _parse_ruckus_wlan_list(wlan_raw)
        airtime_total = {"total": 0, "busy": 0, "tx": 0, "rx": 0}
        has_airtime = False

        for wlan in wlans:
            wlan_name = wlan.get("name")
            if not wlan_name:
                continue

            encryption_raw = await cmd(f"get encryption {wlan_name}")
            wlan["security"] = _parse_ruckus_security(encryption_raw) or wlan.get("security", "unknown")

            airtime_raw = await cmd(f"get airtime {wlan_name}")
            metrics = _parse_airtime(airtime_raw)
            if any(v is not None for v in metrics.values()):
                has_airtime = True
                for key in airtime_total.keys():
                    airtime_total[key] += metrics.get(key) or 0

        model = board_map.get("model") or board_map.get("ap_model") or "Ruckus AP"
        firmware = (
            version_map.get("firmware")
            or version_map.get("firmware_version")
            or version_map.get("version")
            or "unknown"
        )
        serial = board_map.get("serial") or board_map.get("serial_number") or "unknown"
        uptime = uptime_map.get("uptime") or uptime_raw.strip() or "unknown"

        ip = (
            ip_map.get("ip")
            or ip_map.get("ipaddr")
            or ip_map.get("address")
            or device.get("ip")
            or device.get("ip_address")
            or "unknown"
        )

        return {
            "model": model,
            "firmware": firmware,
            "serial": serial,
            "uptime": uptime,
            "ip": ip,
            "netmask": ip_map.get("netmask", "unknown"),
            "gateway": ip_map.get("gateway", "unknown"),
            "wlans": wlans,
            "airtime": airtime_total if has_airtime else {"total": None, "busy": None, "tx": None, "rx": None},
        }
    finally:
        if connector.is_connected:
            await connector.disconnect()


async def _fetch_switch_live_data(connector: Any) -> Dict[str, Any]:
    try:
        if not await connector.connect():
            raise ConnectionError("Could not connect to switch")

        system = await connector.get_system_info()
        interfaces = await connector.get_interfaces()

        parsed_interfaces = [
            {
                "name": getattr(item, "name", None),
                "status": getattr(item, "status", "unknown"),
                "mac": getattr(item, "mac", None),
                "speed": getattr(item, "speed", None),
                "rx_bytes": getattr(item, "rx_bytes", 0),
                "tx_bytes": getattr(item, "tx_bytes", 0),
            }
            for item in interfaces
        ]

        return {
            "sysName": system.get("name") or system.get("sysname") or "unknown",
            "sysDescr": system.get("descr") or system.get("description") or "unknown",
            "uptime": system.get("uptime") or "unknown",
            "interfaces": parsed_interfaces,
            "system": system,
        }
    finally:
        if connector.is_connected:
            await connector.disconnect()

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

def get_manager(request: Request) -> DeviceManager:
    return request.app.state.device_manager

@router.get("/api/devices", response_model=List[Dict[str, Any]])
async def list_devices(db: DatabaseManager = Depends(get_db)):
    """List all registered network devices"""
    return await crud.list_devices(db)

@router.post("/api/devices", status_code=status.HTTP_201_CREATED)
async def create_device(
    device: DeviceModel, 
    db: DatabaseManager = Depends(get_db)
):
    """Register a new device in the inventory"""
    try:
        device_id = await crud.create_device(db, device)
        return {"id": device_id, "message": "Device registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/devices/{device_id}", response_model=Dict[str, Any])
async def get_device(
    device_id: int, 
    db: DatabaseManager = Depends(get_db)
):
    """Get detailed information for a specific device"""
    device = await crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device["status"] = device.get("status", DeviceStatus.UNKNOWN.value)
    device["latency_ms"] = device.get("config_json", {}).get("last_latency_ms")
    return device


@router.get("/api/devices/{device_id}/detail", response_model=Dict[str, Any])
async def get_device_detail(
    device_id: int,
    db: DatabaseManager = Depends(get_db),
):
    """Return full detail payload used by device detail page."""
    device = await crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    family = _normalize_device_family(device)
    tab_map = {
        "mikrotik": ["overview", "interfaces", "routing", "config", "history"],
        "ap": ["overview", "wireless", "clients", "radio", "config", "history"],
        "switch": ["overview", "interfaces", "config", "history"],
        "generic": ["overview", "config", "history"],
    }

    config_json = device.get("config_json", {}) or {}
    sanitized = _sanitize_config_json(config_json)

    return {
        "id": device.get("id"),
        "name": device.get("name"),
        "ip": device.get("ip") or device.get("ip_address"),
        "type": device.get("type"),
        "connector_type": device.get("connector_type"),
        "status": device.get("status", DeviceStatus.UNKNOWN.value),
        "last_seen": _to_iso(device.get("last_seen")),
        "last_status_change": _to_iso(device.get("last_status_change")),
        "credential_name": config_json.get("credential_name"),
        "device_family": family,
        "tabs": tab_map.get(family, tab_map["generic"]),
        "config_json": sanitized,
    }


@router.get("/api/devices/{device_id}/live-data", response_model=Dict[str, Any])
async def get_device_live_data(
    device_id: int,
    manager: DeviceManager = Depends(get_manager),
):
    """Collect and return live operational data from device connector."""
    device = await crud.get_device(manager.db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    connector = await manager.get_connector(device_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Could not initialize connector for this device")

    family = _normalize_device_family(device)
    connector_type = str(device.get("connector_type") or "").strip().lower()

    try:
        if family == "mikrotik":
            live = await _fetch_mikrotik_live_data(connector)
        elif family == "ap":
            live = await _fetch_ruckus_live_data(connector, device)
        elif family == "switch" and connector_type == "snmp":
            live = await _fetch_switch_live_data(connector)
        else:
            # Best-effort generic collection
            live = await _fetch_switch_live_data(connector)

        live["device_id"] = device_id
        live["device_family"] = family
        live["collected_at"] = datetime.now(timezone.utc).isoformat()
        return live
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to collect live data: {exc}")


@router.get("/api/devices/{device_id}/history", response_model=Dict[str, Any])
async def get_device_history(
    device_id: int,
    db: DatabaseManager = Depends(get_db),
):
    """Return status history and recent per-device test/audit context."""
    device = await crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    config_json = device.get("config_json", {}) or {}
    events: List[Dict[str, Any]] = []

    if device.get("last_status_change"):
        events.append(
            {
                "event": "status_change",
                "status": device.get("status", DeviceStatus.UNKNOWN.value),
                "timestamp": _to_iso(device.get("last_status_change")),
                "message": "Last known status transition",
            }
        )

    if device.get("last_seen"):
        events.append(
            {
                "event": "last_seen",
                "status": device.get("status", DeviceStatus.UNKNOWN.value),
                "timestamp": _to_iso(device.get("last_seen")),
                "message": "Last successful contact time",
            }
        )

    audit_rows = await db.fetch_all(
        "SELECT id, audit_type, status, started_at, completed_at FROM audit_logs WHERE device_id = ? ORDER BY id DESC LIMIT 20",
        (device_id,),
    )

    for row in audit_rows:
        events.append(
            {
                "event": "audit",
                "status": row.get("status", "unknown"),
                "timestamp": _to_iso(row.get("completed_at") or row.get("started_at")),
                "message": f"Audit {row.get('audit_type', 'unknown')} (#{row.get('id')})",
            }
        )

    latest_test = {
        "latency_ms": config_json.get("last_latency_ms"),
        "error": config_json.get("last_test_error"),
        "status": device.get("status", DeviceStatus.UNKNOWN.value),
        "timestamp": _to_iso(device.get("last_seen") or device.get("updated_at")),
    }

    return {
        "device_id": device_id,
        "current_status": device.get("status", DeviceStatus.UNKNOWN.value),
        "last_seen": _to_iso(device.get("last_seen")),
        "last_status_change": _to_iso(device.get("last_status_change")),
        "events": events,
        "latest_test": latest_test,
    }

@router.put("/api/devices/{device_id}")
async def update_device(
    device_id: int, 
    data: Dict[str, Any], 
    db: DatabaseManager = Depends(get_db)
):
    """Update an existing device's configuration or status"""
    await crud.update_device(db, device_id, data)
    return {"message": "Device updated successfully"}

@router.delete("/api/devices/{device_id}")
async def delete_device(
    device_id: int, 
    db: DatabaseManager = Depends(get_db)
):
    """Remove a device from the inventory"""
    await crud.delete_device(db, device_id)
    return {"message": "Device removed"}

@router.get("/api/devices/{device_id}/status")
async def get_device_status(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Get the live operational status of a device"""
    status_str = await manager.get_device_status(device_id)
    if status_str == DeviceStatus.UNKNOWN.value:
         # Check if device exists at all
         device = await crud.get_device(manager.db, device_id)
         if not device:
             raise HTTPException(status_code=404, detail="Device not found")
             
    device = await crud.get_device(manager.db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "id": device_id,
        "status": device.get("status", DeviceStatus.UNKNOWN.value),
        "last_seen": device.get("last_seen"),
        "latency_ms": device.get("config_json", {}).get("last_latency_ms"),
        "features": ["snmp", "ssh"]
    }

@router.post("/api/devices/{device_id}/test")
async def test_device_connectivity(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Initiate a connectivity test for the device"""
    result = await manager.test_device(device_id)

    device = await crud.get_device(manager.db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    config_json = device.get("config_json", {})
    config_json["last_latency_ms"] = result.latency_ms
    if result.error_message:
        config_json["last_test_error"] = result.error_message
    else:
        config_json.pop("last_test_error", None)
    await crud.update_device(manager.db, device_id, {"config_json": config_json})

    updated_device = await crud.get_device(manager.db, device_id)
    status_value = updated_device.get("status", DeviceStatus.UNKNOWN.value) if updated_device else DeviceStatus.UNKNOWN.value

    return {
        "device_id": device_id,
        "success": result.success,
        "status": status_value,
        "latency_ms": result.latency_ms,
        "error": result.error_message
    }


@router.post("/api/devices/maintenance/fix-known-network-data")
async def fix_known_network_data(
    payload: Optional[DeviceDataFixPayload] = None,
    db: DatabaseManager = Depends(get_db),
):
    """Apply known production data fixes for SSH device connectivity."""
    payload = payload or DeviceDataFixPayload()

    fixed: Dict[str, Any] = {
        "ports_updated": [],
        "mikrotik_ip_updated": False,
    }

    for dev_id in [4, 5, 7]:
        device = await crud.get_device(db, dev_id)
        if not device:
            continue
        if int(device.get("port") or 0) != 22:
            await crud.update_device(db, dev_id, {"port": 22})
            fixed["ports_updated"].append(dev_id)

    if payload.mikrotik_real_ip:
        device = await crud.get_device(db, payload.mikrotik_device_id)
        if device:
            await crud.update_device(db, payload.mikrotik_device_id, {"ip": payload.mikrotik_real_ip})
            fixed["mikrotik_ip_updated"] = True

    return {
        "message": "Known network data fixes applied",
        "changes": fixed,
        "sql_reference": "UPDATE devices SET port = 22 WHERE id IN (4,5,7);",
    }
    
@router.post("/api/devices/test-all")
async def test_all_devices(manager: DeviceManager = Depends(get_manager)):
    """Test all devices sequence"""
    devices = await crud.list_devices(manager.db)
    results = []
    online = 0
    offline = 0
    for device in devices:
        res = await test_device_connectivity(device["id"], manager)
        results.append(res)
        if res["status"] == DeviceStatus.ONLINE.value:
            online += 1
        else:
            offline += 1
            
    return {
        "total": len(devices),
        "online": online,
        "offline": offline,
        "results": results
    }

@router.get("/api/devices/{device_id}/interfaces")
async def get_device_interfaces(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return interface list from last poll"""
    data = await manager.get_device_data(device_id)
    if not data:
        raise HTTPException(status_code=404, detail="No poll data available for this device")
    return data.get("interfaces", [])

@router.get("/api/devices/{device_id}/arp")
async def get_device_arp(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return ARP table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "arp_table" not in data:
        raise HTTPException(status_code=404, detail="No ARP data available. Try /refresh first.")
    return data.get("arp_table", [])

@router.get("/api/devices/{device_id}/mac-table")
async def get_device_mac(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return MAC table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "mac_table" not in data:
        raise HTTPException(status_code=404, detail="No MAC data available. Try /refresh first.")
    return data.get("mac_table", [])

@router.get("/api/devices/{device_id}/routes")
async def get_device_routes(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return routing table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "routes" not in data:
        raise HTTPException(status_code=404, detail="No routing data available. Try /refresh first.")
    return data.get("routes", [])

@router.get("/api/devices/{device_id}/vlans")
async def get_device_vlans(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return VLAN info from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "vlans" not in data:
        # Check if system_info has some hints or if it's just missing
        return []
    return data.get("vlans", [])

@router.get("/api/devices/{device_id}/system")
async def get_device_system(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return full system info from last poll"""
    data = await manager.get_device_data(device_id)
    if not data:
        raise HTTPException(status_code=404, detail="No data available")
    return data.get("system_info", {})

@router.post("/api/devices/{device_id}/refresh")
async def refresh_device(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Force a full data refresh (poll + all tables)"""
    # This might be slow, so we could theoretically run it in background
    # but for manual refresh, user usually expects it to complete.
    await manager.refresh_device_data(device_id)
    return {"message": "Data refresh triggered", "device_id": device_id}

@router.get("/api/devices/{device_id}/refresh")
async def refresh_device_get(
    device_id: int,
    manager: DeviceManager = Depends(get_manager)
):
    """GET alias for manual refresh actions from dashboard UIs"""
    await manager.refresh_device_data(device_id)
    return {"message": "Data refresh triggered", "device_id": device_id}
