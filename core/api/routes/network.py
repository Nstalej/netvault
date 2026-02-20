"""
NetVault - Global Network routes
Topology visualization and cross-device searching.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from core.engine.device_manager import DeviceManager

router = APIRouter(prefix="/api/network", tags=["network"])

def get_manager(request: Request) -> DeviceManager:
    return request.app.state.device_manager

@router.get("/topology")
async def get_topology(manager: DeviceManager = Depends(get_manager)):
    """
    Build and return network topology from cross-referencing ARP/MAC data.
    """
    # Simply return nodes and edges for a topology graph
    nodes = []
    edges = []
    
    # 1. Add all devices as nodes
    for device_id, device in manager._devices.items():
        nodes.append({
            "id": f"device_{device_id}",
            "label": device.get("name"),
            "type": "device",
            "status": device.get("status", "unknown"),
            "ip": device.get("ip") or device.get("ip_address")
        })

    # 2. Build edges from MAC/ARP relationships
    # This is a simplified heuristic: if a MAC from device A is seen on device B's port,
    # there is a link.
    for device_id, data in manager._cache.items():
        mac_table = data.get("mac_table", [])
        for entry in mac_table:
            target_mac = entry.get("mac")
            port = entry.get("port")
            
            # Check if this MAC belongs to any other device we know
            for other_id, other_data in manager._cache.items():
                if other_id == device_id:
                    continue
                
                # Check system info for MACs
                system_info = other_data.get("system_info", {})
                other_macs = system_info.get("mac_addresses", [])
                
                if target_mac in other_macs:
                    edges.append({
                        "from": f"device_{device_id}",
                        "to": f"device_{other_id}",
                        "label": port,
                        "type": "physical"
                    })

    return {"nodes": nodes, "edges": edges}

@router.get("/search")
async def search_network(
    mac: Optional[str] = None, 
    ip: Optional[str] = None,
    manager: DeviceManager = Depends(get_manager)
):
    """Search all devices for a MAC or IP address"""
    if not mac and not ip:
        raise HTTPException(status_code=400, detail="Must provide 'mac' or 'ip' parameter")

    results = []
    
    for device_id, data in manager._cache.items():
        device_cfg = manager._devices.get(device_id, {})
        
        # Search in MAC table
        if mac:
            mac_table = data.get("mac_table", [])
            for entry in mac_table:
                if entry.get("mac") == mac:
                    results.append({
                        "device_id": device_id,
                        "device_name": device_cfg.get("name"),
                        "type": "mac_match",
                        "port": entry.get("port"),
                        "vlan": entry.get("vlan")
                    })
        
        # Search in ARP table
        if ip:
            arp_table = data.get("arp_table", [])
            for entry in arp_table:
                if entry.get("ip") == ip:
                    results.append({
                        "device_id": device_id,
                        "device_name": device_cfg.get("name"),
                        "type": "arp_match",
                        "mac": entry.get("mac"),
                        "interface": entry.get("interface")
                    })
                    
        # Check device itself
        device_ip = device_cfg.get("ip") or device_cfg.get("ip_address")
        if ip and device_ip == ip:
             results.append({
                "device_id": device_id,
                "device_name": device_cfg.get("name"),
                "type": "device_match",
                "ip": device_ip
            })

    return results
