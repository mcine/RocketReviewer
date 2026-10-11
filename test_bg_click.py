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

# Find RocketSolver window and render child
rocket_hwnd = None
def foreach_window(h, l):
    global rocket_hwnd
    if user32.IsWindowVisible(h):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        h_proc = kernel32.OpenProcess(0x1000, False, pid.value)
        if h_proc:
            pbuf = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(512)
            kernel32.QueryFullProcessImageNameW(h_proc, 0, pbuf, ctypes.byref(size))
            pname = pbuf.value.split("\\")[-1]
            kernel32.CloseHandle(h_proc)
            if pname.lower() == "rocketsolver.exe":
                rocket_hwnd = h
                return False
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(foreach_window), 0)

print("RocketSolver HWND:", rocket_hwnd)

# Find Chrome_RenderWidgetHostHWND
render_hwnd = None
def enum_child(h, l):
    global render_hwnd
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, buff, 256)
    if buff.value == "Chrome_RenderWidgetHostHWND":
        render_hwnd = h
    return True

user32.EnumChildWindows(rocket_hwnd, WNDENUMPROC(enum_child), 0)
print("Render HWND:", render_hwnd)

rect = wintypes.RECT()
user32.GetClientRect(render_hwnd, ctypes.byref(rect))
w = rect.right - rect.left
h = rect.bottom - rect.top
print(f"Render client rect: {w}x{h}")

# Click Home button at 65% width, 37% height without touching foreground window or cursor!
target_x = int(w * 0.65)
target_y = int(h * 0.37)
lParam = (target_y << 16) | (target_x & 0xFFFF)

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001

# Send message directly to render_hwnd in background
user32.PostMessageW(render_hwnd, WM_MOUSEMOVE, 0, lParam)
time.sleep(0.05)
user32.PostMessageW(render_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)
time.sleep(0.05)
user32.PostMessageW(render_hwnd, WM_LBUTTONUP, 0, lParam)

print(f"Sent background click to Home ({target_x}, {target_y}) without changing active window.")
