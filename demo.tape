# modbus-cli demo recording -- high resolution
Output demo.gif

Set Shell "zsh"
Set FontSize 16
Set Width 1400
Set Height 800
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms
Set Padding 30
Set Framerate 30

Sleep 300ms

Type "cd /Users/bernard/dev/modbus-cli && source .venv/bin/activate"
Enter
Sleep 1s

# Show the new readable banner
Type "modbus"
Enter
Sleep 3s

# Read 10 registers with styled panels and value bars
Type "modbus read localhost 40001 -c 10 -p 5020"
Enter
Sleep 3500ms

# Read in hex format
Type "modbus read localhost 40001 -c 8 -p 5020 -f hex"
Enter
Sleep 3500ms

# Write a value and verify
Type "modbus write localhost 40001 4242 -p 5020"
Enter
Sleep 2500ms

Type "modbus read localhost 40001 -c 1 -p 5020"
Enter
Sleep 2500ms

# Scan for devices with animated progress bar
Type "modbus scan localhost --range 1-5 -p 5020"
Enter
Sleep 6s

# Dump registers with progress bar
Type "modbus dump localhost 40001 40016 -p 5020"
Enter
Sleep 4s

# JSON output for scripting
Type "modbus read localhost 40001 -c 4 -p 5020 --json | python3 -m json.tool"
Enter
Sleep 3s

Sleep 2s
