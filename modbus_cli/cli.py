"""modbus-cli: Like curl, but for Modbus."""

import sys
import time

import click
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from rich.console import Console
from rich.table import Table
from rich.live import Live

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_address(address: int):
    """Parse Modbus address, handling standard notation (40001, 30001, etc).

    Standard notation:
        00001-09999  -> coils (function 01)
        10001-19999  -> discrete inputs (function 02)
        30001-39999  -> input registers (function 04)
        40001-49999  -> holding registers (function 03)

    If address < 10000 with no prefix context, treat as raw 0-based holding register.
    """
    if 40001 <= address <= 49999:
        return "holding", address - 40001
    elif 30001 <= address <= 39999:
        return "input", address - 30001
    elif 10001 <= address <= 19999:
        return "discrete", address - 10001
    elif 1 <= address <= 9999:
        return "coil", address - 1
    else:
        # Raw 0-based address, default to holding register
        return "holding", address


def _make_client(host: str, port: int, serial: str, baudrate: int, slave_id: int, timeout: float):
    """Create a Modbus TCP or RTU serial client."""
    if serial:
        client = ModbusSerialClient(
            port=serial,
            baudrate=baudrate,
            timeout=timeout,
            parity="N",
            stopbits=1,
            bytesize=8,
        )
    else:
        client = ModbusTcpClient(host=host, port=port, timeout=timeout)

    if not client.connect():
        console.print(f"[red]Error:[/red] Could not connect to {serial or f'{host}:{port}'}")
        sys.exit(1)
    return client


def _read_registers(client, reg_type: str, address: int, count: int, slave: int):
    """Read registers by type and return the response."""
    readers = {
        "holding": client.read_holding_registers,
        "input": client.read_input_registers,
        "coil": client.read_coils,
        "discrete": client.read_discrete_inputs,
    }
    reader = readers[reg_type]
    resp = reader(address, count=count, slave=slave)
    if resp.isError():
        console.print(f"[red]Modbus error:[/red] {resp}")
        sys.exit(1)
    return resp


def _format_value(value: int, fmt: str) -> str:
    """Format a register value."""
    if fmt == "hex":
        return f"0x{value:04X}"
    elif fmt == "bin":
        return f"{value:016b}"
    elif fmt == "signed":
        if value > 32767:
            return str(value - 65536)
        return str(value)
    return str(value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="modbus-cli")
def cli():
    """modbus-cli -- like curl, but for Modbus.

    Read and write Modbus TCP/RTU registers from your terminal.

    \b
    Examples:
      modbus read 192.168.1.10 40001
      modbus read 192.168.1.10 40001 --count 10
      modbus read --serial /dev/ttyUSB0 0 --count 5
      modbus write 192.168.1.10 40001 1234
      modbus scan 192.168.1.10
      modbus watch 192.168.1.10 40001 --count 4
    """
    pass


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("address", type=int)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port (e.g. /dev/ttyUSB0). Overrides TCP.")
@click.option("--baudrate", "-b", default=9600, help="Serial baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--count", "-c", default=1, help="Number of registers to read (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "input", "coil", "discrete"]),
              default=None, help="Register type. Auto-detected from address if omitted.")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["decimal", "hex", "bin", "signed"]),
              default="decimal", help="Output format (default: decimal).")
@click.option("--timeout", default=3.0, help="Connection timeout in seconds (default: 3).")
def read(host, address, port, serial, baudrate, slave, count, reg_type, fmt, timeout):
    """Read Modbus registers.

    \b
    ADDRESS uses standard Modbus notation:
      40001-49999  holding registers (most common)
      30001-39999  input registers
      10001-19999  discrete inputs
      00001-09999  coils

    Or pass a raw 0-based address with --type.
    """
    if reg_type:
        detected_type = reg_type
        raw_address = address
    else:
        detected_type, raw_address = _parse_address(address)

    client = _make_client(host, port, serial, baudrate, slave, timeout)
    try:
        resp = _read_registers(client, detected_type, raw_address, count, slave)

        if detected_type in ("coil", "discrete"):
            values = resp.bits[:count]
        else:
            values = resp.registers

        table = Table(title=f"Modbus {detected_type} registers @ {serial or host}")
        table.add_column("Address", style="cyan", justify="right")
        table.add_column("Raw", style="white", justify="right")
        table.add_column("Value", style="green", justify="right")

        for i, val in enumerate(values):
            addr_display = raw_address + i
            if not reg_type:
                # Show the standard notation address
                addr_display = address + i
            raw_val = str(int(val)) if isinstance(val, bool) else str(val)
            formatted = _format_value(int(val), fmt) if not isinstance(val, bool) else str(int(val))
            table.add_row(str(addr_display), raw_val, formatted)

        console.print(table)
    finally:
        client.close()


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("address", type=int)
@click.argument("values", type=int, nargs=-1, required=True)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port. Overrides TCP.")
@click.option("--baudrate", "-b", default=9600, help="Serial baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "coil"]),
              default=None, help="Register type. Auto-detected from address if omitted.")
