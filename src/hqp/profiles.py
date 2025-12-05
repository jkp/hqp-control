"""HQPlayer profile management via SSH."""

import asyncio
import socket
from typing import Optional

import paramiko

from hqp.models import Profile


class ProfileManager:
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
        self.host = host
        self.user = user
        self.profiles_path = profiles_path
        self.config_path = config_path
        self.ssh_key_path = ssh_key_path
        self.xml_port = xml_port
        self.wait_timeout = wait_timeout
        self.poll_interval = poll_interval

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

    async def list_profiles(self) -> list[Profile]:
        """List available profiles."""
        command = f"ls -1 '{self.profiles_path}'"
        stdout, stderr, exit_code = await self._run_ssh_command(command)

        if exit_code != 0:
            return []

        profiles = []
        for line in stdout.strip().split("\n"):
            if line and line.endswith(".xml"):
                name = line[:-4]  # Remove .xml extension
                path = f"{self.profiles_path}/{line}"
                profiles.append(Profile(name=name, path=path))

        return profiles

    async def _check_hqplayer_alive(self) -> bool:
        """Check if hqplayerd is responding on the XML port."""

        def _check():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((self.host, self.xml_port))
                # Send a simple status command
                sock.sendall(b'<?xml version="1.0" encoding="UTF-8"?><Status/>')
                response = sock.recv(4096)
                sock.close()
                # Check we got a valid XML response
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

    async def switch_profile(self, name: str, wait: bool = True) -> bool:
        """Switch to a profile by name.

        Copies the profile config to the active config and restarts hqplayerd.
        If wait=True (default), blocks until hqplayerd is back online.
        """
        profile_path = f"{self.profiles_path}/{name}.xml"

        # Copy profile to active config
        cp_command = f"sudo cp '{profile_path}' '{self.config_path}'"
        stdout, stderr, exit_code = await self._run_ssh_command(cp_command)

        if exit_code != 0:
            return False

        # Restart hqplayerd
        restart_command = "sudo systemctl restart hqplayerd"
        stdout, stderr, exit_code = await self._run_ssh_command(restart_command)

        if exit_code != 0:
            return False

        if wait:
            # Wait for service to come back online
            return await self._wait_for_hqplayer()

        return True

    async def get_current_profile(self) -> Optional[str]:
        """Try to detect which profile is currently active.

        Compares MD5 hashes of current config with all profiles.
        Returns None if no match found.
        """
        # Get hash of current config
        cmd = f"md5sum '{self.config_path}'"
        stdout, stderr, exit_code = await self._run_ssh_command(cmd)

        if exit_code != 0:
            return None

        current_hash = stdout.split()[0] if stdout else None
        if not current_hash:
            return None

        # Get hashes of all profiles
        cmd = f"cd '{self.profiles_path}' && md5sum *.xml 2>/dev/null"
        stdout, stderr, exit_code = await self._run_ssh_command(cmd)

        if exit_code != 0:
            return None

        for line in stdout.strip().split("\n"):
            if not line:
                continue
            # md5sum output: "hash  filename" (two spaces)
            # Split only on first whitespace to handle filenames with spaces
            parts = line.split(None, 1)  # Split on first whitespace only
            if len(parts) >= 2:
                profile_hash = parts[0]
                profile_file = parts[1].strip()
                if profile_hash == current_hash and profile_file.endswith(".xml"):
                    return profile_file[:-4]  # Remove .xml

        return None

    async def save_current_as_profile(self, name: str) -> bool:
        """Save the current config as a new profile."""
        profile_path = f"{self.profiles_path}/{name}.xml"
        command = f"sudo cp '{self.config_path}' '{profile_path}'"
        stdout, stderr, exit_code = await self._run_ssh_command(command)
        return exit_code == 0

    async def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
        profile_path = f"{self.profiles_path}/{name}.xml"
        command = f"sudo rm '{profile_path}'"
        stdout, stderr, exit_code = await self._run_ssh_command(command)
        return exit_code == 0
