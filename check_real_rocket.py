import ctypes
from ctypes import wintypes
import time
from PIL import Image

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

# Find EXACT RocketSolver.exe HWND
rocket_hwnd = None
def foreach_window(hwnd, lParam):
    global rocket_hwnd
    if user32.IsWindowVisible(hwnd):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h_proc = kernel32.OpenProcess(0x1000, False, pid.value)
        if h_proc:
            pbuf = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(512)
            kernel32.QueryFullProcessImageNameW(h_proc, 0, pbuf, ctypes.byref(size))
            pname = pbuf.value.split("\\")[-1]
            kernel32.CloseHandle(h_proc)
            if pname.lower() == "rocketsolver.exe":
                rocket_hwnd = hwnd
                return False
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(foreach_window), 0)

print("Exact RocketSolver.exe HWND:", rocket_hwnd)

rect = wintypes.RECT()
user32.GetWindowRect(rocket_hwnd, ctypes.byref(rect))
w = rect.right - rect.left
h = rect.bottom - rect.top

# Capture window
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
user32.PrintWindow.restype = wintypes.BOOL
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    wintypes.LPVOID, ctypes.c_void_p, wintypes.UINT
]

hdc_screen = user32.GetDC(rocket_hwnd)
hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
gdi32.SelectObject(hdc_mem, hbm)

user32.PrintWindow(rocket_hwnd, hdc_mem, 2)

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)
    ]

bmi = BITMAPINFOHEADER()
bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bmi.biWidth = w
bmi.biHeight = -h
bmi.biPlanes = 1
bmi.biBitCount = 32
bmi.biCompression = 0

buf = ctypes.create_string_buffer(w * h * 4)
gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bmi), 0)

from pathlib import Path
im.save(str(Path(__file__).resolve().parent / "real_rocketsolver.png"))
print("Saved real_rocketsolver.png")
