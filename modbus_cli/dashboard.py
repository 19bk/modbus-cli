"""Textual TUI dashboard for modbus watch mode."""

from __future__ import annotations

import time
from collections import deque

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Header, Footer, Static, DataTable, Sparkline, Label
from textual.timer import Timer

from pymodbus.client import ModbusTcpClient, ModbusSerialClient


# ---------------------------------------------------------------------------
# Helper widgets
# ---------------------------------------------------------------------------

class ConnectionStatus(Static):
    """Shows connection state with colored indicator."""

    connected = reactive(False)

    def render(self):
        if self.connected:
            return "  [bold #6bcb77]CONNECTED[/]"
        return "  [bold #e17055]DISCONNECTED[/]"


class RegisterSparkline(Static):
    """Sparkline history for a single register."""

    def __init__(self, label: str, **kwargs):
        super().__init__(**kwargs)
        self.history: deque[float] = deque(maxlen=60)
        self.reg_label = label

    def compose(self) -> ComposeResult:
        yield Label(f"[bold #7c6ff7]{self.reg_label}[/]")
        yield Sparkline([], id=f"spark-{self.reg_label}")

    def update_value(self, value: float):
        self.history.append(value)
        spark = self.query_one(Sparkline)
        spark.data = list(self.history)


class StatsBar(Static):
    """Shows live stats: poll count, min, max, avg."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.poll_count = 0
        self.total_changes = 0
        self.start_time = time.time()

    def update_stats(self, poll_count: int, total_changes: int):
        self.poll_count = poll_count
        self.total_changes = total_changes
        elapsed = time.time() - self.start_time
        rate = self.poll_count / elapsed if elapsed > 0 else 0
        self.update(
            f"  [bold #00d4aa]polls:[/] {self.poll_count}  "
            f"  [bold #fdcb6e]changes:[/] {self.total_changes}  "
            f"  [bold #7c6ff7]rate:[/] {rate:.1f}/s  "
            f"  [dim #636e72]elapsed: {int(elapsed)}s[/]"
        )


# ---------------------------------------------------------------------------
# Main dashboard app
# ---------------------------------------------------------------------------

DASHBOARD_CSS = """
Screen {
    background: #1a1a2e;
}

Header {
    background: #16213e;
    color: #00d4aa;
}

Footer {
    background: #16213e;
}

#main-container {
    height: 1fr;
}

#table-panel {
    height: 1fr;
    border: round #636e72;
    padding: 0 1;
}

#sparkline-panel {
    height: auto;
    max-height: 30;
    border: round #636e72;
    padding: 0 1;
}

#stats-bar {
    height: 1;
    background: #16213e;
    color: #dfe6e9;
}

#connection-status {
    height: 1;
    background: #16213e;
    dock: top;
}

DataTable {
    height: 1fr;
}

DataTable > .datatable--header {
    background: #16213e;
    color: #00d4aa;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #2d3436;
    color: #00d4aa;
}

DataTable > .datatable--even-row {
    background: #1a1a2e;
}

DataTable > .datatable--odd-row {
    background: #16213e;
}

Sparkline {
    height: 3;
    margin: 0 0 1 0;
}

Sparkline > .sparkline--max-color {
    color: #00d4aa;
}

Sparkline > .sparkline--min-color {
    color: #16213e;
}

