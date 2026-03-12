I spent three years managing 2,500 IoT fuel dispensing kiosks across Kenya and Rwanda. Every one of them had Modbus sensors: flow meters, level sensors, temperature probes, all talking RS485 Modbus RTU or TCP.

When something went wrong at 2am (and it always did at 2am), debugging meant one of two things: fire up QModMaster on a Windows laptop, or write yet another throwaway Python script with pymodbus boilerplate.

Both options are terrible when you're SSH'd into a headless Linux gateway in the field.

So I built modbus-cli. It's curl for Modbus.

## What it does

One command. No config files. No GUI.

```bash
pip install modbus-curl
```

```bash
# Read 10 holding registers
modbus read 192.168.1.10 40001 --count 10

# Write a value
modbus write 192.168.1.10 40001 1234

# Find all devices on a bus
modbus scan 192.168.1.10 --range 1-10

# Live monitoring dashboard
modbus watch 192.168.1.10 40001 --count 8

# Dump 200 registers to CSV
modbus dump 192.168.1.10 40001 40200 --csv registers.csv

# JSON output for scripting
modbus read 192.168.1.10 40001 -c 5 --json | jq '.registers[].value'
```

It auto-detects register types from standard Modbus addressing. Type `40001` and it knows you want a holding register. Type `30001` and it reads input registers. No flags needed.

## The watch mode is where it gets interesting

I built the monitoring dashboard with Textual, the Python TUI framework from the Rich team. It gives you a full-screen terminal app with:

* Live data table that updates every poll cycle
* Sparkline history per register (last 60 samples)
* Change detection showing deltas between polls
* Stats bar tracking poll count, change rate, and timing

Keybindings: `q` to quit, `f` to cycle between decimal/hex/binary/signed, `p` to pause, `r` to reset stats.

This is the feature that would have saved me hours at KOKO. When a flow meter starts drifting, you need to watch the raw register values over time and spot the pattern. Staring at a terminal running `while True: print(client.read_holding_registers(...))` is not it.

## The design choices

**Standard Modbus addressing.** This was the #1 source of confusion for everyone on my team. Is register 0 the same as 40001? Is it 0-based or 1-based? modbus-cli handles both. If you type `40001`, it subtracts 40001 and reads holding register 0. If you type `0 --type holding`, it reads the same thing. No more off-by-one debugging.

**TCP and serial RTU in the same tool.** Just add `--serial /dev/ttyUSB0` and it switches to RTU mode. Same commands, same output. I needed this because our kiosks used TCP gateways in some sites and direct RS485 in others.

**Styled terminal output.** Every command shows colored panels, connection status, and value bars. This isn't just cosmetic. When you're scanning through 247 slave IDs, you want to see results as they come in, not wait for a wall of text at the end. The progress bars and live discovery output make that possible.

**CSV and JSON export.** `modbus dump 192.168.1.10 40001 40500 --csv device_map.csv` reads registers in chunks of 125 (the Modbus protocol max per request) and writes everything to a file. Add `--json` to any read, scan, or dump command to get structured output you can pipe into `jq` or feed into automation scripts.

## How I tested it without hardware

The repo includes a simulator:

```bash
python simulator.py
```

It starts a Modbus TCP server on port 5020 with three slave devices and 100 registers. The values drift every 500ms to simulate real sensor behavior: temperature wanders between 20-28C, pressure fluctuates around 1000 mbar, battery voltage slowly drops.

Then in another terminal:

```bash
modbus read localhost 40001 -c 10 -p 5020
modbus watch localhost 40001 -c 8 -p 5020
```

The drifting values make the watch dashboard sparklines come alive.

## What's next

The project already has its first contributor and Docker support. The short list of features I'm working on:

* Register map files (`modbus read --map device.yaml`) so you see `temperature` instead of `40001`
* 32-bit float decoding across register pairs (`--float` with byte/word order options)
* Modbus ASCII protocol support

If you work with Modbus devices and want a feature, open an issue. PRs welcome.

The repo: [github.com/19bk/modbus-cli](https://github.com/19bk/modbus-cli)

```bash
pip install modbus-curl
```
