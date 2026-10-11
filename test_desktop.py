import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GENERIC_ALL = 0x10000000
DESKTOP_SWITCHDESKTOP = 0x0100
DESKTOP_READOBJECTS = 0x0001
DESKTOP_WRITEOBJECTS = 0x0080
DESKTOP_ALL_ACCESS = 0x01FF

# Try opening 'default' desktop
h_desk_default = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL_ACCESS)
print(f"OpenDesktopW('default') handle: {h_desk_default}")

if h_desk_default == 0:
    err = kernel32.GetLastError()
    print(f"Failed with error code: {err}")
    # Try with read access
    h_desk_default = user32.OpenDesktopW("default", 0, False, 0x01FF)

if h_desk_default:
    res = user32.SetThreadDesktop(h_desk_default)
    print(f"SetThreadDesktop result: {res}")
    if res == 0:
        print("SetThreadDesktop failed with error:", kernel32.GetLastError())
    else:
        # Now try EnumWindows
        def foreach_window(hwnd, lParam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                if user32.IsWindowVisible(hwnd):
                    print(f"HWND: {hwnd} | Title: {buff.value}")
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(foreach_window), 0)
