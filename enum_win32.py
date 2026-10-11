import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

def enum_windows():
    titles = []
    def foreach_window(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                titles.append((hwnd, buff.value))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(foreach_window), 0)
    return titles

for hwnd, title in enum_windows():
    print(f"HWND: {hwnd} | Title: {title}")
