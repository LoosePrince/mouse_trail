import configparser
import ctypes
import os
import subprocess
import sys
import time
import traceback
from ctypes import wintypes

import win32api
import win32con
import win32gui
from pynput import mouse as pynput_mouse

# ---------------------------------------------------------------------------
# Win32 / GDI+ bindings
# ---------------------------------------------------------------------------

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
gdiplus = ctypes.windll.gdiplus
shell32 = ctypes.windll.shell32
comdlg32 = ctypes.windll.comdlg32

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_HSCROLL = 0x0114
WM_TRAYICON = win32con.WM_USER + 1
WM_GLOBAL_CLICK = win32con.WM_USER + 2

TIMER_TRAIL = 1

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

BI_RGB = 0
DIB_RGB_COLORS = 0

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205

TBS_AUTOTICKS = 0x0001
TBM_SETRANGE = win32con.WM_USER + 6
TBM_SETPOS = win32con.WM_USER + 5
TBM_GETPOS = win32con.WM_USER

CC_RGBINIT = 0x00000001
CC_FULLOPEN = 0x00000002

IDM_SHOW_TERMINAL = 1001
IDM_COLOR = 1002
IDM_SMOOTH = 1003
IDM_SETTINGS = 1004
IDM_INSTRUCTIONS = 1005
IDM_AUTO_START = 1006
IDM_QUIT = 1007

AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_REG_NAME = "MouseTrail"

IDT_THICKNESS = 2001
IDT_OPACITY = 2002
IDT_FRAMERATE = 2003
IDT_SKIP_CENTER_THRESHOLD = 2004
IDC_CLICK_ANIM = 2101
IDC_TRAIL = 2102
IDC_OPACITY_VAR = 2103
IDC_WIDTH_VAR = 2104
IDC_SKIP_CENTER_CLICK = 2105
IDC_ADMIN_MODE = 2106
IDC_APPLY = 2201
IDC_CANCEL = 2202

UnitPixel = 2
SmoothingModeAntiAlias = 4
LineCapFlat = 0
LineCapRound = 2
LineJoinRound = 2
FillModeAlternate = 0

class GpPointF(ctypes.Structure):
    _fields_ = [("X", ctypes.c_float), ("Y", ctypes.c_float)]


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", ctypes.c_uint32),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", ctypes.c_int),
        ("SuppressExternalCodecs", ctypes.c_int),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
    ]


class CHOOSECOLORW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("rgbResult", wintypes.COLORREF),
        ("lpCustColors", ctypes.POINTER(wintypes.DWORD)),
        ("Flags", wintypes.DWORD),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", wintypes.LPCWSTR),
    ]


_OVERLAY_WINDOWS = {}
_TRAY_WINDOWS = {}
_TERMINAL_WINDOWS = {}
_SETTINGS_WINDOWS = {}
_INSTRUCTIONS_WINDOWS = {}


def _init_gdiplus_api():
    gdiplus.GdipCreateFromHDC.argtypes = [wintypes.HDC, ctypes.POINTER(ctypes.c_void_p)]
    gdiplus.GdipCreateFromHDC.restype = ctypes.c_int
    gdiplus.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
    gdiplus.GdipSetSmoothingMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdiplus.GdipGraphicsClear.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    gdiplus.GdipCreatePen1.argtypes = [ctypes.c_uint32, ctypes.c_float, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    gdiplus.GdipDeletePen.argtypes = [ctypes.c_void_p]
    gdiplus.GdipSetPenStartCap.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdiplus.GdipSetPenEndCap.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdiplus.GdipDrawLine.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_float,
        ctypes.c_float,
        ctypes.c_float,
        ctypes.c_float,
    ]
    gdiplus.GdipDrawEllipse.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_float,
        ctypes.c_float,
        ctypes.c_float,
        ctypes.c_float,
    ]
    gdiplus.GdipCreatePath.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    gdiplus.GdipDeletePath.argtypes = [ctypes.c_void_p]
    gdiplus.GdipAddPathLine2.argtypes = [ctypes.c_void_p, ctypes.POINTER(GpPointF), ctypes.c_int]
    gdiplus.GdipDrawPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    gdiplus.GdipSetPenLineJoin.argtypes = [ctypes.c_void_p, ctypes.c_int]


def overlay_wndproc(hwnd, msg, wparam, lparam):
    inst = _OVERLAY_WINDOWS.get(hwnd)
    if inst:
        return inst._window_proc(hwnd, msg, wparam, lparam)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def tray_wndproc(hwnd, msg, wparam, lparam):
    inst = _TRAY_WINDOWS.get(hwnd)
    if inst:
        return inst._window_proc(hwnd, msg, wparam, lparam)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def terminal_wndproc(hwnd, msg, wparam, lparam):
    inst = _TERMINAL_WINDOWS.get(hwnd)
    if inst:
        return inst._window_proc(hwnd, msg, wparam, lparam)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def settings_wndproc(hwnd, msg, wparam, lparam):
    inst = _SETTINGS_WINDOWS.get(hwnd)
    if inst:
        return inst._window_proc(hwnd, msg, wparam, lparam)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def instructions_wndproc(hwnd, msg, wparam, lparam):
    inst = _INSTRUCTIONS_WINDOWS.get(hwnd)
    if inst:
        return inst._window_proc(hwnd, msg, wparam, lparam)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


_WNDPROC_KEEPALIVE = [
    overlay_wndproc,
    tray_wndproc,
    terminal_wndproc,
    settings_wndproc,
    instructions_wndproc,
]


def config_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def app_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return config_dir()


def settings_path():
    return os.path.join(config_dir(), "settings.ini")


