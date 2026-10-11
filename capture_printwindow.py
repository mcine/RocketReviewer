import ctypes
from ctypes import wintypes
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

import uiautomation as auto

win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
hwnd = win.NativeWindowHandle

rect = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
w = rect.right - rect.left
h = rect.bottom - rect.top

# Configure 64-bit types
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
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.LPVOID,
    ctypes.c_void_p,
    wintypes.UINT
]

hdc_screen = user32.GetDC(hwnd)
hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
gdi32.SelectObject(hdc_mem, hbm)

res = user32.PrintWindow(hwnd, hdc_mem, 2)
print("PrintWindow res:", res)

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
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
im.save(str(Path(__file__).resolve().parent / "rocketsolver_printwindow.png"))
print("Saved rocketsolver_printwindow.png successfully!")

gdi32.DeleteObject(hbm)
gdi32.DeleteDC(hdc_mem)
user32.ReleaseDC(hwnd, hdc_screen)
