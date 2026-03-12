TITLE: I built curl for Modbus
COVER IMAGE: linkedin_screenshot.png

INSTRUCTIONS:
- Paste everything below the === line into LinkedIn's article editor
- Select each section heading line and click H2 in the toolbar
- Select each command block and click the <> code button in the toolbar
- Select "github.com/19bk/modbus-cli" at the bottom and hyperlink it to https://github.com/19bk/modbus-cli
- Bold the lead-ins marked [BOLD] below, then delete the [BOLD] tags

===

I spent three years as a Device Lifecycle Engineer at KOKO Networks, managing 2,500 IoT fuel dispensing kiosks across Kenya and Rwanda. Every kiosk had Modbus sensors: flow meters measuring ethanol dispensed, level sensors tracking tank volumes, temperature probes watching for overheating. All of them talking RS485 Modbus RTU or TCP back to our systems.

For those outside industrial automation: Modbus is a 45-year-old communication protocol that refuses to die. It's how most industrial sensors and PLCs talk to each other. Every flow meter, every level sensor, every motor controller in a factory or field deployment probably speaks Modbus. The protocol is simple. The tooling around it is not.

The 2am problem

When something went wrong at 2am (and it always did at 2am), debugging meant one of two things. Fire up QModMaster on a Windows laptop and click through its GUI. Or write yet another throwaway Python script with pymodbus boilerplate: import the library, create a client, connect, read registers, close, handle errors, print output. Fifteen lines of code you've written a hundred times before.

Both options are terrible when you're SSH'd into a headless Linux gateway in a fuel depot in Nairobi.

I wanted something like curl. One command, one line, instant result. So I built it.

What modbus-cli does

pip install modbus-curl

Then:

modbus read 192.168.1.10 40001 --count 10
modbus write 192.168.1.10 40001 1234
modbus scan 192.168.1.10 --range 1-10
modbus watch 192.168.1.10 40001 --count 8
modbus dump 192.168.1.10 40001 40200 --csv registers.csv

Five commands. That's the entire tool. Read registers, write values, scan for devices on a bus, watch values live, dump a range to CSV or JSON.

It auto-detects register types from standard Modbus addressing. Type 40001 and it knows you want a holding register. Type 30001 and it reads input registers. This was the single biggest source of confusion on my team at KOKO. Is register 0 the same as 40001? Is it 0-based or 1-based? modbus-cli handles both conventions so you stop wasting time on off-by-one bugs.

The watch dashboard

The read/write/scan commands are useful. The watch mode is where it gets interesting.

I built a full-screen terminal dashboard using Textual, the Python TUI framework from the team behind Rich. It gives you:

- A live data table that updates every poll cycle
- Sparkline history per register showing the last 60 samples
- Change detection with deltas between polls
- A stats bar tracking poll count and timing

Press f to cycle through decimal, hex, binary, and signed formats. Press p to pause. Press r to reset.

This is the feature that would have saved me hours at KOKO. When a flow meter starts drifting, you need to watch the raw register values over time and spot the pattern. Staring at a terminal running a Python while-loop printing numbers is not the way to do that. You need to see the trend. The sparklines give you that instantly.

Design decisions that came from real fieldwork

[BOLD]TCP and serial RTU in the same tool.[BOLD] Our kiosks used TCP gateways at some sites and direct RS485 at others. I didn't want two different tools or two different mental models. Just add --serial /dev/ttyUSB0 and it switches to RTU mode. Same commands, same output.

[BOLD]Styled terminal output with progress bars.[BOLD] This is not cosmetic. When you're scanning through 247 possible slave IDs on a bus, you want to see devices discovered as they appear, not wait thirty seconds for a wall of text at the end. The animated progress bar and live discovery output make that possible.

[BOLD]CSV and JSON export.[BOLD] modbus dump reads registers in chunks of 125 (the Modbus protocol maximum per request) with a progress bar, and writes everything to a file. Add --json to any command and pipe it into jq or feed it into whatever automation you have. One of the first community contributions was adding this JSON output, which tells me other people needed it too.

What happened when I open-sourced it

I pushed the repo on a Saturday. By Monday I had pull requests from two different contributors. One added Docker support. Another added JSON output to every command. A third opened a PR for 32-bit float decoding across register pairs, which is a feature I had on my roadmap but hadn't gotten to yet.

I didn't promote it anywhere at that point. People found it through GitHub's explore page and through keyword searches. That told me something: there's a gap in the tooling. People who work with Modbus devices have been putting up with GUI tools or writing the same boilerplate scripts over and over.

Testing without hardware

You don't need a PLC on your desk to try it. The repo includes a simulator that starts a Modbus TCP server on port 5020 with three slave devices and 100 registers. The values drift every 500ms to simulate real sensor behavior: temperature wanders between 20 and 28 degrees, pressure fluctuates around 1000 mbar, battery voltage slowly drops.

python simulator.py

Then in another terminal:

modbus read localhost 40001 -c 10 -p 5020
modbus watch localhost 40001 -c 8 -p 5020

The drifting values make the watch dashboard sparklines actually move, which is satisfying to watch even if you have no idea what Modbus is.

What I'm building next

[BOLD]Register map files[BOLD], so you can do modbus read --map device.yaml and see "temperature" and "pressure" instead of "40001" and "40005". Anyone who has stared at a register map PDF while cross-referencing hex addresses knows why this matters.

[BOLD]32-bit float decoding[BOLD] across register pairs, with configurable byte and word order. Different manufacturers do this differently, which is one of those things nobody warns you about until you're reading garbage values at 2am.

[BOLD]Modbus ASCII protocol support[BOLD], for the older equipment that still uses it.

If you work with Modbus devices, PLCs, SCADA systems, or any kind of industrial sensor network, give it a try. Feature requests and PRs are welcome.

github.com/19bk/modbus-cli

pip install modbus-curl
