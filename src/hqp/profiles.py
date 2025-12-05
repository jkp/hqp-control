"""HQPlayer profile management via SSH or local commands."""

import asyncio
import hashlib
import shutil
import socket
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Optional

import paramiko

from hqp.models import Profile


class BaseProfileManager(ABC):
    """Abstract base class for profile management."""

    def __init__(
        self,
        host: str,
        profiles_path: str = "/var/lib/hqplayer/home/cfgs",
        config_path: str = "/etc/hqplayer/hqplayerd.xml",
        xml_port: int = 4321,
        wait_timeout: float = 30.0,
        poll_interval: float = 0.5,
    ):
        self.host = host
        self.profiles_path = profiles_path
        self.config_path = config_path
        self.xml_port = xml_port
        self.wait_timeout = wait_timeout
        self.poll_interval = poll_interval

    @abstractmethod
    async def _run_command(self, command: str) -> tuple[str, str, int]:
        """Run a command and return (stdout, stderr, exit_code)."""
        pass

    @abstractmethod
    async def _copy_file(self, src: str, dst: str) -> bool:
        """Copy a file from src to dst. Returns success."""
        pass

    @abstractmethod
    async def _list_files(self, directory: str) -> list[str]:
        """List files in a directory."""
        pass

    @abstractmethod
    async def _get_file_hash(self, path: str) -> Optional[str]:
        """Get MD5 hash of a file."""
        pass

    async def _check_hqplayer_alive(self) -> bool:
        """Check if hqplayerd is responding on the XML port."""

        def _check():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((self.host, self.xml_port))
                sock.sendall(b'<?xml version="1.0" encoding="UTF-8"?><Status/>')
                response = sock.recv(4096)
                sock.close()
                return b"<Status" in response and b"state=" in response
            except (socket.error, socket.timeout, OSError):
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    async def _wait_for_hqplayer(self) -> bool:
        """Wait for hqplayerd to come back online after restart."""
        import time

        start = time.monotonic()
        while time.monotonic() - start < self.wait_timeout:
            if await self._check_hqplayer_alive():
                return True
            await asyncio.sleep(self.poll_interval)
        return False

    async def list_profiles(self) -> list[Profile]:
        """List available profiles."""
        files = await self._list_files(self.profiles_path)
        profiles = []
        for filename in files:
            if filename.endswith(".xml"):
                name = filename[:-4]
                path = f"{self.profiles_path}/{filename}"
                profiles.append(Profile(name=name, path=path))
        return profiles

    async def switch_profile(self, name: str, wait: bool = True) -> bool:
        """Switch to a profile by name."""
        profile_path = f"{self.profiles_path}/{name}.xml"

        if not await self._copy_file(profile_path, self.config_path):
            return False

        stdout, stderr, exit_code = await self._run_command(
            "sudo systemctl restart hqplayerd"
        )

        if exit_code != 0:
            return False

        if wait:
            return await self._wait_for_hqplayer()

        return True

    async def get_current_profile(self) -> Optional[str]:
        """Try to detect which profile is currently active."""
        current_hash = await self._get_file_hash(self.config_path)
        if not current_hash:
            return None

        files = await self._list_files(self.profiles_path)
        for filename in files:
            if not filename.endswith(".xml"):
                continue
            profile_path = f"{self.profiles_path}/{filename}"
            profile_hash = await self._get_file_hash(profile_path)
            if profile_hash == current_hash:
                return filename[:-4]

        return None

    async def save_current_as_profile(self, name: str) -> bool:
        """Save the current config as a new profile."""
        profile_path = f"{self.profiles_path}/{name}.xml"
        return await self._copy_file(self.config_path, profile_path)

    async def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
        profile_path = f"{self.profiles_path}/{name}.xml"
        stdout, stderr, exit_code = await self._run_command(f"rm '{profile_path}'")
        return exit_code == 0


