"""Configuration management for HQPlayer control."""

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class HQPlayerConfig(BaseModel):
    """HQPlayer connection settings."""

    host: str = "localhost"
    xml_port: int = 4321
    web_port: int = 8088


class ProfilesConfig(BaseModel):
    """Profile management settings."""

    mode: Literal["ssh", "local"] = "ssh"
    ssh_user: str = "hqplayer"
    ssh_key_path: Optional[str] = None
    config_path: str = "/etc/hqplayer/hqplayerd.xml"
    profiles_path: str = "/var/lib/hqplayer/home/cfgs"


class ServerConfig(BaseModel):
    """HTTP API server settings."""

    host: str = "0.0.0.0"
    port: int = 9100


class Settings(BaseSettings):
    """Application settings loaded from environment or config file."""

    hqplayer: HQPlayerConfig = HQPlayerConfig()
    profiles: ProfilesConfig = ProfilesConfig()
    server: ServerConfig = ServerConfig()

    model_config = {
        "env_prefix": "HQP_",
        "env_nested_delimiter": "__",
    }


def load_settings() -> Settings:
    """Load settings from environment variables.

    Environment variable examples:
        HQP_HQPLAYER__HOST=hqplayer.local
        HQP_PROFILES__MODE=ssh
        HQP_SERVER__PORT=8000
    """
    return Settings()


# Default settings instance
settings = load_settings()
