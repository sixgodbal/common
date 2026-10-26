# -*- coding: utf-8 -*-
"""快速打开文件夹（Quick Folder Launcher）

一键打开某个功能/项目需要的一组文件夹。
配置保存在程序目录下的 config.json，也可以在界面里可视化编辑。

仅依赖 Python 标准库（tkinter），双击本文件即可运行。
"""

import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "快速打开文件夹"

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# ------------------------------------------------------------------ 配色 / 字体
BG = "#F3F5FA"
CARD_BG = "#FFFFFF"
BORDER = "#E2E7F0"
TEXT = "#1E2430"
MUTED = "#79839A"
ACCENT = "#2F6FED"
ACCENT_HOVER = "#255FD0"
CHIP_BG = "#EDF3FE"
CHIP_FG = "#29509E"
CHIP_HOVER = "#DCE8FD"
WARN_BG = "#FDECEC"
WARN_FG = "#C0392B"
WARN_HOVER = "#F8DADA"
STATUS_BG = "#E9EDF5"

PALETTE = ["#2F6FED", "#0E9F6E", "#E08B00", "#7C5CE0", "#E0455C", "#0AA3B8", "#DB4C8C"]
COLOR_NAMES = ["蓝色", "绿色", "橙色", "紫色", "红色", "青色", "粉色"]

FONTS = {}

DEFAULT_SETTINGS = {
    "open_mode": "tabs",
    "open_delay_ms": 60,
    "minimize_after_open": False,
    "always_on_top": False,
    "window_geometry": "",
}


# ------------------------------------------------------------------ 基础工具
def uid():
    return uuid.uuid4().hex[:8]


def enable_dpi_awareness():
    if os.name != "nt":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def ui_scale(window):
    """按系统 DPI 缩放窗口尺寸（字体本身按点自动缩放）。"""
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
    FONTS["title"] = (family, 17, "bold")
    FONTS["subtitle"] = (family, 9)
    FONTS["card"] = (family, 12, "bold")
    FONTS["body"] = (family, 10)
    FONTS["small"] = (family, 9)
    FONTS["chip"] = (family, 10)
    FONTS["button"] = (family, 10, "bold")


def setup_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Treeview",
        background=CARD_BG,
        fieldbackground=CARD_BG,
        foreground=TEXT,
        font=FONTS["body"],
        rowheight=26,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        font=FONTS["small"],
        background="#F7F9FD",
        foreground=MUTED,
        relief="flat",
        padding=(8, 6),
    )
    style.map("Treeview", background=[("selected", "#DCE8FD")], foreground=[("selected", TEXT)])
    style.map("Treeview.Heading", background=[("active", "#EEF2FA")])
    style.configure(
        "Vertical.TScrollbar",
        background="#C8D1E0",
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=MUTED,
        relief="flat",
        width=10,
    )
    style.map("Vertical.TScrollbar", background=[("active", "#AEBACD")])


def resolve_path(path):
    """展开环境变量/用户目录，相对路径按本程序目录解析。"""
    if not path:
        return ""
    p = str(path).strip().strip('"').strip("'")
    p = os.path.expandvars(os.path.expanduser(p))
    if not os.path.isabs(p):
        p = os.path.join(BASE_DIR, p)
    return os.path.normpath(p)


def folder_label(path):
    if not path:
        return "未命名"
    p = str(path).rstrip("\\/")
    if not p:
        return str(path)
    base = os.path.basename(p)
    return base or p


def open_path(path):
    if os.name == "nt":
        os.startfile(path)  # noqa: 只在 Windows 存在
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_path(path):
    if os.name == "nt" and path and os.path.exists(path):
        subprocess.Popen('explorer /select,"{}"'.format(os.path.normpath(path)))
    elif path:
        open_path(os.path.dirname(path) or path)


def color_name(hexv):
    try:
        return COLOR_NAMES[PALETTE.index(str(hexv).upper())]
    except (ValueError, TypeError):
        for i, c in enumerate(PALETTE):
            if c.lower() == str(hexv).lower():
                return COLOR_NAMES[i]
    return COLOR_NAMES[0]


def color_hex(name):
    try:
        return PALETTE[COLOR_NAMES.index(name)]
    except ValueError:
        return PALETTE[0]


# ------------------------------------------------------------------ 配置读写
def default_config():
    return {
        "version": 1,
        "settings": dict(DEFAULT_SETTINGS),
        "groups": [
            {
                "id": uid(),
                "name": "示例：常用文件夹",
                "color": PALETTE[0],
                "items": [
                    {"id": uid(), "name": "桌面", "path": r"%USERPROFILE%\Desktop"},
                    {"id": uid(), "name": "下载", "path": r"%USERPROFILE%\Downloads"},
                    {"id": uid(), "name": "文档", "path": r"%USERPROFILE%\Documents"},
                ],
            },
            {
                "id": uid(),
                "name": "示例：项目 A 开发",
                "color": PALETTE[1],
                "items": [
                    {"id": uid(), "name": "本工具目录", "path": "."},
                    {"id": uid(), "name": "临时目录", "path": "%TEMP%"},
                    {"id": uid(), "name": "用户目录", "path": "%USERPROFILE%"},
                ],
            },
        ],
    }


def normalize_config(data):
    if not isinstance(data, dict):
        data = {}
    groups = []
    raw_groups = data.get("groups")
    if not isinstance(raw_groups, list):
        raw_groups = []
    for i, g in enumerate(raw_groups):
        if not isinstance(g, dict):
            continue
        items = []
        raw_items = g.get("items")
        if isinstance(raw_items, list):
            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                items.append(
                    {
                        "id": str(it.get("id") or uid()),
                        "name": str(it.get("name") or ""),
                        "path": str(it.get("path") or ""),
                    }
                )
        groups.append(
            {
                "id": str(g.get("id") or uid()),
                "name": str(g.get("name") or "功能 %d" % (i + 1)),
                "color": g.get("color") if isinstance(g.get("color"), str) else PALETTE[i % len(PALETTE)],
                "items": items,
            }
        )

    raw_settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    settings = dict(DEFAULT_SETTINGS)
    if raw_settings.get("open_mode") in ("tabs", "windows"):
        settings["open_mode"] = raw_settings["open_mode"]
    if isinstance(raw_settings.get("open_delay_ms"), (int, float)):
        settings["open_delay_ms"] = max(0, min(5000, int(raw_settings["open_delay_ms"])))
    for key in ("minimize_after_open", "always_on_top"):
        if isinstance(raw_settings.get(key), bool):
            settings[key] = raw_settings[key]
    if isinstance(raw_settings.get("window_geometry"), str):
        settings["window_geometry"] = raw_settings["window_geometry"]

    return {"version": 1, "settings": settings, "groups": groups}