RegisterSparkline {
    height: auto;
    padding: 0 1;
}
"""


class ModbusDashboard(App):
    """Live Modbus register dashboard."""

    CSS = DASHBOARD_CSS
    TITLE = "modbus-cli watch"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reset", "Reset stats"),
        ("f", "cycle_format", "Cycle format"),
        ("p", "toggle_pause", "Pause/Resume"),
    ]

    paused = reactive(False)

    def __init__(
        self,
        host: str,
        address: int,
        raw_address: int,
        reg_type: str,
        port: int = 502,
        serial_port: str | None = None,
        baudrate: int = 9600,
        slave: int = 1,
        count: int = 1,
        interval: float = 1.0,
        fmt: str = "decimal",
        timeout: float = 3.0,
    ):
        super().__init__()
        self.host = host
        self.address = address
        self.raw_address = raw_address
        self.reg_type = reg_type
        self.port = port
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.slave = slave
        self.count = count
        self.interval = interval
        self.fmt = fmt
        self.timeout = timeout
        self.formats = ["decimal", "hex", "bin", "signed"]
        self.fmt_index = self.formats.index(fmt)
        self.client = None
        self.prev_values: list[int | None] = [None] * count
        self.poll_count = 0
        self.total_changes = 0
        self.sparklines: list[RegisterSparkline] = []
        self.poll_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        target = self.serial_port or f"{self.host}:{self.port}"
        yield Header()
        yield ConnectionStatus(id="connection-status")
        with Vertical(id="main-container"):
            with Vertical(id="table-panel"):
                yield DataTable(id="reg-table")
            if self.count <= 8:
                with Vertical(id="sparkline-panel"):
                    for i in range(self.count):
                        addr = self.address + i
                        sl = RegisterSparkline(str(addr), id=f"reg-spark-{i}")
                        self.sparklines.append(sl)
                        yield sl
        yield StatsBar(id="stats-bar")
        yield Footer()

    def on_mount(self):
        table = self.query_one("#reg-table", DataTable)
        table.add_column("Address", key="addr")
        table.add_column("Value", key="val")
        table.add_column("Raw", key="raw")
        table.add_column("Change", key="change")
        table.add_column("", key="bar")
        table.cursor_type = "row"
        table.zebra_stripes = True

        for i in range(self.count):
            addr = self.address + i
            table.add_row(
                str(addr), "--", "--", "--", "",
                key=str(i),
            )

        self._connect()
        self.poll_timer = self.set_interval(self.interval, self._poll)

    def _connect(self):
        try:
            if self.serial_port:
                self.client = ModbusSerialClient(
                    port=self.serial_port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    parity="N", stopbits=1, bytesize=8,
                )
            else:
                self.client = ModbusTcpClient(
                    host=self.host, port=self.port, timeout=self.timeout,
                )
            connected = self.client.connect()
            status = self.query_one("#connection-status", ConnectionStatus)
            status.connected = connected
        except Exception:
            status = self.query_one("#connection-status", ConnectionStatus)
            status.connected = False

    def _format_value(self, value: int) -> str:
        if self.fmt == "hex":
            return f"0x{value:04X}"
        elif self.fmt == "bin":
            return f"{value:016b}"
        elif self.fmt == "signed":
            return str(value - 65536 if value > 32767 else value)
        return str(value)

    def _poll(self):
        if self.paused or self.client is None:
            return

        try:
            readers = {
                "holding": self.client.read_holding_registers,
                "input": self.client.read_input_registers,
                "coil": self.client.read_coils,
                "discrete": self.client.read_discrete_inputs,
            }
            resp = readers[self.reg_type](
                self.raw_address, count=self.count, slave=self.slave,
            )
            if resp.isError():
                return

            if self.reg_type in ("coil", "discrete"):
                values = [int(b) for b in resp.bits[:self.count]]
            else:
                values = list(resp.registers)

        except Exception:
            status = self.query_one("#connection-status", ConnectionStatus)
            status.connected = False
            self._connect()
            return

        status = self.query_one("#connection-status", ConnectionStatus)
        status.connected = True
        self.poll_count += 1

        table = self.query_one("#reg-table", DataTable)
        for i, val in enumerate(values):
            addr = self.address + i
            formatted = self._format_value(val)
            prev = self.prev_values[i]

            if prev is not None and val != prev:
                diff = val - prev
                sign = "+" if diff > 0 else ""
                change = f"{sign}{diff}"
                self.total_changes += 1
                change_display = change
            elif prev is None:
                change_display = "--"
            else:
                change_display = "."

            # Value bar
            ratio = min(val / 65535, 1.0) if self.reg_type not in ("coil", "discrete") else val
            bar_len = 15
            filled = int(ratio * bar_len)
            bar = ("█" * filled) + ("░" * (bar_len - filled))

            table.update_cell(str(i), "addr", str(addr))
            table.update_cell(str(i), "val", formatted)
            table.update_cell(str(i), "raw", str(val))
            table.update_cell(str(i), "change", change_display)
            table.update_cell(str(i), "bar", bar)

            # Update sparklines
            if i < len(self.sparklines):
                self.sparklines[i].update_value(float(val))

        self.prev_values = values

        stats = self.query_one("#stats-bar", StatsBar)
        stats.update_stats(self.poll_count, self.total_changes)

    def action_quit(self):
        if self.client:
            self.client.close()
        self.exit()

    def action_reset(self):
        self.poll_count = 0
        self.total_changes = 0
        self.prev_values = [None] * self.count
        stats = self.query_one("#stats-bar", StatsBar)
        stats.start_time = time.time()
        stats.update_stats(0, 0)

    def action_cycle_format(self):
        self.fmt_index = (self.fmt_index + 1) % len(self.formats)
        self.fmt = self.formats[self.fmt_index]
        self.sub_title = f"format: {self.fmt}"

    def action_toggle_pause(self):
        self.paused = not self.paused
        self.sub_title = "PAUSED" if self.paused else ""
