"""modbus-cli: Like curl, but for Modbus."""

import json
import sys
import time

import click
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

from .theme import console, banner, connection_header, error_panel, success_panel, value_bar

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_address(address: int):
    """Parse Modbus address, handling standard notation (40001, 30001, etc)."""
    if 40001 <= address <= 49999:
        return "holding", address - 40001
    elif 30001 <= address <= 39999:
        return "input", address - 30001
    elif 10001 <= address <= 19999:
        return "discrete", address - 10001
    elif 1 <= address <= 9999:
        return "coil", address - 1
    else:
        return "holding", address


def _make_client(host, port, serial, baudrate, slave_id, timeout):
    """Create a Modbus TCP or RTU serial client."""
    if serial:
        client = ModbusSerialClient(
            port=serial, baudrate=baudrate, timeout=timeout,
            parity="N", stopbits=1, bytesize=8,
        )
    else:
        client = ModbusTcpClient(host=host, port=port, timeout=timeout)

    if not client.connect():
        error_panel(f"Could not connect to {serial or f'{host}:{port}'}")
        sys.exit(1)
    return client


def _read_registers(client, reg_type, address, count, slave, silent=False):
    """Read registers by type. If silent=True, return None on error instead of exiting."""
    readers = {
        "holding": client.read_holding_registers,
        "input": client.read_input_registers,
        "coil": client.read_coils,
        "discrete": client.read_discrete_inputs,
    }
    resp = readers[reg_type](address, count=count, **_slave_kwarg(slave))
    if resp.isError():
        if silent:
            return None
        error_panel(f"Modbus error: {resp}")
        sys.exit(1)
    return resp


def _slave_kwarg(slave_id: int) -> dict:
    """Return the correct keyword arg for the installed pymodbus version.

    pymodbus <3.7 uses 'slave', >=3.7 uses 'device_id'.
    """
    import pymodbus
    major, minor = (int(x) for x in pymodbus.__version__.split(".")[:2])
    if major >= 4 or (major == 3 and minor >= 7):
        return {"device_id": slave_id}
    return {"slave": slave_id}


def _format_value(value, fmt):
    """Format a register value."""
    if fmt == "hex":
        return f"0x{value:04X}"
    elif fmt == "bin":
        return f"{value:016b}"
    elif fmt == "signed":
        return str(value - 65536 if value > 32767 else value)
    return str(value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.version_option(package_name="modbus-cli")
@click.pass_context
def cli(ctx):
    """Like curl, but for Modbus.

    \b
    Read and write Modbus TCP/RTU registers from your terminal.

    \b
    Quick start:
      modbus read 192.168.1.10 40001
      modbus read 192.168.1.10 40001 --count 10
      modbus write 192.168.1.10 40001 1234
      modbus scan 192.168.1.10
      modbus watch 192.168.1.10 40001 --count 4
    """
    if ctx.invoked_subcommand is None:
        banner()
        console.print(ctx.get_help())


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("address", type=int)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port (e.g. /dev/ttyUSB0).")
@click.option("--baudrate", "-b", default=9600, help="Baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--count", "-c", default=1, help="Number of registers (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "input", "coil", "discrete"]),
              default=None, help="Register type. Auto-detected if omitted.")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["decimal", "hex", "bin", "signed"]),
              default="decimal", help="Output format (default: decimal).")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--timeout", default=3.0, help="Timeout in seconds (default: 3).")