def write_config(data):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, CONFIG_PATH)


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return normalize_config(json.load(f))
        except Exception:
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    raw = f.read()
                with open(CONFIG_PATH + ".broken", "w", encoding="utf-8") as f:
                    f.write(raw)
            except Exception:
                pass
            try:
                write_config(default_config())
            except Exception:
                pass
            return default_config()
    data = default_config()
    try:
        write_config(data)
    except Exception:
        pass
    return data


# ------------------------------------------------------------------ 通用控件
class FlatButton(tk.Label):
    def __init__(self, master, text, command=None, kind="ghost", padx=12, pady=6, font=None, **kw):
        palettes = {
            "primary": (ACCENT, "#FFFFFF", ACCENT_HOVER),
            "ghost": (CARD_BG, TEXT, "#EDF1F8"),
            "chip": (CHIP_BG, CHIP_FG, CHIP_HOVER),
        }
        bg, fg, hover = palettes.get(kind, palettes["ghost"])
        super().__init__(
            master,
            text=text,
            bg=bg,
            fg=fg,
            padx=padx,
            pady=pady,
            font=font or FONTS["button"],
            cursor="hand2",
            bd=0,
            highlightthickness=1 if kind == "ghost" else 0,
            highlightbackground=BORDER,
            **kw
        )
        self._bg = bg
        self._hover = hover
        self._command = command
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event=None):
        self.configure(bg=self._hover)

    def _on_leave(self, _event=None):
        self.configure(bg=self._bg)

    def _on_click(self, _event=None):
        if self._command:
            self._command()


class FlowFrame(tk.Frame):
    """自动换行的容器（子控件用 place 排列）。"""

    def __init__(self, master, gap=8, **kw):
        super().__init__(master, **kw)
        self.gap = gap
        self.bind("<Configure>", lambda _e: self.relayout())

    def relayout(self):
        width = self.winfo_width()
        if width <= 1:
            return
        x = y = 0
        row_h = 0
        for child in self.winfo_children():
            child.update_idletasks()
            cw = child.winfo_reqwidth()
            ch = child.winfo_reqheight()
            if x and x + cw > width:
                x = 0
                y += row_h + self.gap
                row_h = 0
            child.place(x=x, y=y, width=min(cw, width), height=ch)
            x += cw + self.gap
            row_h = max(row_h, ch)
        self.configure(height=y + row_h)


# ------------------------------------------------------------------ 分组卡片
class GroupCard(tk.Frame):
    def __init__(self, master, app, group, items):
        super().__init__(master, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        self.app = app
        self.group = group
        color = group.get("color") or ACCENT

        tk.Frame(self, bg=color, width=4).pack(side="left", fill="y")
        body = tk.Frame(self, bg=CARD_BG)
        body.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        head = tk.Frame(body, bg=CARD_BG)
        head.pack(fill="x")

        title = group.get("name") or "未命名分组"
        tk.Label(head, text=title, bg=CARD_BG, fg=TEXT, font=FONTS["card"], anchor="w").pack(side="left")

        all_items = group.get("items") or []
        missing = sum(
            1
            for it in all_items
            if not it.get("path") or not os.path.exists(resolve_path(it.get("path", "")))
        )
        meta = "%d 个文件夹" % len(all_items) if all_items else "未配置文件夹"
        if missing:
            meta += " · %d 个路径不存在" % missing
        tk.Label(
            head,
            text="  " + meta,
            bg=CARD_BG,
            fg=WARN_FG if missing else MUTED,
            font=FONTS["small"],
        ).pack(side="left")

        FlatButton(
            head,
            "打开全部",
            lambda: app.open_items(group, all_items),
            kind="primary",
            padx=14,
            pady=6,
        ).pack(side="right")
        FlatButton(
            head,
            "编辑",
            lambda: app.manage(group.get("id")),
            kind="ghost",
            padx=10,
            pady=6,
        ).pack(side="right", padx=(0, 8))

        flow = FlowFrame(body, bg=CARD_BG, gap=8)
        flow.pack(fill="x", pady=(10, 0))

        if not items:
            if not all_items:
                text = "还没有文件夹，点右上角「编辑」添加 →"
            else:
                text = "没有匹配的文件夹"
            tk.Label(flow, text=text, bg=CARD_BG, fg=MUTED, font=FONTS["small"])
        else:
            for it in items:
                self._make_chip(flow, it)

    def _make_chip(self, parent, item):
        path = resolve_path(item.get("path", ""))
        label = item.get("name") or folder_label(path)
        exists = bool(path) and os.path.exists(path)
        bg, fg, hover = (CHIP_BG, CHIP_FG, CHIP_HOVER) if exists else (WARN_BG, WARN_FG, WARN_HOVER)
        text = label if exists else label + "（路径不存在）"
        if len(text) > 26:
            text = text[:25] + "…"

        chip = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=FONTS["chip"],
            padx=12,
            pady=7,
            cursor="hand2",
            bd=0,
        )
        chip.bind("<Button-1>", lambda _e: self.app.open_items(self.group, [item]))
        chip.bind("<Button-3>", lambda e: self._menu(e, item))
        chip.bind("<Enter>", lambda _e: (chip.configure(bg=hover), self.app.set_status(path or "未设置路径")))
        chip.bind("<Leave>", lambda _e: (chip.configure(bg=bg), self.app.set_status("")))
        return chip

    def _menu(self, event, item):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="打开此文件夹", command=lambda: self.app.open_items(self.group, [item]))
        menu.add_command(label="在资源管理器中显示", command=lambda: self.app.reveal(item))
        menu.add_separator()
        menu.add_command(label="复制路径", command=lambda: self.app.copy_path(item))
        menu.add_command(
            label="编辑「%s」…" % (self.group.get("name") or "分组"),
            command=lambda: self.app.manage(self.group.get("id")),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


# ------------------------------------------------------------------ Windows 资源管理器标签页
IS_WINDOWS = os.name == "nt"
TAB_MIN_BUILD = 22621  # Windows 11 22H2 起资源管理器支持标签页

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    _user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]

    _EXPLORER_CLASSES = ("CabinetWClass", "ExploreWClass")

