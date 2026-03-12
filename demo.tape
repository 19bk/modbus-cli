# modbus-cli demo recording
Output demo.gif

Set Shell "zsh"
Set FontSize 14
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set Padding 20

Sleep 300ms

Type "cd /Users/bernard/dev/modbus-cli && source .venv/bin/activate"
Enter
Sleep 1s

# Show the banner
Type "modbus"
Enter
Sleep 2500ms

# Read registers with styled panels
Type "modbus read localhost 40001 -c 10 -p 5020"
Enter
Sleep 3s

# Read in hex format
Type "modbus read localhost 40001 -c 8 -p 5020 -f hex"
Enter
Sleep 3s

# Write a value
Type "modbus write localhost 40001 4242 -p 5020"
Enter
Sleep 2500ms

# Verify the write
Type "modbus read localhost 40001 -c 1 -p 5020"
Enter
Sleep 2500ms

# Scan for devices on the bus
Type "modbus scan localhost --range 1-5 -p 5020"
Enter
Sleep 6s

# Dump a register range
Type "modbus dump localhost 40001 40016 -p 5020"
Enter
Sleep 3s

Sleep 2s