def read(host, address, port, serial, baudrate, slave, count, reg_type, fmt, json_output, timeout):
    """Read Modbus registers.

    \b
    ADDRESS uses standard Modbus notation:
      40001-49999  holding registers
      30001-39999  input registers
      10001-19999  discrete inputs
      00001-09999  coils
    """
    if reg_type:
        detected_type, raw_address = reg_type, address
    else:
        detected_type, raw_address = _parse_address(address)

    target = serial or f"{host}:{port}"

    if json_output:
        client = _make_client(host, port, serial, baudrate, slave, timeout)
        try:
            resp = _read_registers(client, detected_type, raw_address, count, slave)
        finally:
            client.close()

        if detected_type in ("coil", "discrete"):
            values = resp.bits[:count]
        else:
            values = resp.registers

        registers = []
        for i, val in enumerate(values):
            addr_display = address + i if not reg_type else raw_address + i
            int_val = int(val)
            formatted = _format_value(int_val, fmt) if not isinstance(val, bool) else str(int_val)
            registers.append({"address": addr_display, "raw": int_val, "value": formatted})

        click.echo(json.dumps({
            "host": host,
            "target": target,
            "type": detected_type,
            "slave": slave,
            "registers": registers,
        }))
        return

    console.print()

    with console.status(f"[#00d4aa]  Connecting to {target}...[/]", spinner="dots"):
        client = _make_client(host, port, serial, baudrate, slave, timeout)

    connection_header(target, detected_type, slave)

    with console.status(f"[#00d4aa]  Reading {count} {detected_type} register(s)...[/]", spinner="dots"):
        try:
            resp = _read_registers(client, detected_type, raw_address, count, slave)
        finally:
            client.close()

    if detected_type in ("coil", "discrete"):
        values = resp.bits[:count]
    else:
        values = resp.registers

    table = Table(
        show_header=True,
        header_style="bold #00d4aa",
        border_style="#636e72",
        title_style="bold #7c6ff7",
        row_styles=["", "dim"],
        pad_edge=True,
        expand=False,
    )
    table.add_column("Address", style="bold #7c6ff7", justify="right", min_width=8)
    table.add_column("Value", style="bold #00d4aa", justify="right", min_width=10)
    table.add_column("Raw", style="#dfe6e9", justify="right", min_width=8)
    if detected_type not in ("coil", "discrete"):
        table.add_column("Bar", min_width=22, no_wrap=True)

    for i, val in enumerate(values):
        addr_display = address + i if not reg_type else raw_address + i
        int_val = int(val)
        formatted = _format_value(int_val, fmt) if not isinstance(val, bool) else str(int_val)
        raw_str = str(int_val)

        row = [str(addr_display), formatted, raw_str]
        if detected_type not in ("coil", "discrete"):
            row.append(value_bar(int_val))
        table.add_row(*row)

    console.print(Panel(
        table,
        border_style="#636e72",
        title=f"[bold #00d4aa]{detected_type}[/] [dim]registers[/]",
        subtitle=f"[dim]{count} register(s) from {target}[/]",
        padding=(1, 2),
    ))
    console.print()


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("address", type=int)
@click.argument("values", type=int, nargs=-1, required=True)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port.")
@click.option("--baudrate", "-b", default=9600, help="Baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "coil"]),
              default=None, help="Register type. Auto-detected if omitted.")
@click.option("--timeout", default=3.0, help="Timeout in seconds (default: 3).")
def write(host, address, values, port, serial, baudrate, slave, reg_type, timeout):
    """Write values to Modbus registers.

    \b
    Examples:
      modbus write 192.168.1.10 40001 100
      modbus write 192.168.1.10 40001 100 200 300
      modbus write 192.168.1.10 1 1 --type coil
    """
    if reg_type:
        detected_type, raw_address = reg_type, address
    else:
        detected_type, raw_address = _parse_address(address)

    if detected_type not in ("holding", "coil"):
        error_panel(f"Cannot write to {detected_type} registers (read-only)")
        sys.exit(1)

    target = serial or f"{host}:{port}"
    console.print()

    with console.status(f"[#00d4aa]  Connecting to {target}...[/]", spinner="dots"):
        client = _make_client(host, port, serial, baudrate, slave, timeout)

    connection_header(target, detected_type, slave)

    try:
        skw = _slave_kwarg(slave)
        if detected_type == "coil":
            if len(values) == 1:
                resp = client.write_coil(raw_address, bool(values[0]), **skw)
            else:
                resp = client.write_coils(raw_address, [bool(v) for v in values], **skw)
        else:
            if len(values) == 1:
                resp = client.write_register(raw_address, values[0], **skw)
            else:
                resp = client.write_registers(raw_address, list(values), **skw)

        if resp.isError():
            error_panel(f"Modbus error: {resp}")
            sys.exit(1)
    finally:
        client.close()

    vals_str = ", ".join(f"[bold #00d4aa]{v}[/]" for v in values)
    success_panel(
        f"Wrote [{vals_str}] to {detected_type} register(s) "
        f"starting at [bold #7c6ff7]{address}[/] (slave {slave})"
    )
    console.print()


# ---------------------------------------------------------------------------
# SCAN
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port.")
@click.option("--baudrate", "-b", default=9600, help="Baud rate (default: 9600).")
@click.option("--range", "-r", "scan_range", default="1-247",
              help="Slave ID range (default: 1-247).")
