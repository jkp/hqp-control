"""Pydantic models for HQPlayer data structures."""

from pydantic import BaseModel, Field


class HQPStatus(BaseModel):
    """HQPlayer playback status from XML API."""

    # Playback state: 0=stopped, 1=playing, 2=paused
    state: int = 0

    # Volume in dB (typically -40 to 0)
    volume: float = 0.0

    # Current track info
    track: int = 0
    tracks_total: int = 0

    # Time info (in seconds)
    position: int = 0
    length: int = 0

    # Display time
    min: int = Field(default=0, alias="min")
    sec: int = Field(default=0, alias="sec")
    remain_min: int = 0
    remain_sec: int = 0
    total_min: int = 0
    total_sec: int = 0

    # Active processing settings
    active_mode: str = ""
    active_filter: str = ""
    active_shaper: str = ""
    active_rate: int = 0
    active_bits: int = 0
    active_channels: int = 0

    # Queue/buffer status
    queued: int = 0
    input_fill: int = 0
    output_fill: int = 0
    output_delay: int = 0

    # Flags
    random: int = 0
    repeat: int = 0
    clips: int = 0

    # Serials for change detection
    track_serial: int = 0
    transport_serial: int = 0

    model_config = {"populate_by_name": True}

    @property
    def is_playing(self) -> bool:
        return self.state == 1

    @property
    def is_paused(self) -> bool:
        return self.state == 2

    @property
    def is_stopped(self) -> bool:
        return self.state == 0

    @property
    def state_name(self) -> str:
        return {0: "stopped", 1: "playing", 2: "paused"}.get(self.state, "unknown")

    @property
    def position_str(self) -> str:
        return f"{self.min}:{self.sec:02d}"

    @property
    def remaining_str(self) -> str:
        return f"{self.remain_min}:{self.remain_sec:02d}"


class Profile(BaseModel):
    """HQPlayer profile/configuration."""

    name: str
    path: str