TABS_SCRIPT = os.path.join(BASE_DIR, "explorer_tabs.ps1")

TAB_ERROR_TEXT = {
    "read paths failed": "读取路径列表失败",
    "no paths": "没有要打开的文件夹",
    "window lost": "资源管理器窗口丢失",
    "no add button": "资源管理器没有「新建标签页」按钮，系统可能不支持标签页",
    "invoke add failed": "点击「新建标签页」失败",
    "tab not created": "资源管理器没有新建标签页，后续标签已停止",
    "navigation timeout": "标签页没有跳转到目标文件夹",
}


def tabs_supported():
    """当前系统是否支持资源管理器标签页。"""
    if not IS_WINDOWS:
        return False
    try:
        return sys.getwindowsversion().build >= TAB_MIN_BUILD
    except Exception:
        return False


def _explorer_windows():
    handles = set()

    def _callback(hwnd, _lparam):
        try:
            if _user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(64)
                _user32.GetClassNameW(hwnd, buf, 64)
                if buf.value in _EXPLORER_CLASSES:
                    handles.add(hwnd)
        except Exception:
            pass
        return True

    if IS_WINDOWS:
        _user32.EnumWindows(_WNDENUMPROC(_callback), 0)
    return handles


def open_in_tabs(paths):
    """在同一个资源管理器窗口里用标签页打开多个文件夹。

    自动化逻辑在 explorer_tabs.ps1 里（UI Automation，不模拟组合键）。
    返回 (成功打开的个数, 错误信息列表)，调用方应在后台线程执行。
    """
    if not paths:
        return 0, ["没有要打开的文件夹"]
    if not tabs_supported() or not os.path.isfile(TABS_SCRIPT):
        for path in paths:
            open_path(path)
        return len(paths), []

    existing = _explorer_windows()
    try:
        subprocess.Popen('explorer.exe /n,"%s"' % os.path.normpath(paths[0]))
    except Exception as exc:  # noqa: BLE001
        return 0, ["无法启动资源管理器：%s" % exc]

    hwnd = 0
    deadline = time.time() + 8.0
    while time.time() < deadline:
        time.sleep(0.08)
        fresh = _explorer_windows() - existing
        if fresh:
            hwnd = fresh.pop()
            break
    if not hwnd:
        for path in paths[1:]:
            try:
                open_path(path)
            except Exception:
                pass
        return 1, ["没有找到新打开的资源管理器窗口，其余文件夹已改为分别打开"]

    paths_file = None
    try:
        fd, paths_file = tempfile.mkstemp(prefix="quickopen_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(paths, f, ensure_ascii=False)

        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            TABS_SCRIPT,
            "-Hwnd",
            str(hwnd),
            "-PathsFile",
            paths_file,
        ]
        timeout = max(20, 8 + 3 * len(paths))
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        payload = None
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue
        if not isinstance(payload, dict):
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(detail[:300] or "PowerShell 没有返回结果")

        opened = int(payload.get("opened") or 0)
        raw_errors = payload.get("errors") or []
        if isinstance(raw_errors, str):
            raw_errors = [raw_errors]
        errors = [TAB_ERROR_TEXT.get(str(e), str(e)) for e in raw_errors]
        return opened, errors
    except Exception as exc:  # noqa: BLE001
        return 1, [
            "标签页模式执行失败：%s。可以在「设置」里改用「每个文件夹单独一个窗口」。" % exc
        ]
    finally:
        if paths_file:
            try:
                os.remove(paths_file)
            except OSError:
                pass


