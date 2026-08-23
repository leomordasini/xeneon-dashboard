'' Xeneon Dashboard — Silent Background Launcher
'' Run this at login via Task Scheduler (already registered by setup_autostart.bat)
'' No terminal window will appear.

Dim sh
Set sh = CreateObject("WScript.Shell")

Dim dir
dir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' Start server.py
sh.Run "python """ & dir & "server.py""", 0, False

' Wait 2 seconds
WScript.Sleep 2000

' Start osc_bridge.py
sh.Run "python """ & dir & "osc_bridge.py""", 0, False

' Wait 3 seconds
WScript.Sleep 3000

' Start tunnel.py
sh.Run "python """ & dir & "tunnel.py""", 0, False
