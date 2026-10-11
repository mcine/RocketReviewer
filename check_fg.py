import ctypes

user32 = ctypes.windll.user32
h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
if h_desk:
    user32.SetThreadDesktop(h_desk)

fg = user32.GetForegroundWindow()
length = user32.GetWindowTextLengthW(fg)
buff = ctypes.create_unicode_buffer(length + 1)
user32.GetWindowTextW(fg, buff, length + 1)
print(f"Foreground HWND: {fg}, Title: '{buff.value}'")
