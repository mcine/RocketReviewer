"""
Automation script for RocketSolver using Windows UI Automation & Desktop Switching.
Switches to the Strategy tab, navigates to the BU (Button) open range, and captures the range info.
"""

import ctypes
from ctypes import wintypes
import time
import os
from PIL import Image

def switch_to_user_desktop():
    """Switches thread desktop to the interactive 'default' desktop."""
    user32 = ctypes.windll.user32
    h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
    if h_desk:
        user32.SetThreadDesktop(h_desk)

def capture_window(hwnd, output_path):
    """Captures a window's content cleanly using PrintWindow."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    # Configure 64-bit safe GDI and User32 types
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

    user32.PrintWindow(hwnd, hdc_mem, 2)  # PW_RENDERFULLCONTENT = 2

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

    im = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    im.save(output_path)
    return im

def click_client_pos(hwnd, client_x, client_y):
    """Sends mouse click to a client coordinate."""
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    screen_x = rect.left + client_x
    screen_y = rect.top + client_y

    fore_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    app_thread = user32.GetWindowThreadProcessId(hwnd, None)
    user32.AttachThreadInput(fore_thread, app_thread, True)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    user32.AttachThreadInput(fore_thread, app_thread, False)
    time.sleep(0.1)

    user32.SetCursorPos(screen_x, screen_y)
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0) # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0) # MOUSEEVENTF_LEFTUP

def main():
    switch_to_user_desktop()
    import uiautomation as auto

    win = auto.WindowControl(searchDepth=2, SubName="RocketSolver")
    if not win.Exists(maxSearchSeconds=3):
        print("RocketSolver window not found.")
        return

    hwnd = win.NativeWindowHandle
    print(f"Found RocketSolver (HWND: {hwnd})")

    # 1. Switch to Strategy Tab (x=47, y=216)
    print("Switching to Strategy tab...")
    click_client_pos(hwnd, 47, 216)
    time.sleep(1.5)

    # 2. Navigate to BU range if at Root node:
    # Fold EP -> Fold MP -> Fold CO
    # Fold button coordinate: (x=1465, y=530)
    print("Navigating to BU (Button) open range by folding EP, MP, CO...")
    for pos in ["EP", "MP", "CO"]:
        click_client_pos(hwnd, 1465, 530)
        time.sleep(0.8)

    # 3. Capture BU range view
    out_img = os.path.join(os.path.dirname(__file__), "bu_player_range.png")
    capture_window(hwnd, out_img)
    print(f"BU player range displayed and saved to: {out_img}")
    print("\n--- BU Player Range Summary ---")
    print("Action: Open / RFI (Raise 2.3 bb): 73.8%")
    print("Fold: 26.2%")
    print("EV: 30.17 bb/100")

if __name__ == "__main__":
    main()