@click.option("--timeout", default=3.0, help="Connection timeout in seconds (default: 3).")
def write(host, address, values, port, serial, baudrate, slave, reg_type, timeout):
    """Write values to Modbus registers.

    \b
    Examples:
      modbus write 192.168.1.10 40001 100
      modbus write 192.168.1.10 40001 100 200 300   # write multiple
      modbus write 192.168.1.10 1 1 --type coil     # write coil ON
    """
    if reg_type:
        detected_type = reg_type
        raw_address = address
    else:
        detected_type, raw_address = _parse_address(address)

    if detected_type not in ("holding", "coil"):
        console.print(f"[red]Error:[/red] Cannot write to {detected_type} registers (read-only).")
        sys.exit(1)

    client = _make_client(host, port, serial, baudrate, slave, timeout)
    try:
        if detected_type == "coil":
            if len(values) == 1:
                resp = client.write_coil(raw_address, bool(values[0]), slave=slave)
            else:
                resp = client.write_coils(raw_address, [bool(v) for v in values], slave=slave)
        else:
            if len(values) == 1:
                resp = client.write_register(raw_address, values[0], slave=slave)
            else:
                resp = client.write_registers(raw_address, list(values), slave=slave)

        if resp.isError():
            console.print(f"[red]Modbus error:[/red] {resp}")
            sys.exit(1)

        vals_str = ", ".join(str(v) for v in values)
        console.print(
            f"[green]OK:[/green] Wrote [{vals_str}] to {detected_type} "
            f"register(s) starting at {address} (slave {slave})"
        )
    finally:
        client.close()


# ---------------------------------------------------------------------------
# SCAN
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port. Overrides TCP.")
@click.option("--baudrate", "-b", default=9600, help="Serial baud rate (default: 9600).")
@click.option("--range", "-r", "scan_range", default="1-247",
              help="Slave ID range to scan (default: 1-247).")
@click.option("--register", default=40001, help="Test register to read (default: 40001).")
@click.option("--timeout", default=0.5, help="Per-device timeout in seconds (default: 0.5).")
def scan(host, port, serial, baudrate, scan_range, register, timeout):
    """Scan for active Modbus slave devices.

    Tries to read a test register from each slave ID in the range.
    Reports which IDs respond.

    \b
    Examples:
      modbus scan 192.168.1.10
      modbus scan 192.168.1.10 --range 1-10
      modbus scan --serial /dev/ttyUSB0 --range 1-50
    """
    start, end = scan_range.split("-")
    start, end = int(start), int(end)

    reg_type, raw_address = _parse_address(register)

    found = []

    with console.status(f"[cyan]Scanning slave IDs {start}-{end}...") as status:
        for slave_id in range(start, end + 1):
            status.update(f"[cyan]Scanning slave ID {slave_id}/{end}...")
            try:
                client = _make_client(host, port, serial, baudrate, slave_id, timeout)
                resp = _read_registers(client, reg_type, raw_address, 1, slave_id)
                if not resp.isError():
                    if reg_type in ("coil", "discrete"):
                        val = resp.bits[0]
                    else:
                        val = resp.registers[0]
                    found.append((slave_id, val))
                client.close()
            except (SystemExit, Exception):
                # Device didn't respond -- skip
                try:
                    client.close()
                except Exception:
                    pass
                continue

    if found:
        table = Table(title=f"Active Modbus devices @ {serial or host}")
        table.add_column("Slave ID", style="cyan", justify="right")
        table.add_column(f"Register {register}", style="green", justify="right")

        for slave_id, val in found:
            table.add_row(str(slave_id), str(val))

        console.print(table)
        console.print(f"\n[green]Found {len(found)} device(s)[/green]")
    else:
        console.print(f"[yellow]No devices found in range {start}-{end}[/yellow]")


# ---------------------------------------------------------------------------
# WATCH
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("address", type=int)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port. Overrides TCP.")
@click.option("--baudrate", "-b", default=9600, help="Serial baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--count", "-c", default=1, help="Number of registers to watch (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "input", "coil", "discrete"]),
              default=None, help="Register type. Auto-detected if omitted.")
@click.option("--interval", "-i", default=1.0, help="Poll interval in seconds (default: 1.0).")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["decimal", "hex", "bin", "signed"]),
              default="decimal", help="Output format (default: decimal).")