@click.option("--register", default=40001, help="Test register (default: 40001).")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--timeout", default=0.5, help="Per-device timeout (default: 0.5).")
def scan(host, port, serial, baudrate, scan_range, register, json_output, timeout):
    """Scan for active Modbus devices on the bus.

    \b
    Examples:
      modbus scan 192.168.1.10
      modbus scan 192.168.1.10 --range 1-10
      modbus scan --serial /dev/ttyUSB0 --range 1-50
    """
    start, end = scan_range.split("-")
    start, end = int(start), int(end)
    total = end - start + 1

    reg_type, raw_address = _parse_address(register)
    target = serial or f"{host}:{port}"
    found = []

    if json_output:
        for slave_id in range(start, end + 1):
            try:
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
                    continue

                resp = _read_registers(client, reg_type, raw_address, 1, slave_id, silent=True)
                if resp is not None:
                    val = resp.bits[0] if reg_type in ("coil", "discrete") else resp.registers[0]
                    found.append({"slave": slave_id, "value": int(val)})
                client.close()
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass

        click.echo(json.dumps({
            "host": host,
            "target": target,
            "register": register,
            "type": reg_type,
            "range": {"start": start, "end": end},
            "devices": found,
        }))
        return

    console.print()

    with Progress(
        SpinnerColumn("dots", style="#00d4aa"),
        TextColumn("[bold #00d4aa]Scanning[/]"),
        BarColumn(
            bar_width=40,
            style="#636e72",
            complete_style="#00d4aa",
            finished_style="#6bcb77",
        ),
        TextColumn("[#7c6ff7]{task.percentage:>3.0f}%[/]"),
        TextColumn("[dim]slave {task.fields[current_id]}[/]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("scan", total=total, current_id=start)

        for slave_id in range(start, end + 1):
            progress.update(task, advance=1, current_id=slave_id)
            try:
                client = _make_client(host, port, serial, baudrate, slave_id, timeout)
                resp = _read_registers(client, reg_type, raw_address, 1, slave_id, silent=True)
                if resp is not None:
                    val = resp.bits[0] if reg_type in ("coil", "discrete") else resp.registers[0]
                    found.append((slave_id, val))
                    progress.console.print(
                        f"  [bold #6bcb77]  Found slave {slave_id}[/] "
                        f"[dim]register {register} = {val}[/]"
                    )
                client.close()
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass

    console.print()

    if found:
        table = Table(
            show_header=True,
            header_style="bold #00d4aa",
            border_style="#636e72",
            row_styles=["", "dim"],
        )
        table.add_column("Slave ID", style="bold #7c6ff7", justify="right")
        table.add_column(f"Register {register}", style="#00d4aa", justify="right")
        table.add_column("Status", justify="center")

        for slave_id, val in found:
            table.add_row(str(slave_id), str(val), "[bold #6bcb77]ONLINE[/]")

        console.print(Panel(
            table,
            border_style="#6bcb77",
            title=f"[bold #6bcb77]  {len(found)} device(s) found[/]",
            subtitle=f"[dim]scanned {target} IDs {scan_range}[/]",
            padding=(1, 2),
        ))
    else:
        console.print(Panel(
            f"[#ffd93d]No devices responded in range {scan_range}[/]",
            border_style="#ffd93d",
            title="[bold #ffd93d]scan complete[/]",
            padding=(0, 1),
        ))
    console.print()


# ---------------------------------------------------------------------------
# WATCH (launches Textual dashboard)
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("address", type=int)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port.")
@click.option("--baudrate", "-b", default=9600, help="Baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--count", "-c", default=1, help="Number of registers (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "input", "coil", "discrete"]),
              default=None, help="Register type. Auto-detected if omitted.")
@click.option("--interval", "-i", default=1.0, help="Poll interval in seconds (default: 1.0).")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["decimal", "hex", "bin", "signed"]),
              default="decimal", help="Output format (default: decimal).")
@click.option("--timeout", default=3.0, help="Timeout in seconds (default: 3).")
def watch(host, address, port, serial, baudrate, slave, count, reg_type, interval, fmt, timeout):
    """Live dashboard for monitoring Modbus registers.

    Opens a full-screen TUI with live data table, sparkline history,
    and change detection. Press q to quit.

    \b
    Keybindings:
      q  quit
      r  reset stats
      f  cycle format (decimal/hex/bin/signed)
      p  pause/resume polling

    \b
    Examples:
      modbus watch 192.168.1.10 40001 --count 4
      modbus watch 192.168.1.10 40001 -c 8 -i 0.5 -f hex
    """
    if reg_type:
        detected_type, raw_address = reg_type, address
    else:
        detected_type, raw_address = _parse_address(address)

    from .dashboard import ModbusDashboard

    app = ModbusDashboard(
        host=host,
        address=address,
        raw_address=raw_address,
        reg_type=detected_type,
        port=port,
        serial_port=serial,
        baudrate=baudrate,
        slave=slave,
        count=count,
        interval=interval,
        fmt=fmt,
        timeout=timeout,
    )
    app.run()