def get_launch_command():
    if getattr(sys, "frozen", False):
        return f'"{os.path.abspath(sys.executable)}"'
    script = os.path.abspath(__file__)
    executable = sys.executable
    if executable.lower().endswith("python.exe"):
        pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(pythonw):
            executable = pythonw
    return f'"{executable}" "{script}"'


def get_launch_executable_and_params():
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable), ""
    script = os.path.abspath(__file__)
    executable = sys.executable
    if executable.lower().endswith("python.exe"):
        pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(pythonw):
            executable = pythonw
    return executable, f'"{script}"'


def is_admin():
    try:
        return bool(shell32.IsUserAnAdmin())
    except AttributeError:
        return False


def relaunch_elevated():
    executable, params = get_launch_executable_and_params()
    ret = shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    if ret <= 32:
        raise OSError(f"无法以管理员身份启动: {ret}")
    sys.exit(0)


def relaunch_normal():
    subprocess.Popen(f"explorer.exe {get_launch_command()}", shell=True)
    sys.exit(0)


def ensure_admin_mode(settings):
    if settings.get("admin_mode", True) and not is_admin():
        relaunch_elevated()


def is_auto_start_enabled():
    try:
        key = win32api.RegOpenKey(
            win32con.HKEY_CURRENT_USER,
            AUTOSTART_REG_KEY,
            0,
            win32con.KEY_READ,
        )
        try:
            value, _ = win32api.RegQueryValueEx(key, AUTOSTART_REG_NAME)
            return value == get_launch_command()
        except win32api.error:
            return False
        finally:
            win32api.RegCloseKey(key)
    except win32api.error:
        return False


def set_auto_start(enabled):
    key = win32api.RegOpenKey(
        win32con.HKEY_CURRENT_USER,
        AUTOSTART_REG_KEY,
        0,
        win32con.KEY_SET_VALUE,
    )
    try:
        if enabled:
            win32api.RegSetValueEx(
                key,
                AUTOSTART_REG_NAME,
                0,
                win32con.REG_SZ,
                get_launch_command(),
            )
        else:
            try:
                win32api.RegDeleteValue(key, AUTOSTART_REG_NAME)
            except win32api.error:
                pass
    finally:
        win32api.RegCloseKey(key)


def sync_auto_start(enabled):
    if enabled:
        set_auto_start(True)
    else:
        set_auto_start(False)


def hide_console():
    if sys.platform.startswith("win"):
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)


def argb(a, r, g, b):
    return (int(a) << 24) | (int(r) << 16) | (int(g) << 8) | int(b)


def colorref_to_rgb(colorref):
    return colorref & 0xFF, (colorref >> 8) & 0xFF, (colorref >> 16) & 0xFF


def load_settings():
    config = configparser.ConfigParser()
    config.read(settings_path(), encoding="utf-8")
    if not config.has_section("Settings"):
        config.add_section("Settings")

    defaults = {
        "trail_color": "255,0,0",
        "trail_thickness": "5",
        "frame_rate": "60",
        "opacity_enabled": "True",
        "width_enabled": "True",
        "click_animation_enabled": "True",
        "initial_opacity": "1.0",
        "trail_enabled": "True",
        "auto_start": "False",
        "skip_center_click": "True",
        "skip_center_click_threshold": "5",
        "admin_mode": "True",
    }
    for key, value in defaults.items():
        if not config.has_option("Settings", key):
            config.set("Settings", key, value)

    with open(settings_path(), "w", encoding="utf-8") as configfile:
        config.write(configfile)

    trail_color = config.get("Settings", "trail_color")
    r, g, b = map(int, trail_color.split(","))
    auto_start = config.getboolean("Settings", "auto_start")
    sync_auto_start(auto_start)
    return {
        "trail_color": (r, g, b),
        "trail_thickness": config.getint("Settings", "trail_thickness"),
        "frame_rate": config.getint("Settings", "frame_rate"),
        "opacity_enabled": config.getboolean("Settings", "opacity_enabled"),
        "width_enabled": config.getboolean("Settings", "width_enabled"),
        "click_animation_enabled": config.getboolean("Settings", "click_animation_enabled"),
        "initial_opacity": config.getfloat("Settings", "initial_opacity"),
        "trail_enabled": config.getboolean("Settings", "trail_enabled"),
        "auto_start": auto_start,
        "skip_center_click": config.getboolean("Settings", "skip_center_click"),
        "skip_center_click_threshold": config.getint("Settings", "skip_center_click_threshold"),
        "admin_mode": config.getboolean("Settings", "admin_mode"),
    }


