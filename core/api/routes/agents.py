"""
NetVault - Remote Agent management routes
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status

from core.database.models import AgentModel
from core.database import crud
from core.database.db import DatabaseManager
from core.config import Settings

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
    # This might combine DB data with live heartbeat data from memory
    return await crud.fetch_all_agents_with_status(db) # We should add this to crud or use a custom query

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_agent(
    agent: AgentModel,
    db: DatabaseManager = Depends(get_db),
    _token = Depends(validate_agent_token)
):
    """Agent self-registration (called by the agent on startup)"""
    try:
        agent_id = await crud.create_agent(db, agent)
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
    # Phase 4 feature
    return {
        "agent_type": agent_type,
        "download_url": f"https://github.com/ingenieroredes/netvault/releases/latest/agent_{agent_type}.zip"
    }

# --- Helper logic for list_agents (could be in crud.py) ---
async def fetch_all_agents_with_status(db: DatabaseManager):
    return await db.fetch_all("SELECT * FROM agents")
# Updating crud.py might be better, but let's keep it here for now if needed.
