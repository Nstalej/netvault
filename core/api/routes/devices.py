"""
NetVault - Device management routes
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.api.deps import require_editor_or_above, get_current_user
from core.database.models import DeviceModel, DeviceStatus
from core.database import crud
from core.database.db import DatabaseManager
from core.engine.device_manager import DeviceManager

router = APIRouter(tags=["devices"], dependencies=[Depends(get_current_user)])



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
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Register a new device in the inventory"""
    try:
        device_id = await crud.create_device(db, device)
        return {"id": device_id, "message": "Device registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/devices/{device_id}", response_model=Dict[str, Any])
async def get_device(device_id: int, db: DatabaseManager = Depends(get_db)):
    """Get detailed information for a specific device"""
    device = await crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device["status"] = device.get("status", DeviceStatus.UNKNOWN.value)
    device["latency_ms"] = device.get("config_json", {}).get("last_latency_ms")
    return device


@router.put("/api/devices/{device_id}")
async def update_device(
    device_id: int,
    data: Dict[str, Any],
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Update an existing device's configuration or status"""
    await crud.update_device(db, device_id, data)
    return {"message": "Device updated successfully"}


@router.delete("/api/devices/{device_id}")
async def delete_device(
    device_id: int,
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Remove a device from the inventory"""
    await crud.delete_device(db, device_id)
    return {"message": "Device removed"}


@router.get("/api/devices/{device_id}/status")
async def get_device_status(device_id: int, manager: DeviceManager = Depends(get_manager)):
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
        "features": ["snmp", "ssh"],
    }


@router.post("/api/devices/{device_id}/test")
async def test_device_connectivity(
    device_id: int,
    manager: DeviceManager = Depends(get_manager),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Initiate a connectivity test for the device"""
    result = await manager.test_device(device_id)

    result_status = DeviceStatus.OFFLINE
    if result.success:
        result_status = DeviceStatus.WARNING if (result.latency_ms or 0) > 2000 else DeviceStatus.ONLINE

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
        "error": result.error_message,
    }


@router.post("/api/devices/test-all")
async def test_all_devices(
    manager: DeviceManager = Depends(get_manager),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
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

    return {"total": len(devices), "online": online, "offline": offline, "results": results}



@router.get("/api/devices/{device_id}/interfaces")
async def get_device_interfaces(device_id: int, manager: DeviceManager = Depends(get_manager)):
    """Return interface list from last poll"""
    data = await manager.get_device_data(device_id)
    if not data:
        raise HTTPException(status_code=404, detail="No poll data available for this device")
    return data.get("interfaces", [])


@router.get("/api/devices/{device_id}/arp")
async def get_device_arp(device_id: int, manager: DeviceManager = Depends(get_manager)):
    """Return ARP table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "arp_table" not in data:
        raise HTTPException(status_code=404, detail="No ARP data available. Try /refresh first.")
    return data.get("arp_table", [])


@router.get("/api/devices/{device_id}/mac-table")
async def get_device_mac(device_id: int, manager: DeviceManager = Depends(get_manager)):
    """Return MAC table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "mac_table" not in data:
        raise HTTPException(status_code=404, detail="No MAC data available. Try /refresh first.")
    return data.get("mac_table", [])


@router.get("/api/devices/{device_id}/routes")
async def get_device_routes(device_id: int, manager: DeviceManager = Depends(get_manager)):
    """Return routing table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "routes" not in data:
        raise HTTPException(status_code=404, detail="No routing data available. Try /refresh first.")
    return data.get("routes", [])


@router.get("/api/devices/{device_id}/vlans")
async def get_device_vlans(device_id: int, manager: DeviceManager = Depends(get_manager)):
    """Return VLAN info from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "vlans" not in data:
        return []
    return data.get("vlans", [])


@router.get("/api/devices/{device_id}/system")
async def get_device_system(device_id: int, manager: DeviceManager = Depends(get_manager)):
    """Return full system info from last poll"""
    data = await manager.get_device_data(device_id)
    if not data:
        raise HTTPException(status_code=404, detail="No data available")
    return data.get("system_info", {})


@router.post("/api/devices/{device_id}/refresh")
async def refresh_device(
    device_id: int,
    manager: DeviceManager = Depends(get_manager),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Force a full data refresh (poll + all tables)"""
    await manager.refresh_device_data(device_id)
    return {"message": "Data refresh triggered", "device_id": device_id}


@router.get("/api/devices/{device_id}/refresh")
async def refresh_device_get(
    device_id: int,
    manager: DeviceManager = Depends(get_manager),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """GET alias for manual refresh actions from dashboard UIs"""
    await manager.refresh_device_data(device_id)
    return {"message": "Data refresh triggered", "device_id": device_id}
