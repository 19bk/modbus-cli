"""Shared theme and styling for modbus-cli."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.theme import Theme

# Color palette -- industrial meets modern
COLORS = {
    "primary": "#00d4aa",      # teal/mint
    "secondary": "#7c6ff7",    # purple
    "accent": "#ff6b6b",       # coral red
    "warning": "#ffd93d",      # gold
    "success": "#6bcb77",      # green
    "muted": "#636e72",        # gray
    "surface": "#2d3436",      # dark bg
    "text": "#dfe6e9",         # light text
    "highlight": "#00cec9",    # bright teal
    "changed": "#fdcb6e",      # amber
    "error": "#e17055",        # warm red
}

custom_theme = Theme({
    "info": Style(color=COLORS["primary"]),
    "warning": Style(color=COLORS["warning"]),
    "error": Style(color=COLORS["error"], bold=True),
    "success": Style(color=COLORS["success"], bold=True),
    "muted": Style(color=COLORS["muted"]),
    "address": Style(color=COLORS["secondary"], bold=True),
    "value": Style(color=COLORS["primary"]),
    "changed": Style(color=COLORS["changed"], bold=True),
    "header": Style(color=COLORS["primary"], bold=True),
    "register": Style(color=COLORS["highlight"]),
})

console = Console(theme=custom_theme)

BANNER = r"""[bold #00d4aa]               _                   _ _ [/]
[bold #1ad4b8]  _ __  ___  __| |__ _  _ ___  __ _| (_)[/]
[bold #33d4c6] | '  \/ _ \/ _` / _` || (_-< / _| | | |[/]
[bold #4dd4d4] |_|_|_\___/\__,_\__,_|\_/__/ \__|_|_|_|[/]
"""

TAGLINE = "[dim]like curl, but for modbus[/dim]"


def banner():
    """Print the animated banner."""
    console.print()
    console.print(BANNER, highlight=False)
    console.print(f"  {TAGLINE}  [dim #636e72]v0.1.0[/]")
    console.print()


def connection_header(target: str, reg_type: str, slave: int):
    """Print a styled connection info bar."""
    conn = Text()
    conn.append("  ", style="bold green")
    conn.append("connected", style="bold #6bcb77")
    conn.append("  ", style="dim")
    conn.append(target, style="bold #00d4aa")
    conn.append("  ", style="dim")
    conn.append(f"slave {slave}", style="#7c6ff7")
    conn.append("  ", style="dim")
    conn.append(reg_type, style="#ff6b6b")
    console.print(Panel(conn, border_style="#636e72", padding=(0, 1)))


def error_panel(message: str):
    """Print an error in a styled panel."""
    console.print(Panel(
        f"[bold #e17055]{message}[/]",
        title="[bold #e17055]error[/]",
        border_style="#e17055",
        padding=(0, 1),
    ))


def success_panel(message: str):
    """Print a success message in a styled panel."""
    console.print(Panel(
        f"[bold #6bcb77]{message}[/]",
        title="[bold #6bcb77]done[/]",
        border_style="#6bcb77",
        padding=(0, 1),
    ))


def value_bar(value: int, max_val: int = 65535, width: int = 20) -> str:
    """Create a mini bar visualization for a register value."""
    if max_val == 0:
        ratio = 0
    else:
        ratio = min(value / max_val, 1.0)
    filled = int(ratio * width)
    empty = width - filled

    # Gradient from teal to purple based on value
    if ratio < 0.33:
        color = "#00d4aa"
    elif ratio < 0.66:
        color = "#7c6ff7"
    else:
        color = "#ff6b6b"

    return f"[{color}]{'━' * filled}[/][dim #636e72]{'─' * empty}[/]"
