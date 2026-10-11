import ctypes
import sys
import time

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
doc = win.DocumentControl()

print("Doc:", doc.Name, doc.ControlTypeName)
children = doc.GetChildren()
print(f"Doc direct children count: {len(children)}")

# Let's collect all elements under doc
all_elements = []
def collect(ctrl, depth=0):
    if depth > 15:
        return
    name = ctrl.Name
    ctype = ctrl.ControlTypeName
    if name:
        all_elements.append((depth, ctype, name))
    for c in ctrl.GetChildren():
        collect(c, depth + 1)

collect(doc)
print(f"Total elements with names under doc: {len(all_elements)}")
for d, ctype, name in all_elements[:40]:
    print(f"{'  '*d}[{ctype}] {name}")
