# modbus-cli

**Like curl, but for Modbus.**

A dead-simple command-line tool for reading and writing Modbus TCP and RTU registers. No GUI, no config files, no bloat. Just connect and query.

```bash
pip install modbus-cli
```

```
$ modbus read 192.168.1.10 40001 --count 5

  Modbus holding registers @ 192.168.1.10
 ┏━━━━━━━━━┳━━━━━━┳━━━━━━━┓
 ┃ Address ┃  Raw ┃ Value ┃
 ┡━━━━━━━━━╇━━━━━━╇━━━━━━━┩
 │   40001 │  237 │   237 │
 │   40002 │ 1024 │  1024 │
 │   40003 │   58 │    58 │
 │   40004 │  900 │   900 │
 │   40005 │    0 │     0 │
 └─────────┴──────┴───────┘
```

## Why?

Every Modbus device ships with register maps. To test them, you currently need:

- A Windows GUI tool (QModMaster, ModRSsim, Simply Modbus)
- Or a throwaway Python script with pymodbus boilerplate

Neither works well when you're SSH'd into a headless gateway, debugging a PLC at 2am, or just want a quick sanity check.

`modbus-cli` gives you one command. That's it.

## Install

```bash
pip install modbus-cli
```

Requires Python 3.8+. No binary dependencies. Works on Linux, macOS, and Windows.

## Commands

### `modbus read` -- Read registers

```bash
# Read a single holding register
modbus read 192.168.1.10 40001

# Read 10 holding registers
modbus read 192.168.1.10 40001 --count 10

# Read input registers in hex
modbus read 192.168.1.10 30001 --count 4 --format hex

# Read coils
modbus read 192.168.1.10 1 --count 8 --type coil

# Read via serial RTU
modbus read --serial /dev/ttyUSB0 40001 --slave 2 --baudrate 19200

# Signed 16-bit values
modbus read 192.168.1.10 40001 -c 5 -f signed
```

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
# Scan all slave IDs (1-247)
modbus scan 192.168.1.10

# Scan a specific range
modbus scan 192.168.1.10 --range 1-10

# Scan serial bus
modbus scan --serial /dev/ttyUSB0 --range 1-50
```

### `modbus watch` -- Live-poll registers

```bash
# Watch 4 registers, update every second
modbus watch 192.168.1.10 40001 --count 4

# Watch at 500ms intervals in hex
modbus watch 192.168.1.10 40001 -c 8 -i 0.5 -f hex
```

Shows a live-updating table with change detection. Highlights when values change between polls. Press `Ctrl+C` to stop.

### `modbus dump` -- Export register ranges

```bash
# Dump 100 registers to terminal
modbus dump 192.168.1.10 40001 40100

# Export to CSV
modbus dump 192.168.1.10 40001 40200 --csv registers.csv
```

Reads in chunks of 125 registers (Modbus protocol max). Useful for capturing full register maps.

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
