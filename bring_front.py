import ctypes
import time
import sys

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
if not win.Exists(maxSearchSeconds=3):
    print("Not found")
    sys.exit(1)

hwnd = win.NativeWindowHandle
print("RocketSolver HWND:", hwnd)

# Bring window to front
user32.ShowWindow(hwnd, 9) # SW_RESTORE = 9
user32.SetForegroundWindow(hwnd)
time.sleep(1)

from pathlib import Path
# Now capture screenshot
img_path = str(Path(__file__).resolve().parent / "rocketsolver_front.png")
win.CaptureToImage(img_path)
print("Saved screenshot to:", img_path)
