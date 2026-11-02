# -*- coding: utf-8 -*-
"""MIDI 转换器

把 MIDI 渲染成 MP3 / WAV / FLAC / OGG，也能在常见音频格式之间互相转换。
窗口很小，支持把文件直接拖进来。

依赖：numpy、soundfile、lameenc（见「安装依赖.bat」）。
"""

import ctypes
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "MIDI"
APP_VERSION = "1.0"

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ICON_PATH = os.path.join(BASE_DIR, "icon.ico")

# ------------------------------------------------------------------ 配色 / 字体
BG = "#F3F5FA"
CARD_BG = "#FFFFFF"
BORDER = "#DCE3EF"
BORDER_HOVER = "#B9C8E4"
TEXT = "#1E2430"
MUTED = "#79839A"
ACCENT = "#2F6FED"
ACCENT_HOVER = "#255FD0"
ACCENT_SOFT = "#EDF3FE"
GREEN = "#0E9F6E"
RED = "#C0392B"
AMBER = "#B5730A"
DROP_BG = "#FAFCFF"

FONTS = {}

FORMATS = {
    "MP3": {
        "ext": "mp3",
        "qualities": [("128 kbps", "128"), ("192 kbps", "192"), ("320 kbps", "320")],
        "default": "192",
    },
    "WAV": {
        "ext": "wav",
        "qualities": [("22.05 kHz", "22050"), ("44.1 kHz", "44100"), ("48 kHz", "48000")],
        "default": "44100",
    },
    "FLAC": {
        "ext": "flac",
        "qualities": [("快速", "0.2"), ("标准", "0.6"), ("最大压缩", "0.9")],
        "default": "0.6",
    },
    "OGG": {
        "ext": "ogg",
        "qualities": [("低", "0.2"), ("标准", "0.5"), ("高", "0.9")],
        "default": "0.5",
    },
}
FORMAT_ORDER = ["MP3", "WAV", "FLAC", "OGG"]


# ------------------------------------------------------------------ 基础工具
def enable_dpi_awareness():
    if os.name != "nt":
        return
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def ui_scale(window):
    try:
        return max(1.0, min(3.0, window.winfo_fpixels("1i") / 96.0))
    except Exception:
        return 1.0


def setup_fonts(root):
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    family = None
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI"):
        if name in families:
            family = name
            break
    if not family:
        family = "TkDefaultFont"
    FONTS["drop"] = (family, 10, "bold")
    FONTS["drop_small"] = (family, 8)
    FONTS["file"] = (family, 9, "bold")
    FONTS["body"] = (family, 9)
    FONTS["button"] = (family, 10, "bold")
    FONTS["status"] = (family, 8)
    FONTS["family"] = family


def setup_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "TCombobox",
        fieldbackground=CARD_BG,
        background=CARD_BG,
        foreground=TEXT,
        arrowcolor=MUTED,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(4, 2),
        relief="flat",
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", CARD_BG), ("disabled", "#F0F3F9")],
        foreground=[("disabled", MUTED)],
        bordercolor=[("hover", BORDER_HOVER), ("focus", ACCENT)],
        arrowcolor=[("disabled", "#B8C1D2")],
    )
    root.option_add("*TCombobox*Listbox.font", FONTS["body"])
    root.option_add("*TCombobox*Listbox.background", CARD_BG)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_SOFT)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)


def resolve_geometry(window, geo):
    if not geo:
        return None
    m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", str(geo).strip())
    if not m:
        return None
    w, h, x, y = (int(v) for v in m.groups())
    try:
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
    except Exception:
        return None
    if x < -w + 40 or y < -h + 40 or x > sw - 40 or y > sh - 40:
        return None
    return w, h, x, y


# ------------------------------------------------------------------ 配置
DEFAULT_QUALITY = {k: v["default"] for k, v in FORMATS.items()}
DEFAULT_SETTINGS = {
    "format": "MP3",
    "quality": dict(DEFAULT_QUALITY),
    "window_geometry": "",
    "last_dir": "",
}


