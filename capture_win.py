import ctypes
import os
import sys

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
if not win.Exists(maxSearchSeconds=3):
    print("Window not found")
    sys.exit(1)

rect = win.BoundingRectangle
print("Window rect:", rect)

# Capture to image
img_path = r"c:\misc\code\appautomation\rocketsolver_current.png"
win.CaptureToImage(img_path)
print("Saved screenshot to:", img_path)
