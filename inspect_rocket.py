import ctypes
import sys
import time

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
if not win.Exists(maxSearchSeconds=3):
    print("RocketSolver window not found.")
    sys.exit(1)

print(f"Found RocketSolver window: {win.Name}")

# Look for controls inside
# Electron apps expose tabs as TabItem, Button, Hyperlink, or Custom controls.
def dump_controls(ctrl, depth=0, max_depth=5):
    if depth > max_depth:
        return
    indent = "  " * depth
    name = ctrl.Name or ""
    ctype = ctrl.ControlTypeName or ""
    auto_id = ctrl.AutomationId or ""
    print(f"{indent}[{ctype}] Name: '{name}' AutomationId: '{auto_id}'")
    for child in ctrl.GetChildren():
        dump_controls(child, depth + 1, max_depth)

print("\nDumping top 3 levels of RocketSolver:")
dump_controls(win, 0, 3)
