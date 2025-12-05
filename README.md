# HQPlayer Control

Python client library and HTTP API for controlling HQPlayer Embedded.

## Features

- **Profile switching**: Switch between saved HQPlayer profiles (output devices, filters, modulators)
- **Transport controls**: Play, pause, stop
- **Volume control**: Get/set volume, volume up/down
- **HTTP API**: REST API for remote control from any device (iPhone, etc.)
- **CLI**: Command-line interface for quick control

## Installation

```bash
cd hqp-control
uv sync
```

## Configuration

Set environment variables or use defaults:

```bash
export HQP_HQPLAYER__HOST=hqplayer.local  # HQPlayer server hostname
export HQP_PROFILES__SSH_USER=hqplayer    # SSH user for profile switching
```

## CLI Usage

```bash
# Status
hqp status

# Profiles
hqp profiles                    # List profiles (* = current)
hqp switch "Living Room"        # Switch profile (waits for restart)
hqp switch "Office" --no-wait   # Switch without waiting
hqp save "Living Room"          # Save current config as profile

# Volume
hqp vol                         # Show current volume
hqp vol -s -25                  # Set to -25 dB
hqp vol --up                    # +1 dB
hqp vol --down                  # -1 dB

# Transport
hqp play
hqp pause
hqp stop

# HTTP Server
hqp serve                       # Start on port 9100
hqp serve --port 8080           # Custom port
```

## HTTP API

Start the server: `hqp serve`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Playback status and current profile |
| GET | `/profiles` | List profiles with current indicator |
| POST | `/profiles/{name}` | Switch to profile (add `?wait=false` to not wait) |
| POST | `/volume` | Set volume `{"value": -25}` |
| POST | `/volume/up` | Volume +1 dB |
| POST | `/volume/down` | Volume -1 dB |
| POST | `/transport/play` | Start playback |
| POST | `/transport/pause` | Pause playback |
| POST | `/transport/stop` | Stop playback |

Swagger docs available at `http://<host>:9100/docs`

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   iPhone/Mac    │────▶│   HTTP API      │────▶│  hqplayer.local │
│   Clients       │     │   (this app)    │     │   (hqplayerd)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              │ XML/TCP :4321          │
                              │ SSH (profile switch)   │
                              └────────────────────────┘
```

## HQPlayer API Notes

### XML Control API (port 4321)

No authentication required. Commands discovered:

```xml
<Status/>                    <!-- Returns full playback state -->
<Volume value="-20"/>        <!-- Set volume in dB -->
<Play/>, <Pause/>, <Stop/>   <!-- Transport controls -->
<Next/>, <Previous/>         <!-- Track navigation (limited by controller) -->
<PlaylistClear/>             <!-- Clear playlist -->
<PlaylistAdd uri="..."/>     <!-- Add track to playlist -->
```

**Note**: JPlay maintains its own queue and feeds tracks one at a time, so Next/Previous only work within JPlay's queue.

### Profile Storage

- Active config: `/etc/hqplayer/hqplayerd.xml`
- Saved profiles: `/var/lib/hqplayer/home/cfgs/*.xml`
- Service: `systemctl restart hqplayerd`

Profile switching works by:
1. Copying profile XML to active config
2. Restarting hqplayerd service
3. Waiting for service to respond on port 4321

### Web Interface (port 8088)

Requires digest authentication. Useful for configuration but not ideal for automation.

## Development

```bash
# Run tests
uv run pytest -v

# Run with auto-reload
uv run uvicorn hqp.server:app --reload --port 9100
```

## Future Plans

- Qobuz integration for search and queue management
- Direct streaming without JPlay dependency
- macOS menu bar app
