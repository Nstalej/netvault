"""
NetVault - Security and Network audit routes
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.database.models import AuditLogModel
from core.database import crud
from core.database.db import DatabaseManager
from core.engine.audit_engine import AuditEngine

router = APIRouter(prefix="/api/audit", tags=["audit"])
v1_router = APIRouter(prefix="/api/v1/audit", tags=["audit-v1"])

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

def get_engine(request: Request) -> AuditEngine:
    return request.app.state.audit_engine

@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
@v1_router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_audit(
    device_id: int, 
    audit_type: str, 
    engine: AuditEngine = Depends(get_engine)
):
    """Trigger a manual audit run for a specific device or the network"""
    if device_id == 0 or audit_type == "network":
        # Global network audit
        import asyncio
        asyncio.create_task(engine.run_network_audit())
        return {
            "status": "triggered",
            "device_id": 0,
            "audit_type": "network",
            "message": "Global network audit initiated"
        }
    else:
        # Single device audit
        import asyncio
        asyncio.create_task(engine.run_device_audit(device_id))
        return {
            "status": "triggered",
            "device_id": device_id,
            "audit_type": audit_type,
            "message": f"Audit {audit_type} initiated for device {device_id}"
        }


@router.post("/results", status_code=status.HTTP_201_CREATED)
@v1_router.post("/results", status_code=status.HTTP_201_CREATED)
async def submit_audit_results(
    log_data: AuditLogModel,
    db: DatabaseManager = Depends(get_db)
):
    """Submit audit results from an agent"""
    try:
        log_id = await crud.create_audit_log(db, log_data)
        return {"log_id": log_id, "message": "Audit results submitted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/results", response_model=List[Dict[str, Any]])
@v1_router.get("/results", response_model=List[Dict[str, Any]])
async def list_audit_results(
    limit: int = 50,
    audit_type: Optional[str] = None,
    status: Optional[str] = None,
    device_id: Optional[int] = None,
    offset: int = 0,
    db: DatabaseManager = Depends(get_db)
):
    """
    List historical audit results with optional filters.

    Examples:
    - GET /api/v1/audit/results?limit=20&audit_type=device&status=completed
    - GET /api/v1/audit/results?device_id=5&limit=10

    Notes:
    - limit=0 returns all matching rows.
    - offset is ignored when limit=0.
    """
    if limit < 0:
        raise HTTPException(status_code=400, detail="limit must be >= 0")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    return await crud.list_audit_logs(
        db,
        device_id=device_id,
        audit_type=audit_type,
        status=status,
        limit=limit,
        offset=offset
    )

@router.get("/results/{audit_id}", response_model=Dict[str, Any])
@v1_router.get("/results/{audit_id}", response_model=Dict[str, Any])
async def get_audit_result(
    audit_id: int, 
    db: DatabaseManager = Depends(get_db)
):
    """Get detailed results for a specific audit execution"""
    row = await crud.get_audit_log(db, audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    return row

@router.get("/schedule")
@v1_router.get("/schedule")
async def list_scheduled_audits():
    """List all configured recurring audit schedules (Phase 5)"""
    return []

@router.post("/schedule")
@v1_router.post("/schedule")
async def create_audit_schedule(schedule_data: Dict[str, Any]):
    """Configure a new recurring audit schedule (Phase 5)"""
    return {"message": "Scheduling feature coming in Phase 5"}
