"""
NetVault - Network Discovery Engine
Async subnet scanning with background jobs and result polling.
"""

import asyncio
import ipaddress
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from core.database.db import DatabaseManager
from core.engine.logger import get_logger

logger = get_logger("netvault.engine.network_discovery")


class NetworkDiscoveryEngine:
    """Run network discovery jobs in background and expose status/results."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._job_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._max_jobs = 20

    async def start_discovery(self, subnets: List[str], methods: List[str]) -> str:
        validated_subnets = self._validate_subnets(subnets)
        normalized_methods = self._normalize_methods(methods)
        job_id = str(uuid.uuid4())

        job = {
            "job_id": job_id,
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "subnets": [str(net) for net in validated_subnets],
            "methods": normalized_methods,
            "results": [],
            "progress": {
                "total_hosts": sum(max(net.num_addresses - 2, 0) for net in validated_subnets),
                "scanned_hosts": 0,
                "responding_hosts": 0,
            },
            "error": None,
        }

        async with self._lock:
            self._jobs[job_id] = job
            self._prune_jobs_locked()

        logger.info("Starting network discovery job=%s subnets=%s methods=%s", job_id, job["subnets"], normalized_methods)
        task = asyncio.create_task(self._run_discovery(job_id, validated_subnets, normalized_methods))
        self._job_tasks[job_id] = task
        return job_id

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return dict(job)

    def _validate_subnets(self, subnets: List[str]) -> List[ipaddress.IPv4Network]:
        if not subnets:
            raise ValueError("At least one subnet is required")

        validated: List[ipaddress.IPv4Network] = []
        for raw in subnets:
            network = ipaddress.ip_network(raw, strict=False)
            if not isinstance(network, ipaddress.IPv4Network):
                raise ValueError(f"Only IPv4 subnet is supported: {raw}")
            validated.append(network)
        return validated

    @staticmethod
    def _normalize_methods(methods: List[str]) -> List[str]:
        allowed = {"ping", "ssh", "snmp"}
        normalized = []
        for method in methods:
            lower = str(method).strip().lower()
            if lower in allowed and lower not in normalized:
                normalized.append(lower)
        if not normalized:
            normalized = ["ping", "ssh", "snmp"]
        return normalized

    async def _run_discovery(self, job_id: str, subnets: List[ipaddress.IPv4Network], methods: List[str]):
        try:
            registered_ips = await self._load_registered_ips()

            targets: List[str] = []
            for net in subnets:
                for host in net.hosts():
                    targets.append(str(host))

            sem = asyncio.Semaphore(128)
            results: List[Dict[str, Any]] = []

            async def _scan(ip: str):
                async with sem:
                    result = await self._scan_host(ip, methods, registered_ips)
                    await self._increment_progress(job_id, scanned=1, responding=1 if result else 0)
                    if result:
                        results.append(result)

            await asyncio.gather(*[_scan(ip) for ip in targets], return_exceptions=False)

            async with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["status"] = "completed"
                    self._jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self._jobs[job_id]["results"] = sorted(results, key=lambda item: item["ip"])

            logger.info("Network discovery completed job=%s hosts=%s discovered=%s", job_id, len(targets), len(results))
        except Exception as exc:
            logger.error("Network discovery failed job=%s error=%s", job_id, exc, exc_info=True)
            async with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["status"] = "failed"
                    self._jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self._jobs[job_id]["error"] = str(exc)

    async def _increment_progress(self, job_id: str, scanned: int = 0, responding: int = 0):
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["progress"]["scanned_hosts"] += scanned
            job["progress"]["responding_hosts"] += responding

    async def _load_registered_ips(self) -> Set[str]:
        rows = await self.db.fetch_all("SELECT ip, ip_address FROM devices")
        ips: Set[str] = set()
        for row in rows:
            if row.get("ip"):
                ips.add(str(row["ip"]))
            if row.get("ip_address"):
                ips.add(str(row["ip_address"]))
        return ips

    async def _scan_host(self, ip: str, methods: List[str], registered_ips: Set[str]) -> Optional[Dict[str, Any]]:
        open_ports: Set[int] = set()
        device_type = "unknown"
        banner = ""

        # ping-like sweep using common TCP ports
        is_reachable = False
        if "ping" in methods:
            ping_ports = await self._probe_tcp_ports(ip, [22, 80, 443], timeout=0.4)
            if ping_ports:
                open_ports.update(ping_ports)
                is_reachable = True

        if "ssh" in methods:
            ssh_open = await self._is_tcp_port_open(ip, 22, timeout=0.6)
            if ssh_open:
                open_ports.add(22)
                is_reachable = True
                banner = await self._read_ssh_banner(ip)
                lower = banner.lower()
                if "mikrotik" in lower:
                    device_type = "mikrotik"
                elif "ruckus" in lower or "rkscli" in lower:
                    device_type = "AP"

        if "snmp" in methods:
            # heuristic TCP port probe for discovery speed/simplicity
            if await self._is_tcp_port_open(ip, 161, timeout=0.6):
                open_ports.add(161)
                is_reachable = True

        if not is_reachable:
            return None

        hostname = await self._reverse_lookup(ip)
        return {
            "ip": ip,
            "open_ports": sorted(open_ports),
            "type": device_type,
            "hostname": hostname,
            "already_registered": ip in registered_ips,
            "banner": banner[:120] if banner else "",
        }

    @staticmethod
    async def _is_tcp_port_open(ip: str, port: int, timeout: float = 0.5) -> bool:
        try:
            fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _probe_tcp_ports(self, ip: str, ports: List[int], timeout: float = 0.5) -> List[int]:
        async def _probe(port: int):
            return port if await self._is_tcp_port_open(ip, port, timeout) else None

        results = await asyncio.gather(*[_probe(p) for p in ports], return_exceptions=False)
        return [port for port in results if port is not None]

    async def _read_ssh_banner(self, ip: str) -> str:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 22), timeout=0.8)
            data = await asyncio.wait_for(reader.read(256), timeout=0.8)
            writer.close()
            await writer.wait_closed()
            return data.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    async def _reverse_lookup(self, ip: str) -> str:
        def _resolve() -> str:
            try:
                return socket.gethostbyaddr(ip)[0]
            except Exception:
                return ""

        return await asyncio.to_thread(_resolve)

    def _prune_jobs_locked(self):
        if len(self._jobs) <= self._max_jobs:
            return

        ordered = sorted(self._jobs.values(), key=lambda item: item.get("created_at") or "")
        to_remove = max(0, len(self._jobs) - self._max_jobs)

        for idx in range(to_remove):
            job_id = ordered[idx].get("job_id")
            if job_id:
                self._jobs.pop(job_id, None)
                task = self._job_tasks.pop(job_id, None)
                if task and not task.done():
                    task.cancel()
