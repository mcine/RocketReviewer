import ctypes
import sys
import time

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")

# In Electron/Chromium, DocumentControl activates the full accessibility tree
doc = win.DocumentControl()
print("doc Exists?", doc.Exists(maxSearchSeconds=3))

# Search for any controls with name containing 'Strategy'
all_matches = []
def search(ctrl, depth=0):
    if depth > 12:
        return
    name = ctrl.Name or ""
    if "strategy" in name.lower():
        all_matches.append(ctrl)
        print(f"Match found at depth {depth}: [{ctrl.ControlTypeName}] Name: '{name}' Rect: {ctrl.BoundingRectangle}")
    for c in ctrl.GetChildren():
        search(c, depth + 1)

print("Searching tree...")
search(win)
print(f"Matches count: {len(all_matches)}")
