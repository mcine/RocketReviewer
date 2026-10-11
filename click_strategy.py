import ctypes
from ctypes import wintypes
import time
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

# Find Chrome_RenderWidgetHostHWND
render_hwnd = None
def enum_child(h, l):
    global render_hwnd
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, buff, 256)
    if buff.value == "Chrome_RenderWidgetHostHWND":
        render_hwnd = h
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumChildWindows(hwnd, WNDENUMPROC(enum_child), 0)

target_x = 47
target_y = 216
screen_x = rect.left + target_x
screen_y = rect.top + target_y

print(f"Targeting Strategy tab at client ({target_x}, {target_y}), screen ({screen_x}, {screen_y})")

# Bring to foreground
fore_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
app_thread = user32.GetWindowThreadProcessId(hwnd, None)
user32.AttachThreadInput(fore_thread, app_thread, True)
user32.ShowWindow(hwnd, 9)
user32.SetForegroundWindow(hwnd)
user32.BringWindowToTop(hwnd)
user32.AttachThreadInput(fore_thread, app_thread, False)
time.sleep(0.2)

# Method 1: mouse_event
user32.SetCursorPos(screen_x, screen_y)
time.sleep(0.1)
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
time.sleep(0.1)
user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

# Method 2: PostMessage to render_hwnd
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
lParam = (target_y << 16) | (target_x & 0xFFFF)
user32.PostMessageW(render_hwnd, WM_MOUSEMOVE, 0, lParam)
user32.PostMessageW(render_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)
time.sleep(0.05)
user32.PostMessageW(render_hwnd, WM_LBUTTONUP, 0, lParam)

print("Clicked! Waiting 2 seconds for tab to switch...")
time.sleep(2)

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

hdc_screen = user32.GetDC(hwnd)
hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
gdi32.SelectObject(hdc_mem, hbm)

user32.PrintWindow(hwnd, hdc_mem, 2)

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
im.save(str(Path(__file__).resolve().parent / "strategy_tab_view2.png"))
print("Saved strategy_tab_view2.png")