def save_settings(**kwargs):
    config = configparser.ConfigParser()
    config.read(settings_path(), encoding="utf-8")
    if not config.has_section("Settings"):
        config.add_section("Settings")

    if "trail_color" in kwargs and kwargs["trail_color"] is not None:
        r, g, b = kwargs["trail_color"]
        config.set("Settings", "trail_color", f"{r},{g},{b}")
    if kwargs.get("trail_thickness") is not None:
        config.set("Settings", "trail_thickness", str(kwargs["trail_thickness"]))
    if kwargs.get("frame_rate") is not None:
        config.set("Settings", "frame_rate", str(kwargs["frame_rate"]))
    if kwargs.get("opacity_enabled") is not None:
        config.set("Settings", "opacity_enabled", str(kwargs["opacity_enabled"]))
    if kwargs.get("width_enabled") is not None:
        config.set("Settings", "width_enabled", str(kwargs["width_enabled"]))
    if kwargs.get("click_animation_enabled") is not None:
        config.set("Settings", "click_animation_enabled", str(kwargs["click_animation_enabled"]))
    if kwargs.get("initial_opacity") is not None:
        config.set("Settings", "initial_opacity", str(kwargs["initial_opacity"]))
    if kwargs.get("trail_enabled") is not None:
        config.set("Settings", "trail_enabled", str(kwargs["trail_enabled"]))
    if kwargs.get("auto_start") is not None:
        config.set("Settings", "auto_start", str(kwargs["auto_start"]))
    if kwargs.get("skip_center_click") is not None:
        config.set("Settings", "skip_center_click", str(kwargs["skip_center_click"]))
    if kwargs.get("skip_center_click_threshold") is not None:
        config.set("Settings", "skip_center_click_threshold", str(kwargs["skip_center_click_threshold"]))
    if kwargs.get("admin_mode") is not None:
        config.set("Settings", "admin_mode", str(kwargs["admin_mode"]))

    with open(settings_path(), "w", encoding="utf-8") as configfile:
        config.write(configfile)

    if kwargs.get("auto_start") is not None:
        sync_auto_start(kwargs["auto_start"])


class GdiplusSession:
    def __init__(self):
        _init_gdiplus_api()
        self.token = ctypes.c_ulong()
        startup = GdiplusStartupInput()
        startup.GdiplusVersion = 1
        status = gdiplus.GdiplusStartup(ctypes.byref(self.token), ctypes.byref(startup), None)
        if status != 0:
            raise OSError(f"GdiplusStartup failed: {status}")

    def shutdown(self):
        gdiplus.GdiplusShutdown(self.token)


class PointF:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)


