import ctypes
from ctypes import wintypes
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

def foreach_window(hwnd, lParam):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            h_proc = kernel32.OpenProcess(0x1000, False, pid.value) # PROCESS_QUERY_LIMITED_INFORMATION
            pname = ""
            if h_proc:
                pbuf = ctypes.create_unicode_buffer(512)
                size = wintypes.DWORD(512)
                kernel32.QueryFullProcessImageNameW(h_proc, 0, pbuf, ctypes.byref(size))
                pname = pbuf.value.split("\\")[-1]
                kernel32.CloseHandle(h_proc)
            title = buff.value.encode("ascii", errors="replace").decode()
            if any(k in title.lower() or k in pname.lower() for k in ["rocket", "solver", "6max"]):
                print(f"HWND: {hwnd} | PID: {pid.value} | Process: {pname} | Title: {title}")
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(foreach_window), 0)
