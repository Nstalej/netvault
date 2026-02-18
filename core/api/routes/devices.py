"""
NetVault - Device management routes
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.database.models import DeviceModel
from core.database import crud
from core.database.db import DatabaseManager

router = APIRouter(prefix="/api/devices", tags=["devices"])

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

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
    db: DatabaseManager = Depends(get_db)
):
    """Get the live operational status of a device (Phase 3)"""
    device = await crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "device_id": device_id,
        "status": device.get("status", "unknown"),
        "last_seen": device.get("last_seen"),
        "features": ["snmp_v2", "ping"]
    }

@router.post("/{device_id}/test")
async def test_device_connectivity(
    device_id: int, 
    db: DatabaseManager = Depends(get_db)
):
    """Initiate a connectivity test for the device (Phase 3)"""
    device = await crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # In Phase 3, this will call the appropriate connector
    return {
        "device_id": device_id,
        "test_result": "pending",
        "message": f"Connectivity test initiated for {device['ip']}"
    }