def catmull_rom_spline(p0, p1, p2, p3, segments=10):
    points = []
    for i in range(segments + 1):
        t = i / segments
        t2 = t * t
        t3 = t2 * t
        x = 0.5 * (
            (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3
            + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2
            + (-p0.x + p2.x) * t
            + 2 * p1.x
        )
        y = 0.5 * (
            (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3
            + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2
            + (-p0.y + p2.y) * t
            + 2 * p1.y
        )
        points.append(PointF(x, y))
    return points


class TrailOverlay:
    def __init__(self, terminal, settings):
        self.terminal = terminal
        self.settings = settings
        self.trail = []
        self.max_trail_length = 50
        self.last_pos = None
        self.cursor_local = None
        self.click_animations = []
        self.smooth_mode = True
        self._layer_dc = None
        self._layer_bmp = None
        self._layer_old = None

        self.screen_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.screen_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self.screen_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        self.screen_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

        self.class_name = "MouseTrailOverlay"
        self._register_class()
        self.hwnd = self._create_window()
        _OVERLAY_WINDOWS[self.hwnd] = self
        self._apply_timer_interval()
        self._render_frame()

    def _register_class(self):
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = self.class_name
        wc.lpfnWndProc = overlay_wndproc
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as exc:
            if exc.winerror != 1410:
                raise

    def _create_window(self):
        ex_style = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
        style = win32con.WS_POPUP
        hwnd = win32gui.CreateWindowEx(
            ex_style,
            self.class_name,
            "MouseTrailOverlay",
            style,
            self.screen_x,
            self.screen_y,
            self.screen_w,
            self.screen_h,
            0,
            0,
            win32gui.GetModuleHandle(None),
            None,
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            self.screen_x,
            self.screen_y,
            self.screen_w,
            self.screen_h,
            win32con.SWP_SHOWWINDOW,
        )
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        return hwnd

    def _apply_timer_interval(self):
        if self.smooth_mode:
            interval = 8
        else:
            interval = max(1, 1000 // self.settings["frame_rate"])
        user32.SetTimer(self.hwnd, TIMER_TRAIL, interval, None)

    def set_smooth_mode(self, enabled):
        self.smooth_mode = enabled
        if enabled:
            user32.SetTimer(self.hwnd, TIMER_TRAIL, 8, None)
        else:
            user32.SetTimer(self.hwnd, TIMER_TRAIL, 32, None)

    def apply_settings(self, new_settings):
        self.settings.update(new_settings)
        save_settings(**new_settings)
        self._apply_timer_interval()

    def set_trail_color(self, color):
        self.settings["trail_color"] = color
        save_settings(trail_color=color)

    def global_to_local(self, x, y):
        return x - self.screen_x, y - self.screen_y

    def is_screen_center_click(self, x, y):
        if not self.settings.get("skip_center_click", True):
            return False
        threshold = max(0, min(20, self.settings.get("skip_center_click_threshold", 5)))
        center_x = self.screen_x + self.screen_w // 2
        center_y = self.screen_y + self.screen_h // 2
        dx = x - center_x
        dy = y - center_y
        return dx * dx + dy * dy <= threshold * threshold

    def handle_global_click(self, x, y):
        if self.is_screen_center_click(x, y):
            return
        local_x, local_y = self.global_to_local(x, y)
        self.click_animations.append(
            {
                "center": PointF(local_x, local_y),
                "start": time.time(),
                "duration": 0.5,
                "max_radius": 50,
            }
        )
        self._render_frame()

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TIMER and wparam == TIMER_TRAIL:
            self._update_trail()
            return 0
        if msg == WM_GLOBAL_CLICK:
            # 与拖尾一致，使用 Win32 屏幕坐标，避免 pynput 在高 DPI 下偏移
            point = win32gui.GetCursorPos()
            self.handle_global_click(point[0], point[1])
            return 0
        if msg == WM_DESTROY:
            user32.KillTimer(hwnd, TIMER_TRAIL)
            self._release_layer_buffer()
            _OVERLAY_WINDOWS.pop(hwnd, None)
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _update_trail(self):
        point = win32gui.GetCursorPos()
        local_x, local_y = self.global_to_local(point[0], point[1])
        self.cursor_local = PointF(local_x, local_y)

        if self.last_pos is not None and self.last_pos == (local_x, local_y):
            self._render_frame()
            return

        if self.last_pos is not None:
            distance = abs(local_x - self.last_pos[0]) + abs(local_y - self.last_pos[1])
            if distance < 2:
                self._render_frame()
                return

        self.trail.append((PointF(local_x, local_y), time.time()))
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)
        self.last_pos = (local_x, local_y)
        self._render_frame()

        if self.terminal.visible:
            self.terminal.append(f"Mouse moved to: {local_x}, {local_y}")

    def _clean_old_trail(self):
        current_time = time.time()
        self.trail = [(pos, t) for pos, t in self.trail if current_time - t < 0.5]

    def _ensure_layer_buffer(self):
        if self._layer_dc is not None:
            return
        self._layer_dc = gdi32.CreateCompatibleDC(0)
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = self.screen_w
        bmi.biHeight = -self.screen_h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        self._layer_bmp = gdi32.CreateDIBSection(
            self._layer_dc,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
            ctypes.byref(bits),
            None,
            0,
        )
        self._layer_old = gdi32.SelectObject(self._layer_dc, self._layer_bmp)

    def _release_layer_buffer(self):
        if self._layer_dc is None:
            return
        gdi32.SelectObject(self._layer_dc, self._layer_old)
        gdi32.DeleteObject(self._layer_bmp)
        gdi32.DeleteDC(self._layer_dc)
        self._layer_dc = None
        self._layer_bmp = None
        self._layer_old = None

    def _render_frame(self):
        self._ensure_layer_buffer()
        hdc_mem = self._layer_dc

        graphics = ctypes.c_void_p()
        gdiplus.GdipCreateFromHDC(hdc_mem, ctypes.byref(graphics))
        gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeAntiAlias)
        gdiplus.GdipGraphicsClear(graphics, 0x00000000)

        self._draw_scene(graphics)
        gdiplus.GdipDeleteGraphics(graphics)

        size = wintypes.SIZE(self.screen_w, self.screen_h)
        point_src = wintypes.POINT(0, 0)
        point_dst = wintypes.POINT(self.screen_x, self.screen_y)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        hdc_screen = user32.GetDC(0)
        user32.UpdateLayeredWindow(
            self.hwnd,
            hdc_screen,
            ctypes.byref(point_dst),
            ctypes.byref(size),
            hdc_mem,
            ctypes.byref(point_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )
        user32.ReleaseDC(0, hdc_screen)

    def _create_pen(self, r, g, b, opacity, width, start_cap, end_cap):
        alpha = int(max(0, min(255, opacity * 255)))
        if alpha <= 0 or width <= 0:
            return None
        pen = ctypes.c_void_p()
        gdiplus.GdipCreatePen1(argb(alpha, r, g, b), float(width), UnitPixel, ctypes.byref(pen))
        gdiplus.GdipSetPenStartCap(pen, start_cap)
        gdiplus.GdipSetPenEndCap(pen, end_cap)
        gdiplus.GdipSetPenLineJoin(pen, LineJoinRound)
        return pen

    def _draw_polyline(self, graphics, points, r, g, b, opacity, width, round_start=False, round_end=False):
        if len(points) < 2:
            return
        pen = self._create_pen(
            r,
            g,
            b,
            opacity,
            width,
            LineCapRound if round_start else LineCapFlat,
            LineCapRound if round_end else LineCapFlat,
        )
        if pen is None:
            return

        gp_points = (GpPointF * len(points))()
        for index, point in enumerate(points):
            gp_points[index].X = point.x
            gp_points[index].Y = point.y

        path = ctypes.c_void_p()
        if gdiplus.GdipCreatePath(FillModeAlternate, ctypes.byref(path)) != 0:
            gdiplus.GdipDeletePen(pen)
            return
        if gdiplus.GdipAddPathLine2(path, gp_points, len(points)) != 0:
            gdiplus.GdipDeletePath(path)
            gdiplus.GdipDeletePen(pen)
            return
        gdiplus.GdipDrawPath(graphics, pen, path)
        gdiplus.GdipDeletePath(path)
        gdiplus.GdipDeletePen(pen)

    def _draw_scene(self, graphics):
        settings = self.settings
        r, g, b = settings["trail_color"]

        if settings["trail_enabled"] and len(self.trail) > 2:
            stroke_batches = []
            current_batch = None
            for i in range(1, len(self.trail) - 1):
                p0 = self.trail[i - 1][0] if i - 1 >= 0 else self.trail[i][0]
                p1 = self.trail[i][0]
                p2 = self.trail[i + 1][0]
                p3 = self.trail[i + 2][0] if i + 2 < len(self.trail) else self.trail[i + 1][0]
                interpolated = catmull_rom_spline(p0, p1, p2, p3, segments=10)
                age = time.time() - self.trail[i][1]

                if settings["opacity_enabled"]:
                    opacity = max(0, (1 - age / 0.5) * settings["initial_opacity"])
                else:
                    opacity = settings["initial_opacity"]

                if settings["width_enabled"]:
                    width = max(0.0, settings["trail_thickness"] * (1 - age / 0.5))
                else:
                    width = float(settings["trail_thickness"])

                if opacity <= 0 or width <= 0:
                    current_batch = None
                    continue

                style_key = (int(opacity * 255) // 12, int(width * 2))
                if current_batch and current_batch["style_key"] == style_key:
                    current_batch["points"].extend(interpolated[1:])
                else:
                    if current_batch:
                        stroke_batches.append(current_batch)
                    current_batch = {
                        "points": list(interpolated),
                        "opacity": opacity,
                        "width": width,
                        "style_key": style_key,
                    }

            if current_batch:
                stroke_batches.append(current_batch)

            for index, batch in enumerate(stroke_batches):
                self._draw_polyline(
                    graphics,
                    batch["points"],
                    r,
                    g,
                    b,
                    batch["opacity"],
                    batch["width"],
                    round_start=(index == 0),
                    round_end=(index == len(stroke_batches) - 1),
                )

            if self.cursor_local is not None and len(self.trail) >= 1:
                head = self.trail[-1][0]
                if head.x != self.cursor_local.x or head.y != self.cursor_local.y:
                    self._draw_polyline(
                        graphics,
                        [head, self.cursor_local],
                        r,
                        g,
                        b,
                        settings["initial_opacity"],
                        settings["trail_thickness"],
                        round_start=False,
                        round_end=True,
                    )

        self._clean_old_trail()

        if settings["click_animation_enabled"]:
            current_time = time.time()
            for anim in self.click_animations[:]:
                progress = (current_time - anim["start"]) / anim["duration"]
                if progress >= 1.0:
                    self.click_animations.remove(anim)
                    continue
                radius = anim["max_radius"] * progress
                alpha = int(255 * (1 - progress))
                pen = ctypes.c_void_p()
                gdiplus.GdipCreatePen1(argb(alpha, r, g, b), 3.0, UnitPixel, ctypes.byref(pen))
                gdiplus.GdipDrawEllipse(
                    graphics,
                    pen,
                    ctypes.c_float(anim["center"].x - radius),
                    ctypes.c_float(anim["center"].y - radius),
                    ctypes.c_float(radius * 2),
                    ctypes.c_float(radius * 2),
                )
                gdiplus.GdipDeletePen(pen)


class TerminalWindow:
    def __init__(self):
        self.visible = False
        self.class_name = "MouseTrailTerminal"
        self._register_class()
        self.hwnd = self._create_window()
        _TERMINAL_WINDOWS[self.hwnd] = self
        self.edit_hwnd = win32gui.CreateWindowEx(
            0,
            "EDIT",
            "",
            win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.WS_VSCROLL | win32con.ES_MULTILINE | win32con.ES_READONLY | win32con.ES_AUTOVSCROLL,
            10,
            10,
            380,
            280,
            self.hwnd,
            0,
            win32gui.GetModuleHandle(None),
            None,
        )

    def _register_class(self):
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = self.class_name
        wc.lpfnWndProc = terminal_wndproc
        wc.hbrBackground = win32con.COLOR_WINDOW + 1
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as exc:
            if exc.winerror != 1410:
                raise

    def _create_window(self):
        return win32gui.CreateWindowEx(
            0,
            self.class_name,
            "终端",
            win32con.WS_OVERLAPPEDWINDOW,
            100,
            100,
            420,
            340,
            0,
            0,
            win32gui.GetModuleHandle(None),
            None,
        )

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLOSE:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            self.visible = False
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def show(self):
        self.visible = True
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)

    def hide(self):
        self.visible = False
        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)

    def append(self, text):
        win32gui.SendMessage(self.edit_hwnd, win32con.EM_SETSEL, -1, -1)
        win32gui.SendMessage(self.edit_hwnd, win32con.EM_REPLACESEL, 0, text + "\r\n")


class SettingsDialog:
    def __init__(self, parent_hwnd, overlay):
        self.parent_hwnd = parent_hwnd
        self.overlay = overlay
        self.result = None
        self.class_name = "MouseTrailSettings"
        self._register_class()
        self.hwnd = None
        self.controls = {}

    def _register_class(self):
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = self.class_name
        wc.lpfnWndProc = settings_wndproc
        wc.hbrBackground = win32con.COLOR_BTNFACE + 1
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as exc:
            if exc.winerror != 1410:
                raise

    def _create_label(self, text, x, y, width=80):
        return win32gui.CreateWindowEx(
            0,
            "STATIC",
            text,
            win32con.WS_CHILD | win32con.WS_VISIBLE,
            x,
            y,
            width,
            20,
            self.hwnd,
            0,
            win32gui.GetModuleHandle(None),
            None,
        )

    def _create_trackbar(self, ctrl_id, x, y, width, min_val, max_val, value):
        hwnd = win32gui.CreateWindowEx(
            0,
            "msctls_trackbar32",
            "",
            win32con.WS_CHILD | win32con.WS_VISIBLE | TBS_AUTOTICKS,
            x,
            y,
            width,
            30,
            self.hwnd,
            ctrl_id,
            win32gui.GetModuleHandle(None),
            None,
        )
        win32gui.SendMessage(hwnd, TBM_SETRANGE, 1, (max_val << 16) | min_val)
        win32gui.SendMessage(hwnd, TBM_SETPOS, 1, value)
        return hwnd

    def _create_checkbox(self, ctrl_id, text, x, y, checked):
        style = win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.BS_AUTOCHECKBOX
        hwnd = win32gui.CreateWindowEx(
            0,
            "BUTTON",
            text,
            style,
            x,
            y,
            220,
            22,
            self.hwnd,
            ctrl_id,
            win32gui.GetModuleHandle(None),
            None,
        )
        if checked:
            win32gui.SendMessage(hwnd, win32con.BM_SETCHECK, win32con.BST_CHECKED, 0)
        return hwnd

    def show_modal(self):
        settings = self.overlay.settings
        self.hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_DLGMODALFRAME,
            self.class_name,
            "设置",
            win32con.WS_CAPTION | win32con.WS_SYSMENU | win32con.WS_POPUP,
            120,
            120,
            360,
            440,
            self.parent_hwnd,
            0,
            win32gui.GetModuleHandle(None),
            None,
        )
        _SETTINGS_WINDOWS[self.hwnd] = self

        self._create_label("线条粗细:", 16, 18)
        self.controls["thickness"] = self._create_trackbar(IDT_THICKNESS, 100, 14, 180, 1, 20, settings["trail_thickness"])
        self.controls["thickness_label"] = self._create_label(str(settings["trail_thickness"]), 290, 18, 40)

        self._create_label("初始透明度:", 16, 58)
        self.controls["opacity"] = self._create_trackbar(IDT_OPACITY, 100, 54, 180, 0, 100, int(settings["initial_opacity"] * 100))
        self.controls["opacity_label"] = self._create_label(f"{settings['initial_opacity']:.2f}", 290, 58, 40)

        self._create_label("帧率:", 16, 98)
        self.controls["framerate"] = self._create_trackbar(IDT_FRAMERATE, 100, 94, 180, 10, 240, settings["frame_rate"])
        self.controls["framerate_label"] = self._create_label(str(settings["frame_rate"]), 290, 98, 40)

        self.controls["click_anim"] = self._create_checkbox(IDC_CLICK_ANIM, "启用点击动画", 16, 140, settings["click_animation_enabled"])
        self.controls["trail"] = self._create_checkbox(IDC_TRAIL, "启用鼠标拖尾", 16, 166, settings["trail_enabled"])
        self.controls["opacity_var"] = self._create_checkbox(IDC_OPACITY_VAR, "启用透明度变化", 16, 192, settings["opacity_enabled"])
        self.controls["width_var"] = self._create_checkbox(IDC_WIDTH_VAR, "启用粗细变化", 16, 218, settings["width_enabled"])
        self.controls["skip_center_click"] = self._create_checkbox(
            IDC_SKIP_CENTER_CLICK,
            "屏幕正中心不显示点击动画",
            16,
            244,
            settings["skip_center_click"],
        )

        self._create_label("判断阈值:", 16, 274, 90)
        threshold = settings["skip_center_click_threshold"]
        self.controls["skip_center_threshold"] = self._create_trackbar(
            IDT_SKIP_CENTER_THRESHOLD,
            110,
            270,
            170,
            0,
            20,
            threshold,
        )
        self.controls["skip_center_threshold_label"] = self._create_label(f"{threshold}px", 290, 274, 50)

        self.controls["admin_mode"] = self._create_checkbox(
            IDC_ADMIN_MODE,
            "管理员模式（应用后重启）",
            16,
            306,
            settings["admin_mode"],
        )

        win32gui.CreateWindowEx(
            0,
            "BUTTON",
            "应用",
            win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.BS_DEFPUSHBUTTON,
            70,
            350,
            90,
            28,
            self.hwnd,
            IDC_APPLY,
            win32gui.GetModuleHandle(None),
            None,
        )
        win32gui.CreateWindowEx(
            0,
            "BUTTON",
            "取消",
            win32con.WS_CHILD | win32con.WS_VISIBLE,
            190,
            350,
            90,
            28,
            self.hwnd,
            IDC_CANCEL,
            win32gui.GetModuleHandle(None),
            None,
        )

        win32gui.EnableWindow(self.parent_hwnd, False)
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(self.hwnd)

        while win32gui.IsWindow(self.hwnd):
            try:
                rc, msg = win32gui.GetMessage(self.hwnd, 0, 0)
            except win32gui.error:
                break
            if rc == 0:
                break
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)

        _SETTINGS_WINDOWS.pop(self.hwnd, None)
        win32gui.EnableWindow(self.parent_hwnd, True)
        return self.result

    def _read_values(self):
        thickness = win32gui.SendMessage(self.controls["thickness"], TBM_GETPOS, 0, 0)
        opacity = win32gui.SendMessage(self.controls["opacity"], TBM_GETPOS, 0, 0) / 100.0
        frame_rate = win32gui.SendMessage(self.controls["framerate"], TBM_GETPOS, 0, 0)
        frame_rate = (frame_rate // 10) * 10
        return {
            "trail_thickness": thickness,
            "initial_opacity": opacity,
            "frame_rate": frame_rate,
            "click_animation_enabled": win32gui.SendMessage(self.controls["click_anim"], win32con.BM_GETCHECK, 0, 0) == win32con.BST_CHECKED,
            "trail_enabled": win32gui.SendMessage(self.controls["trail"], win32con.BM_GETCHECK, 0, 0) == win32con.BST_CHECKED,
            "opacity_enabled": win32gui.SendMessage(self.controls["opacity_var"], win32con.BM_GETCHECK, 0, 0) == win32con.BST_CHECKED,
            "width_enabled": win32gui.SendMessage(self.controls["width_var"], win32con.BM_GETCHECK, 0, 0) == win32con.BST_CHECKED,
            "skip_center_click": win32gui.SendMessage(self.controls["skip_center_click"], win32con.BM_GETCHECK, 0, 0) == win32con.BST_CHECKED,
            "skip_center_click_threshold": win32gui.SendMessage(self.controls["skip_center_threshold"], TBM_GETPOS, 0, 0),
            "admin_mode": win32gui.SendMessage(self.controls["admin_mode"], win32con.BM_GETCHECK, 0, 0) == win32con.BST_CHECKED,
        }

    def _update_labels(self, ctrl_id):
        if ctrl_id == IDT_THICKNESS:
            value = win32gui.SendMessage(self.controls["thickness"], TBM_GETPOS, 0, 0)
            win32gui.SetWindowText(self.controls["thickness_label"], str(value))
        elif ctrl_id == IDT_OPACITY:
            value = win32gui.SendMessage(self.controls["opacity"], TBM_GETPOS, 0, 0) / 100.0
            win32gui.SetWindowText(self.controls["opacity_label"], f"{value:.2f}")
        elif ctrl_id == IDT_FRAMERATE:
            value = win32gui.SendMessage(self.controls["framerate"], TBM_GETPOS, 0, 0)
            value = (value // 10) * 10
            win32gui.SendMessage(self.controls["framerate"], TBM_SETPOS, 1, value)
            win32gui.SetWindowText(self.controls["framerate_label"], str(value))
        elif ctrl_id == IDT_SKIP_CENTER_THRESHOLD:
            value = win32gui.SendMessage(self.controls["skip_center_threshold"], TBM_GETPOS, 0, 0)
            win32gui.SetWindowText(self.controls["skip_center_threshold_label"], f"{value}px")

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_HSCROLL:
            ctrl_id = win32gui.GetDlgCtrlID(lparam)
            if ctrl_id in (IDT_THICKNESS, IDT_OPACITY, IDT_FRAMERATE, IDT_SKIP_CENTER_THRESHOLD):
                self._update_labels(ctrl_id)
            return 0
        if msg == WM_COMMAND:
            cmd = win32api_lo(wparam)
            if cmd == IDC_APPLY:
                self.result = self._read_values()
                win32gui.DestroyWindow(hwnd)
                return 0
            if cmd == IDC_CANCEL:
                self.result = None
                win32gui.DestroyWindow(hwnd)
                return 0
        if msg == WM_DESTROY:
            _SETTINGS_WINDOWS.pop(hwnd, None)
            return 0
        if msg == WM_CLOSE:
            self.result = None
            win32gui.DestroyWindow(hwnd)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def win32api_lo(wparam):
    return wparam & 0xFFFF


class InstructionsDialog:
    TEXT = (
        "鼠标拖尾说明:\n\n"
        "1. 右键托盘图标打开菜单。\n"
        "2. 流畅模式可在约 120 帧与 30 帧之间切换。\n"
        "3. 设置中可调整颜色、粗细、帧率等；自定义帧率会覆盖流畅模式。\n"
        "4. 开机启动可将本程序加入系统登录自启项。\n"
        "5. settings.ini 为配置文件，与程序放在同一目录。\n\n"
        "© 2023-2024 blog.xzt.plus（@树梢上有只鸟）"
    )

    def __init__(self, parent_hwnd):
        self.parent_hwnd = parent_hwnd
        self.class_name = "MouseTrailInstructions"
        self._register_class()

    def _register_class(self):
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = self.class_name
        wc.lpfnWndProc = instructions_wndproc
        wc.hbrBackground = win32con.COLOR_WINDOW + 1
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as exc:
            if exc.winerror != 1410:
                raise

    def show_modal(self):
        hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_DLGMODALFRAME,
            self.class_name,
            "使用说明",
            win32con.WS_CAPTION | win32con.WS_SYSMENU | win32con.WS_POPUP,
            120,
            120,
            640,
            360,
            self.parent_hwnd,
            0,
            win32gui.GetModuleHandle(None),
            None,
        )
        _INSTRUCTIONS_WINDOWS[hwnd] = self
        win32gui.CreateWindowEx(
            win32con.WS_EX_CLIENTEDGE,
            "STATIC",
            self.TEXT,
            win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.SS_LEFT,
            12,
            12,
            600,
            260,
            hwnd,
            0,
            win32gui.GetModuleHandle(None),
            None,
        )
        win32gui.CreateWindowEx(
            0,
            "BUTTON",
            "确定",
            win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.BS_DEFPUSHBUTTON,
            270,
            285,
            90,
            28,
            hwnd,
            win32con.IDOK,
            win32gui.GetModuleHandle(None),
            None,
        )
        win32gui.EnableWindow(self.parent_hwnd, False)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        while win32gui.IsWindow(hwnd):
            try:
                rc, msg = win32gui.GetMessage(hwnd, 0, 0)
            except win32gui.error:
                break
            if rc == 0:
                break
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)

        _INSTRUCTIONS_WINDOWS.pop(hwnd, None)
        win32gui.EnableWindow(self.parent_hwnd, True)

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_COMMAND and win32api_lo(wparam) == win32con.IDOK:
            win32gui.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            _INSTRUCTIONS_WINDOWS.pop(hwnd, None)
            return 0
        if msg == WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


