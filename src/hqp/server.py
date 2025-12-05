"""FastAPI HTTP server for HQPlayer control."""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from hqp.config import settings
from hqp.models import HQPStatus, Profile
from hqp.profiles import BaseProfileManager, create_profile_manager
from hqp.xml_client import HQPClient


# Request/Response models
class VolumeRequest(BaseModel):
    value: float


class VolumeStepRequest(BaseModel):
    step: float = 1.0


class StatusResponse(BaseModel):
    status: HQPStatus
    current_profile: Optional[str] = None


class ProfilesResponse(BaseModel):
    profiles: list[Profile]
    current: Optional[str] = None


class ResultResponse(BaseModel):
    success: bool
    message: Optional[str] = None


# Global clients
hqp_client: Optional[HQPClient] = None
profile_manager: Optional[BaseProfileManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize clients on startup."""
    global hqp_client, profile_manager

    hqp_client = HQPClient(
        host=settings.hqplayer.host,
        port=settings.hqplayer.xml_port,
    )

    profile_manager = create_profile_manager(
        mode=settings.profiles.mode,
        host=settings.hqplayer.host,
        user=settings.profiles.ssh_user,
        profiles_path=settings.profiles.profiles_path,
        config_path=settings.profiles.config_path,
        ssh_key_path=settings.profiles.ssh_key_path,
        xml_port=settings.hqplayer.xml_port,
    )

    yield

    # Cleanup if needed
    hqp_client = None
    profile_manager = None


app = FastAPI(
    title="HQPlayer Control API",
    description="HTTP API for controlling HQPlayer Embedded",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """API info."""
    return {
        "name": "HQPlayer Control API",
        "version": "0.1.0",
        "hqplayer_host": settings.hqplayer.host,
    }


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get current playback status."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        status = await hqp_client.get_status()
        current_profile = None
        if profile_manager:
            try:
                current_profile = await profile_manager.get_current_profile()
            except Exception:
                pass  # Profile detection is best-effort
        return StatusResponse(status=status, current_profile=current_profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profiles", response_model=ProfilesResponse)
async def list_profiles():
    """List available profiles."""
    if not profile_manager:
        raise HTTPException(status_code=503, detail="Profile manager not initialized")

    try:
        profiles = await profile_manager.list_profiles()
        current = await profile_manager.get_current_profile()
        return ProfilesResponse(profiles=profiles, current=current)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profiles/{name}", response_model=ResultResponse)
async def switch_profile(name: str, wait: bool = True):
    """Switch to a profile by name.

    Args:
        name: Profile name to switch to
        wait: If true (default), wait for hqplayerd to restart before returning
    """
    if not profile_manager:
        raise HTTPException(status_code=503, detail="Profile manager not initialized")

    try:
        success = await profile_manager.switch_profile(name, wait=wait)
        if success:
            return ResultResponse(success=True, message=f"Switched to profile: {name}")
        else:
            msg = f"Failed to switch to profile: {name}"
            if wait:
                msg += " (timeout waiting for service)"
            return ResultResponse(success=False, message=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/volume", response_model=ResultResponse)
async def set_volume(request: VolumeRequest):
    """Set volume to a specific value in dB."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.set_volume(request.value)
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/volume/up", response_model=ResultResponse)
async def volume_up(request: VolumeStepRequest = VolumeStepRequest()):
    """Increase volume by step dB."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.volume_up(request.step)
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/volume/down", response_model=ResultResponse)
async def volume_down(request: VolumeStepRequest = VolumeStepRequest()):
    """Decrease volume by step dB."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.volume_down(request.step)
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transport/play", response_model=ResultResponse)
async def play():
    """Start playback."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.play()
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transport/pause", response_model=ResultResponse)
async def pause():
    """Pause playback."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.pause()
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transport/stop", response_model=ResultResponse)
async def stop():
    """Stop playback."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.stop()
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transport/next", response_model=ResultResponse)
async def next_track():
    """Skip to next track."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.next_track()
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transport/prev", response_model=ResultResponse)
async def prev_track():
    """Skip to previous track."""
    if not hqp_client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    try:
        success = await hqp_client.previous_track()
        return ResultResponse(success=success)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server():
    """Run the API server."""
    import uvicorn

    uvicorn.run(
        "hqp.server:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )


if __name__ == "__main__":
    run_server()