class SSHProfileManager(BaseProfileManager):
    """Manage HQPlayer profiles via SSH."""

    def __init__(
        self,
        host: str,
        user: str = "hqplayer",
        profiles_path: str = "/var/lib/hqplayer/home/cfgs",
        config_path: str = "/etc/hqplayer/hqplayerd.xml",
        ssh_key_path: Optional[str] = None,
        xml_port: int = 4321,
        wait_timeout: float = 30.0,
        poll_interval: float = 0.5,
    ):
        super().__init__(
            host=host,
            profiles_path=profiles_path,
            config_path=config_path,
            xml_port=xml_port,
            wait_timeout=wait_timeout,
            poll_interval=poll_interval,
        )
        self.user = user
        self.ssh_key_path = ssh_key_path

    def _get_ssh_client(self) -> paramiko.SSHClient:
        """Create and configure SSH client."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    async def _run_ssh_command(self, command: str) -> tuple[str, str, int]:
        """Run a command via SSH and return (stdout, stderr, exit_code)."""

        def _run():
            client = self._get_ssh_client()
            try:
                connect_kwargs = {
                    "hostname": self.host,
                    "username": self.user,
                }
                if self.ssh_key_path:
                    connect_kwargs["key_filename"] = self.ssh_key_path

                client.connect(**connect_kwargs)
                stdin, stdout, stderr = client.exec_command(command)
                exit_code = stdout.channel.recv_exit_status()
                return stdout.read().decode(), stderr.read().decode(), exit_code
            finally:
                client.close()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)

    async def _run_command(self, command: str) -> tuple[str, str, int]:
        """Run a command via SSH."""
        return await self._run_ssh_command(command)

    async def _copy_file(self, src: str, dst: str) -> bool:
        """Copy a file via SSH."""
        stdout, stderr, exit_code = await self._run_ssh_command(
            f"sudo cp '{src}' '{dst}'"
        )
        return exit_code == 0

    async def _list_files(self, directory: str) -> list[str]:
        """List files via SSH."""
        stdout, stderr, exit_code = await self._run_ssh_command(f"ls -1 '{directory}'")
        if exit_code != 0:
            return []
        return [f for f in stdout.strip().split("\n") if f]

    async def _get_file_hash(self, path: str) -> Optional[str]:
        """Get MD5 hash via SSH."""
        stdout, stderr, exit_code = await self._run_ssh_command(f"md5sum '{path}'")
        if exit_code != 0:
            return None
        parts = stdout.split()
        return parts[0] if parts else None


class LocalProfileManager(BaseProfileManager):
    """Manage HQPlayer profiles via local file operations."""

    def __init__(
        self,
        profiles_path: str = "/var/lib/hqplayer/home/cfgs",
        config_path: str = "/etc/hqplayer/hqplayerd.xml",
        xml_port: int = 4321,
        wait_timeout: float = 30.0,
        poll_interval: float = 0.5,
    ):
        super().__init__(
            host="localhost",
            profiles_path=profiles_path,
            config_path=config_path,
            xml_port=xml_port,
            wait_timeout=wait_timeout,
            poll_interval=poll_interval,
        )

    async def _run_command(self, command: str) -> tuple[str, str, int]:
        """Run a command locally."""

        def _run():
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
            )
            return result.stdout, result.stderr, result.returncode

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)

    async def _copy_file(self, src: str, dst: str) -> bool:
        """Copy a file locally."""

        def _copy():
            try:
                shutil.copy2(src, dst)
                return True
            except (OSError, IOError):
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _copy)

    async def _list_files(self, directory: str) -> list[str]:
        """List files locally."""

        def _list():
            try:
                path = Path(directory)
                return [f.name for f in path.iterdir() if f.is_file()]
            except (OSError, IOError):
                return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list)

    async def _get_file_hash(self, path: str) -> Optional[str]:
        """Get MD5 hash locally."""

        def _hash():
            try:
                with open(path, "rb") as f:
                    return hashlib.md5(f.read()).hexdigest()
            except (OSError, IOError):
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _hash)


def create_profile_manager(
    mode: Literal["ssh", "local"],
    host: str = "localhost",
    user: str = "hqplayer",
    profiles_path: str = "/var/lib/hqplayer/home/cfgs",
    config_path: str = "/etc/hqplayer/hqplayerd.xml",
    ssh_key_path: Optional[str] = None,
    xml_port: int = 4321,
    wait_timeout: float = 30.0,
    poll_interval: float = 0.5,
) -> BaseProfileManager:
    """Factory function to create the appropriate profile manager."""
    if mode == "local":
        return LocalProfileManager(
            profiles_path=profiles_path,
            config_path=config_path,
            xml_port=xml_port,
            wait_timeout=wait_timeout,
            poll_interval=poll_interval,
        )
    else:
        return SSHProfileManager(
            host=host,
            user=user,
            profiles_path=profiles_path,
            config_path=config_path,
            ssh_key_path=ssh_key_path,
            xml_port=xml_port,
            wait_timeout=wait_timeout,
            poll_interval=poll_interval,
        )


# Backwards compatibility alias
ProfileManager = SSHProfileManager
