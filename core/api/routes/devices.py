"""
NetVault - Device management routes
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.database.models import DeviceModel
from core.database import crud
from core.database.db import DatabaseManager
from core.engine.device_manager import DeviceManager

router = APIRouter(prefix="/api/devices", tags=["devices"])

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

def get_manager(request: Request) -> DeviceManager:
    return request.app.state.device_manager

@router.get("/", response_model=List[Dict[str, Any]])
async def list_devices(db: DatabaseManager = Depends(get_db)):
    """List all registered network devices"""
    return await crud.list_devices(db)

@router.post("/", status_code=status.HTTP_201_CREATED)
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

@router.get("/{device_id}", response_model=Dict[str, Any])
async def get_device(
    device_id: int, 
    db: DatabaseManager = Depends(get_db)
):
    """Get detailed information for a specific device"""
    device = await crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.put("/{device_id}")
async def update_device(
    device_id: int, 
    data: Dict[str, Any], 
    db: DatabaseManager = Depends(get_db)
):
    """Update an existing device's configuration or status"""
    await crud.update_device(db, device_id, data)
    return {"message": "Device updated successfully"}

@router.delete("/{device_id}")
async def delete_device(
    device_id: int, 
    db: DatabaseManager = Depends(get_db)
):
    """Remove a device from the inventory"""
    await crud.delete_device(db, device_id)
    return {"message": "Device removed"}

@router.get("/{device_id}/status")
async def get_device_status(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Get the live operational status of a device"""
    status_str = await manager.get_device_status(device_id)
    if status_str == "unknown":
         # Check if device exists at all
         device = await crud.get_device(manager.db, device_id)
         if not device:
             raise HTTPException(status_code=404, detail="Device not found")
             
    data = await manager.get_device_data(device_id)
    return {
        "device_id": device_id,
        "status": status_str,
        "last_seen": data.get("last_poll") if data else None,
        "features": ["snmp", "ssh"] # Placeholder for actual capability detection
    }

@router.post("/{device_id}/test")
async def test_device_connectivity(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Initiate a connectivity test for the device"""
    result = await manager.test_device(device_id)
    return {
        "device_id": device_id,
        "success": result.success,
        "latency_ms": result.latency_ms,
        "error": result.error_message
    }

@router.get("/{device_id}/interfaces")
async def get_device_interfaces(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return interface list from last poll"""
    data = await manager.get_device_data(device_id)
    if not data:
        raise HTTPException(status_code=404, detail="No poll data available for this device")
    return data.get("interfaces", [])

@router.get("/{device_id}/arp")
async def get_device_arp(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return ARP table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "arp_table" not in data:
        raise HTTPException(status_code=404, detail="No ARP data available. Try /refresh first.")
    return data.get("arp_table", [])

@router.get("/{device_id}/mac-table")
async def get_device_mac(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return MAC table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "mac_table" not in data:
        raise HTTPException(status_code=404, detail="No MAC data available. Try /refresh first.")
    return data.get("mac_table", [])

@router.get("/{device_id}/routes")
async def get_device_routes(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return routing table from last poll"""
    data = await manager.get_device_data(device_id)
    if not data or "routes" not in data:
        raise HTTPException(status_code=404, detail="No routing data available. Try /refresh first.")
    return data.get("routes", [])

@router.get("/{device_id}/vlans")
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

@router.get("/{device_id}/system")
async def get_device_system(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Return full system info from last poll"""
    data = await manager.get_device_data(device_id)
    if not data:
        raise HTTPException(status_code=404, detail="No data available")
    return data.get("system_info", {})

@router.post("/{device_id}/refresh")
async def refresh_device(
    device_id: int, 
    manager: DeviceManager = Depends(get_manager)
):
    """Force a full data refresh (poll + all tables)"""
    # This might be slow, so we could theoretically run it in background
    # but for manual refresh, user usually expects it to complete.
    await manager.refresh_device_data(device_id)
    return {"message": "Data refresh triggered", "device_id": device_id}