# ------------------------------------------------------------------ 主窗口
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        setup_fonts(self)
        setup_style(self)
        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.minsize(int(800 * ui_scale(self)), int(540 * ui_scale(self)))
        self.data = load_config()
        self._apply_window()
        self._build_ui()
        self.apply_settings()
        self.rebuild()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind("<F5>", self.reload)
        self.bind("<Control-n>", lambda _e: self.new_group())
        self.bind("<Control-e>", lambda _e: self.manage())
        self.bind("<Control-f>", self._focus_search)
        self.bind("<Escape>", lambda _e: self.search_var.set(""))

        self.deiconify()
        self.focus_force()

    # -------------------------------------------------- 界面
    def _build_ui(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 6))
        hl = tk.Frame(header, bg=BG)
        hl.pack(side="left", anchor="w")
        tk.Label(hl, text=APP_TITLE, bg=BG, fg=TEXT, font=FONTS["title"]).pack(anchor="w")
        tk.Label(
            hl,
            text="点一下，把一组文件夹一起打开",
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
        ).pack(anchor="w", pady=(2, 0))

        hr = tk.Frame(header, bg=BG)
        hr.pack(side="right", anchor="e")
        FlatButton(hr, "＋ 新建分组", self.new_group, kind="primary", padx=14, pady=7).pack(side="right")
        FlatButton(hr, "管理配置", self.manage, kind="ghost", padx=12, pady=7).pack(
            side="right", padx=(0, 8)
        )
        FlatButton(hr, "设置", self.open_settings, kind="ghost", padx=12, pady=7).pack(
            side="right", padx=(0, 8)
        )

        toolrow = tk.Frame(outer, bg=BG)
        toolrow.pack(fill="x", padx=20, pady=(4, 0))
        search_box = tk.Frame(toolrow, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        search_box.pack(side="left")
        tk.Label(search_box, text="筛选", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left", padx=(10, 4)
        )
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            bd=0,
            relief="flat",
            bg=CARD_BG,
            fg=TEXT,
            insertbackground=TEXT,
            font=FONTS["body"],
            width=26,
        )
        self.search_entry.pack(side="left", ipady=6, pady=2)
        clear = tk.Label(
            search_box, text="✕", bg=CARD_BG, fg=MUTED, font=FONTS["small"], cursor="hand2", padx=8
        )
        clear.pack(side="left")
        clear.bind("<Button-1>", lambda _e: self.search_var.set(""))
        self.stats_label = tk.Label(toolrow, text="", bg=BG, fg=MUTED, font=FONTS["small"])
        self.stats_label.pack(side="right")

        self.status_var = tk.StringVar(value="就绪")
        bar = tk.Frame(outer, bg=STATUS_BG)
        bar.pack(side="bottom", fill="x")
        tk.Label(
            bar,
            textvariable=self.status_var,
            bg=STATUS_BG,
            fg=MUTED,
            font=FONTS["small"],
            anchor="w",
        ).pack(fill="x", padx=20, pady=6)

        listwrap = tk.Frame(outer, bg=BG)
        listwrap.pack(fill="both", expand=True, padx=(20, 12), pady=(12, 0))
        listwrap.columnconfigure(0, weight=1)
        listwrap.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(listwrap, bg=BG, highlightthickness=0, yscrollincrement=18)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb = ttk.Scrollbar(listwrap, orient="vertical", command=self.canvas.yview)
        self.vsb.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._scroll_job = None
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.search_var.trace_add("write", lambda *_a: self.rebuild(reset_scroll=True))

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._schedule_scrollbar_sync()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._win, width=event.width)
        self._schedule_scrollbar_sync()

    def _schedule_scrollbar_sync(self):
        if self._scroll_job is not None:
            try:
                self.after_cancel(self._scroll_job)
            except Exception:
                pass
        self._scroll_job = self.after(30, self._sync_scrollbar)

    def _sync_scrollbar(self):
        self._scroll_job = None
        try:
            bbox = self.canvas.bbox("all")
            need = bool(bbox) and (bbox[3] - bbox[1]) > self.canvas.winfo_height() + 1
            mapped = bool(self.vsb.winfo_ismapped())
            if need and not mapped:
                self.vsb.grid()
            elif not need and mapped:
                self.vsb.grid_remove()
        except Exception:
            pass

    def _focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")
        return "break"

    def _empty_state(self, has_groups, query):
        box = tk.Frame(self.inner, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="x", pady=(0, 10))
        pad = tk.Frame(box, bg=CARD_BG)
        pad.pack(fill="x", padx=24, pady=30)
        if not has_groups:
            tk.Label(
                pad, text="还没有配置任何功能分组", bg=CARD_BG, fg=TEXT, font=FONTS["card"]
            ).pack()
            tk.Label(
                pad,
                text="新建一个分组，把要一起打开的文件夹加进去。",
                bg=CARD_BG,
                fg=MUTED,
                font=FONTS["small"],
            ).pack(pady=(6, 14))
            FlatButton(pad, "＋ 新建分组", self.new_group, kind="primary", padx=16, pady=8).pack()
        else:
            tk.Label(
                pad,
                text=("没有匹配「%s」的分组" % query) if query else "没有匹配的分组",
                bg=CARD_BG,
                fg=TEXT,
                font=FONTS["card"],
            ).pack()
            tk.Label(
                pad,
                text="试试换个关键词，或者清空筛选条件。",
                bg=CARD_BG,
                fg=MUTED,
                font=FONTS["small"],
            ).pack(pady=(6, 14))
            FlatButton(
                pad, "清除筛选", lambda: self.search_var.set(""), kind="ghost", padx=16, pady=8
            ).pack()

    def rebuild(self, reset_scroll=False):
        for w in self.inner.winfo_children():
            w.destroy()

        query = self.search_var.get().strip().lower()
        groups = self.data.get("groups", [])
        shown = 0
        for group in groups:
            items = group.get("items") or []
            if query:
                if query in (group.get("name") or "").lower():
                    display = items
                else:
                    display = [
                        it
                        for it in items
                        if query in (it.get("name") or "").lower()
                        or query in (it.get("path") or "").lower()
                    ]
                    if not display:
                        continue
            else:
                display = items
            GroupCard(self.inner, self, group, display).pack(fill="x", pady=(0, 10))
            shown += 1

        if shown == 0:
            self._empty_state(bool(groups), self.search_var.get().strip())

        total_items = sum(len(g.get("items") or []) for g in groups)
        self.stats_label.configure(text="%d 个分组 · %d 个文件夹" % (len(groups), total_items))
        self.set_status("")
        if reset_scroll:
            self.canvas.yview_moveto(0)
        self.update_idletasks()

    def set_status(self, text):
        if text:
            self.status_var.set(text)
            return
        self.status_var.set("就绪 · 右键文件夹按钮可复制路径、在资源管理器中显示")

    def _on_wheel(self, event):
        try:
            cx, cy = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        except Exception:
            return
        if not (cx <= event.x_root <= cx + cw and cy <= event.y_root <= cy + ch):
            return
        if not event.delta:
            return
        step = -int(event.delta / 40)
        step = max(-4, min(4, step)) or (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(step, "units")

    # -------------------------------------------------- 打开文件夹
    def open_items(self, group, items):
        if not items:
            messagebox.showinfo(
                "提示", "这个分组还没有配置文件夹，点「编辑」添加。", parent=self
            )
            return

        exists = []
        missing = []
        for it in items:
            path = resolve_path(it.get("path", ""))
            if path and os.path.exists(path):
                exists.append(path)
            else:
                missing.append((it, path or "（空路径）"))

        if missing:
            lines = "\n".join(
                "· %s：%s" % (it.get("name") or folder_label(p), p) for it, p in missing[:10]
            )
            if len(missing) > 10:
                lines += "\n… 还有 %d 个" % (len(missing) - 10)
            if not exists:
                messagebox.showwarning(
                    "路径不存在", "以下路径不存在，无法打开：\n\n" + lines, parent=self
                )
                return
            if not messagebox.askyesno(
                "部分路径不存在",
                "以下 %d 个路径不存在：\n\n%s\n\n是否继续打开其余 %d 个文件夹？"
                % (len(missing), lines, len(exists)),
                parent=self,
            ):
                return

        self._launch(exists)

    def _launch(self, paths):
        settings = self.data.get("settings", {})
        delay = int(settings.get("open_delay_ms", 0) or 0)
        mode = settings.get("open_mode", "tabs")
        use_tabs = mode == "tabs" and len(paths) > 1 and tabs_supported()

        if use_tabs:
            self.set_status("正在同一窗口打开 %d 个标签页…" % len(paths))
        else:
            self.set_status("正在打开 %d 个文件夹…" % len(paths))

        def worker():
            if use_tabs:
                opened, errors = open_in_tabs(paths)
                self.after(0, lambda: self._launch_done(opened, errors, True))
                return
            errors = []
            for path in paths:
                try:
                    open_path(path)
                except Exception as exc:  # noqa: BLE001
                    errors.append("%s：%s" % (path, exc))
                if delay:
                    time.sleep(delay / 1000.0)
            self.after(0, lambda: self._launch_done(len(paths), errors, False))

        threading.Thread(target=worker, daemon=True).start()
        if settings.get("minimize_after_open"):
            self.after(600, self.iconify)

    def _launch_done(self, count, errors, tabs=False):
        unit = "标签页" if tabs else "文件夹"
        if errors:
            self.set_status(
                "已打开 %d 个%s，%d 个未完成" % (count, unit, len(errors))
            )
            messagebox.showwarning(
                "部分文件夹打开失败", "\n".join(errors[:10]), parent=self
            )
        elif tabs:
            self.set_status("已在同一窗口的 %d 个标签页中打开" % count)
        else:
            self.set_status("已打开 %d 个文件夹" % count)

    def reveal(self, item):
        path = resolve_path(item.get("path", ""))
        if not path or not os.path.exists(path):
            messagebox.showwarning("路径不存在", path or "未设置路径", parent=self)
            return
        reveal_path(path)

    def copy_path(self, item):
        path = resolve_path(item.get("path", ""))
        self.clipboard_clear()
        self.clipboard_append(path)
        self.set_status("已复制路径：" + (path or "（空）"))

    # -------------------------------------------------- 配置
    def save(self):
        try:
            write_config(self.data)
            return True
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("保存失败", "写入配置文件失败：\n%s\n\n%s" % (CONFIG_PATH, exc), parent=self)
            return False

    def reload(self, _event=None):
        self.data = load_config()
        self.apply_settings()
        self.rebuild(reset_scroll=True)
        self.set_status("已重新载入配置")

    def new_group(self):
        group = {
            "id": uid(),
            "name": "新分组 %d" % (len(self.data["groups"]) + 1),
            "color": PALETTE[len(self.data["groups"]) % len(PALETTE)],
            "items": [],
        }
        self.data["groups"].append(group)
        self.save()
        self.rebuild()
        self.manage(group["id"])

    def manage(self, group_id=None, _event=None):
        ConfigDialog(self, group_id)

    def open_settings(self):
        SettingsDialog(self)

    def open_config_dir(self):
        open_path(BASE_DIR)

    def apply_settings(self):
        settings = self.data.get("settings", {})
        try:
            self.attributes("-topmost", bool(settings.get("always_on_top")))
        except tk.TclError:
            pass

    # -------------------------------------------------- 窗口状态
    def _apply_window(self):
        geometry = self.data.get("settings", {}).get("window_geometry") or ""
        if geometry:
            try:
                self.geometry(geometry)
                self.after(40, self._clamp_window)
                return
            except tk.TclError:
                pass
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        scale = ui_scale(self)
        w = min(int(1020 * scale), sw - 80)
        h = min(int(720 * scale), sh - 140)
        x = (sw - w) // 2
        y = max(0, (sh - h) // 3)
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def _clamp_window(self):
        try:
            self.update_idletasks()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h = self.winfo_width(), self.winfo_height()
            x, y = self.winfo_x(), self.winfo_y()
            x = min(max(0, x), max(0, sw - w))
            y = min(max(0, y), max(0, sh - h - 40))
            if (x, y) != (self.winfo_x(), self.winfo_y()):
                self.geometry("+%d+%d" % (x, y))
        except Exception:
            pass

    def _on_close(self):
        try:
            self.data.setdefault("settings", {})["window_geometry"] = self.geometry()
            write_config(self.data)
        except Exception:
            pass
        self.destroy()


# ------------------------------------------------------------------ 编辑文件夹对话框
class ItemDialog(tk.Toplevel):
    def __init__(self, parent, title, name="", path=""):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(parent)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=16)

        tk.Label(body, text="名称（显示在按钮上，可留空）", bg=BG, fg=MUTED, font=FONTS["small"]).pack(
            anchor="w"
        )
        self.name_var = tk.StringVar(value=name)
        tk.Entry(
            body,
            textvariable=self.name_var,
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=FONTS["body"],
            width=52,
        ).pack(fill="x", pady=(4, 12), ipady=5, ipadx=4)

        tk.Label(body, text="文件夹路径", bg=BG, fg=MUTED, font=FONTS["small"]).pack(anchor="w")
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 6))
        self.path_var = tk.StringVar(value=path)
        tk.Entry(
            row,
            textvariable=self.path_var,
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=FONTS["body"],
            width=44,
        ).pack(side="left", fill="x", expand=True, ipady=5, ipadx=4)
        FlatButton(row, "浏览…", self._browse, kind="ghost", padx=10, pady=5).pack(
            side="left", padx=(6, 0)
        )

        tk.Label(
            body,
            text="支持 %USERPROFILE% 这类环境变量，以及相对本程序目录的相对路径。",
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
        ).pack(anchor="w")

        foot = tk.Frame(body, bg=BG)
        foot.pack(fill="x", pady=(14, 0))
        FlatButton(foot, "确定", self._ok, kind="primary", padx=18, pady=7).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=7).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        place_near_parent(self, parent, 560, 0)
        self.grab_set()
        self.after(30, lambda: self.focus_force())

    def _browse(self):
        current = self.path_var.get().strip()
        initial = resolve_path(current) if current else BASE_DIR
        if not os.path.isdir(initial):
            initial = BASE_DIR
        chosen = filedialog.askdirectory(parent=self, title="选择文件夹", initialdir=initial)
        if chosen:
            self.path_var.set(os.path.normpath(chosen))
            if not self.name_var.get().strip():
                self.name_var.set(folder_label(chosen))

    def _ok(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("提示", "请填写或选择文件夹路径。", parent=self)
            return
        name = self.name_var.get().strip() or folder_label(resolve_path(path))
        self.result = (name, path)
        self.destroy()


# ------------------------------------------------------------------ 批量添加对话框
class BatchDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("批量添加文件夹")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(parent)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=16)
        tk.Label(
            body, text="每行一个文件夹路径（名称自动取文件夹名）", bg=BG, fg=TEXT, font=FONTS["body"]
        ).pack(anchor="w")
        tk.Label(
            body,
            text="支持以 # 开头的注释行，支持 %USERPROFILE% 等环境变量。",
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
        ).pack(anchor="w", pady=(2, 6))

        box = tk.Frame(body, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="both", expand=True)
        self.text = tk.Text(
            box,
            width=64,
            height=12,
            bd=0,
            relief="flat",
            bg=CARD_BG,
            fg=TEXT,
            insertbackground=TEXT,
            font=FONTS["body"],
            padx=8,
            pady=8,
            wrap="none",
        )
        self.text.pack(fill="both", expand=True)

        foot = tk.Frame(body, bg=BG)
        foot.pack(fill="x", pady=(14, 0))
        FlatButton(foot, "添加", self._ok, kind="primary", padx=18, pady=7).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=7).pack(
            side="right", padx=(0, 8)
        )
        self.bind("<Escape>", lambda _e: self.destroy())
        place_near_parent(self, parent, 580, 0)
        self.grab_set()
        self.text.focus_set()

    def _ok(self):
        raw = self.text.get("1.0", "end").splitlines()
        paths = []
        for line in raw:
            line = line.strip().strip('"').strip("'")
            if not line or line.startswith("#"):
                continue
            paths.append(line)
        if not paths:
            messagebox.showwarning("提示", "没有识别到任何路径。", parent=self)
            return
        self.result = paths
        self.destroy()