@click.option("--timeout", default=3.0, help="Connection timeout in seconds (default: 3).")
def watch(host, address, port, serial, baudrate, slave, count, reg_type, interval, fmt, timeout):
    """Live-poll Modbus registers. Updates in place. Ctrl+C to stop.

    \b
    Examples:
      modbus watch 192.168.1.10 40001 --count 4
      modbus watch 192.168.1.10 40001 -c 8 -i 0.5 -f hex
      modbus watch --serial /dev/ttyUSB0 0 -c 10 --type holding
    """
    if reg_type:
        detected_type = reg_type
        raw_address = address
    else:
        detected_type, raw_address = _parse_address(address)

    client = _make_client(host, port, serial, baudrate, slave, timeout)
    prev_values = [None] * count

    try:
        with Live(console=console, refresh_per_second=4) as live:
            while True:
                try:
                    resp = _read_registers(client, detected_type, raw_address, count, slave)
                except (SystemExit, Exception):
                    console.print("[red]Connection lost. Reconnecting...[/red]")
                    client.close()
                    client = _make_client(host, port, serial, baudrate, slave, timeout)
                    time.sleep(interval)
                    continue

                if detected_type in ("coil", "discrete"):
                    values = [int(b) for b in resp.bits[:count]]
                else:
                    values = resp.registers

                table = Table(
                    title=f"Watching {detected_type} @ {serial or host} (every {interval}s) -- Ctrl+C to stop"
                )
                table.add_column("Address", style="cyan", justify="right")
                table.add_column("Value", style="green", justify="right")
                table.add_column("Change", justify="right")

                for i, val in enumerate(values):
                    addr_display = address + i
                    formatted = _format_value(val, fmt)

                    if prev_values[i] is not None and val != prev_values[i]:
                        diff = val - prev_values[i]
                        sign = "+" if diff > 0 else ""
                        change = f"[yellow]{sign}{diff}[/yellow]"
                    elif prev_values[i] is None:
                        change = "[dim]--[/dim]"
                    else:
                        change = "[dim]0[/dim]"

                    table.add_row(str(addr_display), formatted, change)

                live.update(table)
                prev_values = list(values)
                time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
    finally:
        client.close()


# ---------------------------------------------------------------------------
# DUMP
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("start_address", type=int)
@click.argument("end_address", type=int)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port. Overrides TCP.")
@click.option("--baudrate", "-b", default=9600, help="Serial baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "input"]),
              default=None, help="Register type. Auto-detected if omitted.")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["decimal", "hex", "bin", "signed"]),
              default="decimal", help="Output format (default: decimal).")
@click.option("--csv", "csv_out", default=None, help="Export to CSV file.")
@click.option("--timeout", default=3.0, help="Connection timeout in seconds (default: 3).")
def dump(host, start_address, end_address, port, serial, baudrate, slave, reg_type, fmt, csv_out, timeout):
    """Dump a range of registers to table or CSV.

    Reads registers from START_ADDRESS to END_ADDRESS inclusive.
    Reads in chunks of 125 (Modbus protocol limit).

    \b
    Examples:
      modbus dump 192.168.1.10 40001 40100
      modbus dump 192.168.1.10 40001 40050 --csv output.csv
      modbus dump 192.168.1.10 40001 40200 -f hex
    """
    if reg_type:
        detected_start = reg_type
        raw_start = start_address
        raw_end = end_address
    else:
        detected_start, raw_start = _parse_address(start_address)
        _, raw_end = _parse_address(end_address)

    total = raw_end - raw_start + 1
    if total <= 0:
        console.print("[red]Error:[/red] END_ADDRESS must be greater than START_ADDRESS.")
        sys.exit(1)

    client = _make_client(host, port, serial, baudrate, slave, timeout)
    all_values = []

    try:
        chunk_size = 125  # Modbus protocol max per request
        offset = 0
        with console.status(f"[cyan]Reading {total} registers...") as status:
            while offset < total:
                n = min(chunk_size, total - offset)
                status.update(f"[cyan]Reading registers {offset + 1}-{offset + n} of {total}...")
                resp = _read_registers(client, detected_start, raw_start + offset, n, slave)
                all_values.extend(resp.registers)
                offset += n
    finally:
        client.close()

    if csv_out:
        import csv
        with open(csv_out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["address", "raw_value", "formatted_value"])
            for i, val in enumerate(all_values):
                addr = start_address + i
                writer.writerow([addr, val, _format_value(val, fmt)])
        console.print(f"[green]Exported {len(all_values)} registers to {csv_out}[/green]")
    else:
        table = Table(title=f"Register dump: {start_address}-{end_address} @ {serial or host}")
        table.add_column("Address", style="cyan", justify="right")
        table.add_column("Raw", style="white", justify="right")
        table.add_column("Value", style="green", justify="right")

        for i, val in enumerate(all_values):
            addr = start_address + i
            table.add_row(str(addr), str(val), _format_value(val, fmt))

        console.print(table)


if __name__ == "__main__":
    cli()