# ---------------------------------------------------------------------------
# DUMP
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("host", default="localhost")
@click.argument("start_address", type=int)
@click.argument("end_address", type=int)
@click.option("--port", "-p", default=502, help="TCP port (default: 502).")
@click.option("--serial", "-s", default=None, help="Serial port.")
@click.option("--baudrate", "-b", default=9600, help="Baud rate (default: 9600).")
@click.option("--slave", "-u", default=1, help="Slave/unit ID (default: 1).")
@click.option("--type", "-t", "reg_type",
              type=click.Choice(["holding", "input"]),
              default=None, help="Register type. Auto-detected if omitted.")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["decimal", "hex", "bin", "signed"]),
              default="decimal", help="Output format (default: decimal).")
@click.option("--csv", "csv_out", default=None, help="Export to CSV file.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--timeout", default=3.0, help="Timeout in seconds (default: 3).")
def dump(host, start_address, end_address, port, serial, baudrate, slave, reg_type, fmt, csv_out, json_output, timeout):
    """Dump a range of registers to table or CSV.

    \b
    Examples:
      modbus dump 192.168.1.10 40001 40100
      modbus dump 192.168.1.10 40001 40050 --csv output.csv
      modbus dump 192.168.1.10 40001 40200 -f hex
    """
    if reg_type:
        detected_start = reg_type
        raw_start, raw_end = start_address, end_address
    else:
        detected_start, raw_start = _parse_address(start_address)
        _, raw_end = _parse_address(end_address)

    total = raw_end - raw_start + 1
    if total <= 0:
        error_panel("END_ADDRESS must be greater than START_ADDRESS")
        sys.exit(1)

    target = serial or f"{host}:{port}"
    console.print()

    with console.status(f"[#00d4aa]  Connecting to {target}...[/]", spinner="dots"):
        client = _make_client(host, port, serial, baudrate, slave, timeout)

    connection_header(target, detected_start, slave)
    all_values = []

    try:
        chunk_size = 125
        with Progress(
            SpinnerColumn("dots", style="#00d4aa"),
            TextColumn("[bold #00d4aa]Dumping[/]"),
            BarColumn(
                bar_width=40,
                style="#636e72",
                complete_style="#00d4aa",
                finished_style="#6bcb77",
            ),
            TextColumn("[#7c6ff7]{task.percentage:>3.0f}%[/]"),
            TextColumn("[dim]{task.fields[regs_done]}/{task.fields[regs_total]} registers[/]"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("dump", total=total, regs_done=0, regs_total=total)
            offset = 0
            while offset < total:
                n = min(chunk_size, total - offset)
                resp = _read_registers(client, detected_start, raw_start + offset, n, slave)
                all_values.extend(resp.registers)
                offset += n
                progress.update(task, advance=n, regs_done=offset)
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
        success_panel(f"Exported {len(all_values)} registers to [bold]{csv_out}[/]")
    elif json_output:
        registers = []
        for i, val in enumerate(all_values):
            addr = start_address + i
            registers.append({
                "address": addr,
                "raw": int(val),
                "value": _format_value(val, fmt),
            })
        click.echo(json.dumps({
            "host": host,
            "target": target,
            "type": detected_start,
            "slave": slave,
            "start_address": start_address,
            "end_address": end_address,
            "registers": registers,
        }))
    else:
        table = Table(
            show_header=True,
            header_style="bold #00d4aa",
            border_style="#636e72",
            row_styles=["", "dim"],
        )
        table.add_column("Address", style="bold #7c6ff7", justify="right", min_width=8)
        table.add_column("Value", style="bold #00d4aa", justify="right", min_width=10)
        table.add_column("Raw", style="#dfe6e9", justify="right", min_width=8)
        table.add_column("Bar", min_width=22, no_wrap=True)

        for i, val in enumerate(all_values):
            addr = start_address + i
            table.add_row(str(addr), _format_value(val, fmt), str(val), value_bar(val))

        console.print(Panel(
            table,
            border_style="#636e72",
            title=f"[bold #00d4aa]register dump[/] [dim]{start_address}-{end_address}[/]",
            subtitle=f"[dim]{len(all_values)} registers from {target}[/]",
            padding=(1, 2),
        ))

    console.print()


if __name__ == "__main__":
    cli()
