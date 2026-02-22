"""
NetVault - MCP Server
Implementation of the Model Context Protocol server using SSE over HTTP.
"""
import asyncio
import logging
import uvicorn
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request
from starlette.responses import Response

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server.sse import SseServerTransport

from core.config import get_config
from core.database.db import DatabaseManager
from core.engine.device_manager import DeviceManager
from core.engine.audit_engine import AuditEngine
from core.engine.logger import get_logger
from core.mcp_server.tools import MCPToolProvider

logger = get_logger("netvault.mcp.server")

class NetVaultMCPServer:
    """
    MCP Server for NetVault that exposes network monitoring tools via SSE.
    """
    def __init__(self, db: DatabaseManager, device_manager: DeviceManager, audit_engine: AuditEngine):
        self.config = get_config()
        self.server = Server("netvault-mcp")
        self.provider = MCPToolProvider(db, device_manager, audit_engine)
        self.sse = SseServerTransport("/messages")
        self._setup_tools()
        
        # Internal FastAPI app for MCP
        self.app = FastAPI(title="NetVault MCP Server")
        self._setup_routes()
        
        logger.info("MCP Server instance created")

    def _setup_routes(self):
        """Setup SSE routes for the MCP server."""
        
        @self.app.get("/sse")
        async def handle_sse(request: Request):
            async with self.sse.connect_sse(request.scope, request.receive, request.send) as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="netvault-mcp",
                        server_version=self.config.app.version,
                        capabilities=self.server.get_capabilities(
                            notification_options=types.ServerCapabilitiesNotificationOptions(),
                            experimental_capabilities={},
                        ),
                    ),
                )

        @self.app.post("/messages")
        async def handle_messages(request: Request):
            await self.sse.handle_post_message(request.scope, request.receive, request.send)

    def _setup_tools(self):
        """Register all tools with the MCP server."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name="list_devices",
                    description="List all monitored devices with their basic status.",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                ),
                types.Tool(
                    name="get_device_details",
                    description="Get full details for a specific device by name or IP.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_name_or_ip": {"type": "string", "description": "The name or IP address of the device."}
                        },
                        "required": ["device_name_or_ip"]
                    }
                ),
                # ... (Other tools omitted for brevity in thought, but included in full below)
                types.Tool(
                    name="get_device_interfaces",
                    description="Retrieve the interface table for a specific device.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_name_or_ip": {"type": "string", "description": "The name or IP address of the device."}
                        },
                        "required": ["device_name_or_ip"]
                    }
                ),
                types.Tool(
                    name="get_arp_table",
                    description="Retrieve the ARP table for a specific device.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_name_or_ip": {"type": "string", "description": "The name or IP address of the device."}
                        },
                        "required": ["device_name_or_ip"]
                    }
                ),
                types.Tool(
                    name="get_mac_table",
                    description="Retrieve the MAC address table for a specific device.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_name_or_ip": {"type": "string", "description": "The name or IP address of the device."}
                        },
                        "required": ["device_name_or_ip"]
                    }
                ),
                types.Tool(
                    name="run_audit",
                    description="Trigger a security audit for a device and return the result.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_name_or_ip": {"type": "string", "description": "The name or IP address of the device."}
                        },
                        "required": ["device_name_or_ip"]
                    }
                ),
                types.Tool(
                    name="get_audit_history",
                    description="Retrieve past audit results for a device.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_name_or_ip": {"type": "string", "description": "The name or IP address of the device."},
                            "days": {"type": "integer", "description": "Number of days of history to retrieve.", "default": 7}
                        },
                        "required": ["device_name_or_ip"]
                    }
                ),
                types.Tool(
                    name="get_network_topology",
                    description="Retrieve the discovered network topology map.",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                ),
                types.Tool(
                    name="get_alerts",
                    description="Retrieve current alerts filtered by severity and status.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string", "description": "Filter by severity (critical, warning, info)."},
                            "acknowledged": {"type": "boolean", "description": "Filter by acknowledgment status.", "default": False}
                        },
                        "required": []
                    }
                ),
                types.Tool(
                    name="search_device_by_mac",
                    description="Find which device and port has a specific MAC address.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "mac_address": {"type": "string", "description": "The MAC address to search for (e.g., 00:11:22:33:44:55)."}
                        },
                        "required": ["mac_address"]
                    }
                ),
                types.Tool(
                    name="search_device_by_ip",
                    description="Find device information by its IP address.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ip_address": {"type": "string", "description": "The IP address to search for."}
                        },
                        "required": ["ip_address"]
                    }
                ),
                types.Tool(
                    name="get_ad_users",
                    description="Retrieve list of AD users from connected agents.",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                ),
                types.Tool(
                    name="get_ad_groups",
                    description="Retrieve list of AD groups from connected agents.",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                ),
                types.Tool(
                    name="get_ad_gpo_status",
                    description="Retrieve GPO health check status.",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
            """Handle tool execution requests."""
            logger.info(f"MCP Tool Call: {name} (args: {arguments})")
            
            try:
                if name == "list_devices":
                    res = await self.provider.list_devices()
                elif name == "get_device_details":
                    res = await self.provider.get_device_details(arguments["device_name_or_ip"])
                elif name == "get_device_interfaces":
                    res = await self.provider.get_device_interfaces(arguments["device_name_or_ip"])
                elif name == "get_arp_table":
                    res = await self.provider.get_arp_table(arguments["device_name_or_ip"])
                elif name == "get_mac_table":
                    res = await self.provider.get_mac_table(arguments["device_name_or_ip"])
                elif name == "run_audit":
                    res = await self.provider.run_audit(arguments["device_name_or_ip"])
                elif name == "get_audit_history":
                    res = await self.provider.get_audit_history(
                        arguments["device_name_or_ip"], 
                        arguments.get("days", 7)
                    )
                elif name == "get_network_topology":
                    res = await self.provider.get_network_topology()
                elif name == "get_alerts":
                    res = await self.provider.get_alerts(
                        arguments.get("severity"),
                        arguments.get("acknowledged", False)
                    )
                elif name == "search_device_by_mac":
                    res = await self.provider.search_device_by_mac(arguments["mac_address"])
                elif name == "search_device_by_ip":
                    res = await self.provider.search_device_by_ip(arguments["ip_address"])
                elif name == "get_ad_users":
                    res = await self.provider.get_ad_users()
                elif name == "get_ad_groups":
                    res = await self.provider.get_ad_groups()
                elif name == "get_ad_gpo_status":
                    res = await self.provider.get_ad_gpo_status()
                else:
                    return [types.TextContent(type="text", text=f"Tool '{name}' not found")]

                import json
                return [types.TextContent(type="text", text=json.dumps(res, indent=2, default=str))]

            except Exception as e:
                logger.error(f"Error executing MCP tool {name}: {e}")
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    async def run(self):
        """Run the MCP server using uvicorn."""
        config = uvicorn.Config(
            self.app, 
            host="0.0.0.0", 
            port=self.config.mcp.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        logger.info(f"MCP Server starting on port {self.config.mcp.port}")
        await server.serve()

async def start_mcp_server(db, device_manager, audit_engine):
    """Entry point for starting the server."""
    server = NetVaultMCPServer(db, device_manager, audit_engine)
    asyncio.create_task(server.run())
    return server