class TrayApp:
    def __init__(self, overlay, terminal, settings):
        self.overlay = overlay
        self.terminal = terminal
        self.settings = settings
        self.show_terminal = False
        self.smooth_mode = True
        self.auto_start = settings.get("auto_start", False)
        self.class_name = "MouseTrailTrayHost"
        self._register_class()
        self.hwnd = win32gui.CreateWindowEx(
            0,
            self.class_name,
            "MouseTrailTrayHost",
            0,
            0,
            0,
            0,
            0,
            None,
            None,
            win32gui.GetModuleHandle(None),
            None,
        )
        _TRAY_WINDOWS[self.hwnd] = self
        self.icon_path = os.path.join(app_dir(), "1.ico")
        self.hicon = self._load_icon()
        self._add_tray_icon()

    def _register_class(self):
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = self.class_name
        wc.lpfnWndProc = tray_wndproc
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as exc:
            if exc.winerror != 1410:
                raise

    def _load_icon(self):
        if os.path.exists(self.icon_path):
            try:
                return win32gui.LoadImage(
                    0,
                    self.icon_path,
                    win32con.IMAGE_ICON,
                    0,
                    0,
                    win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
                )
            except win32gui.error:
                pass
        return win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

    def _make_tray_nid(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self.hicon
        nid.szTip = "鼠标拖尾"
        return nid

    def _add_tray_icon(self):
        self._nid = self._make_tray_nid()
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid)):
            raise OSError("无法创建系统托盘图标")

    def _remove_tray_icon(self):
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))

    def _show_menu(self):
        menu = win32gui.CreatePopupMenu()
        flags = win32con.MF_STRING | (win32con.MF_CHECKED if self.show_terminal else 0)
        win32gui.AppendMenu(menu, flags, IDM_SHOW_TERMINAL, "显示终端")
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_COLOR, "设置拖尾颜色")
        smooth_flags = win32con.MF_STRING | (win32con.MF_CHECKED if self.smooth_mode else 0)
        win32gui.AppendMenu(menu, smooth_flags, IDM_SMOOTH, "流畅模式")
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_INSTRUCTIONS, "使用说明")
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_SETTINGS, "设置")
        auto_start_flags = win32con.MF_STRING | (win32con.MF_CHECKED if self.auto_start else 0)
        win32gui.AppendMenu(menu, auto_start_flags, IDM_AUTO_START, "开机启动")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_QUIT, "关闭应用")

        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu, win32con.TPM_RIGHTALIGN, pos[0], pos[1], 0, self.hwnd, None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        win32gui.DestroyMenu(menu)

    def _choose_color(self):
        custom_colors = (wintypes.DWORD * 16)()
        r, g, b = self.overlay.settings["trail_color"]
        cc = CHOOSECOLORW()
        cc.lStructSize = ctypes.sizeof(CHOOSECOLORW)
        cc.hwndOwner = self.hwnd
        cc.rgbResult = win32api.RGB(r, g, b)
        cc.lpCustColors = custom_colors
        cc.Flags = CC_RGBINIT | CC_FULLOPEN
        if comdlg32.ChooseColorW(ctypes.byref(cc)):
            rgb = colorref_to_rgb(cc.rgbResult)
            self.overlay.set_trail_color(rgb)

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON and lparam in (WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
            self._show_menu()
            return 0
        if msg == WM_COMMAND:
            cmd = win32api_lo(wparam)
            if cmd == IDM_SHOW_TERMINAL:
                self.show_terminal = not self.show_terminal
                if self.show_terminal:
                    self.terminal.show()
                else:
                    self.terminal.hide()
            elif cmd == IDM_COLOR:
                self._choose_color()
            elif cmd == IDM_SMOOTH:
                self.smooth_mode = not self.smooth_mode
                self.overlay.set_smooth_mode(self.smooth_mode)
            elif cmd == IDM_INSTRUCTIONS:
                InstructionsDialog(hwnd).show_modal()
            elif cmd == IDM_SETTINGS:
                dialog = SettingsDialog(hwnd, self.overlay)
                result = dialog.show_modal()
                if result:
                    self.overlay.smooth_mode = False
                    self.smooth_mode = False
                    old_admin_mode = self.overlay.settings.get("admin_mode", True)
                    new_admin_mode = result.get("admin_mode", True)
                    self.overlay.apply_settings(result)
                    if old_admin_mode != new_admin_mode:
                        if new_admin_mode:
                            relaunch_elevated()
                        else:
                            relaunch_normal()
            elif cmd == IDM_AUTO_START:
                self.auto_start = not self.auto_start
                self.settings["auto_start"] = self.auto_start
                save_settings(auto_start=self.auto_start)
            elif cmd == IDM_QUIT:
                self._remove_tray_icon()
                _TRAY_WINDOWS.pop(hwnd, None)
                win32gui.DestroyWindow(self.overlay.hwnd)
            return 0
        if msg == WM_DESTROY:
            _TRAY_WINDOWS.pop(hwnd, None)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def post_global_click(hwnd):
    user32.PostMessageW(hwnd, WM_GLOBAL_CLICK, 0, 0)


def write_error_log(exc):
    log_path = os.path.join(config_dir(), "mouse_trail_error.log")
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(traceback.format_exc())
    if sys.executable.lower().endswith("pythonw.exe"):
        ctypes.windll.user32.MessageBoxW(
            0,
            f"鼠标拖尾启动失败，详情见:\n{log_path}\n\n{exc}",
            "鼠标拖尾",
            0x10,
        )


def main():
    os.chdir(config_dir())
    hide_console()
    timer_period_set = False
    try:
        if ctypes.windll.winmm.timeBeginPeriod(1) == 0:
            timer_period_set = True
    except OSError:
        pass

    gdi = GdiplusSession()
    settings = load_settings()
    ensure_admin_mode(settings)
    terminal = TerminalWindow()
    overlay = TrailOverlay(terminal, settings)
    tray = TrayApp(overlay, terminal, settings)

    def on_click(x, y, button, pressed):
        if pressed:
            post_global_click(overlay.hwnd)

    listener = pynput_mouse.Listener(on_click=on_click)
    listener.start()

    try:
        while True:
            rc, msg = win32gui.GetMessage(None, 0, 0)
            if rc == 0:
                break
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)
    finally:
        listener.stop()
        gdi.shutdown()
        if timer_period_set:
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except OSError:
                pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_error_log(exc)
        raise
