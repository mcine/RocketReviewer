"""
Bridge to interact with RocketSolver without stealing active window focus.
Uses PostMessage directly to the Chrome_RenderWidgetHostHWND so the user
can continue typing and working in other windows undisturbed.
"""
import math
import ctypes
from ctypes import wintypes
import time
from typing import Optional, Dict, Tuple, List, Any
from PIL import Image

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

class RocketSolverBridge:
    def __init__(self):
        self.hwnd = None
        self.render_hwnd = None
        self.cancel_requested = False
        self.calibrated_colors = None

    def is_escape_pressed(self) -> bool:
        """Checks if physical Escape key is pressed anywhere in Windows."""
        try:
            return bool(user32.GetAsyncKeyState(0x1B) & 0x8000)
        except Exception:
            return False

    def cancel(self):
        self.cancel_requested = True

    def reset_cancel(self):
        self.cancel_requested = False
        try:
            # Clear any pending key state
            user32.GetAsyncKeyState(0x1B)
        except Exception:
            pass

    def is_cancelled(self) -> bool:
        if bool(self.cancel_requested):
            return True
        if self.is_escape_pressed():
            self.cancel_requested = True
            return True
        return False

    def sleep_interruptible(self, duration: float, cancel_check=None) -> bool:
        """
        Sleeps for duration seconds in increments of 30ms, returning True
        immediately if cancellation is requested or Escape key is pressed.
        """
        end_time = time.time() + duration
        while time.time() < end_time:
            if self.is_cancelled() or (cancel_check and cancel_check()):
                return True
            time.sleep(min(0.03, max(0.0, end_time - time.time())))
        return self.is_cancelled() or bool(cancel_check and cancel_check())

    def switch_to_desktop(self):
        h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)

    def find_window(self):
        self.switch_to_desktop()
        self.hwnd = None
        self.render_hwnd = None

        def foreach_window(h, l):
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
                        self.hwnd = h
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(foreach_window), 0)

        if self.hwnd:
            def enum_child(h, l):
                buff = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, buff, 256)
                if buff.value == "Chrome_RenderWidgetHostHWND":
                    self.render_hwnd = h
                    return False
                return True

            user32.EnumChildWindows(self.hwnd, WNDENUMPROC(enum_child), 0)

        return self.hwnd

    def ensure_ready(self):
        if not self.hwnd or not self.render_hwnd:
            self.find_window()
        if not self.hwnd:
            return False
        # If minimized, restore without activating
        if user32.IsIconic(self.hwnd):
            # SW_SHOWNOACTIVATE = 4
            user32.ShowWindow(self.hwnd, 4)
            time.sleep(0.3)
        return True

    def get_render_client_size(self):
        if not self.render_hwnd:
            return 1280, 720
        rect = wintypes.RECT()
        user32.GetClientRect(self.render_hwnd, ctypes.byref(rect))
        return rect.right - rect.left, rect.bottom - rect.top

    def click_background_relative(self, rel_x_pct, rel_y_pct):
        """
        Clicks RocketSolver via PostMessage in the background.
        DOES NOT steal focus or move the physical mouse cursor, allowing
        the user to work in other applications simultaneously.
        """
        if not self.ensure_ready() or not self.render_hwnd:
            return False

        w, h = self.get_render_client_size()
        target_x = int(w * rel_x_pct)
        target_y = int(h * rel_y_pct)
        lParam = (target_y << 16) | (target_x & 0xFFFF)

        WM_MOUSEMOVE = 0x0200
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        MK_LBUTTON = 0x0001

        user32.PostMessageW(self.render_hwnd, WM_MOUSEMOVE, 0, lParam)
        time.sleep(0.04)
        user32.PostMessageW(self.render_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)
        time.sleep(0.04)
        user32.PostMessageW(self.render_hwnd, WM_LBUTTONUP, 0, lParam)
        return True

    def bring_to_foreground(self):
        """Brings RocketSolver window to foreground so the user sees it working."""
        if not self.ensure_ready():
            return False
        fore_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        app_thread = user32.GetWindowThreadProcessId(self.hwnd, None)
        user32.AttachThreadInput(fore_thread, app_thread, True)
        user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(self.hwnd)
        user32.BringWindowToTop(self.hwnd)
        user32.AttachThreadInput(fore_thread, app_thread, False)
        time.sleep(0.15)
        return True

    def minimize(self) -> bool:
        """Minimizes RocketSolver window."""
        if not self.ensure_ready() or not self.hwnd:
            return False
        # SW_MINIMIZE = 6
        user32.ShowWindow(self.hwnd, 6)
        time.sleep(0.1)
        return True

    def click_foreground_client(self, client_x, client_y):
        """Clicks at client coordinates and shows visible cursor so user sees RocketSolver working."""
        if not self.ensure_ready() or not self.render_hwnd:
            return False
        pt = wintypes.POINT(int(client_x), int(client_y))
        user32.ClientToScreen(self.render_hwnd, ctypes.byref(pt))
        user32.SetCursorPos(pt.x, pt.y)
        time.sleep(0.08)
        user32.mouse_event(0x0002, 0, 0, 0, 0) # LEFTDOWN
        time.sleep(0.06)
        user32.mouse_event(0x0004, 0, 0, 0, 0) # LEFTUP
        time.sleep(0.1)
        return True

    def is_strategy_tab_active(self, im: Optional[Image.Image] = None) -> bool:
        """
        Returns True if RocketSolver is currently on the Strategy tab.
        When active, the Strategy button on the left sidebar (y=180..280)
        is filled with solid emerald green (#18ad76, > 2000 green pixels).
        When on Tree, Jobs, or Settings, green pixel count is low (~788).
        """
        if im is None:
            im = self.capture_current_image()
        if not im:
            return False

        green_count = 0
        for y in range(180, 280):
            for x in range(10, min(80, im.width)):
                r, g, b, _ = im.getpixel((x, y))
                if g > 140 and g > r + 35 and g > b + 20:
                    green_count += 1
        return green_count > 2000

    def ensure_strategy_tab(self, max_attempts: int = 5) -> bool:
        """
        Always ensures that the Strategy tab is active before checking or resetting hands.
        If RocketSolver is on Settings, Tree, Jobs, or any other tab, clicks the Strategy tab
        on the sidebar (x=40, y=230) and verifies that the Strategy tab is confirmed active.
        """
        if not self.ensure_ready():
            return False

        if self.is_strategy_tab_active():
            return True

        self.bring_to_foreground()
        for attempt in range(max_attempts):
            # Click Strategy icon on sidebar (center is x=40, y=230)
            self.click_foreground_client(40, 230)
            time.sleep(0.25)
            if self.is_strategy_tab_active():
                return True

        return self.is_strategy_tab_active()

    def switch_to_strategy(self) -> bool:
        """Switches to Strategy tab and verifies it is active."""
        return self.ensure_strategy_tab()

    def switch_to_settings(self) -> bool:
        """Switches to Settings tab on sidebar (x=45, y=480)."""
        if not self.ensure_ready():
            return False
        self.bring_to_foreground()
        self.click_foreground_client(45, 480)
        time.sleep(0.35)
        return True

    def calibrate_colors(self, force: bool = False, on_action=None) -> Dict[str, Tuple[int, int, int]]:
        """
        Calibrates action colors from RocketSolver's Settings -> Appearance panel.
        Automatically runs on every first run of the reviewer.
        Samples Fold, Check, All-in, Bet 1 (Small), and Bet 2 (Big) swatches,
        then switches RocketSolver back to Strategy tab.
        """
        if self.calibrated_colors and not force:
            return self.calibrated_colors

        if not self.ensure_ready():
            # Fallback default RocketSolver colors if window not accessible
            self.calibrated_colors = {
                "fold": (178, 101, 113),
                "check": (118, 161, 12),
                "all_in": (78, 18, 180),
                "bet_small": (69, 152, 244),
                "bet_big": (18, 44, 175)
            }
            return self.calibrated_colors

        if on_action:
            on_action("Calibrating action colors from RocketSolver Settings...")

        # Switch to Settings tab
        self.switch_to_settings()
        im = self.capture_current_image()

        # Swatch positions in Appearance card
        swatch_coords = {
            "fold": (340, 185),
            "check": (340, 255),
            "all_in": (340, 320),
            "bet_small": (340, 385),
            "bet_big": (390, 385)
        }

        calibrated = {}
        if im:
            for name, (sx, sy) in swatch_coords.items():
                if sx < im.width and sy < im.height:
                    calibrated[name] = im.getpixel((sx, sy))[:3]

        # Validate we got valid non-black non-white swatches
        if len(calibrated) == 5 and all(max(c) > 50 for c in calibrated.values()):
            self.calibrated_colors = calibrated
        else:
            self.calibrated_colors = {
                "fold": (178, 101, 113),
                "check": (118, 161, 12),
                "all_in": (78, 18, 180),
                "bet_small": (69, 152, 244),
                "bet_big": (18, 44, 175)
            }

        if on_action:
            on_action(
                f"Action colors calibrated: Fold {self.calibrated_colors['fold']}, "
                f"Check {self.calibrated_colors['check']}, BetSmall {self.calibrated_colors['bet_small']}, "
                f"BetBig {self.calibrated_colors['bet_big']}"
            )

        # Always switch back to Strategy tab after calibration
        self.switch_to_strategy()
        time.sleep(0.2)
        return self.calibrated_colors

    def get_button_row_y(self, im: Optional[Image.Image] = None) -> int:
        """Finds the vertical Y coordinate of the button bar below the table."""
        if im is None:
            im = self.capture_current_image()
        if not im:
            return 535
        w, h = im.size
        # The action button bar ALWAYS contains the Home button around x=1240-1250 and < Back around x=1340
        for y in range(int(h * 0.35), int(h * 0.60), 2):
            for hx in [1240, 1245, 1250]:
                r, g, b, _ = im.getpixel((hx, y))
                if (r > 38 and g > 45 and b > 55):
                    for bx in [1335, 1340, 1348]:
                        r2, g2, b2, _ = im.getpixel((bx, y))
                        if (r2 > 38 and g2 > 45 and b2 > 55):
                            return y + 10
        return 535 if abs(h - 1230) < 50 else int(h * 0.44)

    def is_back_button_grayed_out(self, im: Optional[Image.Image] = None) -> bool:
        """
        Returns True if the '< Back' button below the table is grayed out / disabled,
        meaning RocketSolver is at the Root / start stage of the tree.
        Crucially, first verifies that the Strategy tab is active; if on Settings or another
        tab, returns False immediately so RocketSolver is forced to switch back to Strategy.
        """
        if im is None:
            im = self.capture_current_image()
        if not im:
            return False

        # If not even on the Strategy tab (e.g. in Settings), cannot be at Strategy root!
        if not self.is_strategy_tab_active(im):
            return False

        btn_y = self.get_button_row_y(im)
        # '< Back' button center is around x=1340
        crop = im.crop((1305, max(0, btn_y - 18), 1375, min(im.height, btn_y + 18)))
        max_rgb = max(max(p[:3]) for p in crop.getdata())
        return max_rgb < 175

    def reset_to_root(self, max_attempts: int = 4) -> bool:
        """
        Guarantees the RocketSolver navigation tree is reset back to Root (Preflop start).
        1. Always ensures Strategy tab is active (switches out of Settings/Tree/Jobs).
        2. Clears any combo/hand filter that might be active.
        3. Clicks Home button and verifies Back button is grayed out.
        """
        if not self.ensure_ready():
            return False

        # 1. ALWAYS guarantee Strategy tab is active
        self.ensure_strategy_tab()
        time.sleep(0.12)

        # 2. Clear any combo/hand filter that might be active (Clear button x=804, y=800)
        self.click_foreground_client(804, 800)
        time.sleep(0.08)

        btn_y = self.get_button_row_y()
        # Home button is at x=1240
        self.click_foreground_client(1240, btn_y)
        time.sleep(0.25)

        if self.is_back_button_grayed_out():
            return True

        for _ in range(max_attempts):
            self.ensure_strategy_tab()
            self.click_foreground_client(1240, btn_y)
            time.sleep(0.15)
            if self.is_back_button_grayed_out():
                return True
            # Try '< Back' button at x=1340
            self.click_foreground_client(1340, btn_y)
            time.sleep(0.15)
            if self.is_back_button_grayed_out():
                return True

        return self.is_back_button_grayed_out()

    def get_card_keyboard_geometry(self, im: Optional[Image.Image] = None) -> Dict[str, Any]:
        """
        Dynamically detects the 4x13 card keyboard on screen.
        Row 0: Hearts (Red)
        Row 1: Spades (Gray)
        Row 2: Diamonds (Blue)
        Row 3: Clubs (Green)
        Columns: A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
        """
        if im is None:
            im = self.capture_current_image()
        if not im:
            return {
                "row0_y": 759, "row_step": 61.0,
                "min_x": 1210, "col_step": 54.5
            }

        w, h = im.size
        # Search for first red row band (Hearts, Row 0)
        red_band = []
        in_red = False
        for y in range(int(h * 0.4), int(h * 0.95), 2):
            rc = sum(1 for x in range(int(w * 0.6), int(w * 0.98), 2)
                     if im.getpixel((x, y))[0] > 160 and im.getpixel((x, y))[0] > im.getpixel((x, y))[1] + 60 and im.getpixel((x, y))[0] > im.getpixel((x, y))[2] + 60)
            if rc > 12:
                in_red = True
                red_band.append(y)
            elif in_red:
                break

        if not red_band:
            fallback_row0 = 759 if h < 1300 else 894
            fallback_min_x = 1210 if h < 1300 else 1222
            return {
                "row0_y": fallback_row0, "row_step": 61.0,
                "min_x": fallback_min_x, "col_step": 54.5
            }

        row0_y = (min(red_band) + max(red_band)) // 2

        # Search for first green band (Clubs, Row 3)
        green_band = []
        in_green = False
        for y in range(row0_y + 80, int(h * 0.95), 2):
            gc = sum(1 for x in range(int(w * 0.6), int(w * 0.98), 2)
                     if im.getpixel((x, y))[1] > 150 and im.getpixel((x, y))[1] > im.getpixel((x, y))[0] + 60 and im.getpixel((x, y))[1] > im.getpixel((x, y))[2] + 20)
            if gc > 10:
                in_green = True
                green_band.append(y)
            elif in_green:
                break

        row3_y = (min(green_band) + max(green_band)) // 2 if green_band else (row0_y + 183)
        row_step = (row3_y - row0_y) / 3.0

        red_xs = []
        for y in red_band:
            red_xs.extend([x for x in range(int(w * 0.6), int(w * 0.98), 2)
                           if im.getpixel((x, y))[0] > 160 and im.getpixel((x, y))[0] > im.getpixel((x, y))[1] + 60 and im.getpixel((x, y))[0] > im.getpixel((x, y))[2] + 60])

        min_x = min(red_xs) if red_xs else (1210 if h < 1300 else 1222)
        max_x = max(red_xs) if red_xs else (min_x + 655)
        col_step = (max_x - min_x) / 12.0

        return {
            "row0_y": row0_y, "row_step": row_step,
            "min_x": min_x, "col_step": col_step
        }

    def click_fold(self):
        """Clicks Fold button in RocketSolver."""
        return self.click_action("fold")

    def click_call_or_check(self):
        """Clicks Call / Check button in RocketSolver."""
        return self.click_action("call")

    def click_raise(self):
        """Clicks Raise button in RocketSolver."""
        return self.click_action("raise")

    def input_board_card(self, card_token: str):
        """
        Inputs a board card (e.g. '8c', 'Ts', 'As') using RocketSolver's on-screen card keyboard.
        Row 0: Hearts (h), Row 1: Spades (s), Row 2: Diamonds (d), Row 3: Clubs (c).
        Columns: A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2.
        """
        if not card_token or len(card_token) < 2:
            return False
        rank = card_token[0].upper()
        suit = card_token[1].lower()

        ranks_order = "AKQJT98765432"
        suit_order = {"h": 0, "s": 1, "d": 2, "c": 3}

        if rank not in ranks_order or suit not in suit_order:
            return False

        col_idx = ranks_order.index(rank)
        row_idx = suit_order[suit]

        geom = self.get_card_keyboard_geometry()
        card_x = int(geom["min_x"] + col_idx * geom["col_step"] + 15)
        card_y = int(geom["row0_y"] + row_idx * geom["row_step"])

        res = self.click_foreground_client(card_x, card_y)
        time.sleep(0.25)
        return res

    def capture_current_image(self) -> Optional[Image.Image]:
        """Captures clean image of RocketSolver window."""
        if not self.ensure_ready():
            return None
        rect = wintypes.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return None

        hdc_screen = user32.GetDC(self.hwnd)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        gdi32.SelectObject(hdc_mem, hbm)
        user32.PrintWindow(self.hwnd, hdc_mem, 2)

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

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bmi), 0)
        im = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)

        # Cleanup GDI objects
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(self.hwnd, hdc_screen)
        return im

    def get_live_hand_strategy(self, canon_hand: str, facing_bet: bool = True) -> Dict[str, Any]:
        """
        Samples the 13x13 strategy grid directly from RocketSolver's active solution on screen.
        Works across any loaded solution (.rsl file, custom nodelocks, or bet profiles).
        Uses calibrated action colors sampled from the RocketSolver Settings view.
        When facing_bet=True:
            Swatches: Fold (Red), Check/Call (Green), Bet 1 (Small), Bet 2 (Big), All-in.
            Returns {'raise': pct, 'call': pct, 'fold': pct, 'bet_small': pct, 'bet_big': pct, 'all_in': pct, 'in_range': bool}.
        When facing_bet=False (facing a check or first to act on a street):
            There is no fold option (fold=0.0%).
            Candidates: Check (Green), Bet 1 (Small), Bet 2 (Big), All-in.
            Returns {'raise': bet_pct, 'call': check_pct, 'fold': 0.0, 'bet': bet_pct, 'check': check_pct, 'bet_small': pct, 'bet_big': pct, 'in_range': bool}.
        """
        im = self.capture_current_image()
        if not im:
            if not facing_bet:
                return {"raise": 0.0, "call": 1.0, "fold": 0.0, "in_range": True, "check": 1.0, "bet": 0.0}
            return {"raise": 0.0, "call": 0.0, "fold": 1.0, "in_range": True}

        # Ensure colors are calibrated
        if not self.calibrated_colors:
            self.calibrate_colors()

        swatches = self.calibrated_colors or {
            "fold": (178, 101, 113),
            "check": (118, 161, 12),
            "all_in": (78, 18, 180),
            "bet_small": (69, 152, 244),
            "bet_big": (18, 44, 175)
        }

        # Candidate actions:
        # If facing_bet is False: fold is not possible (only check, bet_small, bet_big, all_in)
        # If facing_bet is True: fold, check/call, bet_small, bet_big, all_in are possible
        candidate_keys = ["check", "bet_small", "bet_big", "all_in"]
        if facing_bet:
            candidate_keys.append("fold")

        candidate_swatches = {k: swatches[k] for k in candidate_keys if k in swatches}

        ranks_order = "AKQJT98765432"
        rank_to_idx = {r: i for i, r in enumerate(ranks_order)}

        if len(canon_hand) == 2:  # Pocket pair (diagonal)
            r = rank_to_idx.get(canon_hand[0], 0)
            row, col = r, r
        elif canon_hand.endswith("s"):  # Suited (above diagonal)
            r1 = rank_to_idx.get(canon_hand[0], 0)
            r2 = rank_to_idx.get(canon_hand[1], 0)
            row, col = min(r1, r2), max(r1, r2)
        else:  # Offsuit (below diagonal)
            r1 = rank_to_idx.get(canon_hand[0], 0)
            r2 = rank_to_idx.get(canon_hand[1], 0)
            row, col = max(r1, r2), min(r1, r2)

        x0 = 147.0
        cw = 55.45
        y0 = 75.0
        ch = 45.3

        x_start = int(x0 + col * cw + 6)
        x_end = int(x0 + (col + 1) * cw - 6)
        y_start = int(y0 + row * ch + 6)
        y_end = int(y0 + (row + 1) * ch - 6)

        counts = {k: 0 for k in candidate_keys}

        def classify_pixel(r: int, g: int, b: int) -> Optional[str]:
            # Filter out dark cell backgrounds (RocketSolver background is dark blue/slate, max < 95)
            if max(r, g, b) < 95:
                return None
            # Filter out white and light-gray text inside cell ("KK", "AKs", etc.)
            if min(r, g, b) > 165:
                return None
            # Filter out grayish / desaturated anti-aliasing text edges
            if max(r, g, b) - min(r, g, b) < 25 and min(r, g, b) > 105:
                return None

            # Primary: Dominant channel classification
            if g > r + 15 and g > b + 15:
                return "check" if "check" in candidate_keys else None
            elif facing_bet and r > g + 25 and r > b + 15:
                return "fold" if "fold" in candidate_keys else None
            elif b > r + 15 and b > g + 15:
                if "all_in" in candidate_keys and r > 60 and g < 60 and b > 140:
                    return "all_in"
                elif "bet_small" in candidate_keys and g > 90:
                    return "bet_small"
                elif "bet_big" in candidate_keys:
                    return "bet_big"
                return "bet_small" if "bet_small" in candidate_keys else None
            else:
                # Fallback to calibrated swatches with strict threshold (< 60)
                best_k = None
                best_d = 999999.0
                for k, swatch in candidate_swatches.items():
                    d = math.dist((r, g, b), swatch)
                    if d < best_d:
                        best_d = d
                        best_k = k
                if best_d < 60 and best_k:
                    return best_k
            return None

        for y in range(y_start, y_end):
            for x in range(x_start, x_end):
                rgb = im.getpixel((x, y))[:3]
                res = classify_pixel(rgb[0], rgb[1], rgb[2])
                if res:
                    counts[res] += 1

        total = sum(counts.values())
        if total < 20:
            # Grid might have been redrawing after a click/transition; wait 0.25s and retry once
            time.sleep(0.25)
            im_retry = self.capture_current_image()
            if im_retry:
                counts_retry = {k: 0 for k in candidate_keys}
                for y in range(y_start, y_end):
                    for x in range(x_start, x_end):
                        rgb = im_retry.getpixel((x, y))[:3]
                        res = classify_pixel(rgb[0], rgb[1], rgb[2])
                        if res:
                            counts_retry[res] += 1
                if sum(counts_retry.values()) >= 20:
                    counts = counts_retry
                    total = sum(counts.values())

        # If no strategy colors are present in the cell, hand is NOT in the active range window
        if total < 20:
            return {
                "raise": 0.0,
                "call": 0.0,
                "fold": 0.0,
                "in_range": False,
                "total_colored_pixels": total
            }

        # Bet counts include both small bet, big bet, and all-in
        bet_total_count = counts.get("bet_small", 0) + counts.get("bet_big", 0) + counts.get("all_in", 0)
        bet_pct = round(bet_total_count / total, 3)
        check_call_pct = round(counts.get("check", 0) / total, 3)
        fold_pct = round(counts.get("fold", 0) / total, 3) if facing_bet else 0.0

        res = {
            "raise": bet_pct,
            "call": check_call_pct,
            "fold": fold_pct,
            "bet": bet_pct,
            "check": check_call_pct,
            "bet_small": round(counts.get("bet_small", 0) / total, 3),
            "bet_big": round(counts.get("bet_big", 0) / total, 3),
            "all_in": round(counts.get("all_in", 0) / total, 3),
            "in_range": True,
            "total_colored_pixels": total
        }
        return res

    def detect_action_buttons(self) -> List[Dict[str, Any]]:
        """
        Detects action buttons currently rendered in RocketSolver.
        Action buttons are in the row below the table starting after '< Back' (x >= 1420).
        Returns list of buttons: [{'x': x, 'y': y, 'width': w}, ...]
        Ordered from left to right (e.g. Fold/Check, Call/Bet, Raise).
        """
        im = self.capture_current_image()
        if not im:
            return []

        w, h = im.size
        btn_y = self.get_button_row_y(im)

        found = []
        in_btn = False
        start_x = 0
        for x in range(1420, int(w * 0.98)):
            r, g, b, _ = im.getpixel((x, btn_y))
            is_btn = (r > 38 and g > 45 and b > 55)
            if is_btn and not in_btn:
                in_btn = True
                start_x = x
            elif not is_btn and in_btn:
                in_btn = False
                w_btn = x - start_x
                if w_btn > 35:
                    found.append({"x": (start_x + x) // 2, "y": btn_y, "width": w_btn})
        if in_btn and int(w * 0.98) - start_x > 35:
            found.append({"x": (start_x + int(w * 0.98)) // 2, "y": btn_y, "width": int(w * 0.98) - start_x})
        return found

    def click_action(self, action_type: str) -> bool:
        """
        Clicks the closest matching action button in RocketSolver.
        Supports 'fold', 'check', 'call', 'bet', 'raise'.
        """
        btns = self.detect_action_buttons()
        btn_y = self.get_button_row_y()
        if not btns:
            # Fallback coordinates if detection found nothing
            if action_type in ("fold", "check"):
                return self.click_foreground_client(1480, btn_y)
            elif action_type == "call":
                return self.click_foreground_client(1580, btn_y)
            elif action_type in ("bet", "raise"):
                return self.click_foreground_client(1620, btn_y)
            return False

        if action_type in ("fold", "check"):
            btn = btns[0]
            return self.click_foreground_client(btn["x"], btn["y"])
        elif action_type == "call":
            if len(btns) >= 2:
                btn = btns[1]
            else:
                btn = btns[0]
            return self.click_foreground_client(btn["x"], btn["y"])
        elif action_type in ("bet", "raise"):
            if len(btns) > 1:
                btn = btns[-1]
                return self.click_foreground_client(btn["x"], btn["y"])
            return False
        return False

    def step_hand(self, hand: Any, visual_delay: float = 0.45, on_action=None, stop_on_error: bool = False, reset_at_end: bool = False, minimize_at_end: bool = False, cancel_check=None) -> Dict[str, Any]:
        """
        Steps through a hand action-by-action in RocketSolver Strategy view:
        - Brings RocketSolver to foreground so user sees it visually working.
        - Resets tree to Root.
        - Steps through each action: clicks fold, call, raise, inputs board cards.
        - When Hero acts: samples live strategy from active .rsl solution.
        - If hand had to be folded or is not in range window, check ends immediately.
        - Non hand-ending mistakes (wrong raise size, call vs raise) allow solving to continue.
        - Replays the actions visually so the user watches the hand unfold.
        - After last hand, resets strategy window to start stage if reset_at_end is True.
        - Can be cancelled anytime via cancel_check or self.cancel().
        """
        review_reasons = []
        street_analyses = []
        blunder_found = False

        def should_cancel() -> bool:
            return self.is_cancelled() or bool(cancel_check and cancel_check())

        def cancel_result():
            if on_action:
                on_action("RocketSolver operation cancelled by user.")
            return {"cancelled": True, "marked_for_review": False, "review_reasons": review_reasons, "street_analyses": street_analyses}

        if should_cancel():
            return cancel_result()

        if not self.ensure_ready():
            return {"error": "RocketSolver window not available", "marked_for_review": False}

        self.bring_to_foreground()

        # Calibrate action colors on first run from Settings view
        if not self.calibrated_colors:
            self.calibrate_colors(on_action=on_action)

        # Always check that Strategy tab is active when starting to check a hand
        if not self.ensure_strategy_tab():
            if on_action:
                on_action("Warning: Could not switch to Strategy tab in RocketSolver.")
            return {"error": "RocketSolver Strategy tab not active", "marked_for_review": False}

        self.reset_to_root()
        if not self.is_back_button_grayed_out():
            if self.sleep_interruptible(0.2, cancel_check):
                return cancel_result()
            self.ensure_strategy_tab()
            self.reset_to_root()
        self._folded_tree_positions = set()
        if self.sleep_interruptible(visual_delay, cancel_check):
            return cancel_result()

        from hand_checker import get_hero_info, to_canonical_hand, get_player_position

        hero_seat, hero_pos, hero_cards = get_hero_info(hand)
        canon_hand = to_canonical_hand(hero_cards)
        card_str = " ".join(hero_cards) if hero_cards else ""

        street = "Preflop"
        facing_bet = True
        street_raises = 1  # Preflop BB counts as 1st bet
        last_bettor = {"pos": "BB", "amt": "", "action": "Big Blind", "short": "Big Blind"}
        blunder_found = False

        board_cards_inputted = 0
        for act in hand.actions:
            if should_cancel():
                return cancel_result()

            t = act.action_type
            if t == "holecards":
                continue

            if t == "deal_flop":
                street = "Flop"
                facing_bet = False
                street_raises = 0
                last_bettor = None
                if on_action:
                    on_action(f"Dealing Flop: {' '.join(act.cards)}")
                if self.sleep_interruptible(0.5, cancel_check):
                    return cancel_result()
                for c in act.cards:
                    if should_cancel():
                        return cancel_result()
                    if board_cards_inputted < 5:
                        self.input_board_card(c)
                        board_cards_inputted += 1
                        if self.sleep_interruptible(visual_delay, cancel_check):
                            return cancel_result()
                continue

            elif t == "deal_turn":
                street = "Turn"
                facing_bet = False
                street_raises = 0
                last_bettor = None
                if on_action:
                    on_action(f"Dealing Turn: {' '.join(act.cards)}")
                if self.sleep_interruptible(0.5, cancel_check):
                    return cancel_result()
                for c in act.cards:
                    if should_cancel():
                        return cancel_result()
                    if board_cards_inputted < 5:
                        self.input_board_card(c)
                        board_cards_inputted += 1
                        if self.sleep_interruptible(visual_delay, cancel_check):
                            return cancel_result()
                continue

            elif t == "deal_river":
                street = "River"
                facing_bet = False
                street_raises = 0
                last_bettor = None
                if on_action:
                    on_action(f"Dealing River: {' '.join(act.cards)}")
                if self.sleep_interruptible(0.5, cancel_check):
                    return cancel_result()
                for c in act.cards:
                    if should_cancel():
                        return cancel_result()
                    if board_cards_inputted < 5:
                        self.input_board_card(c)
                        board_cards_inputted += 1
                        if self.sleep_interruptible(visual_delay, cancel_check):
                            return cancel_result()
                continue

            elif t in ("post_sb", "post_bb"):
                continue

            elif t in ("fold", "check", "call", "bet", "raise"):
                is_hero = (act.seat == hero_seat)
                pos = get_player_position(hand, act.seat) if act.seat else "?"
                amt_str = f"${act.amount / 100:.2f}" if act.amount else ""

                # When navigating a 6-max tree preflop at tables with < 6 players,
                # any missing positions before the current actor (e.g. MP at a 5-handed table)
                # must be folded in the solver tree so the tree matches the actual action sequence.
                if street == "Preflop":
                    table_positions = {get_player_position(hand, s) for s in hand.players.keys()}
                    # Preflop tree sequence before flop: EP, MP, CO, BU, SB, BB
                    preflop_order = ["EP", "MP", "CO", "BU", "SB", "BB"]
                    if not hasattr(self, "_folded_tree_positions") or self._folded_tree_positions is None:
                        self._folded_tree_positions = set()

                    if pos in preflop_order:
                        pos_target_idx = preflop_order.index(pos)
                        for p_idx in range(pos_target_idx):
                            if should_cancel():
                                return cancel_result()
                            prior_pos = preflop_order[p_idx]
                            if prior_pos not in table_positions and prior_pos not in self._folded_tree_positions:
                                self._folded_tree_positions.add(prior_pos)
                                if on_action:
                                    on_action(f"Auto-folding missing seat {prior_pos} in 6-max tree")
                                self.click_fold()
                                if self.sleep_interruptible(visual_delay, cancel_check):
                                    return cancel_result()

                # Determine human-friendly action terminology and context
                if street == "Preflop":
                    if t == "raise":
                        if street_raises == 1:
                            action_verb = f"open raised to {amt_str}".strip() if amt_str else "open raised"
                            action_badge = f"Open Raise {amt_str}".strip()
                        elif street_raises == 2:
                            action_verb = f"3-bet raised to {amt_str}".strip() if amt_str else "3-bet raised"
                            action_badge = f"3-Bet {amt_str}".strip()
                        elif street_raises == 3:
                            action_verb = f"4-bet raised to {amt_str}".strip() if amt_str else "4-bet raised"
                            action_badge = f"4-Bet {amt_str}".strip()
                        else:
                            action_verb = f"{street_raises+1}-bet raised to {amt_str}".strip() if amt_str else f"{street_raises+1}-bet raised"
                            action_badge = f"{street_raises+1}-Bet {amt_str}".strip()
                    elif t == "call":
                        action_verb = f"called {amt_str}".strip() if amt_str else "called"
                        action_badge = f"Call {amt_str}".strip()
                    elif t == "check":
                        action_verb = "checked"
                        action_badge = "Check"
                    elif t == "fold":
                        action_verb = "folded"
                        action_badge = "Fold"
                else:
                    if t in ("bet", "raise"):
                        if street_raises == 0:
                            action_verb = f"bet {amt_str}".strip() if amt_str else "bet"
                            action_badge = f"Bet {amt_str}".strip()
                        elif street_raises == 1:
                            action_verb = f"raised to {amt_str}".strip() if amt_str else "raised"
                            action_badge = f"Raise {amt_str}".strip()
                        elif street_raises == 2:
                            action_verb = f"3-bet raised to {amt_str}".strip() if amt_str else "3-bet raised"
                            action_badge = f"3-Bet {amt_str}".strip()
                        else:
                            action_verb = f"{street_raises+1}-bet raised to {amt_str}".strip() if amt_str else f"{street_raises+1}-bet raised"
                            action_badge = f"{street_raises+1}-Bet {amt_str}".strip()
                    elif t == "call":
                        action_verb = f"called {amt_str}".strip() if amt_str else "called"
                        action_badge = f"Call {amt_str}".strip()
                    elif t == "check":
                        action_verb = "checked"
                        action_badge = "Check"
                    elif t == "fold":
                        action_verb = "folded"
                        action_badge = "Fold"

                # Facing context description
                if last_bettor and (facing_bet or street == "Preflop"):
                    if last_bettor.get("action") == "Big Blind":
                        facing_desc = "unopened pot"
                    else:
                        facing_desc = f"facing {last_bettor['pos']}'s {last_bettor['amt']} {last_bettor['short']}".replace("  ", " ").strip()
                elif not facing_bet:
                    facing_desc = "first to act" if street != "Preflop" else "unopened pot"
                else:
                    facing_desc = ""

                if is_hero:
                    strat = self.get_live_hand_strategy(canon_hand, facing_bet=facing_bet)
                    in_range = strat.get("in_range", True)

                    # 1. If hand is not in the active range window anymore, check can be ended immediately
                    if not in_range:
                        if on_action:
                            on_action(f"Hero's hand ({canon_hand}) is no longer in range window on {street}. Check ended.")
                        break

                    fold_pct = strat.get("fold", 0.0)
                    call_pct = strat.get("call", 0.0)
                    raise_pct = strat.get("raise", 0.0)

                    if not facing_bet:
                        strat_desc = f"Check: {call_pct*100:.1f}%, Bet: {raise_pct*100:.1f}%"
                        if on_action:
                            on_action(f"Hero's turn ({hero_pos}): {canon_hand} -> Solver: Check {call_pct*100:.0f}%, Bet {raise_pct*100:.0f}%")
                    else:
                        strat_desc = f"Fold: {fold_pct*100:.1f}%, Call: {call_pct*100:.1f}%, Raise: {raise_pct*100:.1f}%"
                        if on_action:
                            on_action(f"Hero's turn ({hero_pos}): {canon_hand} -> Solver: Fold {fold_pct*100:.0f}%, Call {call_pct*100:.0f}%, Raise {raise_pct*100:.0f}%")

                    freq = 0.0
                    if t in ("raise", "bet"):
                        freq = raise_pct
                    elif t in ("call", "check"):
                        freq = call_pct
                    elif t == "fold":
                        freq = fold_pct

                    act_summary = f"{action_verb} with {card_str} ({canon_hand}) from {hero_pos}"
                    if facing_desc:
                        act_summary += f" ({facing_desc})"

                    # Hand has to be folded ONLY if facing a bet and fold is required
                    hand_has_to_be_folded = facing_bet and (fold_pct >= 0.95 or (call_pct < 0.05 and raise_pct < 0.05))

                    if freq < 0.05:
                        blunder_found = True
                        if hand_has_to_be_folded and t != "fold":
                            # Hand-ending mistake: Hero had to fold. The check ends here.
                            exp = (
                                f"{street}: Hero {act_summary}. "
                                f"In RocketSolver active solution, {canon_hand} has {freq*100:.1f}% frequency "
                                f"({strat_desc}). "
                                f"This action deviates significantly from GTO strategy (hand has to be folded). Check ended."
                            )
                            review_reasons.append({
                                "street": street,
                                "action": action_badge,
                                "cards": card_str,
                                "position": hero_pos,
                                "explanation": exp,
                                "solver_strategy": strat
                            })
                            street_analyses.append({
                                "street": street,
                                "seat": act.seat,
                                "action": t,
                                "amount": amt_str,
                                "solver_match": False
                            })
                            if on_action:
                                on_action(f"Blunder detected: {exp}")
                            # Stop checking further streets as hand had to be folded
                            break
                        else:
                            # Non hand-ending mistake (e.g. wrong raise size, call vs raise, bet vs check)
                            exp = (
                                f"{street}: Hero {act_summary}. "
                                f"In RocketSolver active solution, {canon_hand} has {freq*100:.1f}% frequency "
                                f"({strat_desc}). "
                                f"This action deviates from GTO strategy."
                            )
                            review_reasons.append({
                                "street": street,
                                "action": action_badge,
                                "cards": card_str,
                                "position": hero_pos,
                                "explanation": exp,
                                "solver_strategy": strat
                            })
                            street_analyses.append({
                                "street": street,
                                "seat": act.seat,
                                "action": t,
                                "amount": amt_str,
                                "solver_match": False
                            })
                            if on_action:
                                on_action(f"Deviation detected: {exp}")
                            if t == "fold":
                                break
                            if stop_on_error:
                                break

                    else:
                        street_analyses.append({
                            "street": street,
                            "seat": act.seat,
                            "action": t,
                            "amount": amt_str,
                            "solver_match": True
                        })
                        if t == "fold":
                            break

                    # Update bet state after Hero's action
                    if t in ("bet", "raise"):
                        street_raises += 1
                        facing_bet = True
                        last_bettor = {
                            "pos": hero_pos,
                            "amt": amt_str,
                            "action": action_badge,
                            "short": action_badge.split()[0]
                        }

                    # Perform Hero's action so RocketSolver tree advances and user sees full hand replay
                    self.click_action(t)
                    if self.sleep_interruptible(visual_delay, cancel_check):
                        return cancel_result()

                else:
                    v_name = hand.players.get(act.seat).name if act.seat and act.seat in hand.players else f"Villain {act.seat}"
                    if on_action:
                        on_action(f"Villain {v_name} ({pos}) {action_verb}")

                    # Check available action buttons in RocketSolver for villain
                    btns_available = self.detect_action_buttons()
                    # If villain bets/raises but only 1 button (check) exists in the solver tree:
                    if t in ("bet", "raise") and len(btns_available) <= 1:
                        v_issue_exp = (
                            f"{street}: Villain {v_name} in {pos} {action_verb}, but in RocketSolver's solution "
                            f"{pos} has no {t} button at this node (only Check is allowed in the GTO tree). "
                            f"Villain took an off-tree action deviating from GTO strategy."
                        )
                        v_cards = "--"
                        for a in hand.actions:
                            if a.seat == act.seat and a.cards and a.cards != ["back", "back"]:
                                v_cards = " ".join(a.cards)
                                break

                        review_reasons.append({
                            "street": street,
                            "action": action_badge,
                            "cards": v_cards,
                            "position": pos,
                            "explanation": v_issue_exp,
                            "villain_deviation": True
                        })
                        street_analyses.append({
                            "street": street,
                            "seat": act.seat,
                            "action": t,
                            "amount": amt_str,
                            "solver_match": False
                        })
                        if on_action:
                            on_action(f"Villain deviation: {v_issue_exp}")
                        break
                    else:
                        street_analyses.append({
                            "street": street,
                            "seat": act.seat,
                            "action": t,
                            "amount": amt_str,
                            "solver_match": True
                        })

                    if t in ("bet", "raise"):
                        street_raises += 1
                        facing_bet = True
                        last_bettor = {
                            "pos": pos,
                            "amt": amt_str,
                            "action": action_badge,
                            "short": action_badge.split()[0]
                        }
                    self.click_action(t)
                    if self.sleep_interruptible(visual_delay, cancel_check):
                        return cancel_result()

        # Keep the final board and solver state visible on screen so user can inspect it
        if not should_cancel():
            self.sleep_interruptible(1.5, cancel_check)

        if reset_at_end and not should_cancel():
            self.reset_to_root()

        if minimize_at_end and not should_cancel():
            self.minimize()

        has_villain_deviation = any(r.get("villain_deviation") for r in review_reasons)
        return {
            "marked_for_review": blunder_found or has_villain_deviation,
            "review_reasons": review_reasons,
            "street_analyses": street_analyses
        }

