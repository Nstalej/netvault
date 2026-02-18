"""
NetVault - Security and Network audit routes
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.database.models import AuditLogModel
from core.database import crud
from core.database.db import DatabaseManager

router = APIRouter(prefix="/api/audit", tags=["audit"])

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_audit(
    device_id: int, 
    audit_type: str, 
    db: DatabaseManager = Depends(get_db)
):
    """Trigger a manual audit run for a specific device"""
    # In Phase 3, this will trigger the connector engine
    return {
        "status": "triggered",
        "device_id": device_id,
        "audit_type": audit_type,
        "message": f"Audit {audit_type} initiated for device {device_id}"
    }

@router.get("/results", response_model=List[Dict[str, Any]])
async def list_audit_results(
    device_id: Optional[int] = None, 
    db: DatabaseManager = Depends(get_db)
):
    """List historical audit results, optionally filtered by device"""
    return await crud.list_audit_logs(db, device_id)

@router.get("/results/{audit_id}", response_model=Dict[str, Any])
async def get_audit_result(
    audit_id: int, 
    db: DatabaseManager = Depends(get_db)
):
    """Get detailed results for a specific audit execution"""
    row = await db.fetch_one("SELECT * FROM audit_logs WHERE id = ?", (audit_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Audit result not found")
    return dict(row)

@router.get("/schedule")
async def list_scheduled_audits():
    """List all configured recurring audit schedules (Phase 5)"""
    return []

@router.post("/schedule")
async def create_audit_schedule(schedule_data: Dict[str, Any]):
    """Configure a new recurring audit schedule (Phase 5)"""
    return {"message": "Scheduling feature coming in Phase 5"}
