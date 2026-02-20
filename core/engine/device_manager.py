"""
NetVault - Device Manager Engine
Main engine for managing network devices, credentials, and polling operations.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from core.database.db import DatabaseManager
from core.database import crud
from core.engine.credential_vault import CredentialVault
from core.engine.logger import get_logger
from connectors.base import get_connector, ConnectionTestResult

logger = get_logger("netvault.engine.device_manager")

class DeviceManager:
    """
    Singleton engine that coordinates between API, Database, and Connectors.
    Handles device loading, connector instantiation, and parallel polling.
    """
    _instance: Optional['DeviceManager'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DeviceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db: DatabaseManager, vault: CredentialVault):
        # Ensure __init__ only runs once if singleton
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.db = db
        self.vault = vault
        self._devices: Dict[int, Dict[str, Any]] = {}  # Cache of DB device configs
        self._connectors: Dict[int, Any] = {}          # Cache of connector instances
        self._cache: Dict[int, Dict[str, Any]] = {}    # Cache of latest poll data
        self._semaphore = asyncio.Semaphore(5)         # Default max concurrent polls
        self._initialized = True
        logger.info("Device Manager initialized")

    @classmethod
    def get_instance(cls) -> 'DeviceManager':
        """Access the singleton instance of the Device Manager."""
        if cls._instance is None:
            raise RuntimeError("DeviceManager not initialized. Call __init__ first.")
        return cls._instance

    async def load_devices(self):
        """Load all devices from the database into memory."""
        try:
            devices = await crud.list_devices(self.db)
            self._devices = {d['id']: d for d in devices}
            logger.info(f"Loaded {len(self._devices)} devices from database")
        except Exception as e:
            logger.error(f"Failed to load devices from DB: {e}")

    async def get_connector(self, device_id: int) -> Optional[Any]:
        """Create or return a cached connector for a device."""
        if device_id in self._connectors:
            return self._connectors[device_id]

        device_cfg = self._devices.get(device_id)
        if not device_cfg:
            # Try reloading if not found in cache
            await self.load_devices()
            device_cfg = self._devices.get(device_id)
        
        if not device_cfg:
            logger.warning(f"Device ID {device_id} not found")
            return None

        connector_type = device_cfg.get("connector_type")
        connector_cls = get_connector(connector_type)
        
        if not connector_cls:
            logger.error(f"Connector type '{connector_type}' not registered")
            return None

        # Get credentials from vault
        # In current models, devices have a credential_id or we look up by name
        # The prompt says: "Retrieves decrypted credentials from CredentialVault for each device"
        # Let's check how credentials are stored. Based on core/engine/device_manager.py (old):
        # it used cred_id. Based on crud.py, we have get_credential(db, cred_id).
        # Based on credential_vault.py, it uses name.
        
        # We'll try to find the credential name from the device config or name
        cred_name = device_cfg.get("config_json", {}).get("credential_name")
        if not cred_name:
             # Fallback: check if there's a credential_id in the device record
             cred_id = device_cfg.get("credential_id")
             if cred_id:
                 cred_record = await crud.get_credential(self.db, cred_id)
                 if cred_record:
                     cred_name = cred_record.get("name")

        if not cred_name:
            logger.warning(f"No credential associated with device {device_cfg.get('name')}")
            # Some connectors might not need credentials, but usually they do
            credentials = {}
        else:
            credentials = await self.vault.get_credential(cred_name)
            if not credentials:
                logger.error(f"Credential '{cred_name}' not found in vault")
                return None

        try:
            # Instantiate connector
            connector = connector_cls(
                device_id=str(device_id),
                device_ip=device_cfg.get("ip") or device_cfg.get("ip_address"),
                credentials=credentials
            )
            self._connectors[device_id] = connector
            return connector
        except Exception as e:
            logger.error(f"Failed to instantiate connector for device {device_id}: {e}")
            return None

    async def poll_device(self, device_id: int):
        """Connect, collect system_info + interfaces, and update DB status."""
        async with self._semaphore:
            device_cfg = self._devices.get(device_id)
            if not device_cfg:
                logger.warning(f"Cannot poll unknown device {device_id}")
                return

            name = device_cfg.get("name")
            ip = device_cfg.get("ip") or device_cfg.get("ip_address")
            start_time = time.time()
            
            logger.info(f"Polling device {name} ({ip})...")
            
            connector = await self.get_connector(device_id)
            if not connector:
                await self._update_device_status(device_id, "offline")
                return

            try:
                # 1. Test connection/Connect
                connected = await connector.connect()
                if not connected:
                    logger.warning(f"Failed to connect to {name} ({ip})")
                    await self._update_device_status(device_id, "offline")
                    return

                # 2. Collect basic data
                system_info = await connector.get_system_info()
                interfaces = await connector.get_interfaces()
                
                # Convert dataclasses to dicts if necessary (assuming they are serializable or handled by JSON)
                # For simplified cache, we store raw results
                poll_data = {
                    "system_info": system_info,
                    "interfaces": [vars(i) if hasattr(i, '__dict__') else i for i in interfaces],
                    "last_poll": datetime.now(timezone.utc).isoformat()
                }
                
                self._cache[device_id] = poll_data
                
                # 3. Update Status
                status = "online"
                if not interfaces:
                    status = "warning" # Connected but failed to get interfaces
                
                await self._update_device_status(device_id, status)
                
                duration = time.time() - start_time
                logger.info(f"Poll completed for {name} in {duration:.2f}s - {status}")

            except Exception as e:
                logger.exception(f"Unexpected error polling {name} ({ip}): {e}")
                await self._update_device_status(device_id, "offline")
            finally:
                if connector.is_connected:
                    await connector.disconnect()

    async def poll_all(self, max_concurrent: int = 5):
        """Poll all devices in parallel with semaphore control."""
        # Update semaphore if requested
        if max_concurrent != self._semaphore._value:
            self._semaphore = asyncio.Semaphore(max_concurrent)
            
        await self.load_devices()
        tasks = [self.poll_device(device_id) for device_id in self._devices.keys()]
        if tasks:
            logger.info(f"Starting parallel poll of {len(tasks)} devices (max_concurrent={max_concurrent})")
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("All poll operations completed")

    async def test_device(self, device_id: int) -> ConnectionTestResult:
        """Run test_connection() and return result."""
        connector = await self.get_connector(device_id)
        if not connector:
            return ConnectionTestResult(success=False, latency_ms=0, error_message="Could not initialize connector")
        
        try:
            result = await connector.test_connection()
            return result
        except Exception as e:
            return ConnectionTestResult(success=False, latency_ms=0, error_message=str(e))

    async def get_device_status(self, device_id: int) -> str:
        """Return cached status without polling."""
        device = self._devices.get(device_id)
        if not device:
            # Fallback to DB
            device = await crud.get_device(self.db, device_id)
            if device:
                self._devices[device_id] = device
            else:
                return "unknown"
        return device.get("status", "unknown")

    async def get_device_data(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Return cached data (system_info, interfaces, etc.)."""
        return self._cache.get(device_id)

    async def refresh_device_data(self, device_id: int):
        """Force full data collection (ARP, MAC, routes too)."""
        async with self._semaphore:
            connector = await self.get_connector(device_id)
            if not connector:
                return

            try:
                if not await connector.connect():
                    return

                # Collect EVERYTHING
                system_info = await connector.get_system_info()
                interfaces = await connector.get_interfaces()
                arp_table = await connector.get_arp_table()
                mac_table = await connector.get_mac_table()
                routes = await connector.get_routes()
                
                data = {
                    "system_info": system_info,
                    "interfaces": [vars(i) if hasattr(i, '__dict__') else i for i in interfaces],
                    "arp_table": [vars(a) if hasattr(a, '__dict__') else a for a in arp_table],
                    "mac_table": [vars(m) if hasattr(m, '__dict__') else m for m in mac_table],
                    "routes": [vars(r) if hasattr(r, '__dict__') else r for r in routes],
                    "last_refresh": datetime.now(timezone.utc).isoformat()
                }
                
                self._cache[device_id] = data
                await self._update_device_status(device_id, "online")
                logger.info(f"Full data refresh completed for device {device_id}")

            except Exception as e:
                logger.error(f"Error refreshing data for device {device_id}: {e}")
            finally:
                if connector.is_connected:
                    await connector.disconnect()

    async def _update_device_status(self, device_id: int, status: str):
        """Update device status in cache and database."""
        now = datetime.now()
        
        # Update cache
        if device_id in self._devices:
            self._devices[device_id]["status"] = status
            self._devices[device_id]["last_seen"] = now
            
        # Update DB
        try:
            update_data = {"status": status, "last_seen": now}
            await crud.update_device(self.db, device_id, update_data)
        except Exception as e:
            logger.error(f"Failed to update device {device_id} status in DB: {e}")

_DEVICE_MANAGER_INSTANCE: Optional[DeviceManager] = None

def get_device_manager(db: Optional[DatabaseManager] = None, vault: Optional[CredentialVault] = None) -> DeviceManager:
    """Access the singleton instance of the Device Manager."""
    global _DEVICE_MANAGER_INSTANCE
    if _DEVICE_MANAGER_INSTANCE is None:
        if db is None or vault is None:
            raise ValueError("DatabaseManager and CredentialVault required for first initialization")
        _DEVICE_MANAGER_INSTANCE = DeviceManager(db, vault)
    return _DEVICE_MANAGER_INSTANCE
