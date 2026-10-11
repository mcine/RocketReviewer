import ctypes
user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

def foreach_window(hwnd, lParam):
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0 and user32.IsWindowVisible(hwnd):
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        title = buff.value
        if "rocket" in title.lower() or "solver" in title.lower():
            print(f"HWND: {hwnd} | Class: {cls.value} | Title: {repr(title)}")
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUMPROC(foreach_window), 0)
