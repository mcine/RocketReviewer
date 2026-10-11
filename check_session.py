import ctypes
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

h_winsta = user32.GetProcessWindowStation()
buf = ctypes.create_unicode_buffer(256)
user32.GetUserObjectInformationW(h_winsta, 2, buf, 256, None) # UOI_NAME = 2
print("Window Station:", buf.value)

h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
user32.GetUserObjectInformationW(h_desk, 2, buf, 256, None)
print("Desktop:", buf.value)

# Also check processes running
import subprocess
ps = subprocess.check_output(["powershell", "-Command", "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object Id, ProcessName, MainWindowTitle | Format-Table -AutoSize"], text=True)
print(ps)
