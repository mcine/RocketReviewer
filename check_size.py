import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

rect = wintypes.RECT()
user32.GetWindowRect(17632934, ctypes.byref(rect))
print("17632934 rect:", rect.left, rect.top, rect.right, rect.bottom, "IsIconic (minimized)?", user32.IsIconic(17632934))