def load_settings():
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        data = raw.get("settings", raw) if isinstance(raw, dict) else {}
        if isinstance(data, dict):
            fmt = data.get("format")
            if fmt in FORMATS:
                settings["format"] = fmt
            q = data.get("quality")
            if isinstance(q, dict):
                for k in FORMATS:
                    if q.get(k) in [v for _label, v in FORMATS[k]["qualities"]]:
                        settings["quality"][k] = q[k]
            for key in ("window_geometry", "last_dir"):
                if isinstance(data.get(key), str):
                    settings[key] = data[key]
    except FileNotFoundError:
        pass
    except Exception:
        try:
            os.replace(CONFIG_PATH, CONFIG_PATH + ".broken")
        except Exception:
            pass
    return settings


def save_settings(settings):
    try:
        payload = {"version": 1, "settings": settings}
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        pass


# ------------------------------------------------------------------ 拖放
WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4

_user32 = ctypes.windll.user32
_shell32 = ctypes.windll.shell32
_kernel32 = ctypes.windll.kernel32

_user32.SetWindowLongPtrW.restype = ctypes.c_void_p
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
_user32.GetWindowLongPtrW.restype = ctypes.c_void_p
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]
_user32.CallWindowProcW.restype = ctypes.c_ssize_t
_user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                    wintypes.WPARAM, wintypes.LPARAM]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                   wintypes.WPARAM, wintypes.LPARAM]
_shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
_shell32.DragQueryFileW.restype = wintypes.UINT
_shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
_shell32.DragFinish.argtypes = [wintypes.HANDLE]


class DropTarget:
    """给 Tk 窗口挂上 Windows 原生 WM_DROPFILES（不需要额外 pip 包）。"""

    def __init__(self, root, callback):
        self.root = root
        self.callback = callback
        self._hwnds = []
        self._old = {}
        self._proc = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )(self._wndproc)
        root.update_idletasks()
        try:
            client = root.winfo_id()
            frame = int(root.wm_frame(), 16)
        except Exception:
            return
        for hwnd in dict.fromkeys((client, frame)):
            if not hwnd:
                continue
            _shell32.DragAcceptFiles(hwnd, True)
            old = _user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, self._proc)
            self._old[hwnd] = old
            self._hwnds.append(hwnd)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_DROPFILES:
            try:
                n = _shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                files = []
                for i in range(n):
                    ln = _shell32.DragQueryFileW(wparam, i, None, 0)
                    buf = ctypes.create_unicode_buffer(ln + 1)
                    _shell32.DragQueryFileW(wparam, i, buf, ln + 1)
                    files.append(buf.value)
            finally:
                try:
                    _shell32.DragFinish(wparam)
                except Exception:
                    pass
            try:
                self.callback(files)
            except Exception:
                pass
            return 0
        old = self._old.get(hwnd)
        if old:
            return _user32.CallWindowProcW(old, hwnd, msg, wparam, lparam)
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def close(self):
        for hwnd in list(self._hwnds):
            try:
                _shell32.DragAcceptFiles(hwnd, False)
                old = self._old.get(hwnd)
                if old:
                    _user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, old)
            except Exception:
                pass
        self._hwnds = []
        self._old = {}


