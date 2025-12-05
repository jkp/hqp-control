"""Command-line interface for HQPlayer control."""

import asyncio
import sys

import click

from hqp.config import settings
from hqp.profiles import create_profile_manager
from hqp.xml_client import HQPClient


def get_client() -> HQPClient:
    """Create HQP client from settings."""
    return HQPClient(
        host=settings.hqplayer.host,
        port=settings.hqplayer.xml_port,
    )


def get_profile_manager():
    """Create profile manager from settings."""
    return create_profile_manager(
        mode=settings.profiles.mode,
        host=settings.hqplayer.host,
        user=settings.profiles.ssh_user,
        profiles_path=settings.profiles.profiles_path,
        config_path=settings.profiles.config_path,
        ssh_key_path=settings.profiles.ssh_key_path,
    )


def run_async(coro):
    """Run an async coroutine."""
    return asyncio.run(coro)


@click.group()
@click.option(
    "--host",
    envvar="HQP_HQPLAYER__HOST",
    default="localhost",
    help="HQPlayer host",
)
@click.pass_context
def main(ctx, host):
    """HQPlayer control CLI."""
    ctx.ensure_object(dict)
    settings.hqplayer.host = host


@main.command()
@click.pass_context
def status(ctx):
    """Show current playback status."""
    client = get_client()

    async def _status():
        s = await client.get_status()
        click.echo(f"State:    {s.state_name}")
        click.echo(f"Volume:   {s.volume} dB")
        if s.tracks_total > 0:
            click.echo(f"Track:    {s.track}/{s.tracks_total}")
            click.echo(f"Position: {s.position_str} / {s.total_min}:{s.total_sec:02d}")
        click.echo(f"Mode:     {s.active_mode}")
        click.echo(f"Filter:   {s.active_filter}")
        click.echo(f"Shaper:   {s.active_shaper}")
        click.echo(f"Rate:     {s.active_rate} Hz")

    run_async(_status())


@main.command()
@click.pass_context
def profiles(ctx):
    """List available profiles."""
    pm = get_profile_manager()

    async def _profiles():
        profiles_list = await pm.list_profiles()
        current = await pm.get_current_profile()

        for p in profiles_list:
            marker = " *" if p.name == current else ""
            click.echo(f"  {p.name}{marker}")

    run_async(_profiles())


@main.command()
@click.argument("name")
@click.option("--no-wait", is_flag=True, help="Don't wait for service to restart")
@click.pass_context
def switch(ctx, name, no_wait):
    """Switch to a profile."""
    pm = get_profile_manager()

    async def _switch():
        click.echo(f"Switching to profile: {name}...")
        if no_wait:
            success = await pm.switch_profile(name, wait=False)
            if success:
                click.echo("Profile switch initiated.")
            else:
                click.echo("Failed to switch profile", err=True)
                sys.exit(1)
        else:
            click.echo("Waiting for HQPlayer to restart...", nl=False)
            success = await pm.switch_profile(name, wait=True)
            if success:
                click.echo(" ready!")
            else:
                click.echo(" timeout!", err=True)
                sys.exit(1)

    run_async(_switch())


@main.command()
@click.argument("name")
@click.pass_context
def save(ctx, name):
    """Save current config as a new profile."""
    pm = get_profile_manager()

    async def _save():
        click.echo(f"Saving current config as profile: {name}...")
        success = await pm.save_current_as_profile(name)
        if success:
            click.echo("Saved.")
        else:
            click.echo("Failed to save profile", err=True)
            sys.exit(1)

    run_async(_save())


@main.command()
@click.option("-s", "--set", "value", type=float, help="Set volume to VALUE dB")
@click.option("--up", is_flag=True, help="Increase volume by 1dB")
@click.option("--down", is_flag=True, help="Decrease volume by 1dB")
@click.pass_context
def vol(ctx, value, up, down):
    """Get or set volume. Use -s/-set for negative values."""
    client = get_client()

    async def _vol():
        if up:
            await client.volume_up()
            s = await client.get_status()
            click.echo(f"Volume: {s.volume} dB")
        elif down:
            await client.volume_down()
            s = await client.get_status()
            click.echo(f"Volume: {s.volume} dB")
        elif value is not None:
            await client.set_volume(value)
            click.echo(f"Volume: {value} dB")
        else:
            s = await client.get_status()
            click.echo(f"Volume: {s.volume} dB")

    run_async(_vol())


@main.command()
@click.pass_context
def play(ctx):
    """Start playback."""
    client = get_client()
    run_async(client.play())
    click.echo("Play")


@main.command()
@click.pass_context
def pause(ctx):
    """Pause playback."""
    client = get_client()
    run_async(client.pause())
    click.echo("Paused")


@main.command()
@click.pass_context
def stop(ctx):
    """Stop playback."""
    client = get_client()
    run_async(client.stop())
    click.echo("Stopped")


@main.command("next")
@click.pass_context
def next_track(ctx):
    """Next track."""
    client = get_client()
    run_async(client.next_track())
    click.echo("Next")


@main.command("prev")
@click.pass_context
def prev_track(ctx):
    """Previous track."""
    client = get_client()
    run_async(client.previous_track())
    click.echo("Previous")


@main.command()
@click.option("--port", default=9100, help="Server port")
@click.option("--bind", default="0.0.0.0", help="IP address to bind to (e.g., 127.0.0.1 or Tailscale IP)")
@click.pass_context
def serve(ctx, port, bind):
    """Run the HTTP API server."""
    settings.server.port = port
    settings.server.host = bind
    click.echo(f"Starting HQPlayer Control API on {bind}:{port}...")
    click.echo(f"HQPlayer host: {settings.hqplayer.host}")

    from hqp.server import run_server

    run_server()


if __name__ == "__main__":
    main()
