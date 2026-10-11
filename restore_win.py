import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

user32.ShowWindow(17632934, 9) # SW_RESTORE
time.sleep(0.5)

rect = wintypes.RECT()
user32.GetWindowRect(17632934, ctypes.byref(rect))
print("Restored rect:", rect.left, rect.top, rect.right, rect.bottom, "IsIconic?", user32.IsIconic(17632934))
