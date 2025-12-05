"""HQPlayer XML control API client."""

import asyncio
import xml.etree.ElementTree as ET
from typing import Optional

from hqp.models import HQPStatus


def _parse_int(value: str, default: int = 0) -> int:
    """Parse a string to int, handling floats."""
    if not value:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def parse_status_xml(xml_str: str) -> HQPStatus:
    """Parse a Status XML response into an HQPStatus object."""
    root = ET.fromstring(xml_str)
    if root.tag != "Status":
        raise ValueError(f"Expected Status element, got {root.tag}")

    # Extract all attributes, converting types as needed
    attrs = root.attrib
    return HQPStatus(
        state=_parse_int(attrs.get("state", "0")),
        volume=float(attrs.get("volume", 0)),
        track=_parse_int(attrs.get("track", "0")),
        tracks_total=_parse_int(attrs.get("tracks_total", "0")),
        position=_parse_int(attrs.get("position", "0")),
        length=_parse_int(attrs.get("length", "0")),
        min=_parse_int(attrs.get("min", "0")),
        sec=_parse_int(attrs.get("sec", "0")),
        remain_min=_parse_int(attrs.get("remain_min", "0")),
        remain_sec=_parse_int(attrs.get("remain_sec", "0")),
        total_min=_parse_int(attrs.get("total_min", "0")),
        total_sec=_parse_int(attrs.get("total_sec", "0")),
        active_mode=attrs.get("active_mode", ""),
        active_filter=attrs.get("active_filter", ""),
        active_shaper=attrs.get("active_shaper", ""),
        active_rate=_parse_int(attrs.get("active_rate", "0")),
        active_bits=_parse_int(attrs.get("active_bits", "0")),
        active_channels=_parse_int(attrs.get("active_channels", "0")),
        queued=_parse_int(attrs.get("queued", "0")),
        input_fill=_parse_int(attrs.get("input_fill", "0")),
        output_fill=_parse_int(attrs.get("output_fill", "0")),
        output_delay=_parse_int(attrs.get("output_delay", "0")),
        random=_parse_int(attrs.get("random", "0")),
        repeat=_parse_int(attrs.get("repeat", "0")),
        clips=_parse_int(attrs.get("clips", "0")),
        track_serial=_parse_int(attrs.get("track_serial", "0")),
        transport_serial=_parse_int(attrs.get("transport_serial", "0")),
    )


def parse_result_xml(xml_str: str) -> tuple[bool, Optional[str]]:
    """Parse a command result XML response.

    Returns (success, error_message).
    """
    root = ET.fromstring(xml_str)
    result = root.attrib.get("result", "")
    if result == "OK":
        return True, None
    error_text = root.text or result
    return False, error_text


class HQPClient:
    """Async client for HQPlayer XML control API."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4321,
        timeout: float = 5.0,
        volume_min: float = -40.0,
        volume_max: float = 0.0,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.volume_min = volume_min
        self.volume_max = volume_max

    async def _send_command(self, xml_command: str) -> str:
        """Send an XML command and return the response."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self.timeout,
        )
        try:
            # Send command with XML declaration
            full_command = f'<?xml version="1.0" encoding="UTF-8"?>{xml_command}'
            writer.write(full_command.encode("utf-8"))
            await writer.drain()

            # Read response
            response = await asyncio.wait_for(
                reader.read(8192),
                timeout=self.timeout,
            )
            return response.decode("utf-8")
        finally:
            writer.close()
            await writer.wait_closed()

    async def get_status(self) -> HQPStatus:
        """Get current playback status."""
        response = await self._send_command("<Status/>")
        return parse_status_xml(response)

    async def set_volume(self, value: float) -> bool:
        """Set volume in dB (typically -40 to 0)."""
        # Format as integer if whole number, otherwise keep decimal
        if value == int(value):
            vol_str = str(int(value))
        else:
            vol_str = str(value)
        response = await self._send_command(f'<Volume value="{vol_str}"/>')
        success, _ = parse_result_xml(response)
        return success

    async def volume_up(self, step: float = 1.0) -> bool:
        """Increase volume by step dB."""
        status = await self.get_status()
        new_volume = min(status.volume + step, self.volume_max)
        return await self.set_volume(new_volume)

    async def volume_down(self, step: float = 1.0) -> bool:
        """Decrease volume by step dB."""
        status = await self.get_status()
        new_volume = max(status.volume - step, self.volume_min)
        return await self.set_volume(new_volume)

    async def play(self) -> bool:
        """Start playback."""
        response = await self._send_command("<Play/>")
        success, _ = parse_result_xml(response)
        return success

    async def pause(self) -> bool:
        """Pause playback."""
        response = await self._send_command("<Pause/>")
        success, _ = parse_result_xml(response)
        return success

    async def stop(self) -> bool:
        """Stop playback."""
        response = await self._send_command("<Stop/>")
        success, _ = parse_result_xml(response)
        return success

    async def next_track(self) -> bool:
        """Skip to next track."""
        response = await self._send_command("<Next/>")
        success, _ = parse_result_xml(response)
        return success

    async def previous_track(self) -> bool:
        """Skip to previous track."""
        response = await self._send_command("<Previous/>")
        success, _ = parse_result_xml(response)
        return success

    async def playlist_clear(self) -> bool:
        """Clear the playlist."""
        response = await self._send_command("<PlaylistClear/>")
        success, _ = parse_result_xml(response)
        return success

    async def playlist_add(self, uri: str) -> bool:
        """Add a URI to the playlist."""
        # Escape XML special characters in URI
        uri_escaped = (
            uri.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        response = await self._send_command(f'<PlaylistAdd uri="{uri_escaped}"/>')
        success, _ = parse_result_xml(response)
        return success
