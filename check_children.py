import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
hwnd = win.NativeWindowHandle

print("RocketSolver HWND:", hwnd)

# Enumerate child windows
children = []
def enum_child(h, l):
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, buff, 256)
    rect = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(rect))
    children.append((h, buff.value, (rect.left, rect.top, rect.right, rect.bottom)))
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumChildWindows(hwnd, WNDENUMPROC(enum_child), 0)

for h, cls, r in children:
    print(f"Child HWND: {h}, Class: {cls}, Rect: {r}")