# ------------------------------------------------------------------ 设置对话框
class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        settings = app.data.get("settings", {})
        self.title("设置")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app)

        self.delay_var = tk.StringVar(value=str(settings.get("open_delay_ms", 60)))
        self.mode_var = tk.StringVar(value=settings.get("open_mode", "tabs"))
        self.min_var = tk.BooleanVar(value=bool(settings.get("minimize_after_open")))
        self.top_var = tk.BooleanVar(value=bool(settings.get("always_on_top")))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=18)

        tk.Label(body, text="点「打开全部」时", bg=BG, fg=TEXT, font=FONTS["body"]).pack(anchor="w")
        for text, value in (
            ("同一窗口，每个文件夹一个标签页", "tabs"),
            ("每个文件夹单独一个窗口", "windows"),
        ):
            tk.Radiobutton(
                body,
                text=text,
                value=value,
                variable=self.mode_var,
                bg=BG,
                fg=TEXT,
                font=FONTS["body"],
                activebackground=BG,
                activeforeground=TEXT,
                selectcolor=CARD_BG,
                highlightthickness=0,
                bd=0,
                anchor="w",
            ).pack(anchor="w", pady=1)
        if tabs_supported():
            mode_hint = "标签页模式需要 Windows 11（22H2 及以上），在后台创建标签页，不影响你正常操作。"
        else:
            mode_hint = "当前系统不支持资源管理器标签页，会自动改用「单独一个窗口」。"
        tk.Label(
            body,
            text=mode_hint,
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
            justify="left",
            wraplength=int(360 * ui_scale(self)),
        ).pack(anchor="w", pady=(4, 12))

        tk.Label(body, text="打开间隔（毫秒）", bg=BG, fg=TEXT, font=FONTS["body"]).pack(anchor="w")
        tk.Spinbox(
            body,
            from_=0,
            to=5000,
            increment=10,
            textvariable=self.delay_var,
            width=10,
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=FONTS["body"],
            buttonbackground=CARD_BG,
        ).pack(anchor="w", pady=(4, 4), ipady=3)
        tk.Label(
            body,
            text="仅「单独一个窗口」模式使用：0 = 同时打开（最快）；偶尔漏开可调到 60～150。",
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
            justify="left",
            wraplength=int(360 * ui_scale(self)),
        ).pack(anchor="w", pady=(0, 12))

        for text, var in (
            ("打开后最小化本窗口", self.min_var),
            ("窗口置顶", self.top_var),
        ):
            tk.Checkbutton(
                body,
                text=text,
                variable=var,
                bg=BG,
                fg=TEXT,
                font=FONTS["body"],
                activebackground=BG,
                activeforeground=TEXT,
                selectcolor=CARD_BG,
                highlightthickness=0,
                bd=0,
                anchor="w",
            ).pack(anchor="w", pady=2)

        foot = tk.Frame(body, bg=BG)
        foot.pack(fill="x", pady=(16, 0))
        FlatButton(foot, "保存", self._save, kind="primary", padx=18, pady=7).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=7).pack(
            side="right", padx=(0, 8)
        )
        self.bind("<Escape>", lambda _e: self.destroy())
        place_near_parent(self, app, 420, 0)
        self.grab_set()

    def _save(self):
        try:
            delay = int(float(self.delay_var.get()))
        except (TypeError, ValueError):
            delay = 60
        settings = self.app.data.setdefault("settings", {})
        settings["open_mode"] = self.mode_var.get() if self.mode_var.get() in ("tabs", "windows") else "tabs"
        settings["open_delay_ms"] = max(0, min(5000, delay))
        settings["minimize_after_open"] = bool(self.min_var.get())
        settings["always_on_top"] = bool(self.top_var.get())
        if self.app.save():
            self.app.apply_settings()
            self.app.set_status("设置已保存")
        self.destroy()


