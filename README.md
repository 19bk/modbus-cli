# modbus-cli

```
  __  __  ___  ___  ___  _   _ ___        ___ _    ___
 |  \/  |/ _ \|   \| _ )| | | / __|  ___ / __| |  |_ _|
 | |\/| | (_) | |) | _ \| |_| \__ \ |___| (__| |__ | |
 |_|  |_|\___/|___/|___/ \___/|___/      \___|____|___|
```

**Like curl, but for Modbus.**

A dead-simple command-line tool for reading and writing Modbus TCP and RTU registers. Beautiful terminal UI. No GUI, no config files, no bloat.

```bash
pip install modbus-curl
```

![modbus-cli demo](demo.gif)

## Features

- **Styled output** -- color-coded panels, value bars, gradient theme
- **Live dashboard** -- full-screen TUI with sparkline history, change detection, and keybindings (powered by [Textual](https://github.com/Textualize/textual))
- **Smart addressing** -- auto-detects register type from standard Modbus notation (40001 = holding, 30001 = input, etc.)
- **TCP + Serial RTU** -- works with network devices and serial RS485 buses
- **Multiple formats** -- decimal, hex, binary, signed 16-bit
- **Progress bars** -- animated scan and dump with real-time feedback
- **CSV export** -- dump register maps straight to file
- **JSON output** -- pipe read/scan/dump output into jq and automation tools

## Quick Start

```bash
# Read 5 holding registers
modbus read 192.168.1.10 40001 --count 5

# Write a value
modbus write 192.168.1.10 40001 1234

# Scan for devices on the bus
modbus scan 192.168.1.10 --range 1-10

# Open live monitoring dashboard
modbus watch 192.168.1.10 40001 --count 8

# Dump 200 registers to CSV
modbus dump 192.168.1.10 40001 40200 --csv registers.csv
```

## Why?

Every Modbus device ships with register maps. To test them, you currently need:

- A Windows GUI tool (QModMaster, ModRSsim, Simply Modbus)
- Or a throwaway Python script with pymodbus boilerplate

Neither works well when you're SSH'd into a headless gateway, debugging a PLC at 2am, or just want a quick sanity check.

`modbus-cli` gives you one command. That's it.

## Install

```bash
pip install modbus-curl
```

Requires Python 3.8+. No binary dependencies. Works on Linux, macOS, and Windows.

### Docker

```bash
# Build local image
docker build -t 19bk/modbus-cli .

# Run a command inside the container
docker run --rm 19bk/modbus-cli read 192.168.1.10 40001 -c 10
```

## Commands

### `modbus read` -- Read registers

```bash
# Read a single holding register
modbus read 192.168.1.10 40001

# Read 10 holding registers with value bars
modbus read 192.168.1.10 40001 --count 10

# Read input registers in hex
modbus read 192.168.1.10 30001 --count 4 --format hex

# Read coils
modbus read 192.168.1.10 1 --count 8 --type coil

# Read via serial RTU
modbus read --serial /dev/ttyUSB0 40001 --slave 2 --baudrate 19200

# Signed 16-bit values
modbus read 192.168.1.10 40001 -c 5 -f signed

# JSON output for scripting
modbus read 192.168.1.10 40001 -c 5 --json | jq '.registers[].value'
```

Output includes styled panels, connection status, and visual value bars showing register magnitude at a glance.

**Address notation:** Uses standard Modbus addressing. `40001`-`49999` = holding registers, `30001`-`39999` = input registers, `10001`-`19999` = discrete inputs, `1`-`9999` = coils. Or pass raw 0-based addresses with `--type`.

### `modbus write` -- Write registers

```bash
# Write a single holding register
modbus write 192.168.1.10 40001 1234

# Write multiple registers
modbus write 192.168.1.10 40001 100 200 300

# Write a coil ON
modbus write 192.168.1.10 1 1 --type coil
```

### `modbus scan` -- Find active devices

```bash
# Scan all slave IDs (1-247) with animated progress bar
modbus scan 192.168.1.10

# Scan a specific range
modbus scan 192.168.1.10 --range 1-10

# Scan serial bus
modbus scan --serial /dev/ttyUSB0 --range 1-50

# JSON output
modbus scan 192.168.1.10 --range 1-10 --json
```

Devices are reported as they're found, with a progress bar showing scan completion.

### `modbus watch` -- Live monitoring dashboard

```bash
# Watch 4 registers with full-screen TUI
modbus watch 192.168.1.10 40001 --count 4

# Watch at 500ms intervals in hex
modbus watch 192.168.1.10 40001 -c 8 -i 0.5 -f hex
```

Opens a full-screen Textual dashboard with:

- **Live data table** with zebra-striped rows
- **Sparkline history** per register (up to 60 samples)
- **Change detection** showing deltas between polls
- **Stats bar** with poll count, change count, and polling rate

**Keybindings:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Reset stats and history |
| `f` | Cycle format (decimal / hex / bin / signed) |
| `p` | Pause / resume polling |

### `modbus dump` -- Export register ranges

```bash
# Dump 100 registers to terminal with progress bar
modbus dump 192.168.1.10 40001 40100

# Export to CSV
modbus dump 192.168.1.10 40001 40200 --csv registers.csv

# Dump in hex format
modbus dump 192.168.1.10 40001 40200 -f hex

# Dump as JSON
modbus dump 192.168.1.10 40001 40020 --json
```

Reads in chunks of 125 registers (Modbus protocol max). Shows an animated progress bar for large ranges.

## Options

| Flag | Short | Description |
|------|-------|-------------|
| `--port` | `-p` | TCP port (default: 502) |
| `--serial` | `-s` | Serial port (e.g. `/dev/ttyUSB0`), overrides TCP |
| `--baudrate` | `-b` | Serial baud rate (default: 9600) |
| `--slave` | `-u` | Slave/unit ID (default: 1) |
| `--count` | `-c` | Number of registers to read (default: 1) |
| `--type` | `-t` | Register type: holding, input, coil, discrete |
| `--format` | `-f` | Output format: decimal, hex, bin, signed |
| `--timeout` | | Connection timeout in seconds (default: 3) |

## Common Workflows

**Quick register check on a field device:**
```bash
modbus read 10.0.0.50 40001 -c 20 -f hex
```

**Find all devices on a serial bus:**
```bash
modbus scan --serial /dev/ttyUSB0 --range 1-50 --timeout 0.3
```

**Monitor a sensor value live:**
```bash
modbus watch 192.168.1.10 40010 -i 0.5
```

**Dump a full register map for documentation:**
```bash
modbus dump 192.168.1.10 40001 40500 --csv device_map.csv
```

**Compare before/after a config change:**
```bash
modbus dump 192.168.1.10 40001 40050 --csv before.csv
# ... make changes ...
modbus dump 192.168.1.10 40001 40050 --csv after.csv
diff before.csv after.csv
```

## Built With

- [pymodbus](https://github.com/pymodbus-dev/pymodbus) -- Modbus protocol implementation
- [Click](https://click.palletsprojects.com/) -- CLI framework
- [Rich](https://github.com/Textualize/rich) -- Terminal formatting and styled output
- [Textual](https://github.com/Textualize/textual) -- TUI framework for the watch dashboard

## Development

```bash
git clone https://github.com/19bk/modbus-cli.git
cd modbus-cli
python -m venv .venv
source .venv/bin/activate
pip install -e .
modbus --help
```

## Contributing

Issues and PRs welcome. If you work with Modbus devices and want a feature, open an issue describing your use case.

## License

MIT
