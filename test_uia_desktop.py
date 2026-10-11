import ctypes
import os
import sys

# Switch thread desktop to 'default' BEFORE importing / using UI Automation or COM
user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

print("Searching for RocketSolver window...")
win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
if not win.Exists(maxSearchSeconds=3):
    print("Trying RegexName...")
    win = auto.WindowControl(searchDepth=2, RegexName=".*Rocket.*")

if not win.Exists(maxSearchSeconds=3):
    print("Window not found via uiautomation directly. Let's inspect root children:")
    root = auto.GetRootControl()
    for child in root.GetChildren():
        print(f"[{child.ControlTypeName}] Name: {repr(child.Name)} Class: {repr(child.ClassName)}")
else:
    print("FOUND RocketSolver window!")
    print(f"Name: {win.Name}, Class: {win.ClassName}, Rect: {win.BoundingRectangle}")