# ------------------------------------------------------------------ 主窗口
class App:
    def __init__(self, root, engine):
        self.root = root
        self.engine = engine
        self.settings = load_settings()
        self.files = []
        self.outputs = []
        self.last_error = ""
        self.busy = False
        self.queue = queue.Queue()
        self.drop_target = None
        self._drop_size = (0, 0)

        self.scale = ui_scale(root)
        self.width = int(round(200 * self.scale))
        self.height = int(round(200 * self.scale))
        self.pad = int(round(8 * self.scale))

        root.title(APP_TITLE)
        root.configure(bg=BG)
        root.resizable(False, False)
        try:
            if os.path.isfile(ICON_PATH):
                root.iconbitmap(ICON_PATH)
        except Exception:
            pass
        self._place_window()
        setup_fonts(root)
        setup_style(root)

        self._build()
        self._refresh_quality()
        self._render_drop()
        self._set_status("就绪")

        self.drop_target = DropTarget(root, self.on_drop)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Return>", self._on_enter)
        root.bind("<Escape>", lambda e: None)
        root.update_idletasks()
        self._tweak_caption()

    def _on_enter(self, event):
        if isinstance(event.widget, ttk.Combobox):
            return
        if not self.busy:
            self.start_convert()

    def _tweak_caption(self):
        """窗口固定大小，去掉最大化的按钮，给标题栏多留一点宽度。"""
        if os.name != "nt":
            return
        try:
            hwnd = int(self.root.wm_frame(), 16)
            GWL_STYLE = -16
            WS_MAXIMIZEBOX = 0x00010000
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            style = _user32.GetWindowLongPtrW(hwnd, GWL_STYLE) or 0
            _user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style & ~WS_MAXIMIZEBOX)
            _user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    # ---------------- 布局
    def _px(self, v):
        return int(round(v * self.scale))

    def _place_window(self):
        geo = resolve_geometry(self.root, self.settings.get("window_geometry", ""))
        if geo:
            _w, _h, x, y = geo
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(0, (sw - self.width) // 2)
            y = max(0, (sh - self.height) // 3)
        self.root.geometry("%dx%d+%d+%d" % (self.width, self.height, x, y))

    def _build(self):
        s = self.scale
        p = self.pad
        w = self.width - p * 2
        drop_h = self._px(100)

        self.drop = tk.Canvas(
            self.root, bg=BG, highlightthickness=0, bd=0,
            width=w, height=drop_h, cursor="hand2", takefocus=0,
        )
        self.drop.place(x=p, y=p, width=w, height=drop_h)
        self.drop.bind("<Button-1>", lambda e: self.browse())
        self.drop.bind("<Double-Button-1>", self._on_double_click)
        self.drop.bind("<Enter>", lambda e: self._render_drop(hover=True))
        self.drop.bind("<Leave>", lambda e: self._render_drop(hover=False))
        self.drop.bind("<Configure>", self._on_drop_configure)

        row_y = p + drop_h + self._px(4)
        row_h = self._px(26)
        fmt_w = self._px(74)
        self.var_fmt = tk.StringVar(value=self.settings["format"])
        self.cbo_fmt = ttk.Combobox(
            self.root, textvariable=self.var_fmt, values=FORMAT_ORDER,
            state="readonly", width=6, font=FONTS["body"], justify="center",
        )
        self.cbo_fmt.place(x=p, y=row_y, width=fmt_w, height=row_h)
        self.cbo_fmt.bind("<<ComboboxSelected>>", self._on_format_change)

        self.var_quality = tk.StringVar()
        self.cbo_quality = ttk.Combobox(
            self.root, textvariable=self.var_quality, state="readonly",
            width=12, font=FONTS["body"], justify="center",
        )
        self.cbo_quality.place(x=p + fmt_w + self._px(6), y=row_y,
                               width=w - fmt_w - self._px(6), height=row_h)
        self.cbo_quality.bind("<<ComboboxSelected>>", self._on_quality_change)

        btn_y = row_y + row_h + self._px(5)
        btn_h = self._px(30)
        self.btn = tk.Button(
            self.root, text="转  换", command=self.start_convert,
            bg=ACCENT, fg=CARD_BG, activebackground=ACCENT_HOVER,
            activeforeground=CARD_BG, disabledforeground="#FFFFFF",
            relief="flat", bd=0, font=FONTS["button"], cursor="hand2", takefocus=0,
        )
        self.btn.place(x=p, y=btn_y, width=w, height=btn_h)
        self.btn.bind("<Enter>", lambda e: self.btn.configure(bg=ACCENT_HOVER) if not self.busy else None)
        self.btn.bind("<Leave>", lambda e: self.btn.configure(bg=ACCENT) if not self.busy else None)

        status_y = btn_y + btn_h + self._px(3)
        status_h = self.height - p - status_y
        self.status = tk.Label(
            self.root, text="", bg=BG, fg=MUTED, font=FONTS["status"],
            anchor="w", justify="left", cursor="hand2",
        )
        self.status.place(x=p, y=status_y, width=w, height=max(14, status_h))
        self.status.bind("<Button-1>", lambda e: self.open_output())
        self.status.bind("<Button-3>", lambda e: self.show_details())

    # ---------------- 拖放区绘制
    def _truncate(self, text, limit):
        if len(text) <= limit:
            return text
        return text[: max(1, limit - 1)] + "…"

    def _render_drop(self, hover=False):
        c = self.drop
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1:
            w = self.width - self.pad * 2
        if h <= 1:
            h = self._px(100)
        if self.files:
            outline = ACCENT
            bg = ACCENT_SOFT
        else:
            outline = BORDER_HOVER if hover else BORDER
            bg = CARD_BG if hover else DROP_BG
        c.create_rectangle(2, 2, w - 2, h - 2, fill=bg, outline=outline,
                           width=1, dash=(4, 3))
        if not self.files:
            c.create_text(w / 2, h * 0.28, text="♫", fill=ACCENT,
                          font=(FONTS["family"], int(15 * self.scale)))
            c.create_text(w / 2, h * 0.53, text="拖入 MIDI / 音频", fill=TEXT,
                          font=FONTS["drop"])
            c.create_text(w / 2, h * 0.75, text="或点击选择文件", fill=MUTED,
                          font=FONTS["drop_small"])
        else:
            if len(self.files) == 1:
                name = os.path.basename(self.files[0])
                c.create_text(w / 2, h * 0.30, text="已选择 1 个文件", fill=MUTED,
                              font=FONTS["drop_small"])
                c.create_text(w / 2, h * 0.54, text=self._truncate(name, 20),
                              fill=TEXT, font=FONTS["file"])
                ext = os.path.splitext(name)[1].lower().lstrip(".")
                tip = ("MIDI" if ext in ("mid", "midi", "rmi", "kar") else ext.upper())
                c.create_text(w / 2, h * 0.75, text="%s · 点击可更换" % (tip or "文件"),
                              fill=MUTED, font=FONTS["drop_small"])
            else:
                c.create_text(w / 2, h * 0.32, text="已选择 %d 个文件" % len(self.files),
                              fill=TEXT, font=FONTS["drop"])
                c.create_text(w / 2, h * 0.58, text=self._truncate(
                    os.path.basename(self.files[0]), 20), fill=MUTED,
                    font=FONTS["drop_small"])
                c.create_text(w / 2, h * 0.78, text="点击可重新选择", fill=MUTED,
                              font=FONTS["drop_small"])

    def _on_double_click(self, _event):
        if self.files:
            self.start_convert()
        else:
            self.browse()

    def _on_drop_configure(self, event):
        size = (event.width, event.height)
        if size != self._drop_size:
            self._drop_size = size
            self._render_drop()

    # ---------------- 选择文件
    def _filetypes(self):
        return [
            ("支持的文件", "*.mid *.midi *.rmi *.kar *.wav *.mp3 *.flac *.ogg *.oga *.aif *.aiff"),
            ("MIDI", "*.mid *.midi *.rmi *.kar"),
            ("音频", "*.wav *.mp3 *.flac *.ogg *.oga *.aif *.aiff"),
            ("所有文件", "*.*"),
        ]

    def browse(self):
        if self.busy:
            return
        initial = self.settings.get("last_dir") or os.path.expanduser("~")
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        paths = filedialog.askopenfilenames(
            parent=self.root, title="选择 MIDI 或音频文件",
            initialdir=initial, filetypes=self._filetypes(),
        )
        if paths:
            self.set_files(list(paths))

    def on_drop(self, paths):
        if self.busy:
            self._set_status("正在转换，请稍候…", MUTED)
            return
        files = []
        for path in paths:
            try:
                if os.path.isfile(path):
                    files.append(path)
                elif os.path.isdir(path):
                    for name in sorted(os.listdir(path)):
                        full = os.path.join(path, name)
                        if os.path.isfile(full) and self.engine.is_supported(full):
                            files.append(full)
            except OSError:
                continue
        if not files:
            self._set_status("没有可转换的文件", RED)
            return
        self.set_files(files)

    def set_files(self, files):
        good = [f for f in files if self.engine.is_supported(f)]
        if not good:
            self._set_status("不支持的文件格式", RED)
            return
        self.files = good[:50]
        self.outputs = []
        self.last_error = ""
        try:
            self.settings["last_dir"] = os.path.dirname(self.files[0])
        except Exception:
            pass
        self._render_drop()
        if len(self.files) == 1:
            self._set_status("点击「转换」开始", MUTED)
        else:
            self._set_status("已选择 %d 个文件" % len(self.files), MUTED)

    # ---------------- 格式 / 质量
    def _quality_values(self):
        return [label for label, _v in FORMATS[self.var_fmt.get()]["qualities"]]

    def _refresh_quality(self):
        fmt = self.var_fmt.get()
        if fmt not in FORMATS:
            fmt = "MP3"
            self.var_fmt.set(fmt)
        values = self._quality_values()
        self.cbo_quality.configure(values=values)
        target = self.settings["quality"].get(fmt, FORMATS[fmt]["default"])
        index = 0
        for i, (_label, value) in enumerate(FORMATS[fmt]["qualities"]):
            if value == target:
                index = i
                break
        self.cbo_quality.current(index)

    def _on_format_change(self, _event=None):
        self._refresh_quality()
        self.settings["format"] = self.var_fmt.get()
        save_settings(self.settings)

    def _on_quality_change(self, _event=None):
        fmt = self.var_fmt.get()
        idx = self.cbo_quality.current()
        if fmt in FORMATS and 0 <= idx < len(FORMATS[fmt]["qualities"]):
            self.settings["quality"][fmt] = FORMATS[fmt]["qualities"][idx][1]
        save_settings(self.settings)

    def current_format(self):
        fmt = self.var_fmt.get()
        return FORMATS[fmt]["ext"], fmt

    def current_quality(self):
        fmt = self.var_fmt.get()
        idx = self.cbo_quality.current()
        if 0 <= idx < len(FORMATS[fmt]["qualities"]):
            return FORMATS[fmt]["qualities"][idx][1]
        return FORMATS[fmt]["default"]

    # ---------------- 转换
    def start_convert(self):
        if self.busy:
            return
        if not self.files:
            self.browse()
            if not self.files:
                return
        fmt_ext, fmt_name = self.current_format()
        quality = self.current_quality()
        files = list(self.files)
        self.outputs = []
        self.last_error = ""
        self._set_busy(True)
        self._set_status("准备中…", MUTED)
        t = threading.Thread(target=self._work, args=(files, fmt_ext, quality), daemon=True)
        t.start()
        self.root.after(80, self._poll)

    def _work(self, files, fmt_ext, quality):
        outputs = []
        errors = []
        total = len(files)
        for i, src in enumerate(files):
            self.queue.put(("head", i, total, os.path.basename(src)))
            try:
                dst = self.engine.unique_output_path(src, fmt_ext)
                last_pct = [-1]

                def progress(p, _i=i, _last=last_pct):
                    pct = max(0, min(100, int(p * 100)))
                    if pct != _last[0]:
                        _last[0] = pct
                        self.queue.put(("progress", _i, total, pct))

                self.engine.convert_file(src, dst, fmt_ext, quality, progress=progress)
                outputs.append(dst)
                self.queue.put(("ok", i, total, dst))
            except Exception as e:
                errors.append((src, str(e)))
                self.queue.put(("err", i, total, str(e)))
        self.queue.put(("done", outputs, errors))

    def _poll(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "head":
                    _i, total, name = msg[1], msg[2], msg[3]
                    if not total == 1:
                        self._set_status("转换中 %d/%d：%s" % (_i + 1, total, self._truncate(name, 12)), MUTED)
                    else:
                        self._set_status("转换中…", MUTED)
                elif kind == "progress":
                    _i, total, pct = msg[1], msg[2], msg[3]
                    if total == 1:
                        self._set_status("转换中 %d%%" % pct, MUTED)
                    else:
                        self._set_status("转换中 %d/%d · %d%%" % (_i + 1, total, pct), MUTED)
                elif kind == "ok":
                    self.outputs.append(msg[3])
                elif kind == "err":
                    self.last_error = msg[3]
                elif kind == "done":
                    self._finish(msg[1], msg[2])
                    return
        except queue.Empty:
            pass
        if self.busy:
            self.root.after(90, self._poll)

    def _finish(self, outputs, errors):
        self._set_busy(False)
        self.outputs = outputs
        if errors and not outputs:
            self.last_error = errors[0][1]
            self._set_status("失败：%s" % self._truncate(self.last_error, 22), RED)
        elif errors:
            self.last_error = errors[0][1]
            self._set_status("完成 %d 个，失败 %d 个（右键看详情）" % (len(outputs), len(errors)), AMBER)
        elif len(outputs) == 1:
            self._set_status("已保存 %s · 点击打开" % self._truncate(os.path.basename(outputs[0]), 12), GREEN)
        else:
            self._set_status("已保存 %d 个文件 · 点击打开" % len(outputs), GREEN)
        save_settings(self.settings)

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "readonly"
        try:
            self.cbo_fmt.configure(state=state)
            self.cbo_quality.configure(state=state)
            self.btn.configure(
                text="转换中…" if busy else "转  换",
                state="disabled" if busy else "normal",
                bg="#AFC4E8" if busy else ACCENT,
            )
        except Exception:
            pass

    def _set_status(self, text, color=MUTED):
        try:
            self.status.configure(text=text, fg=color)
        except Exception:
            pass

    # ---------------- 打开输出 / 详情
    def open_output(self):
        if self.busy:
            return
        if self.outputs:
            path = self.outputs[0]
            try:
                subprocess.Popen(["explorer.exe", "/select," + os.path.normpath(path)])
                return
            except Exception:
                try:
                    os.startfile(os.path.dirname(path))
                    return
                except Exception:
                    pass
        if self.last_error:
            messagebox.showerror("转换失败", self.last_error, parent=self.root)

    def show_details(self, _event=None):
        if self.outputs or self.last_error:
            lines = []
            if self.outputs:
                lines.append("输出文件：")
                lines.extend(self.outputs[:20])
            if self.last_error:
                lines.append("")
                lines.append("错误：")
                lines.append(self.last_error)
            messagebox.showinfo("转换结果", "\n".join(lines), parent=self.root)

    # ---------------- 关闭
    def on_close(self):
        if self.busy:
            if not messagebox.askyesno("正在转换", "转换还没完成，确定要退出吗？", parent=self.root):
                return
        try:
            geo = self.root.geometry()
            m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", geo)
            if m:
                self.settings["window_geometry"] = "%dx%d+%s+%s" % (
                    self.width, self.height, m.group(3), m.group(4))
            save_settings(self.settings)
        except Exception:
            pass
        if self.drop_target:
            self.drop_target.close()
        self.root.destroy()


# ------------------------------------------------------------------ 入口
def load_engine():
    try:
        import engine
        return engine
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "缺少运行组件",
            "MIDI 转换器需要以下组件：\n"
            "    numpy、soundfile、lameenc\n\n"
            "请双击本目录里的「安装依赖.bat」，\n"
            "或在命令行运行：\n"
            "    pip install numpy soundfile lameenc\n\n"
            "详细信息：%s" % e,
            parent=root,
        )
        root.destroy()
        return None


def main():
    enable_dpi_awareness()
    engine = load_engine()
    if engine is None:
        return
    root = tk.Tk()
    app = App(root, engine)
    root.mainloop()


if __name__ == "__main__":
    main()
