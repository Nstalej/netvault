"""
NetVault - Remote Agent management routes
"""
import io
import json
import os
import zipfile
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from core.config import Settings
from core.database import crud
from core.database.db import DatabaseManager
from core.database.models import AgentModel

router = APIRouter(prefix="/api/agents", tags=["agents"])

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

def get_config(request: Request) -> Settings:
    return request.app.state.config

async def validate_agent_token(
    x_agent_token: str = Header(...),
    config: Settings = Depends(get_config)
):
    """Validate that the agent provides a correct authorization token"""
    if x_agent_token != config.security.agent_auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent authentication token"
        )

@router.get("/", response_model=List[Dict[str, Any]])
async def list_agents(db: DatabaseManager = Depends(get_db)):
    """List all agents currently registered with the dashboard"""
    return await db.fetch_all("SELECT * FROM agents")

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_agent(
    agent: AgentModel,
    db: DatabaseManager = Depends(get_db),
    _token = Depends(validate_agent_token)
):
    """Agent self-registration (called by the agent on startup)"""
    try:
        agent_id = await crud.upsert_agent(db, agent)
        return {"agent_id": agent_id, "message": "Agent registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: int,
    db: DatabaseManager = Depends(get_db),
    _token = Depends(validate_agent_token)
):
    """Update an agent's status and last heartbeat timestamp"""
    await crud.update_agent_heartbeat(db, agent_id)
    return {"status": "ok", "timestamp": str(datetime.now())}

@router.get("/{agent_id}/status")
async def get_agent_status(
    agent_id: int,
    db: DatabaseManager = Depends(get_db)
):
    """Get the current operational status of a specific agent"""
    agent = await crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{agent_id}/ad-data")
async def get_agent_ad_data(
    agent_id: int,
    db: DatabaseManager = Depends(get_db),
):
    """Return latest successful AD audit data payload for an agent."""
    agent = await crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    row = await db.fetch_one(
        (
            "SELECT id, audit_type, status, completed_at, result_json "
            "FROM audit_logs "
            "WHERE agent_id = ? AND audit_type = 'ad_audit' "
            "AND lower(status) IN ('success', 'completed') "
            "ORDER BY completed_at DESC, id DESC LIMIT 1"
        ),
        (agent_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="No AD audit data found for this agent")

    result_json = json.loads(row.get("result_json") or "{}")
    return {
        "agent_id": agent_id,
        "audit_id": row.get("id"),
        "audit_type": row.get("audit_type"),
        "status": row.get("status"),
        "completed_at": row.get("completed_at"),
        "summary": result_json.get("summary", {}),
        "checks": result_json.get("checks", []),
        "data": result_json.get("data", {}),
    }

@router.delete("/{agent_id}")
async def unregister_agent(
    agent_id: int,
    db: DatabaseManager = Depends(get_db)
):
    """Permanently remove an agent from the registry"""
    await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    return {"message": "Agent unregistered"}

@router.get("/download/{agent_type}")
async def download_agent_package(agent_type: str):
    """Provide a download link or package for the requested agent type"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    agent_dir = os.path.join(base_dir, "agents", agent_type)
    
    if not os.path.exists(agent_dir):
        raise HTTPException(status_code=404, detail=f"Agent package for {agent_type} not found locally.")
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(agent_dir):
            for file in files:
                if "__pycache__" in root or "venv" in root:
                    continue
                file_path = os.path.join(root, file)
                # Ensure the root of the zip is the agent name (e.g. windows_ad/...)
                archive_name = os.path.relpath(file_path, os.path.join(base_dir, "agents"))
                zf.write(file_path, archive_name)
    
    memory_file.seek(0)
    return StreamingResponse(
        memory_file, 
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=netvault_{agent_type}_agent.zip"}
    )
