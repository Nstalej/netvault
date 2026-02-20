"""
NetVault - REST API Connector
Implements the REST API connector supporting Sophos XG/XGS and generic HTTP devices.
"""

import time
import asyncio
import httpx
from typing import Dict, List, Any, Optional, Type
from datetime import datetime

from connectors.base import (
    BaseConnector, ConnectionTestResult, InterfaceInfo, 
    ArpEntry, MacEntry, RouteEntry, AuditResult, AuditCheck,
    register_connector
)
from connectors.rest_api.profiles.sophos import SophosProfile
from connectors.rest_api.profiles.generic_http import GenericHTTPProfile
from core.engine.logger import get_logger

log = get_logger(__name__)

@register_connector("rest_api")
class RESTConnector(BaseConnector):
    """
    Connector for interacting with devices via REST API.
    Supports Sophos XG/XGS and Generic JSON-based HTTP profiles.
    """

    def __init__(self, device_id: str, device_ip: str, credentials: Dict[str, Any]):
        super().__init__(device_id, device_ip, credentials)
        self.profile_type = credentials.get("rest_profile", "generic")
        self.port = credentials.get("port")
        self.protocol = credentials.get("protocol", "https")
        self.verify_ssl = credentials.get("verify_ssl", False)
        self.timeout = credentials.get("timeout", 15)
        self.max_retries = credentials.get("max_retries", 3)
        
        # Auth Config
        self.auth_type = credentials.get("auth_type", "basic") # basic, bearer, api_key
        self.api_key = credentials.get("api_key")
        self.api_key_location = credentials.get("api_key_location", "header") # header, query
        self.api_key_name = credentials.get("api_key_name", "X-API-Key")
        
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = f"{self.protocol}://{self.device_ip}"
        
        if self.port:
            self.base_url += f":{self.port}"
        elif self.profile_type == "sophos":
            self.base_url += f":4444"

        # Initialize profile
        if self.profile_type == "sophos":
            self.profile = SophosProfile()
        else:
            self.profile = GenericHTTPProfile(credentials.get("endpoints", {}))

    async def _get_auth_params(self) -> Dict[str, Any]:
        """Prepare authentication headers or query parameters."""
        headers = {}
        params = {}
        
        if self.auth_type == "basic":
            user = self.credentials.get("username", "")
            pwd = self.credentials.get("password", "")
            # httpx handles basic auth natively
            return {"auth": (user, pwd)}
        elif self.auth_type == "bearer":
            token = self.credentials.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif self.auth_type == "api_key":
            if self.api_key_location == "header":
                headers[self.api_key_name] = self.api_key
            else:
                params[self.api_key_name] = self.api_key
                
        return {"headers": headers, "params": params}

    async def connect(self) -> bool:
        """Initialize the HTTP client."""
        if not self.client:
            self.client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=self.timeout,
                follow_redirects=True
            )
        self._is_connected = True
        return True

    async def disconnect(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
        self._is_connected = False

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Internal helper for making requests with retry logic."""
        if not self.client:
            await self.connect()
            
        auth_params = await self._get_auth_params()
        
        # Merge kwargs
        if "headers" in kwargs:
            kwargs["headers"].update(auth_params.get("headers", {}))
        else:
            kwargs["headers"] = auth_params.get("headers", {})
            
        if "params" in kwargs:
            kwargs["params"].update(auth_params.get("params", {}))
        else:
            kwargs["params"] = auth_params.get("params", {})
            
        if "auth" not in kwargs and "auth" in auth_params:
            kwargs["auth"] = auth_params["auth"]

        url = f"{self.base_url}{path}"
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [429, 503] and attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    log.warning(f"Transient error {e.response.status_code} for {url}. Retrying in {wait_time}s...", extra={"device": self.device_id})
                    await asyncio.sleep(wait_time)
                    continue
                raise
            except (httpx.RequestError, asyncio.TimeoutError) as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    log.warning(f"Request error {str(e)} for {url}. Retrying in {wait_time}s...", extra={"device": self.device_id})
                    await asyncio.sleep(wait_time)
                    continue
                raise
        
        # Should not reach here if raise_for_status or re-raising works correctly
        raise httpx.RequestError("Max retries exceeded")

    async def test_connection(self) -> ConnectionTestResult:
        """Test reachability and authentication."""
        start_time = time.time()
        try:
            await self.connect()
            if self.profile_type == "sophos":
                # Sophos test: Get system info
                login_xml = self.profile.get_login_xml(
                    self.credentials.get("username", ""),
                    self.credentials.get("password", "")
                )
                req_xml = self.profile.wrap_request(login_xml, "get", "SystemStatus")
                await self._request("POST", self.profile.API_PATH, content=req_xml)
            else:
                # Generic test: Request the 'system' endpoint or root
                path = self.profile.get_endpoint("system") or "/"
                await self._request("GET", path)
            
            latency = (time.time() - start_time) * 1000
            return ConnectionTestResult(success=True, latency_ms=latency)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            log.error(f"Connection test failed for {self.device_id}: {str(e)}")
            return ConnectionTestResult(success=False, latency_ms=latency, error_message=str(e))

    async def get_system_info(self) -> Dict[str, Any]:
        """Retrieve general system information."""
        try:
            if self.profile_type == "sophos":
                login_xml = self.profile.get_login_xml(
                    self.credentials.get("username", ""),
                    self.credentials.get("password", "")
                )
                req_xml = self.profile.wrap_request(login_xml, "get", "SystemStatus")
                resp = await self._request("POST", self.profile.API_PATH, content=req_xml)
                self._device_info = self.profile.parse_system_info(resp.content)
            else:
                path = self.profile.get_endpoint("system")
                if path:
                    resp = await self._request("GET", path)
                    self._device_info = self.profile.parse_system_info(resp.json())
                else:
                    self._device_info = {"model": "Generic HTTP", "os": "Unknown"}
            return self._device_info
        except Exception as e:
            log.error(f"Failed to get system info for {self.device_id}: {str(e)}")
            return {}

    async def get_interfaces(self) -> List[InterfaceInfo]:
        """Retrieve list of all network interfaces."""
        try:
            if self.profile_type == "sophos":
                login_xml = self.profile.get_login_xml(
                    self.credentials.get("username", ""),
                    self.credentials.get("password", "")
                )
                req_xml = self.profile.wrap_request(login_xml, "get", "Interface")
                resp = await self._request("POST", self.profile.API_PATH, content=req_xml)
                return self.profile.parse_interfaces(resp.content)
            else:
                path = self.profile.get_endpoint("interfaces")
                if path:
                    resp = await self._request("GET", path)
                    return self.profile.parse_interfaces(resp.json())
                return []
        except Exception as e:
            log.error(f"Failed to get interfaces for {self.device_id}: {str(e)}")
            return []

    async def get_arp_table(self) -> List[ArpEntry]:
        """Retrieve the device's ARP table."""
        try:
            if self.profile_type == "sophos":
                login_xml = self.profile.get_login_xml(
                    self.credentials.get("username", ""),
                    self.credentials.get("password", "")
                )
                req_xml = self.profile.wrap_request(login_xml, "get", "ARPTable")
                resp = await self._request("POST", self.profile.API_PATH, content=req_xml)
                return self.profile.parse_arp_table(resp.content)
            else:
                path = self.profile.get_endpoint("arp")
                if path:
                    resp = await self._request("GET", path)
                    return self.profile.parse_arp_table(resp.json())
                return []
        except Exception as e:
            log.error(f"Failed to get ARP table for {self.device_id}: {str(e)}")
            return []

    async def get_mac_table(self) -> List[MacEntry]:
        """Retrieve the device's MAC address table (Not natively supported by many REST APIs)."""
        # Many firewalls/routers don't expose MAC table via simple REST API without deep filtering
        return []

    async def get_routes(self) -> List[RouteEntry]:
        """Retrieve the device's routing table."""
        try:
            if self.profile_type == "sophos":
                login_xml = self.profile.get_login_xml(
                    self.credentials.get("username", ""),
                    self.credentials.get("password", "")
                )
                req_xml = self.profile.wrap_request(login_xml, "get", "RoutingTable")
                resp = await self._request("POST", self.profile.API_PATH, content=req_xml)
                return self.profile.parse_routes(resp.content)
            else:
                # Generic HTTP doesn't have a default route endpoint unless specified
                path = self.profile.get_endpoint("routes")
                if path:
                    resp = await self._request("GET", path)
                    # Use a basic route parser or let profile handle it
                    return [] # Generic route parsing not implemented yet
                return []
        except Exception as e:
            log.error(f"Failed to get routes for {self.device_id}: {str(e)}")
            return []

    async def run_audit(self) -> AuditResult:
        """Perform a security audit."""
        result = AuditResult(device_name=self.device_id)
        
        # Basic check: Connection
        conn_test = await self.test_connection()
        result.checks.append(AuditCheck(
            name="RestAPI Connectivity",
            status="pass" if conn_test.success else "fail",
            message="Successfully reached API" if conn_test.success else f"Error: {conn_test.error_message}"
        ))
        
        # Check: SSL Verification
        result.checks.append(AuditCheck(
            name="SSL Verification",
            status="pass" if self.verify_ssl else "warning",
            message="SSL verification enabled" if self.verify_ssl else "SSL verification disabled (Insecure)"
        ))
        
        result.summary = f"Audit completed with {len([c for c in result.checks if c.status == 'pass'])}/{len(result.checks)} checks passed."
        return result
