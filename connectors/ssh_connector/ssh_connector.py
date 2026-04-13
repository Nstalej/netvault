"""
NetVault - SSH Network Connector
Implementation of SSH-based network device interaction using Paramiko.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import paramiko
from paramiko.ssh_exception import AuthenticationException

from connectors.base import (
    ArpEntry,
    AuditResult,
    BaseConnector,
    ConnectionTestResult,
    InterfaceInfo,
    MacEntry,
    RouteEntry,
    register_connector,
)
from connectors.ssh_connector.parsers import cisco_parser, mikrotik_parser
from core.engine.logger import get_logger

logger = get_logger(__name__)


@register_connector("ssh")
class SSHConnector(BaseConnector):
    """
    SSH Connector for network devices.
    Supports MikroTik (RouterOS) and Cisco (IOS).
    """

    def __init__(self, device_id: str, device_ip: str, credentials: Dict[str, Any]):
        super().__init__(device_id, device_ip, credentials)
        self.port = credentials.get("port", 22)
        self.username = credentials.get("username")
        self.password = credentials.get("password")
        self.key_filename = credentials.get("key_filename")
        self.device_type = credentials.get("device_type", "auto")  # auto, mikrotik, cisco
        self.ssh_mode = str(credentials.get("ssh_mode", "exec")).strip().lower()
        if self.ssh_mode not in {"exec", "interactive"}:
            self.ssh_mode = "exec"
        self.shell_prompt = credentials.get("shell_prompt", "#")
        self.interactive_test_command = credentials.get("interactive_test_command", "get version")
        self.interactive_retries = int(credentials.get("interactive_retries", 2))
        self.known_hosts_file = credentials.get("known_hosts_file")
        self.allow_unknown_host_keys = bool(credentials.get("allow_unknown_host_keys", False))
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.timeout = credentials.get("timeout", 10)
        self._last_error: Optional[str] = None

    def _configure_host_keys(self, client: paramiko.SSHClient):
        """Configure host key verification policy for SSH clients."""
        client.load_system_host_keys()
        if self.known_hosts_file:
            try:
                client.load_host_keys(self.known_hosts_file)
            except Exception as exc:
                logger.warning(
                    "Could not load known_hosts file '%s': %s",
                    self.known_hosts_file,
                    exc,
                    extra={"device_id": self.device_id},
                )

        if self.allow_unknown_host_keys:
            logger.warning(
                "allow_unknown_host_keys is enabled for %s; unknown host keys will be accepted",
                self.device_ip,
                extra={"device_id": self.device_id},
            )
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            return

        client.set_missing_host_key_policy(paramiko.RejectPolicy())

    @staticmethod
    def _is_auth_exception(exc: Exception) -> bool:
        if isinstance(exc, AuthenticationException):
            return True
        text = str(exc).lower()
        auth_markers = [
            "authentication",
            "permission denied",
            "auth failed",
            "invalid password",
            "password",
            "access denied",
        ]
        return any(marker in text for marker in auth_markers)

    def _build_connect_kwargs(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        connect_kwargs: Dict[str, Any] = {
            "hostname": host or self.device_ip,
            "port": port if port is not None else self.port,
            "username": username or self.username,
            "timeout": timeout if timeout is not None else self.timeout,
            "look_for_keys": True,
            "allow_agent": True,
        }

        if password if password is not None else self.password:
            connect_kwargs["password"] = password if password is not None else self.password
        if self.key_filename:
            connect_kwargs["key_filename"] = self.key_filename

        return connect_kwargs

    def _read_until(
        self,
        channel: paramiko.Channel,
        patterns: List[str],
        timeout: float,
        read_chunk: int = 4096,
    ) -> str:
        end_time = time.time() + timeout
        buffer = ""
        lowered_patterns = [p.lower() for p in patterns]

        while time.time() < end_time:
            if channel.recv_ready():
                data = channel.recv(read_chunk)
                if not data:
                    break
                chunk = data.decode("utf-8", errors="ignore")
                buffer += chunk

                lowered_buffer = buffer.lower()
                if any(pattern in lowered_buffer for pattern in lowered_patterns):
                    return buffer
            else:
                time.sleep(0.1)

        raise TimeoutError(f"Timed out waiting for prompts: {patterns}")

    @staticmethod
    def _clean_interactive_output(raw_output: str, command: str, shell_prompt: str) -> str:
        lines = [line.rstrip("\r") for line in raw_output.split("\n")]
        cleaned: List[str] = []

        prompt_lower = shell_prompt.lower()
        command_lower = command.strip().lower()

        for line in lines:
            stripped = line.strip()
            lowered = stripped.lower()

            if not stripped:
                continue
            if lowered == command_lower:
                continue
            if prompt_lower and prompt_lower in lowered:
                continue
            if lowered.startswith("login:") or lowered.startswith("please login:"):
                continue
            if lowered.startswith("password"):
                continue

            cleaned.append(stripped)

        return "\n".join(cleaned).strip()

    def _interactive_login(
        self,
        channel: paramiko.Channel,
        username: str,
        password: str,
        shell_prompt: str,
        timeout: float,
    ):
        initial = self._read_until(
            channel,
            ["login:", "please login:", "username:", "password", shell_prompt],
            timeout,
        )
        lowered = initial.lower()

        if "login:" in lowered or "please login:" in lowered or "username:" in lowered:
            channel.send(f"{username}\n".encode("utf-8"))
            after_user = self._read_until(channel, ["password", shell_prompt], timeout)
            lowered = after_user.lower()

        if "password" in lowered and shell_prompt.lower() not in lowered:
            channel.send(f"{password}\n".encode("utf-8"))
            self._read_until(channel, [shell_prompt], timeout)

    def _open_interactive_shell(self):
        if not self.client:
            raise ConnectionError("SSH client not initialized")

        self.shell = self.client.invoke_shell()
        self.shell.settimeout(self.timeout)

        username = self.username or ""
        password = self.password or ""
        if not username and not password:
            raise PermissionError("Interactive mode requires username/password")

        self._interactive_login(self.shell, username, password, self.shell_prompt, float(self.timeout))

    def _execute_interactive_command_sync(self, command: str) -> str:
        if not self.shell:
            raise ConnectionError("Interactive shell not initialized")

        self.shell.send(f"{command}\n".encode("utf-8"))
        raw = self._read_until(self.shell, [self.shell_prompt, "\nOK\n", "\r\nOK\r\n"], float(self.timeout))
        cleaned = self._clean_interactive_output(raw, command, self.shell_prompt)
        if cleaned:
            return cleaned
        if "ok" in raw.lower():
            return "OK"
        return raw.strip()

    def _connect_interactive(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        shell_prompt: str,
        command: str,
        timeout: float,
    ) -> str:
        """
        Open an interactive shell session, execute a command, and return cleaned output.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, max(1, self.interactive_retries) + 1):
            client: Optional[paramiko.SSHClient] = None
            try:
                client = paramiko.SSHClient()
                self._configure_host_keys(client)

                connect_kwargs = self._build_connect_kwargs(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    timeout=timeout,
                )
                client.connect(**connect_kwargs)

                shell = client.invoke_shell()
                shell.settimeout(timeout)

                self._interactive_login(shell, username, password, shell_prompt, timeout)

                shell.send(f"{command}\n".encode("utf-8"))
                raw = self._read_until(shell, [shell_prompt, "\nOK\n", "\r\nOK\r\n"], timeout)
                cleaned = self._clean_interactive_output(raw, command, shell_prompt)
                if cleaned:
                    return cleaned
                if "ok" in raw.lower():
                    return "OK"
                return raw.strip()

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Interactive SSH attempt %s/%s failed for %s: %s",
                    attempt,
                    max(1, self.interactive_retries),
                    host,
                    exc,
                    extra={"device_id": self.device_id},
                )
                if attempt < max(1, self.interactive_retries):
                    time.sleep(0.3)
            finally:
                if client:
                    client.close()

        if last_exc:
            raise last_exc
        raise ConnectionError("Interactive SSH failed with unknown error")

    async def connect(self) -> bool:
        """Establish SSH connection and detect device type."""
        try:
            self.client = paramiko.SSHClient()
            self._configure_host_keys(self.client)

            connect_kwargs = self._build_connect_kwargs()
            client = self.client
            if client is None:
                raise ConnectionError("SSH client not initialized")

            # Executing blocking paramiko call in a thread pool to keep it async-friendly
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: client.connect(**connect_kwargs))

            if self.ssh_mode == "interactive":
                await loop.run_in_executor(None, self._open_interactive_shell)

            self._is_connected = True
            self._last_error = None

            # Detect device type if set to auto
            if self.device_type == "auto":
                await self._detect_device_type()

            logger.info(
                "Connected to %s (%s) via SSH [%s mode]",
                self.device_ip,
                self.device_type,
                self.ssh_mode,
                extra={"device_id": self.device_id},
            )
            return True

        except Exception as e:
            logger.error("Failed to connect to %s: %s", self.device_ip, str(e), extra={"device_id": self.device_id})
            self._is_connected = False
            self._last_error = str(e)
            return False

    async def disconnect(self):
        """Close SSH connection."""
        if self.shell:
            try:
                self.shell.close()
            except Exception as exc:
                logger.warning(
                    "Error while closing interactive shell for %s: %s",
                    self.device_ip,
                    exc,
                    extra={"device_id": self.device_id},
                )
            self.shell = None
        if self.client:
            self.client.close()
            self._is_connected = False
            logger.info("Disconnected from %s", self.device_ip, extra={"device_id": self.device_id})

    async def test_connection(self) -> ConnectionTestResult:
        """Test connection and measure latency."""
        start_time = time.time()
        try:
            latency = 0.0

            if self.ssh_mode == "interactive":
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(
                    None,
                    lambda: self._connect_interactive(
                        host=self.device_ip,
                        port=self.port,
                        username=self.username or "",
                        password=self.password or "",
                        shell_prompt=self.shell_prompt,
                        command=self.interactive_test_command,
                        timeout=float(self.timeout),
                    ),
                )
                latency = (time.time() - start_time) * 1000
                if "ok" not in output.lower():
                    return ConnectionTestResult(
                        success=False,
                        latency_ms=latency,
                        error_message="Interactive command completed but did not return OK",
                    )
                return ConnectionTestResult(success=True, latency_ms=latency)

            success = await self.connect()
            latency = (time.time() - start_time) * 1000
            if success:
                return ConnectionTestResult(success=True, latency_ms=latency)

            message = self._last_error or "Authentication failed or timeout"
            if self._is_auth_exception(Exception(message)):
                message = f"Authentication failed: {message}"
            return ConnectionTestResult(success=False, latency_ms=latency, error_message=message)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            message = str(e)
            if self._is_auth_exception(e):
                message = f"Authentication failed: {message}"
            return ConnectionTestResult(success=False, latency_ms=latency, error_message=message)
        finally:
            if self.is_connected:
                await self.disconnect()

    async def _execute_command(self, command: str) -> str:
        """Execute a command on the device and return the output."""
        if not self._is_connected:
            if not await self.connect():
                raise ConnectionError("Not connected to device")

        loop = asyncio.get_event_loop()

        if self.ssh_mode == "interactive":
            return await loop.run_in_executor(None, lambda: self._execute_interactive_command_sync(command))

        client = self.client
        if client is None:
            raise ConnectionError("SSH client not initialized")

        def _exec():
            stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout)
            return stdout.read().decode("utf-8", errors="ignore")

        return await loop.run_in_executor(None, _exec)

    async def _detect_device_type(self):
        """Detect if the device is MikroTik or Cisco based on help/version output."""
        try:
            # Try a safe command that works on both or gives away the OS
            output = await self._execute_command("?")
            if "RouterOS" in output or "MikroTik" in output:
                self.device_type = "mikrotik"
            elif "Cisco" in output or "exec" in output:
                self.device_type = "cisco"
            else:
                # Try another command
                ver_output = await self._execute_command("show version")
                if "Cisco" in ver_output:
                    self.device_type = "cisco"
                else:
                    # Default/fallback
                    self.device_type = "unknown"
        except Exception:
            self.device_type = "unknown"

    async def get_system_info(self) -> Dict[str, Any]:
        """Retrieve system info based on device type."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/system resource print")
            msg = mikrotik_parser.parse_system_resource(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show version")
            msg = cisco_parser.parse_show_version(output)
        else:
            msg = {"error": "Unsupported device type"}

        self._device_info = msg
        return msg

    async def get_interfaces(self) -> List[InterfaceInfo]:
        """Retrieve interfaces."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/interface print")
            return mikrotik_parser.parse_interfaces(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show ip interface brief")
            return cisco_parser.parse_show_interfaces(output)
        return []

    async def get_arp_table(self) -> List[ArpEntry]:
        """Retrieve ARP table."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/ip arp print")
            return mikrotik_parser.parse_arp_table(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show ip arp")
            return cisco_parser.parse_show_ip_arp(output)
        return []

    async def get_mac_table(self) -> List[MacEntry]:
        """Retrieve MAC table."""
        if self.device_type == "cisco":
            output = await self._execute_command("show mac address-table")
            return cisco_parser.parse_show_mac_address_table(output)
        # MikroTik MAC table is more complex depending on bridge, skipping for basic implementation
        return []

    async def get_routes(self) -> List[RouteEntry]:
        """Retrieve routing table."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/ip route print")
            return mikrotik_parser.parse_routes(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show ip route")
            return cisco_parser.parse_show_ip_route(output)
        return []

    async def run_audit(self) -> AuditResult:
        """Perform a basic audit."""
        result = AuditResult(device_name=self.device_ip)
        # Placeholder for audit logic
        # Could check for default passwords, open ports, etc.
        return result