# ------------------------------------------------------------------ 管理配置对话框
class ConfigDialog(tk.Toplevel):
    def __init__(self, app, select_id=None):
        super().__init__(app)
        self.app = app
        self.data = copy.deepcopy(app.data)
        groups = self.data.setdefault("groups", [])
        self.group_id = select_id if any(g["id"] == select_id for g in groups) else (
            groups[0]["id"] if groups else None
        )
        self._loading = False
        self._last_dir = BASE_DIR

        self.title("管理配置")
        self.configure(bg=BG)
        self.transient(app)
        self.minsize(int(820 * ui_scale(self)), int(560 * ui_scale(self)))

        self._build()
        self._refresh_groups()
        place_near_parent(self, app, 920, 640)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Control-s>", lambda _e: self._save())
        self.grab_set()
        self.after(60, lambda: self.name_entry.focus_set())

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(18, 10))

        # 左侧：分组列表
        left = tk.Frame(body, bg=BG, width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="功能分组", bg=BG, fg=MUTED, font=FONTS["small"]).pack(anchor="w")
        box = tk.Frame(left, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="both", expand=True, pady=(4, 8))
        self.lb = tk.Listbox(
            box,
            bd=0,
            highlightthickness=0,
            activestyle="none",
            bg=CARD_BG,
            fg=TEXT,
            selectbackground="#DCE8FD",
            selectforeground=TEXT,
            font=FONTS["body"],
            exportselection=False,
        )
        self.lb.pack(fill="both", expand=True, padx=6, pady=6)
        self.lb.bind("<<ListboxSelect>>", self._on_select_group)

        row = tk.Frame(left, bg=BG)
        row.pack(fill="x")
        row.columnconfigure(0, weight=1, uniform="grpbtn")
        row.columnconfigure(1, weight=1, uniform="grpbtn")
        FlatButton(row, "＋ 新建", self._new_group, kind="ghost", padx=8, pady=5).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        FlatButton(row, "删除分组", self._del_group, kind="ghost", padx=8, pady=5).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )
        FlatButton(row, "↑ 上移", lambda: self._move_group(-1), kind="ghost", padx=8, pady=5).grid(
            row=1, column=0, sticky="ew", pady=(6, 0), padx=(0, 4)
        )
        FlatButton(row, "↓ 下移", lambda: self._move_group(1), kind="ghost", padx=8, pady=5).grid(
            row=1, column=1, sticky="ew", pady=(6, 0), padx=(4, 0)
        )

        # 右侧：分组内容
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        tk.Label(right, text="分组名称", bg=BG, fg=MUTED, font=FONTS["small"]).grid(
            row=0, column=0, sticky="w"
        )
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(
            right,
            textvariable=self.name_var,
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=FONTS["body"],
        )
        self.name_entry.grid(row=1, column=0, sticky="ew", pady=(4, 12), padx=(0, 12), ipady=5, ipadx=4)
        self.name_var.trace_add("write", self._on_name_change)

        tk.Label(right, text="颜色", bg=BG, fg=MUTED, font=FONTS["small"]).grid(
            row=0, column=1, sticky="w"
        )
        self.color_var = tk.StringVar()
        self.color_box = ttk.Combobox(
            right,
            textvariable=self.color_var,
            values=COLOR_NAMES,
            state="readonly",
            width=8,
            font=FONTS["body"],
        )
        self.color_box.grid(row=1, column=1, sticky="w", pady=(4, 12))
        self.color_box.bind("<<ComboboxSelected>>", self._on_color_change)

        tk.Label(right, text="文件夹（顺序即显示顺序）", bg=BG, fg=MUTED, font=FONTS["small"]).grid(
            row=2, column=0, columnspan=2, sticky="w"
        )
        tree_box = tk.Frame(right, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        tree_box.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(4, 8))
        self.tree = ttk.Treeview(
            tree_box, columns=("name", "path"), show="headings", height=9, selectmode="browse"
        )
        self.tree.heading("name", text="名称", anchor="w")
        self.tree.heading("path", text="路径", anchor="w")
        self.tree.column("name", width=150, stretch=False, anchor="w")
        self.tree.column("path", width=400, stretch=True, anchor="w")
        vsb = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit_item())

        brow = tk.Frame(right, bg=BG)
        brow.grid(row=4, column=0, columnspan=2, sticky="w")
        FlatButton(brow, "＋ 添加文件夹…", self._add_folder, kind="primary", padx=10, pady=5).pack(
            side="left"
        )
        FlatButton(brow, "批量添加…", self._batch_add, kind="ghost", padx=10, pady=5).pack(
            side="left", padx=6
        )
        FlatButton(brow, "编辑", self._edit_item, kind="ghost", padx=10, pady=5).pack(side="left")
        FlatButton(brow, "删除", self._del_item, kind="ghost", padx=10, pady=5).pack(
            side="left", padx=6
        )

        brow2 = tk.Frame(right, bg=BG)
        brow2.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        FlatButton(brow2, "↑ 上移", lambda: self._move_item(-1), kind="ghost", padx=10, pady=5).pack(
            side="left"
        )
        FlatButton(brow2, "↓ 下移", lambda: self._move_item(1), kind="ghost", padx=10, pady=5).pack(
            side="left", padx=6
        )
        FlatButton(brow2, "在资源管理器中打开", self._open_item, kind="ghost", padx=10, pady=5).pack(
            side="left"
        )

        tk.Label(
            right,
            text="提示：路径支持 %USERPROFILE% 等环境变量；相对路径以本程序目录为基准。",
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", padx=18, pady=(0, 16))
        FlatButton(foot, "保存", self._save, kind="primary", padx=20, pady=7).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=7).pack(
            side="right", padx=(0, 8)
        )
        FlatButton(foot, "打开 config.json 所在目录", self.app.open_config_dir, kind="ghost",
                   padx=10, pady=7).pack(side="left")

    # ---------------------------------------- 分组
    def _current(self):
        for group in self.data["groups"]:
            if group["id"] == self.group_id:
                return group
        return None

    def _refresh_groups(self):
        self._loading = True
        self.lb.delete(0, "end")
        for group in self.data["groups"]:
            self.lb.insert("end", "  " + (group["name"] or "未命名分组"))
        index = next(
            (i for i, g in enumerate(self.data["groups"]) if g["id"] == self.group_id), None
        )
        if index is None and self.data["groups"]:
            index = 0
            self.group_id = self.data["groups"][0]["id"]
        if index is not None:
            self.lb.selection_clear(0, "end")
            self.lb.selection_set(index)
            self.lb.see(index)
        self._load_group()
        self._loading = False

    def _load_group(self):
        group = self._current()
        self._loading = True
        self.name_var.set(group["name"] if group else "")
        self.color_var.set(color_name(group.get("color")) if group else "")
        self._refresh_items()
        self._loading = False

    def _on_select_group(self, _event=None):
        if self._loading:
            return
        selection = self.lb.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self.data["groups"]):
            return
        group_id = self.data["groups"][index]["id"]
        if group_id == self.group_id:
            return
        self.group_id = group_id
        self._load_group()

    def _on_name_change(self, *_a):
        if self._loading:
            return
        group = self._current()
        if not group:
            return
        group["name"] = self.name_var.get()
        index = self.data["groups"].index(group)
        self.lb.delete(index)
        self.lb.insert(index, "  " + (group["name"] or "未命名分组"))
        self.lb.selection_set(index)

    def _on_color_change(self, _event=None):
        group = self._current()
        if group:
            group["color"] = color_hex(self.color_var.get())

    def _new_group(self):
        group = {
            "id": uid(),
            "name": "新分组 %d" % (len(self.data["groups"]) + 1),
            "color": PALETTE[len(self.data["groups"]) % len(PALETTE)],
            "items": [],
        }
        self.data["groups"].append(group)
        self.group_id = group["id"]
        self._refresh_groups()
        self.name_entry.focus_set()
        self.name_entry.select_range(0, "end")

    def _del_group(self):
        group = self._current()
        if not group:
            return
        if not messagebox.askyesno(
            "删除分组",
            "确定删除分组「%s」及其 %d 个文件夹吗？\n（点「保存」后才会真正写入配置）"
            % (group["name"] or "未命名分组", len(group["items"])),
            parent=self,
        ):
            return
        self.data["groups"].remove(group)
        self.group_id = self.data["groups"][0]["id"] if self.data["groups"] else None
        self._refresh_groups()

    def _move_group(self, delta):
        group = self._current()
        if not group:
            return
        index = self.data["groups"].index(group)
        target = index + delta
        if target < 0 or target >= len(self.data["groups"]):
            return
        groups = self.data["groups"]
        groups[index], groups[target] = groups[target], groups[index]
        self._refresh_groups()

    # ---------------------------------------- 文件夹条目
    def _refresh_items(self):
        self.tree.delete(*self.tree.get_children())
        group = self._current()
        if not group:
            return
        for item in group["items"]:
            self.tree.insert(
                "", "end", iid=item["id"], values=(item.get("name") or "—", item.get("path") or "")
            )

    def _selected_item(self):
        selection = self.tree.selection()
        group = self._current()
        if not selection or not group:
            return None, None
        iid = selection[0]
        for index, item in enumerate(group["items"]):
            if item["id"] == iid:
                return index, item
        return None, None

    def _ensure_group(self):
        group = self._current()
        if not group:
            messagebox.showinfo("提示", "请先新建一个分组。", parent=self)
        return group

    def _add_folder(self):
        group = self._ensure_group()
        if not group:
            return
        initial = self._last_dir
        if not os.path.isdir(initial):
            initial = BASE_DIR
        chosen = filedialog.askdirectory(parent=self, title="选择要添加的文件夹", initialdir=initial)
        if not chosen:
            return
        chosen = os.path.normpath(chosen)
        self._last_dir = os.path.dirname(chosen) or chosen
        dialog = ItemDialog(self, "添加文件夹", name=folder_label(chosen), path=chosen)
        self.wait_window(dialog)
        self.grab_set()
        if not dialog.result:
            return
        name, path = dialog.result
        item = {"id": uid(), "name": name, "path": path}
        group["items"].append(item)
        self._refresh_items()
        self.tree.selection_set(item["id"])
        self.tree.see(item["id"])

    def _batch_add(self):
        group = self._ensure_group()
        if not group:
            return
        dialog = BatchDialog(self)
        self.wait_window(dialog)
        self.grab_set()
        if not dialog.result:
            return
        existing = {
            os.path.normcase(resolve_path(it.get("path", ""))) for it in group["items"] if it.get("path")
        }
        added = 0
        last_id = None
        for raw in dialog.result:
            key = os.path.normcase(resolve_path(raw))
            if key in existing:
                continue
            existing.add(key)
            item = {"id": uid(), "name": folder_label(resolve_path(raw)), "path": raw}
            group["items"].append(item)
            last_id = item["id"]
            added += 1
        self._refresh_items()
        if last_id:
            self.tree.selection_set(last_id)
            self.tree.see(last_id)
        self.app.set_status("已添加 %d 个文件夹（记得保存）" % added)

    def _edit_item(self):
        index, item = self._selected_item()
        if item is None:
            messagebox.showinfo("提示", "请先在上面的列表里选中一个文件夹。", parent=self)
            return
        dialog = ItemDialog(
            self, "编辑文件夹", name=item.get("name", ""), path=item.get("path", "")
        )
        self.wait_window(dialog)
        self.grab_set()
        if not dialog.result:
            return
        name, path = dialog.result
        item["name"] = name
        item["path"] = path
        self._refresh_items()
        self.tree.selection_set(item["id"])

    def _del_item(self):
        index, item = self._selected_item()
        group = self._current()
        if item is None or not group:
            messagebox.showinfo("提示", "请先在上面的列表里选中一个文件夹。", parent=self)
            return
        group["items"].remove(item)
        self._refresh_items()

    def _move_item(self, delta):
        index, item = self._selected_item()
        group = self._current()
        if item is None or not group:
            return
        target = index + delta
        if target < 0 or target >= len(group["items"]):
            return
        items = group["items"]
        items[index], items[target] = items[target], items[index]
        self._refresh_items()
        self.tree.selection_set(item["id"])
        self.tree.see(item["id"])

    def _open_item(self):
        _index, item = self._selected_item()
        if item is None:
            messagebox.showinfo("提示", "请先在上面的列表里选中一个文件夹。", parent=self)
            return
        path = resolve_path(item.get("path", ""))
        if not path or not os.path.exists(path):
            messagebox.showwarning("路径不存在", path or "未设置路径", parent=self)
            return
        try:
            open_path(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("打开失败", str(exc), parent=self)

    # ---------------------------------------- 保存
    def _save(self):
        group = self._current()
        if group and not group["name"].strip():
            group["name"] = "未命名分组"
        self.app.data = self.data
        if not self.app.save():
            return
        self.app.apply_settings()
        self.app.rebuild()
        self.app.set_status("配置已保存")
        self.destroy()


def place_near_parent(window, parent, width, height):
    window.update_idletasks()
    scale = ui_scale(parent)
    if width > 0:
        width = int(width * scale)
    if height > 0:
        height = int(height * scale)
    if height <= 0:
        height = window.winfo_reqheight()
    if width <= 0:
        width = window.winfo_reqwidth()
    parent.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    x = px + max(0, (pw - width) // 2)
    y = py + max(0, (ph - height) // 3)
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    x = min(max(0, x), max(0, sw - width))
    y = min(max(0, y), max(0, sh - height - 40))
    window.geometry("%dx%d+%d+%d" % (width, height, x, y))


def main():
    enable_dpi_awareness()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
