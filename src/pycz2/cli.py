# src/pycz2/cli.py
import asyncio
from collections.abc import Coroutine
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .config import settings
from .core.client import ComfortZoneIIClient
from .core.constants import FanMode, SystemMode
from .core.models import SystemStatus

app = typer.Typer(
    name="cli",
    help="Command-Line Interface for interacting with the HVAC system.",
    no_args_is_help=True,
)
console = Console()


async def get_client() -> ComfortZoneIIClient:
    """Async factory for the client."""
    return ComfortZoneIIClient(
        connect_str=settings.CZ_CONNECT,
        zone_count=settings.CZ_ZONES,
        device_id=settings.CZ_ID,
    )


def run_async(coro: Coroutine[Any, Any, None]) -> None:
    """Helper to run an async function from a sync Typer command."""
    asyncio.run(coro)


def print_status(status: SystemStatus) -> None:
    """Prints the status in a human-readable format."""
    console.print(f"[bold]System Time:[/] {status.system_time}")
    console.print(
        f"[bold]Ambient:[/]\t    Outside {status.outside_temp}°F / Indoor humidity {status.zone1_humidity}%"
    )
    console.print(
        f"[bold]Air Handler:[/] {status.air_handler_temp}°F, Fan "
        f"{status.fan_state}, {status.active_state}"
    )
    console.print(
        f"[bold]Mode:[/] \t    {status.system_mode.value} "
        f"({status.effective_mode.value}), Fan {status.fan_mode.value}"
    )
    console.print()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Zone", style="dim")
    table.add_column("Temp (°F)")
    table.add_column("Damper (%)")
    table.add_column("Setpoint")
    table.add_column("Mode")

    is_auto = status.system_mode == SystemMode.AUTO

    for i, zone in enumerate(status.zones):
        zone_name = (
            settings.CZ_ZONE_NAMES[i]
            if settings.CZ_ZONE_NAMES
            else f"Zone {zone.zone_id}"
        )
        mode_str = ""
        if zone.hold:
            mode_str += "[HOLD] "
        if zone.temporary:
            mode_str += "[TEMP] "
        if status.all_mode and zone.zone_id == 1:
            mode_str += "[ALL]"

        if zone.out:
            setpoint_str = "OUT"
        else:
            if is_auto:
                setpoint_str = (
                    f"Cool {zone.cool_setpoint}° / Heat {zone.heat_setpoint}°"
                )
            elif status.effective_mode in (SystemMode.HEAT, SystemMode.EHEAT):
                setpoint_str = f"Heat {zone.heat_setpoint}°"
            else:
                setpoint_str = f"Cool {zone.cool_setpoint}°"

        table.add_row(
            zone_name,
            str(zone.temperature),
            str(zone.damper_position),
            setpoint_str,
            mode_str,
        )
    console.print(table)


@app.command()
def status() -> None:
    """Print an overview of the current system status."""

    async def _status() -> None:
        client = await get_client()
        async with client.connection():
            s = await client.get_status_data()
            print_status(s)

    run_async(_status())


@app.command()
def status_json() -> None:
    """Print the status information in JSON format."""

    async def _status_json() -> None:
        client = await get_client()
        async with client.connection():
            s = await client.get_status_data()
            console.print_json(s.model_dump_json(indent=2))

    run_async(_status_json())


@app.command()
def set_system(
    mode: SystemMode | None = typer.Option(
        None, "--mode", help="System operating mode."
    ),
    fan: FanMode | None = typer.Option(None, "--fan", help="System fan mode."),
    all_mode: bool | None = typer.Option(
        None, "--all/--no-all", help="Enable/disable 'all zones' mode."
    ),
) -> None:
    """Set system-wide options."""

    async def _set_system() -> None:
        if all(v is None for v in [mode, fan, all_mode]):
            console.print("[red]Error:[/] No options specified. Use --help for info.")
            raise typer.Exit(code=1)

        client = await get_client()
        async with client.connection():
            if mode is not None or all_mode is not None:
                await client.set_system_mode(mode, all_mode)
            if fan is not None:
                await client.set_fan_mode(fan)
            console.print("[green]System settings updated. New status:[/]")
            s = await client.get_status_data()
            print_status(s)

    run_async(_set_system())


@app.command()
def set_zone(
    zones: list[int] = typer.Argument(
        ..., help="One or more zone numbers (e.g., 1 3)."
    ),
    heat: int | None = typer.Option(None, help="Heating setpoint (45-74)."),
    cool: int | None = typer.Option(None, help="Cooling setpoint (64-99)."),
    temp: bool = typer.Option(
        False, "--temp", help="Enable 'temporary setpoint' mode."
    ),
    hold: bool = typer.Option(False, "--hold", help="Enable 'hold' mode."),
    out: bool = typer.Option(False, "--out", help="Enable 'out' mode."),
) -> None:
    """Set options for one or more zones."""

    async def _set_zone() -> None:
        client = await get_client()
        async with client.connection():
            await client.set_zone_setpoints(
                zones=zones,
                heat_setpoint=heat,
                cool_setpoint=cool,
                temporary_hold=temp,
                hold=hold,
                out_mode=out,
            )
            console.print("[green]Zone settings updated. New status:[/]")
            s = await client.get_status_data()
            print_status(s)

    run_async(_set_zone())


@app.command()
def monitor() -> None:
    """Passively monitor all serial traffic and print each frame observed."""

    async def _monitor() -> None:
        client = await get_client()
        async with client.connection():
            console.print("Monitoring bus traffic... Press Ctrl+C to stop.")
            async for frame in client.monitor_bus():
                console.print(
                    f"[dim]{frame.source:02d} -> {frame.destination:02d}[/]  "
                    f"[bold cyan]{frame.function.name:<5}[/]  "
                    f"{'.'.join(map(str, frame.data))}"
                )

    run_async(_monitor())


@app.command(name="read")
def read_row(
    dest: int = typer.Argument(..., help="Destination device ID."),
    table: int = typer.Argument(..., help="Table number."),
    row: int = typer.Argument(..., help="Row number."),
) -> None:
    """Send a read request for one row and print the data received."""

    async def _read() -> None:
        client = await get_client()
        async with client.connection():
            reply_frame = await client.read_row(dest, table, row)
            console.print(".".join(map(str, reply_frame.data)))

    run_async(_read())


if __name__ == "__main__":
    app()
