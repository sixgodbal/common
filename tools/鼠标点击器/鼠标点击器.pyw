# -*- coding: utf-8 -*-
"""鼠标点击器（Mouse Clicker & Macro Recorder）

功能：
1. 连点器：自定义间隔、鼠标按键、单击/双击、跟随鼠标或固定坐标，支持全局快捷键开关。
2. 鼠标宏：录制鼠标轨迹、点击、滚轮与键盘操作，分解成事件列表后可编辑、合并、循环回放。
3. 鼠标录制：一键录制整段操作，自动保存为宏；也可导出为独立的 Python 脚本。

依赖：pynput（pip install pynput），界面使用 Python 自带的 tkinter。
数据：程序目录下 config.json（设置）和 macros/*.json（宏），整个目录拷走即可使用。

仅支持 Windows。全局快捷键与模拟输入在管理员窗口上可能无效，需要以管理员身份运行本程序。
"""

import ctypes
import datetime
import json
import logging
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, ttk

try:
    from pynput import keyboard as pk
    from pynput import mouse as pm
except Exception as _exc:  # pragma: no cover - 只在缺少依赖时运行
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        "缺少依赖",
        "本工具需要 pynput 才能模拟鼠标键盘、监听全局快捷键。\n\n"
        "请先打开命令行执行：\n"
        "    pip install pynput\n\n"
        "详细错误：\n%s" % _exc,
    )
    raise SystemExit(1)


APP_TITLE = "鼠标点击器"
APP_VERSION = "1.0"
STOP_HOTKEY = "f9"

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
MACROS_DIR = os.path.join(BASE_DIR, "macros")
LOG_DIR = os.path.join(BASE_DIR, "logs")
ICON_PATH = os.path.join(BASE_DIR, "icon.ico")

log = logging.getLogger("clicker")


# ================================================================== 环境 / 日志
def setup_logging():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handler = logging.FileHandler(os.path.join(LOG_DIR, "error.log"), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    except Exception:
        pass


def enable_dpi_awareness():
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ================================================================== 配色 / 字体
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
SOFT_BG = "#F5F7FC"
GREEN = "#0E9F6E"
GREEN_BG = "#E6F7F0"
RED = "#E0455C"
RED_HOVER = "#C9364B"
RED_BG = "#FDECEC"
RED_FG = "#C0392B"
AMBER = "#C77700"
AMBER_BG = "#FFF4E0"
STATUS_BG = "#E9EDF5"

FONTS = {}


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
    FONTS["title"] = (family, 18, "bold")
    FONTS["subtitle"] = (family, 9)
    FONTS["card"] = (family, 12, "bold")
    FONTS["body"] = (family, 10)
    FONTS["body_bold"] = (family, 10, "bold")
    FONTS["small"] = (family, 9)
    FONTS["tiny"] = (family, 8)
    FONTS["chip"] = (family, 10)
    FONTS["button"] = (family, 10, "bold")
    FONTS["big"] = (family, 15, "bold")
    FONTS["mono"] = ("Consolas", 9)


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
        rowheight=27,
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
    style.configure(
        "TCombobox",
        fieldbackground=CARD_BG,
        background=CARD_BG,
        foreground=TEXT,
        arrowcolor=MUTED,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(6, 4),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", CARD_BG)],
        foreground=[("readonly", TEXT)],
        selectbackground=[("readonly", CARD_BG)],
        selectforeground=[("readonly", TEXT)],
    )
    style.configure(
        "Thin.Horizontal.TProgressbar",
        troughcolor="#E9EDF5",
        background=ACCENT,
        bordercolor="#E9EDF5",
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        thickness=6,
    )


def ui_scale(window):
    try:
        return max(1.0, min(3.0, window.winfo_fpixels("1i") / 96.0))
    except Exception:
        return 1.0


# ================================================================== 配置
DEFAULT_SETTINGS = {
    "click_interval_ms": 100,
    "click_button": "left",
    "click_type": "single",
    "click_position": "cursor",
    "fixed_x": 0,
    "fixed_y": 0,
    "click_repeat": "infinite",
    "click_count": 100,
    "hotkey_click": "f6",
    "hotkey_record": "f7",
    "hotkey_play": "f8",
    "record_moves": True,
    "record_clicks": True,
    "record_keys": True,
    "record_sample_px": 4,
    "record_countdown": 3,
    "record_minimize": True,
    "play_lead_ms": 300,
    "play_speed": 1.0,
    "play_loops": 1,
    "play_infinite": False,
    "play_gap_ms": 150,
    "play_minimize": True,
    "click_ui_countdown": True,
    "always_on_top": False,
    "window_geometry": "",
    "selected_macro": "",
}

MAX_RECORD_EVENTS = 150000


def clamp_int(value, default, lo, hi):
    try:
        value = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def clamp_float(value, default, lo, hi):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def default_config():
    return {"version": 1, "settings": dict(DEFAULT_SETTINGS)}


SPECIAL_KEY_NAMES = {k.name for k in pk.Key} | {"win"}
MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
MODIFIERS = set(MODIFIER_ORDER)
MODIFIER_RAW_NAMES = {
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "shift_l": "shift",
    "shift_r": "shift",
    "alt_l": "alt",
    "alt_r": "alt",
    "cmd": "win",
    "cmd_l": "win",
    "cmd_r": "win",
}

KEY_DISPLAY = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "altgr": "AltGr",
    "space": "Space",
    "enter": "Enter",
    "esc": "Esc",
    "tab": "Tab",
    "backspace": "Backspace",
    "caps_lock": "CapsLock",
    "num_lock": "NumLock",
    "scroll_lock": "ScrollLock",
    "print_screen": "PrintScreen",
    "page_up": "PageUp",
    "page_down": "PageDown",
    "menu": "Menu",
    "media_play_pause": "播放/暂停",
    "media_stop": "停止",
    "media_previous": "上一曲",
    "media_next": "下一曲",
    "media_volume_up": "音量+",
    "media_volume_down": "音量-",
    "media_volume_mute": "静音",
}


def pretty_key(name):
    if not name:
        return "?"
    if len(name) == 1:
        return name.upper()
    if name in KEY_DISPLAY:
        return KEY_DISPLAY[name]
    if re.fullmatch(r"f\d{1,2}", name):
        return name.upper()
    if name.startswith("vk:"):
        return "VK" + name[3:]
    return name.replace("_", " ").title()


def pretty_combo(combo):
    return "+".join(pretty_key(p) for p in (combo or "").split("+") if p)


def normalize_combo(value, default=None):
    """把快捷键标准化成 ctrl+alt+shift+win+主键 的形式。"""
    if not isinstance(value, str):
        return default
    parts = [p.strip().lower() for p in value.split("+") if p.strip()]
    if not parts:
        return default
    mods = []
    mains = []
    for p in parts:
        if p in MODIFIERS:
            if p not in mods:
                mods.append(p)
        else:
            mains.append(p)
    if len(mains) != 1:
        return default
    main = mains[0]
    if main in MODIFIERS or main == "esc":
        return default
    if len(main) > 1 and main not in SPECIAL_KEY_NAMES:
        return default
    if not main:
        return default
    if not mods and not re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", main):
        # 不支持没有修饰键的普通字母/空格等，避免打字时误触发
        return default
    ordered = [m for m in MODIFIER_ORDER if m in mods]
    return "+".join(ordered + [main])


def pick_hotkey(raw, default, used):
    value = normalize_combo(raw, None)
    if value and value not in used:
        used.add(value)
        return value
    if default not in used:
        used.add(default)
        return default
    for i in range(1, 25):
        cand = "f%d" % i
        if cand not in used:
            used.add(cand)
            return cand
    used.add(default)
    return default


def normalize_config(data):
    if not isinstance(data, dict):
        data = {}
    raw = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    s = dict(DEFAULT_SETTINGS)
    s["click_interval_ms"] = clamp_int(raw.get("click_interval_ms"), 100, 1, 3600000)
    s["click_button"] = raw.get("click_button") if raw.get("click_button") in ("left", "right", "middle") else "left"
    s["click_type"] = raw.get("click_type") if raw.get("click_type") in ("single", "double") else "single"
    s["click_position"] = raw.get("click_position") if raw.get("click_position") in ("cursor", "fixed") else "cursor"
    s["fixed_x"] = clamp_int(raw.get("fixed_x"), 0, -32768, 32767)
    s["fixed_y"] = clamp_int(raw.get("fixed_y"), 0, -32768, 32767)
    s["click_repeat"] = raw.get("click_repeat") if raw.get("click_repeat") in ("infinite", "count") else "infinite"
    s["click_count"] = clamp_int(raw.get("click_count"), 100, 1, 10000000)
    s["record_moves"] = bool(raw.get("record_moves", True))
    s["record_clicks"] = bool(raw.get("record_clicks", True))
    s["record_keys"] = bool(raw.get("record_keys", True))
    s["record_sample_px"] = clamp_int(raw.get("record_sample_px"), 4, 1, 100)
    s["record_countdown"] = clamp_int(raw.get("record_countdown"), 3, 0, 10)
    s["record_minimize"] = bool(raw.get("record_minimize", True))
    s["play_lead_ms"] = clamp_int(raw.get("play_lead_ms"), 300, 0, 10000)
    s["play_speed"] = clamp_float(raw.get("play_speed"), 1.0, 0.1, 5.0)
    s["play_loops"] = clamp_int(raw.get("play_loops"), 1, 1, 100000)
    s["play_infinite"] = bool(raw.get("play_infinite", False))
    s["play_gap_ms"] = clamp_int(raw.get("play_gap_ms"), 150, 0, 10000)
    s["play_minimize"] = bool(raw.get("play_minimize", True))
    s["click_ui_countdown"] = bool(raw.get("click_ui_countdown", True))
    s["always_on_top"] = bool(raw.get("always_on_top", False))
    s["window_geometry"] = raw.get("window_geometry") if isinstance(raw.get("window_geometry"), str) else ""
    s["selected_macro"] = raw.get("selected_macro") if isinstance(raw.get("selected_macro"), str) else ""

    used = {STOP_HOTKEY}
    s["hotkey_click"] = pick_hotkey(raw.get("hotkey_click"), "f6", used)
    s["hotkey_record"] = pick_hotkey(raw.get("hotkey_record"), "f7", used)
    s["hotkey_play"] = pick_hotkey(raw.get("hotkey_play"), "f8", used)
    return {"version": 1, "settings": s}


def write_json_atomic(path, data, indent=2):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)


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
    data = default_config()
    try:
        write_json_atomic(CONFIG_PATH, data)
    except Exception:
        pass
    return data


# ================================================================== 宏数据
def sanitize_event(raw):
    if not isinstance(raw, dict):
        return None
    try:
        t = float(raw.get("t", 0))
    except (TypeError, ValueError):
        return None
    if t < 0 or t > 86400000:
        return None
    kind = raw.get("type")
    if kind == "move":
        try:
            return {"t": round(t, 1), "type": "move", "x": int(raw.get("x", 0)), "y": int(raw.get("y", 0))}
        except (TypeError, ValueError):
            return None
    if kind == "button":
        button = raw.get("button")
        if button not in ("left", "right", "middle", "x1", "x2"):
            return None
        try:
            return {
                "t": round(t, 1),
                "type": "button",
                "x": int(raw.get("x", 0)),
                "y": int(raw.get("y", 0)),
                "button": button,
                "pressed": bool(raw.get("pressed")),
            }
        except (TypeError, ValueError):
            return None
    if kind == "scroll":
        try:
            dx = max(-100, min(100, int(raw.get("dx", 0))))
            dy = max(-100, min(100, int(raw.get("dy", 0))))
            return {
                "t": round(t, 1),
                "type": "scroll",
                "x": int(raw.get("x", 0)),
                "y": int(raw.get("y", 0)),
                "dx": dx,
                "dy": dy,
            }
        except (TypeError, ValueError):
            return None
    if kind == "key":
        ev = {"t": round(t, 1), "type": "key", "pressed": bool(raw.get("pressed"))}
        vk = raw.get("vk")
        if isinstance(vk, int) and 0 <= vk <= 255:
            ev["vk"] = vk
        key = raw.get("key")
        if isinstance(key, str) and key:
            ev["key"] = key[:24]
        text = raw.get("text")
        if isinstance(text, str) and text:
            ev["text"] = text[:8]
        if "vk" not in ev and "key" not in ev:
            return None
        return ev
    return None


def sanitize_macro(data, fallback_id=None):
    if not isinstance(data, dict):
        return None
    events = []
    raw_events = data.get("events")
    if isinstance(raw_events, list):
        for raw in raw_events[:MAX_RECORD_EVENTS]:
            ev = sanitize_event(raw)
            if ev is not None:
                events.append(ev)
    events.sort(key=lambda e: e["t"])
    name = re.sub(r"[\r\n\t]+", " ", str(data.get("name") or "未命名宏")).strip()[:80] or "未命名宏"
    duration = round(events[-1]["t"] if events else 0.0, 1)
    mid = str(data.get("id") or fallback_id or uuid.uuid4().hex[:12])
    mid = re.sub(r"[^A-Za-z0-9_-]", "", mid)[:32] or uuid.uuid4().hex[:12]
    created = str(data.get("created") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    try:
        created_ts = float(data.get("created_ts") or 0)
    except (TypeError, ValueError):
        created_ts = 0.0
    if not created_ts:
        try:
            created_ts = datetime.datetime.strptime(created, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            created_ts = time.time()
    return {
        "version": 1,
        "id": mid,
        "name": name,
        "created": created,
        "created_ts": created_ts,
        "duration": duration,
        "events": events,
        "source": str(data.get("source") or "record")[:20],
    }


def load_macros():
    macros = {}
    try:
        os.makedirs(MACROS_DIR, exist_ok=True)
    except Exception:
        return macros
    try:
        names = os.listdir(MACROS_DIR)
    except Exception:
        return macros
    for fn in names:
        if not fn.lower().endswith(".json"):
            continue
        path = os.path.join(MACROS_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                macro = sanitize_macro(json.load(f), fallback_id=os.path.splitext(fn)[0])
            if macro:
                macros[macro["id"]] = macro
        except Exception:
            log.exception("读取宏失败：%s", path)
    return macros


def save_macro_file(macro):
    path = os.path.join(MACROS_DIR, macro["id"] + ".json")
    write_json_atomic(path, macro)


def delete_macro_file(macro_id):
    path = os.path.join(MACROS_DIR, macro_id + ".json")
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        log.exception("删除宏失败：%s", path)


def format_duration(ms, short=False):
    try:
        ms = float(ms)
    except (TypeError, ValueError):
        ms = 0.0
    seconds = ms / 1000.0
    if seconds < 60:
        return ("%.1fs" % seconds) if short else ("%.1f 秒" % seconds)
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    return "%d分%04.1fs" % (minutes, rest) if short else "%d 分 %.1f 秒" % (minutes, rest)


def speed_text(value):
    try:
        text = ("%.2f" % float(value)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        text = "1.0"
    if "." not in text:
        text += ".0"
    return text + "x"


def format_time(ms):
    return "%.1f" % (float(ms) / 1000.0)


BTN_LABELS = {"left": "左键", "right": "右键", "middle": "中键", "x1": "侧键1", "x2": "侧键2"}


def event_action_text(ev):
    kind = ev.get("type")
    if kind == "move":
        return "移动到 (%s, %s)" % (ev.get("x"), ev.get("y"))
    if kind == "button":
        return "%s %s" % ("按下" if ev.get("pressed") else "松开", BTN_LABELS.get(ev.get("button"), "按键"))
    if kind == "scroll":
        dy = ev.get("dy", 0)
        dx = ev.get("dx", 0)
        if dy:
            direction = "上" if dy > 0 else "下"
            return "滚轮%s %d 格" % (direction, abs(dy))
        if dx:
            direction = "左" if dx < 0 else "右"
            return "横向滚动%s %d 格" % (direction, abs(dx))
        return "滚轮"
    if kind == "key":
        name = pretty_key(ev.get("text") or ev.get("key") or ("vk:%s" % ev.get("vk")))
        return "%s %s" % ("按下" if ev.get("pressed") else "松开", name)
    return "未知事件"


def event_detail_text(ev):
    kind = ev.get("type")
    if kind in ("move", "button", "scroll"):
        text = "坐标 (%s, %s)" % (ev.get("x"), ev.get("y"))
        if kind == "button":
            text += " · " + BTN_LABELS.get(ev.get("button"), "?")
        if kind == "scroll":
            text += " · dx=%s dy=%s" % (ev.get("dx"), ev.get("dy"))
        return text
    if kind == "key":
        parts = []
        if ev.get("vk") is not None:
            parts.append("VK %s" % ev["vk"])
        if ev.get("key"):
            parts.append("键值 %s" % ev["key"])
        return " · ".join(parts)
    return ""


def key_event_payload(key):
    """把 pynput 的按键转换为可保存的数据。"""
    if isinstance(key, pk.Key):
        name = MODIFIER_RAW_NAMES.get(key.name, key.name)
        return {"key": name}
    if isinstance(key, pk.KeyCode):
        payload = {}
        char = key.char
        if char and len(char) == 1 and ord(char) >= 32:
            payload["key"] = char
            payload["text"] = char
        if key.vk is not None:
            payload["vk"] = int(key.vk)
        if payload:
            return payload
    return None


def to_pynput_key(ev):
    if ev.get("vk") is not None:
        try:
            return pk.KeyCode.from_vk(int(ev["vk"]))
        except Exception:
            pass
    name = ev.get("key") or ""
    mapped = {"win": "cmd", "altgr": "alt_gr"}.get(name, name)
    key = getattr(pk.Key, mapped, None)
    if key is not None:
        return key
    if len(name) == 1:
        return pk.KeyCode.from_char(name)
    return None


def key_identity(ev):
    if ev.get("vk") is not None:
        return ("vk", ev["vk"])
    return ("key", ev.get("key"))


def raw_key_name(key):
    if isinstance(key, pk.Key):
        return key.name
    if isinstance(key, pk.KeyCode):
        if key.char:
            return "char:" + key.char
        if key.vk is not None:
            return "vk:%d" % key.vk
    return None


def normalize_key_token(raw):
    if raw is None:
        return None
    if raw.startswith("char:"):
        return raw[5:].lower()
    if raw.startswith("vk:"):
        return raw
    return MODIFIER_RAW_NAMES.get(raw, raw)


def unique_macro_name(existing_names, base):
    base = re.sub(r"[\r\n\t]+", " ", (base or "新宏")).strip()[:70] or "新宏"
    if base not in existing_names:
        return base
    i = 2
    while True:
        cand = "%s (%d)" % (base, i)
        if cand not in existing_names:
            return cand
        i += 1


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name or "宏").strip().strip(".")
    return (name or "宏")[:60]


def build_python_script(macro):
    """生成一个不依赖本工具的独立回放脚本。"""
    import pprint

    events = pprint.pformat(macro.get("events") or [], width=118, sort_dicts=False)
    name = macro.get("name") or "宏"
    name = re.sub(r"[\r\n]+", " ", name).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    duration = format_duration(macro.get("duration", 0))
    created = re.sub(r"[\r\n]+", " ", str(macro.get("created") or ""))
    created = created.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '''# -*- coding: utf-8 -*-
"""由「鼠标点击器」导出的回放脚本：%(name)s

录制时长：%(duration)s    导出时间：%(created)s
运行前安装依赖：  pip install pynput
运行：            python 本文件.py
停止：            在本窗口按 Ctrl+C
"""

import time

from pynput import keyboard, mouse

EVENTS = %(events)s

SPEED = 1.0
LOOPS = 1           # 0 表示无限循环
GAP = 0.15          # 每轮之间等待秒数

BUTTONS = {
    "left": mouse.Button.left,
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
    "x1": mouse.Button.x1,
    "x2": mouse.Button.x2,
}


def to_key(ev):
    vk = ev.get("vk")
    if vk is not None:
        try:
            return keyboard.KeyCode.from_vk(int(vk))
        except Exception:
            pass
    name = ev.get("key") or ""
    name = {"win": "cmd", "altgr": "alt_gr"}.get(name, name)
    key = getattr(keyboard.Key, name, None)
    if key is not None:
        return key
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    return None


def main():
    kbd = keyboard.Controller()
    ms = mouse.Controller()
    held_keys = {}
    held_buttons = set()
    loop = 0
    try:
        while True:
            base = time.perf_counter()
            for ev in EVENTS:
                wait = base + ev["t"] / 1000.0 / SPEED - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
                kind = ev["type"]
                if kind == "move":
                    ms.position = (ev["x"], ev["y"])
                elif kind == "button":
                    ms.position = (ev["x"], ev["y"])
                    button = BUTTONS[ev["button"]]
                    if ev["pressed"]:
                        ms.press(button)
                        held_buttons.add(button)
                    else:
                        ms.release(button)
                        held_buttons.discard(button)
                elif kind == "scroll":
                    ms.position = (ev["x"], ev["y"])
                    ms.scroll(ev.get("dx", 0), ev.get("dy", 0))
                elif kind == "key":
                    key = to_key(ev)
                    if key is None:
                        continue
                    ident = (ev.get("vk"), ev.get("key"))
                    if ev["pressed"]:
                        kbd.press(key)
                        held_keys[ident] = key
                    else:
                        kbd.release(key)
                        held_keys.pop(ident, None)
            loop += 1
            if LOOPS and loop >= LOOPS:
                break
            time.sleep(GAP)
    except KeyboardInterrupt:
        print("\\n已停止")
    finally:
        for key in held_keys.values():
            try:
                kbd.release(key)
            except Exception:
                pass
        for button in held_buttons:
            try:
                ms.release(button)
            except Exception:
                pass


if __name__ == "__main__":
    main()
''' % {"name": name, "duration": duration, "created": created, "events": events}


# ================================================================== 全局输入监听
class InputHub:
    """全局键鼠监听 + 注入标记。

    所有发往界面的动作都通过 post 回到 Tk 主线程。
    """

    def __init__(self, post, on_action):
        self._post = post
        self._on_action = on_action
        self.hotkeys = {}
        self.recorder = None
        self.injecting = 0
        self._last_inject = 0.0
        self._pressed_raw = set()
        self._capture = None
        self._capture_cancel = None
        self._listener = None

    def start(self):
        try:
            self._listener = pk.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.daemon = True
            self._listener.start()
        except Exception:
            log.exception("无法启动全局键盘监听")
            self._listener = None

    def stop(self):
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        self._pressed_raw.clear()

    def set_hotkeys(self, mapping):
        self.hotkeys = dict(mapping or {})

    def begin_inject(self):
        self.injecting += 1

    def end_inject(self):
        self.injecting = max(0, self.injecting - 1)
        self._last_inject = time.perf_counter()

    def is_injecting(self):
        return self.injecting > 0 or (time.perf_counter() - self._last_inject) < 0.03

    def capture_next(self, on_key, on_cancel=None):
        self._capture = on_key
        self._capture_cancel = on_cancel
        self._pressed_raw.clear()

    def clear_capture(self):
        self._capture = None
        self._capture_cancel = None

    def _emit(self, action):
        self._post(lambda a=action: self._on_action(a))

    def _combo(self, norm):
        mods = set()
        for raw in self._pressed_raw:
            token = normalize_key_token(raw)
            if token in MODIFIERS:
                mods.add(token)
        ordered = [m for m in MODIFIER_ORDER if m in mods]
        return "+".join(ordered + [norm])

    def _on_press(self, key):
        try:
            raw = raw_key_name(key)
            if raw is None:
                return
            norm = normalize_key_token(raw)
            repeat = raw in self._pressed_raw
            if not repeat:
                self._pressed_raw.add(raw)

            if norm == STOP_HOTKEY:
                if not repeat:
                    self._emit("stop")
                return

            if not repeat and self._capture is not None:
                if norm == "esc":
                    callback = self._capture_cancel
                    self.clear_capture()
                    if callback:
                        self._post(callback)
                    return
                if norm in MODIFIERS:
                    return
                combo = self._combo(norm)
                callback = self._capture
                self.clear_capture()
                if callback:
                    self._post(lambda c=combo: callback(c))
                return

            if self.is_injecting():
                return
            if repeat:
                return
            rec = self.recorder
            if norm in MODIFIERS:
                # 修饰键也必须写入录制，否则 Ctrl+C 之类的组合宏会只剩 C
                if rec is not None and rec.active:
                    rec.record_key(key, True, raw)
                return

            combo = self._combo(norm)
            action = self.hotkeys.get(combo)
            if action:
                self._emit(action)
            if rec is not None and rec.active and combo not in self.hotkeys:
                rec.record_key(key, True, raw)
        except Exception:
            log.exception("处理按键按下失败")

    def _on_release(self, key):
        try:
            raw = raw_key_name(key)
            if raw is None:
                return
            was_down = raw in self._pressed_raw
            self._pressed_raw.discard(raw)
            norm = normalize_key_token(raw)
            if norm == STOP_HOTKEY:
                return
            if self.is_injecting():
                return
            rec = self.recorder
            if rec is not None and rec.active:
                rec.record_key(key, False, raw)
        except Exception:
            log.exception("处理按键松开失败")


# ================================================================== 录制
class Recorder:
    def __init__(self, sample_px=4, record_moves=True, record_clicks=True, record_keys=True, on_limit=None):
        self.sample_px = max(1, int(sample_px))
        self.record_moves = bool(record_moves)
        self.record_clicks = bool(record_clicks)
        self.record_keys = bool(record_keys)
        self.on_limit = on_limit
        self.lock = threading.Lock()
        self.events = []
        self.active = False
        self.start_time = 0.0
        self.down_keys = set()
        self._last_move = None
        self._limit_hit = False

    def start(self):
        with self.lock:
            self.events = []
            self.down_keys.clear()
            self._last_move = None
            self.start_time = time.perf_counter()
            self.active = True

    def _t(self):
        return round((time.perf_counter() - self.start_time) * 1000.0, 1)

    def elapsed_ms(self):
        if not self.active:
            return 0.0
        return max(0.0, (time.perf_counter() - self.start_time) * 1000.0)

    def count(self):
        with self.lock:
            return len(self.events)

    def _append(self, ev):
        with self.lock:
            if not self.active:
                return
            if len(self.events) >= MAX_RECORD_EVENTS:
                if not self._limit_hit:
                    self._limit_hit = True
                    if self.on_limit:
                        self.on_limit()
                return
            self.events.append(ev)

    def record_move(self, x, y):
        if not self.active or not self.record_moves:
            return
        t = self._t()
        with self.lock:
            if not self.active:
                return
            last = self._last_move
            if last is not None:
                dx = int(x) - last[0]
                dy = int(y) - last[1]
                if dx * dx + dy * dy < self.sample_px * self.sample_px:
                    return
            self._last_move = (int(x), int(y), t)
            if len(self.events) >= MAX_RECORD_EVENTS:
                return
            self.events.append({"t": t, "type": "move", "x": int(x), "y": int(y)})

    def record_button(self, x, y, button, pressed):
        if not self.active or not self.record_clicks:
            return
        name = getattr(button, "name", None) or "left"
        if name not in ("left", "right", "middle", "x1", "x2"):
            return
        t = self._t()
        with self.lock:
            if not self.active:
                return
            self._last_move = (int(x), int(y), t)
            if len(self.events) >= MAX_RECORD_EVENTS:
                return
            self.events.append(
                {
                    "t": t,
                    "type": "button",
                    "x": int(x),
                    "y": int(y),
                    "button": name,
                    "pressed": bool(pressed),
                }
            )

    def record_scroll(self, x, y, dx, dy):
        if not self.active or not self.record_clicks:
            return
        if not dx and not dy:
            return
        t = self._t()
        with self.lock:
            if not self.active:
                return
            if len(self.events) >= MAX_RECORD_EVENTS:
                return
            self.events.append(
                {
                    "t": t,
                    "type": "scroll",
                    "x": int(x),
                    "y": int(y),
                    "dx": int(dx),
                    "dy": int(dy),
                }
            )

    def record_key(self, key, pressed, raw):
        if not self.active or not self.record_keys:
            return
        with self.lock:
            if not self.active:
                return
            if pressed:
                if raw in self.down_keys:
                    return
                self.down_keys.add(raw)
            else:
                if raw not in self.down_keys:
                    return
                self.down_keys.discard(raw)
            payload = key_event_payload(key)
            if payload is None:
                return
            if len(self.events) >= MAX_RECORD_EVENTS:
                return
            ev = {"t": self._t(), "type": "key", "pressed": bool(pressed)}
            ev.update(payload)
            self.events.append(ev)

    def stop(self):
        with self.lock:
            if not self.active:
                return [], 0.0
            duration = max(0.0, (time.perf_counter() - self.start_time) * 1000.0)
            self.active = False
            events = list(self.events)
            self.events = []
            self.down_keys.clear()
        events.sort(key=lambda e: e["t"])
        return events, round(duration, 1)


# ================================================================== 连点
class Clicker:
    def __init__(self, hub, settings, on_progress, on_done):
        self.hub = hub
        self.interval = max(1, int(settings["click_interval_ms"]))
        self.button_name = settings["click_button"]
        self.button = getattr(pm.Button, self.button_name, pm.Button.left)
        self.double = settings["click_type"] == "double"
        self.fixed = settings["click_position"] == "fixed"
        self.x = int(settings["fixed_x"])
        self.y = int(settings["fixed_y"])
        self.infinite = settings["click_repeat"] == "infinite"
        self.limit = max(1, int(settings["click_count"]))
        self.on_progress = on_progress
        self.on_done = on_done
        self.count = 0
        self.running = False
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, name="clicker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.running = False

    def join(self, timeout=0.4):
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self):
        mouse = pm.Controller()
        last_report = 0.0
        try:
            while not self._stop.is_set():
                self.hub.begin_inject()
                try:
                    if self.fixed:
                        mouse.position = (self.x, self.y)
                    mouse.press(self.button)
                    mouse.release(self.button)
                    if self.double:
                        if self._stop.wait(0.06):
                            break
                        if self.fixed:
                            mouse.position = (self.x, self.y)
                        mouse.press(self.button)
                        mouse.release(self.button)
                finally:
                    self.hub.end_inject()
                self.count += 1
                now = time.perf_counter()
                if now - last_report > 0.1:
                    last_report = now
                    try:
                        self.on_progress(self.count)
                    except Exception:
                        pass
                if not self.infinite and self.count >= self.limit:
                    break
                if self._stop.wait(self.interval / 1000.0):
                    break
        except Exception:
            log.exception("连点器运行失败")
        finally:
            self.running = False
            try:
                self.on_done(self.count, self._stop.is_set())
            except Exception:
                pass


# ================================================================== 回放
class Player:
    def __init__(self, hub, macro, speed=1.0, loops=1, infinite=False, lead_ms=300, gap_ms=150, on_progress=None, on_done=None):
        self.hub = hub
        self.macro = macro
        self.events = [dict(e) for e in (macro.get("events") or [])]
        self.speed = max(0.1, float(speed))
        self.loops = max(1, int(loops))
        self.infinite = bool(infinite)
        self.lead = max(0, int(lead_ms)) / 1000.0
        self.gap = max(0, int(gap_ms)) / 1000.0
        self.on_progress = on_progress
        self.on_done = on_done
        self.running = False
        self._stop = threading.Event()
        self._thread = None
        self.duration = self.events[-1]["t"] if self.events else 0.0

    def start(self):
        if self.running or not self.events:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, name="player", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        mouse = pm.Controller()
        keyboard = pk.Controller()
        held_keys = {}
        held_buttons = []
        stopped = False
        loop_index = 0
        last_report = 0.0
        try:
            if self.lead and self._stop.wait(self.lead):
                stopped = True
                return
            while not self._stop.is_set():
                loop_start = time.perf_counter()
                for index, ev in enumerate(self.events):
                    if self._stop.is_set():
                        stopped = True
                        break
                    target = loop_start + ev["t"] / 1000.0 / self.speed
                    while True:
                        remaining = target - time.perf_counter()
                        if remaining <= 0.002:
                            break
                        if self._stop.wait(remaining):
                            stopped = True
                            break
                    if stopped:
                        break
                    now = time.perf_counter()
                    if now - target > 0.25:
                        loop_start += now - target
                    self._apply(ev, mouse, keyboard, held_keys, held_buttons)
                    now = time.perf_counter()
                    if now - last_report > 0.1:
                        last_report = now
                        if self.on_progress:
                            try:
                                self.on_progress(index + 1, len(self.events), loop_index + 1, ev["t"])
                            except Exception:
                                pass
                if stopped:
                    break
                loop_index += 1
                if not self.infinite and loop_index >= self.loops:
                    break
                if self.gap and self._stop.wait(self.gap):
                    stopped = True
                    break
        except Exception:
            log.exception("宏回放失败")
        finally:
            self._release_all(mouse, keyboard, held_keys, held_buttons)
            self.running = False
            try:
                self.on_done(loop_index, stopped, self._stop.is_set())
            except Exception:
                pass

    def _apply(self, ev, mouse, keyboard, held_keys, held_buttons):
        kind = ev.get("type")
        if kind == "move":
            self.hub.begin_inject()
            try:
                mouse.position = (ev["x"], ev["y"])
            finally:
                self.hub.end_inject()
        elif kind == "button":
            self.hub.begin_inject()
            try:
                mouse.position = (ev["x"], ev["y"])
                button = getattr(pm.Button, ev.get("button", "left"), pm.Button.left)
                if ev.get("pressed"):
                    mouse.press(button)
                    if button not in held_buttons:
                        held_buttons.append(button)
                else:
                    mouse.release(button)
                    if button in held_buttons:
                        held_buttons.remove(button)
            finally:
                self.hub.end_inject()
        elif kind == "scroll":
            self.hub.begin_inject()
            try:
                mouse.position = (ev["x"], ev["y"])
                mouse.scroll(ev.get("dx", 0), ev.get("dy", 0))
            finally:
                self.hub.end_inject()
        elif kind == "key":
            key = to_pynput_key(ev)
            if key is None:
                return
            ident = key_identity(ev)
            self.hub.begin_inject()
            try:
                if ev.get("pressed"):
                    keyboard.press(key)
                    held_keys[ident] = key
                else:
                    keyboard.release(key)
                    held_keys.pop(ident, None)
            finally:
                self.hub.end_inject()

    def _release_all(self, mouse, keyboard, held_keys, held_buttons):
        self.hub.begin_inject()
        try:
            for key in list(held_keys.values()):
                try:
                    keyboard.release(key)
                except Exception:
                    pass
            held_keys.clear()
            for button in list(held_buttons):
                try:
                    mouse.release(button)
                except Exception:
                    pass
            held_buttons.clear()
        finally:
            self.hub.end_inject()

    def join(self, timeout=0.5):
        if self._thread is not None:
            self._thread.join(timeout=timeout)


# ================================================================== 通用控件
class FlatButton(tk.Label):
    STYLES = {
        "primary": ("#2F6FED", "#FFFFFF", "#255FD0", "#2F6FED"),
        "ghost": (CARD_BG, TEXT, "#EDF1F8", BORDER),
        "soft": (CHIP_BG, CHIP_FG, CHIP_HOVER, CHIP_BG),
        "danger": ("#E0455C", "#FFFFFF", "#C9364B", "#E0455C"),
        "soft_danger": (RED_BG, RED_FG, "#F8DADA", RED_BG),
    }

    def __init__(self, master, text, command=None, kind="ghost", padx=14, pady=7, font=None, **kw):
        self.kind = kind
        self._enabled = True
        self._command = command
        self._padx = padx
        self._pady = pady
        bg, fg, hover, border = self.STYLES.get(kind, self.STYLES["ghost"])
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
            highlightthickness=1,
            highlightbackground=border,
            **kw,
        )
        self._bg = bg
        self._fg = fg
        self._hover = hover
        self._border = border
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event=None):
        if self._enabled:
            self.configure(bg=self._hover)

    def _on_leave(self, _event=None):
        if self._enabled:
            self.configure(bg=self._bg)

    def _on_click(self, _event=None):
        if self._enabled and self._command:
            self._command()

    def set_text(self, text):
        self.configure(text=text)

    def set_kind(self, kind):
        bg, fg, hover, border = self.STYLES.get(kind, self.STYLES["ghost"])
        self.kind = kind
        self._bg = bg
        self._fg = fg
        self._hover = hover
        self._border = border
        self._apply()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if self._enabled else "arrow")
        self._apply()

    def _apply(self):
        if self._enabled:
            self.configure(bg=self._bg, fg=self._fg, highlightbackground=self._border)
        else:
            self.configure(bg="#EDF0F6", fg="#AEB6C6", highlightbackground="#E2E7F0")


class Pills(tk.Frame):
    """一排单选胶囊按钮。"""

    def __init__(self, master, options, variable, command=None, padx=11, pady=4, font=None):
        super().__init__(master, bg=CARD_BG)
        self.variable = variable
        self.command = command
        self._labels = {}
        for value, label in options:
            lbl = tk.Label(
                self,
                text=label,
                bg=SOFT_BG,
                fg=MUTED,
                font=font or FONTS["small"],
                padx=padx,
                pady=pady,
                bd=0,
                cursor="hand2",
            )
            lbl.pack(side="left", padx=(0, 4))
            lbl.bind("<Button-1>", lambda _e, v=value: self._choose(v))
            lbl.bind("<Enter>", lambda _e, v=value: self._hover(v, True))
            lbl.bind("<Leave>", lambda _e, v=value: self._hover(v, False))
            self._labels[value] = lbl
        variable.trace_add("write", lambda *_a: self._sync())
        self._sync()

    def _hover(self, value, entering):
        if self.variable.get() == value:
            return
        self._labels[value].configure(bg="#E8EDF7" if entering else SOFT_BG)

    def _choose(self, value):
        if self.variable.get() != value:
            self.variable.set(value)
            if self.command:
                self.command()

    def _sync(self):
        current = self.variable.get()
        for value, lbl in self._labels.items():
            if value == current:
                lbl.configure(bg=ACCENT, fg="#FFFFFF")
            else:
                lbl.configure(bg=SOFT_BG, fg=MUTED)


class Card(tk.Frame):
    def __init__(self, master, title=None, subtitle=None, padx=18, pady=15):
        super().__init__(master, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        self.body = tk.Frame(self, bg=CARD_BG)
        self.body.pack(fill="both", expand=True, padx=padx, pady=pady)
        self.head = None
        if title:
            self.head = tk.Frame(self.body, bg=CARD_BG)
            self.head.pack(fill="x", pady=(0, 10))
            tk.Label(self.head, text=title, bg=CARD_BG, fg=TEXT, font=FONTS["card"]).pack(side="left")
            if subtitle:
                tk.Label(
                    self.head, text="  " + subtitle, bg=CARD_BG, fg=MUTED, font=FONTS["small"]
                ).pack(side="left")


class TabBar(tk.Frame):
    def __init__(self, master, items, command):
        super().__init__(master, bg=BG)
        self.command = command
        self._items = {}
        for key, label in items:
            wrap = tk.Frame(self, bg=BG)
            wrap.pack(side="left", padx=(0, 26))
            lbl = tk.Label(wrap, text=label, bg=BG, fg=MUTED, font=FONTS["body"], cursor="hand2")
            lbl.pack(pady=(8, 6))
            line = tk.Frame(wrap, bg=BG, height=3)
            line.pack(fill="x")
            lbl.bind("<Button-1>", lambda _e, k=key: self.command(k))
            self._items[key] = (lbl, line)

    def set_active(self, key):
        for k, (lbl, line) in self._items.items():
            active = k == key
            lbl.configure(fg=TEXT if active else MUTED, font=FONTS["body_bold"] if active else FONTS["body"])
            line.configure(bg=ACCENT if active else BG)


class CountdownToast(tk.Toplevel):
    """屏幕上方的小倒计时提示，鼠标可穿透。"""

    def __init__(self, app, seconds, title, hint, on_done, on_cancel=None):
        super().__init__(app)
        self.app = app
        self.seconds = max(0, int(seconds))
        self.on_done = on_done
        self.on_cancel = on_cancel
        self._left = self.seconds
        self._done = False
        self.overrideredirect(True)
        self.configure(bg="#1E2430")
        try:
            self.attributes("-topmost", True)
            self.attributes("-alpha", 0.95)
        except Exception:
            pass

        body = tk.Frame(self, bg="#1E2430")
        body.pack(fill="both", expand=True, padx=20, pady=14)
        tk.Label(body, text=title, bg="#1E2430", fg="#FFFFFF", font=FONTS["card"]).pack(anchor="w")
        tk.Label(
            body, text=hint, bg="#1E2430", fg="#B9C2D6", font=FONTS["small"], justify="left"
        ).pack(anchor="w", pady=(4, 0))
        self.number_label = tk.Label(
            body, text=str(self._left), bg="#1E2430", fg="#6FA0FF", font=(FONTS["title"][0], 24, "bold")
        )
        self.number_label.pack(anchor="e", pady=(2, 0))

        w, h = 420, 138
        sw = self.winfo_screenwidth()
        self.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), 70))
        self.update_idletasks()
        try:
            hwnd = self.winfo_id()
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, -20, ex | 0x00000020 | 0x08000000
            )  # WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        except Exception:
            pass
        self.after(0, self._tick)

    def _tick(self):
        if self._done:
            return
        if self._left <= 0:
            self._finish()
            return
        self.number_label.configure(text=str(self._left))
        self._left -= 1
        self.after(1000, self._tick)

    def _finish(self):
        if self._done:
            return
        self._done = True
        try:
            self.destroy()
        except Exception:
            pass
        if self.on_done:
            self.on_done()

    def cancel(self):
        if self._done:
            return
        self._done = True
        try:
            self.destroy()
        except Exception:
            pass
        if self.on_cancel:
            self.on_cancel()


def make_entry(master, textvariable, width=10, font=None):
    return tk.Entry(
        master,
        textvariable=textvariable,
        width=width,
        bg=CARD_BG,
        fg=TEXT,
        insertbackground=TEXT,
        bd=0,
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
        font=font or FONTS["body"],
        justify="center",
    )


def make_spin(master, textvariable, lo, hi, width=8, increment=1):
    return tk.Spinbox(
        master,
        from_=lo,
        to=hi,
        increment=increment,
        textvariable=textvariable,
        width=width,
        bg=CARD_BG,
        fg=TEXT,
        insertbackground=TEXT,
        bd=0,
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
        buttonbackground=SOFT_BG,
        font=FONTS["body"],
        justify="center",
    )


def make_check(master, text, variable, command=None):
    return tk.Checkbutton(
        master,
        text=text,
        variable=variable,
        command=command,
        bg=CARD_BG,
        fg=TEXT,
        font=FONTS["small"],
        activebackground=CARD_BG,
        activeforeground=TEXT,
        selectcolor=CARD_BG,
        highlightthickness=0,
        bd=0,
        anchor="w",
        cursor="hand2",
    )


def form_label(master, text):
    return tk.Label(master, text=text, bg=CARD_BG, fg=MUTED, font=FONTS["small"], anchor="w")


# ================================================================== 主窗口
class App(tk.Tk):
    HOTKEY_ACTIONS = (
        ("click", "连点开关", "hotkey_click", "f6"),
        ("record", "开始/停止录制", "hotkey_record", "f7"),
        ("play", "回放当前宏", "hotkey_play", "f8"),
    )

    def __init__(self):
        super().__init__()
        self.withdraw()
        setup_fonts(self)
        setup_style(self)
        self.title(APP_TITLE)
        self.configure(bg=BG)
        try:
            if os.path.exists(ICON_PATH):
                self.iconbitmap(default=ICON_PATH)
        except Exception:
            pass

        self.cfg = load_config()
        self.macros = load_macros()
        self.selected_id = ""
        self.queue = queue.Queue()
        self.hub = InputHub(self.post, self._on_global_action)

        self._ready = False
        self._modal_depth = 0
        self._save_job = None
        self._status_job = None
        self._selecting = False
        self._toast = None
        self._countdown_kind = None
        self._rec_append_id = None
        self._rec_minimized_by_us = False
        self._rec_started_at = 0.0
        self._pick_minimized_by_us = False
        self._play_minimized_by_us = False
        self._last_tick = 0.0
        self._last_live_count = -1
        self.recorder = None
        self.mouse_listener = None
        self.clicker = None
        self.player = None

        self.status_var = tk.StringVar(value="")
        self._create_variables()
        self._build_ui()
        self._load_settings_into_ui()
        self._apply_topmost()
        self._ready = True
        self.hub.set_hotkeys(self._hotkey_map())
        self.hub.start()

        self._choose_initial_macro()
        self.refresh_all()
        self._apply_window()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(30, self._pump)
        self.deiconify()
        self.after(80, lambda: self.focus_force())
        self.set_status("就绪 · 连点 F6 · 录制 F7 · 回放 F8 · F9 随时停止", timeout=0)

    # -------------------------------------------------------------- 线程通信
    def post(self, fn):
        self.queue.put(fn)

    def _pump(self):
        try:
            for _ in range(300):
                fn = self.queue.get_nowait()
                try:
                    fn()
                except Exception:
                    log.exception("界面回调失败")
        except queue.Empty:
            pass
        now = time.monotonic()
        if now - self._last_tick > 0.2:
            self._last_tick = now
            self._tick_live()
        self.after(25, self._pump)

    def _tick_live(self):
        if self.recorder is not None and self.recorder.active:
            try:
                count = self.recorder.count()
                elapsed = self.recorder.elapsed_ms()
            except Exception:
                return
            if count != self._last_live_count:
                self._last_live_count = count
                self.rec_count_label.configure(text="%s 个事件" % format(count, ","))
            self.rec_time_label.configure(text=format_duration(elapsed))
            if count >= MAX_RECORD_EVENTS:
                self.stop_recording(limit_hit=True)

    # -------------------------------------------------------------- 界面骨架
    def _build_ui(self):
        scale = ui_scale(self)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.minsize(
            min(int(960 * scale), max(840, sw - 60)),
            min(int(680 * scale), max(600, sh - 100)),
        )

        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 2))

        hl = tk.Frame(header, bg=BG)
        hl.pack(side="left", anchor="w")
        title_row = tk.Frame(hl, bg=BG)
        title_row.pack(anchor="w")
        tk.Label(title_row, text=APP_TITLE, bg=BG, fg=TEXT, font=FONTS["title"]).pack(side="left")
        tk.Label(
            title_row, text="  v%s" % APP_VERSION, bg=BG, fg=MUTED, font=FONTS["tiny"]
        ).pack(side="left", pady=(8, 0))
        tk.Label(
            hl, text="连点 · 录制 · 宏回放，一键完成重复操作", bg=BG, fg=MUTED, font=FONTS["small"]
        ).pack(anchor="w", pady=(2, 0))

        hr = tk.Frame(header, bg=BG)
        hr.pack(side="right", anchor="e")
        self.stop_all_btn = FlatButton(
            hr, "■ 紧急停止   F9", self.stop_all, kind="danger", padx=16, pady=8
        )
        self.stop_all_btn.pack(side="right")
        self.state_pill = tk.Label(
            hr,
            text="● 空闲",
            bg=STATUS_BG,
            fg=MUTED,
            font=FONTS["body_bold"],
            padx=14,
            pady=7,
        )
        self.state_pill.pack(side="right", padx=(0, 12))

        self.tabbar = TabBar(
            outer,
            (("click", "连点器"), ("record", "录制"), ("macro", "宏库"), ("settings", "设置")),
            self.switch_tab,
        )
        self.tabbar.pack(fill="x", padx=24)

        line = tk.Frame(outer, bg=BORDER, height=1)
        line.pack(fill="x")

        bar = tk.Frame(outer, bg=STATUS_BG)
        bar.pack(side="bottom", fill="x")
        self.status_label = tk.Label(
            bar,
            textvariable=self.status_var,
            bg=STATUS_BG,
            fg=MUTED,
            font=FONTS["small"],
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True, padx=24, pady=6)
        tk.Label(
            bar,
            text="F9 紧急停止 · 配置保存在程序目录",
            bg=STATUS_BG,
            fg=MUTED,
            font=FONTS["tiny"],
        ).pack(side="right", padx=24)

        host = tk.Frame(outer, bg=BG)
        host.pack(fill="both", expand=True, padx=24, pady=(12, 10))
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        self.pages = {}
        builders = {
            "click": self._build_click_page,
            "record": self._build_record_page,
            "macro": self._build_macro_page,
            "settings": self._build_settings_page,
        }
        for key, builder in builders.items():
            page = tk.Frame(host, bg=BG)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page
            builder(page)
        self.switch_tab("click")

    def switch_tab(self, key):
        if key not in self.pages:
            return
        self.pages[key].tkraise()
        self.tabbar.set_active(key)
        if key == "macro":
            self.refresh_macro_detail()

    def _create_variables(self):
        s = self.cfg["settings"]
        self.interval_var = tk.StringVar(value=str(s["click_interval_ms"]))
        self.click_button_var = tk.StringVar(value=s["click_button"])
        self.click_type_var = tk.StringVar(value=s["click_type"])
        self.click_position_var = tk.StringVar(value=s["click_position"])
        self.fixed_x_var = tk.StringVar(value=str(s["fixed_x"]))
        self.fixed_y_var = tk.StringVar(value=str(s["fixed_y"]))
        self.click_repeat_var = tk.StringVar(value=s["click_repeat"])
        self.click_count_var = tk.StringVar(value=str(s["click_count"]))

        self.rec_moves_var = tk.BooleanVar(value=s["record_moves"])
        self.rec_clicks_var = tk.BooleanVar(value=s["record_clicks"])
        self.rec_keys_var = tk.BooleanVar(value=s["record_keys"])
        self.rec_sample_var = tk.StringVar(value=str(s["record_sample_px"]))
        self.rec_countdown_var = tk.StringVar(value=str(s["record_countdown"]))
        self.rec_minimize_var = tk.BooleanVar(value=s["record_minimize"])

        self.play_speed_var = tk.StringVar(value=speed_text(s["play_speed"]))
        self.play_loops_var = tk.StringVar(value=str(s["play_loops"]))
        self.play_infinite_var = tk.BooleanVar(value=s["play_infinite"])
        self.play_lead_var = tk.StringVar(value=str(s["play_lead_ms"]))
        self.play_gap_var = tk.StringVar(value=str(s["play_gap_ms"]))
        self.play_minimize_var = tk.BooleanVar(value=s["play_minimize"])
        self.click_ui_countdown_var = tk.BooleanVar(value=s.get("click_ui_countdown", True))
        self.topmost_var = tk.BooleanVar(value=s["always_on_top"])

        watched = [
            self.interval_var,
            self.click_button_var,
            self.click_type_var,
            self.click_position_var,
            self.fixed_x_var,
            self.fixed_y_var,
            self.click_repeat_var,
            self.click_count_var,
            self.rec_moves_var,
            self.rec_clicks_var,
            self.rec_keys_var,
            self.rec_sample_var,
            self.rec_countdown_var,
            self.rec_minimize_var,
            self.play_speed_var,
            self.play_loops_var,
            self.play_infinite_var,
            self.play_lead_var,
            self.play_gap_var,
            self.play_minimize_var,
            self.click_ui_countdown_var,
            self.topmost_var,
        ]
        for var in watched:
            var.trace_add("write", lambda *_a: self._on_ui_change())

    def _on_ui_change(self):
        if not self._ready:
            return
        self._update_click_summary()
        self._sync_fixed_controls()
        self._sync_repeat_controls()
        self._sync_loop_controls()
        self._apply_topmost()
        self.schedule_save()

    def _load_settings_into_ui(self):
        s = self.cfg["settings"]
        self._ready = False
        try:
            self.interval_var.set(str(s["click_interval_ms"]))
            self.click_button_var.set(s["click_button"])
            self.click_type_var.set(s["click_type"])
            self.click_position_var.set(s["click_position"])
            self.fixed_x_var.set(str(s["fixed_x"]))
            self.fixed_y_var.set(str(s["fixed_y"]))
            self.click_repeat_var.set(s["click_repeat"])
            self.click_count_var.set(str(s["click_count"]))
            self.rec_moves_var.set(s["record_moves"])
            self.rec_clicks_var.set(s["record_clicks"])
            self.rec_keys_var.set(s["record_keys"])
            self.rec_sample_var.set(str(s["record_sample_px"]))
            self.rec_countdown_var.set(str(s["record_countdown"]))
            self.rec_minimize_var.set(s["record_minimize"])
            self.play_speed_var.set(speed_text(s["play_speed"]))
            self.play_loops_var.set(str(s["play_loops"]))
            self.play_infinite_var.set(s["play_infinite"])
            self.play_lead_var.set(str(s["play_lead_ms"]))
            self.play_gap_var.set(str(s["play_gap_ms"]))
            self.play_minimize_var.set(s["play_minimize"])
            self.click_ui_countdown_var.set(s.get("click_ui_countdown", True))
            self.topmost_var.set(s["always_on_top"])
        finally:
            self._ready = True
        self._update_click_summary()
        self._sync_fixed_controls()
        self._sync_repeat_controls()
        self._sync_loop_controls()
        self._update_hotkey_labels()

    def _read_int(self, var, default, lo, hi):
        try:
            return max(lo, min(hi, int(float(var.get()))))
        except (TypeError, ValueError):
            return default

    def _read_float(self, var, default, lo, hi):
        try:
            return max(lo, min(hi, float(var.get())))
        except (TypeError, ValueError):
            return default

    def _collect_settings(self):
        s = self.cfg["settings"]
        s["click_interval_ms"] = self._read_int(self.interval_var, s["click_interval_ms"], 1, 3600000)
        s["click_button"] = self.click_button_var.get() if self.click_button_var.get() in ("left", "right", "middle") else s["click_button"]
        s["click_type"] = self.click_type_var.get() if self.click_type_var.get() in ("single", "double") else s["click_type"]
        s["click_position"] = self.click_position_var.get() if self.click_position_var.get() in ("cursor", "fixed") else s["click_position"]
        s["fixed_x"] = self._read_int(self.fixed_x_var, s["fixed_x"], -32768, 32767)
        s["fixed_y"] = self._read_int(self.fixed_y_var, s["fixed_y"], -32768, 32767)
        s["click_repeat"] = self.click_repeat_var.get() if self.click_repeat_var.get() in ("infinite", "count") else s["click_repeat"]
        s["click_count"] = self._read_int(self.click_count_var, s["click_count"], 1, 10000000)
        s["record_moves"] = bool(self.rec_moves_var.get())
        s["record_clicks"] = bool(self.rec_clicks_var.get())
        s["record_keys"] = bool(self.rec_keys_var.get())
        s["record_sample_px"] = self._read_int(self.rec_sample_var, s["record_sample_px"], 1, 100)
        s["record_countdown"] = self._read_int(self.rec_countdown_var, s["record_countdown"], 0, 10)
        s["record_minimize"] = bool(self.rec_minimize_var.get())
        s["play_speed"] = self._parse_speed(self.play_speed_var.get(), s["play_speed"])
        s["play_loops"] = self._read_int(self.play_loops_var, s["play_loops"], 1, 100000)
        s["play_infinite"] = bool(self.play_infinite_var.get())
        s["play_lead_ms"] = self._read_int(self.play_lead_var, s["play_lead_ms"], 0, 10000)
        s["play_gap_ms"] = self._read_int(self.play_gap_var, s["play_gap_ms"], 0, 10000)
        s["play_minimize"] = bool(self.play_minimize_var.get())
        s["click_ui_countdown"] = bool(self.click_ui_countdown_var.get())
        s["always_on_top"] = bool(self.topmost_var.get())
        s["selected_macro"] = self.selected_id
        return s

    def _parse_speed(self, text, default=1.0):
        try:
            return max(0.1, min(5.0, float(str(text).lower().replace("x", "").strip())))
        except (TypeError, ValueError):
            return default

    def schedule_save(self):
        if not self._ready:
            return
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(700, self._save_config)

    def _save_config(self):
        self._save_job = None
        if not self._ready:
            return
        try:
            self._collect_settings()
            write_json_atomic(CONFIG_PATH, self.cfg)
        except Exception:
            log.exception("保存配置失败")
            self.set_status("配置保存失败，请检查程序目录是否可写。", timeout=0)

    def _apply_window(self):
        geometry = self.cfg["settings"].get("window_geometry") or ""
        if geometry:
            try:
                self.geometry(geometry)
                self.after(60, self._clamp_window)
                return
            except tk.TclError:
                pass
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        scale = ui_scale(self)
        w = min(int(1060 * scale), sw - 80)
        h = min(int(750 * scale), sh - 120)
        x = (sw - w) // 2
        y = max(0, (sh - h) // 3)
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def _clamp_window(self):
        try:
            self.update_idletasks()
            w, h = self.winfo_width(), self.winfo_height()
            x, y = self.winfo_x(), self.winfo_y()
            if os.name == "nt":
                u = ctypes.windll.user32
                vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
                vw, vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
            else:
                vx = vy = 0
                vw, vh = self.winfo_screenwidth(), self.winfo_screenheight()
            x = min(max(vx, x), max(vx, vx + vw - w))
            y = min(max(vy, y), max(vy, vy + vh - h))
            if (x, y) != (self.winfo_x(), self.winfo_y()):
                self.geometry("+%d+%d" % (x, y))
        except Exception:
            pass

    def _apply_topmost(self):
        try:
            self.attributes("-topmost", bool(self.cfg["settings"].get("always_on_top")))
        except tk.TclError:
            pass

    def set_status(self, text, timeout=8000):
        self.status_var.set(text)
        if self._status_job is not None:
            try:
                self.after_cancel(self._status_job)
            except Exception:
                pass
            self._status_job = None
        if timeout:
            self._status_job = self.after(timeout, self._reset_status)

    def _reset_status(self):
        self._status_job = None
        self.status_var.set("就绪 · 连点 F6 · 录制 F7 · 回放 F8 · F9 随时停止")

    # -------------------------------------------------------------- 连点器页
    def _build_click_page(self, page):
        hero = tk.Frame(page, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        hero.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(hero, bg=CARD_BG)
        inner.pack(fill="x", padx=20, pady=15)

        left = tk.Frame(inner, bg=CARD_BG)
        left.pack(side="left", anchor="w")
        state_row = tk.Frame(left, bg=CARD_BG)
        state_row.pack(anchor="w")
        self.hero_dot = tk.Label(state_row, text="●", bg=CARD_BG, fg=MUTED, font=FONTS["body_bold"])
        self.hero_dot.pack(side="left", padx=(0, 6))
        self.click_state_label = tk.Label(
            state_row, text="空闲", bg=CARD_BG, fg=TEXT, font=FONTS["card"]
        )
        self.click_state_label.pack(side="left")
        self.click_summary_label = tk.Label(
            left, text="", bg=CARD_BG, fg=MUTED, font=FONTS["small"]
        )
        self.click_summary_label.pack(anchor="w", pady=(5, 0))

        self.click_toggle_btn = FlatButton(
            inner, "▶ 开始连点   F6", self.toggle_clicker_from_ui, kind="primary", padx=20, pady=11
        )
        self.click_toggle_btn.pack(side="right")

        count_box = tk.Frame(inner, bg=CARD_BG)
        count_box.pack(side="right", padx=(0, 26))
        tk.Label(count_box, text="已点击", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(anchor="e")
        self.click_count_label = tk.Label(
            count_box, text="0", bg=CARD_BG, fg=TEXT, font=FONTS["big"]
        )
        self.click_count_label.pack(anchor="e")

        card = Card(page, "点击设置", "间隔越短，点击越快")
        card.pack(fill="x", pady=(0, 10))
        grid = tk.Frame(card.body, bg=CARD_BG)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        form_label(grid, "点击间隔").grid(row=0, column=0, sticky="w", pady=7, padx=(0, 14))
        interval_row = tk.Frame(grid, bg=CARD_BG)
        interval_row.grid(row=0, column=1, sticky="w", pady=7)
        self.interval_spin = make_spin(interval_row, self.interval_var, 1, 3600000, width=9, increment=10)
        self.interval_spin.pack(side="left", ipady=2)
        tk.Label(interval_row, text="毫秒", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left", padx=(6, 18)
        )
        for preset in (10, 50, 100, 200, 500, 1000):
            b = FlatButton(
                interval_row,
                "%d" % preset,
                lambda v=preset: self.interval_var.set(str(v)),
                kind="soft",
                padx=9,
                pady=3,
                font=FONTS["tiny"],
            )
            b.pack(side="left", padx=(0, 4))

        form_label(grid, "鼠标按键").grid(row=1, column=0, sticky="w", pady=7, padx=(0, 14))
        button_row = tk.Frame(grid, bg=CARD_BG)
        button_row.grid(row=1, column=1, sticky="w", pady=7)
        Pills(
            button_row,
            (("left", "左键"), ("right", "右键"), ("middle", "中键")),
            self.click_button_var,
        ).pack(side="left")
        tk.Label(button_row, text="方式", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left", padx=(18, 8)
        )
        Pills(button_row, (("single", "单击"), ("double", "双击")), self.click_type_var).pack(
            side="left"
        )

        form_label(grid, "点击位置").grid(row=2, column=0, sticky="w", pady=7, padx=(0, 14))
        pos_row = tk.Frame(grid, bg=CARD_BG)
        pos_row.grid(row=2, column=1, sticky="w", pady=7)
        Pills(pos_row, (("cursor", "跟随鼠标"), ("fixed", "固定坐标")), self.click_position_var).pack(
            side="left"
        )
        self.fixed_frame = tk.Frame(pos_row, bg=CARD_BG)
        self.fixed_frame.pack(side="left", padx=(10, 0))
        tk.Label(self.fixed_frame, text="X", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left", padx=(0, 3)
        )
        make_entry(self.fixed_frame, self.fixed_x_var, width=7).pack(side="left", ipady=3)
        tk.Label(self.fixed_frame, text="Y", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left", padx=(8, 3)
        )
        make_entry(self.fixed_frame, self.fixed_y_var, width=7).pack(side="left", ipady=3)
        FlatButton(
            self.fixed_frame, "拾取…", self.pick_coordinate, kind="soft", padx=9, pady=3, font=FONTS["tiny"]
        ).pack(side="left", padx=(8, 4))
        FlatButton(
            self.fixed_frame,
            "取当前",
            self.use_current_position,
            kind="ghost",
            padx=9,
            pady=3,
            font=FONTS["tiny"],
        ).pack(side="left")

        form_label(grid, "重复次数").grid(row=3, column=0, sticky="w", pady=7, padx=(0, 14))
        repeat_row = tk.Frame(grid, bg=CARD_BG)
        repeat_row.grid(row=3, column=1, sticky="w", pady=7)
        Pills(repeat_row, (("infinite", "无限"), ("count", "指定次数")), self.click_repeat_var).pack(
            side="left"
        )
        self.click_count_spin = make_spin(
            repeat_row, self.click_count_var, 1, 10000000, width=9, increment=10
        )
        self.click_count_spin.pack(side="left", padx=(12, 5), ipady=2)
        tk.Label(repeat_row, text="次", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(side="left")

        hk = Card(page, "全局快捷键", "在所有程序中生效，无需切回本窗口")
        hk.pack(fill="x", pady=(0, 10))
        hk_grid = tk.Frame(hk.body, bg=CARD_BG)
        hk_grid.pack(fill="x")
        for col in range(4):
            hk_grid.columnconfigure(col, weight=1, uniform="hk")
        self.hotkey_value_labels = {}
        for col, (action, label, _conf_key, default) in enumerate(self.HOTKEY_ACTIONS):
            cell = tk.Frame(hk_grid, bg=CARD_BG)
            cell.grid(row=0, column=col, sticky="w")
            tk.Label(cell, text=label, bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(anchor="w")
            row = tk.Frame(cell, bg=CARD_BG)
            row.pack(anchor="w", pady=(3, 0))
            value = tk.Label(row, text=pretty_combo(default), bg=CARD_BG, fg=ACCENT, font=FONTS["body_bold"])
            value.pack(side="left")
            FlatButton(
                row,
                "修改",
                lambda a=action: self.edit_hotkey(a),
                kind="ghost",
                padx=8,
                pady=2,
                font=FONTS["tiny"],
            ).pack(side="left", padx=(8, 0))
            self.hotkey_value_labels[action] = value
        cell = tk.Frame(hk_grid, bg=CARD_BG)
        cell.grid(row=0, column=3, sticky="w")
        tk.Label(cell, text="紧急停止", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(anchor="w")
        tk.Label(cell, text="F9（固定）", bg=CARD_BG, fg=RED, font=FONTS["body_bold"]).pack(
            anchor="w", pady=(3, 0)
        )
        self.hotkey_value_labels["stop"] = None

        tips = Card(page)
        tips.pack(fill="x", pady=(2, 0))
        tk.Label(
            tips.body,
            text="提示：F6 开始/停止连点 · F7 开始/停止录制 · F8 回放当前宏 · F9 紧急停止",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["small"],
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            tips.body,
            text="连点跟随鼠标时，从按钮启动会先倒计时 2 秒（固定坐标 1 秒），方便把鼠标移到目标上；按 F6 则立即开始。",
            bg=CARD_BG,
            fg="#A0A8B8",
            font=FONTS["tiny"],
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

    def _build_record_page(self, page):
        hero = tk.Frame(page, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        hero.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(hero, bg=CARD_BG)
        inner.pack(fill="x", padx=20, pady=15)

        left = tk.Frame(inner, bg=CARD_BG)
        left.pack(side="left", anchor="w")
        row = tk.Frame(left, bg=CARD_BG)
        row.pack(anchor="w")
        self.rec_dot = tk.Label(row, text="●", bg=CARD_BG, fg=MUTED, font=FONTS["body_bold"])
        self.rec_dot.pack(side="left", padx=(0, 6))
        self.rec_state_label = tk.Label(row, text="未录制", bg=CARD_BG, fg=TEXT, font=FONTS["card"])
        self.rec_state_label.pack(side="left")
        self.rec_append_label = tk.Label(left, text="", bg=CARD_BG, fg=AMBER, font=FONTS["small"])
        self.rec_append_label.pack(anchor="w", pady=(4, 0))
        self.rec_hint_label = tk.Label(
            left, text="按 F7 或点右侧按钮开始录制", bg=CARD_BG, fg=MUTED, font=FONTS["small"]
        )
        self.rec_hint_label.pack(anchor="w", pady=(4, 0))

        self.rec_btn = FlatButton(
            inner,
            "● 开始录制   F7",
            lambda: self.toggle_recording(from_ui=True),
            kind="danger",
            padx=20,
            pady=11,
        )
        self.rec_btn.pack(side="right")

        stats = tk.Frame(inner, bg=CARD_BG)
        stats.pack(side="right", padx=(0, 26))
        tk.Label(stats, text="已记录", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(anchor="e")
        line = tk.Frame(stats, bg=CARD_BG)
        line.pack(anchor="e")
        self.rec_count_label = tk.Label(line, text="0 个事件", bg=CARD_BG, fg=TEXT, font=FONTS["body_bold"])
        self.rec_count_label.pack(side="left")
        self.rec_time_label = tk.Label(
            line, text="0.0 秒", bg=CARD_BG, fg=MUTED, font=FONTS["body_bold"]
        )
        self.rec_time_label.pack(side="left", padx=(10, 0))

        options = Card(page, "录制设置", "录制时本工具会自动最小化，结束后恢复")
        options.pack(fill="x", pady=(0, 10))
        b = options.body
        row1 = tk.Frame(b, bg=CARD_BG)
        row1.pack(fill="x", pady=(0, 8))
        form_label(row1, "开始倒计时").pack(side="left", padx=(0, 8))
        make_spin(row1, self.rec_countdown_var, 0, 10, width=5).pack(side="left", ipady=2)
        tk.Label(row1, text="秒", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left", padx=(5, 16)
        )
        make_check(row1, "录制时最小化本窗口", self.rec_minimize_var).pack(side="left", padx=(0, 20))
        make_check(row1, "记录鼠标轨迹", self.rec_moves_var).pack(side="left", padx=(0, 14))
        make_check(row1, "记录点击与滚轮", self.rec_clicks_var).pack(side="left", padx=(0, 14))
        make_check(row1, "记录键盘按键", self.rec_keys_var).pack(side="left")

        row2 = tk.Frame(b, bg=CARD_BG)
        row2.pack(fill="x")
        tk.Label(
            row2,
            text="轨迹采样",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["small"],
        ).pack(side="left")
        make_spin(row2, self.rec_sample_var, 1, 100, width=5).pack(side="left", padx=(8, 4), ipady=2)
        tk.Label(
            row2,
            text="像素（越小轨迹越顺滑，文件越大）",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["small"],
        ).pack(side="left")
        tk.Label(
            row2,
            text="　停止录制请再按 F7；F9 也可以停止并保存",
            bg=CARD_BG,
            fg="#A0A8B8",
            font=FONTS["tiny"],
        ).pack(side="right")

        lower = tk.Frame(page, bg=BG)
        lower.pack(fill="both", expand=True)
        lower.grid_columnconfigure(0, weight=3)
        lower.grid_columnconfigure(1, weight=2)
        lower.grid_rowconfigure(0, weight=1)

        steps = Card(lower, "怎么用")
        steps.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        for i, (title, desc) in enumerate(
            (
                ("1. 准备", "按 F7（或点开始录制），倒计时结束后开始记录。"),
                ("2. 操作", "像平时一样点击、拖动、滚轮、敲键盘，工具会记录轨迹与间隔。"),
                ("3. 结束", "按 F7 停止，自动保存为宏并出现在「宏库」里。"),
                ("4. 复用", "选中宏按 F8 即可一键回放，也可以编辑、合并、循环。"),
            )
        ):
            row = tk.Frame(steps.body, bg=CARD_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=title, bg=CARD_BG, fg=TEXT, font=FONTS["small"], width=7, anchor="w").pack(
                side="left", anchor="n"
            )
            tk.Label(
                row,
                text=desc,
                bg=CARD_BG,
                fg=MUTED,
                font=FONTS["small"],
                justify="left",
                anchor="w",
                wraplength=int(360 * ui_scale(self)),
            ).pack(side="left", fill="x", expand=True)

        latest = Card(lower, "最近录制")
        latest.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.latest_name = tk.Label(
            latest.body, text="还没有录制", bg=CARD_BG, fg=TEXT, font=FONTS["body_bold"], anchor="w"
        )
        self.latest_name.pack(fill="x")
        self.latest_meta = tk.Label(
            latest.body, text="录制完成后会显示在这里", bg=CARD_BG, fg=MUTED, font=FONTS["small"], anchor="w"
        )
        self.latest_meta.pack(fill="x", pady=(4, 10))
        btn_row = tk.Frame(latest.body, bg=CARD_BG)
        btn_row.pack(fill="x")
        self.latest_view_btn = FlatButton(
            btn_row, "在宏库中查看", self.view_latest, kind="soft", padx=12, pady=5
        )
        self.latest_view_btn.pack(side="left")
        self.latest_play_btn = FlatButton(
            btn_row, "回放", lambda: self.play_latest(), kind="ghost", padx=12, pady=5
        )
        self.latest_play_btn.pack(side="left", padx=(6, 0))
        self.latest_view_btn.set_enabled(False)
        self.latest_play_btn.set_enabled(False)

    def _update_click_summary(self):
        if not hasattr(self, "click_summary_label"):
            return
        try:
            interval = self._read_int(self.interval_var, 100, 1, 3600000)
        except Exception:
            interval = 100
        button = {"left": "左键", "right": "右键", "middle": "中键"}.get(
            self.click_button_var.get(), "左键"
        )
        click_type = "双击" if self.click_type_var.get() == "double" else "单击"
        if self.click_position_var.get() == "fixed":
            pos = "固定 (%s, %s)" % (self.fixed_x_var.get() or "0", self.fixed_y_var.get() or "0")
        else:
            pos = "跟随鼠标"
        repeat = "无限" if self.click_repeat_var.get() == "infinite" else "%s 次" % self.click_count_var.get()
        self.click_summary_label.configure(
            text="间隔 %s ms · %s%s · %s · %s" % (interval, button, click_type, pos, repeat)
        )
        self._sync_fixed_controls()

    def _sync_fixed_controls(self):
        if not hasattr(self, "fixed_frame"):
            return
        if self.click_position_var.get() == "fixed":
            if self.fixed_frame.winfo_manager() != "pack":
                self.fixed_frame.pack(side="left", padx=(10, 0))
        else:
            if self.fixed_frame.winfo_manager() == "pack":
                self.fixed_frame.pack_forget()

    def _sync_repeat_controls(self):
        if not hasattr(self, "click_count_spin"):
            return
        try:
            self.click_count_spin.configure(
                state="normal" if self.click_repeat_var.get() == "count" else "disabled"
            )
        except Exception:
            pass

    def _sync_loop_controls(self):
        if not hasattr(self, "play_loops_spin"):
            return
        try:
            self.play_loops_spin.configure(
                state="disabled" if self.play_infinite_var.get() else "normal"
            )
        except Exception:
            pass

    # -------------------------------------------------------------- 宏库页
    def _build_macro_page(self, page):
        toolbar = tk.Frame(page, bg=BG)
        toolbar.pack(fill="x", pady=(0, 8))
        self.macro_count_label = tk.Label(
            toolbar, text="共 0 个宏", bg=BG, fg=TEXT, font=FONTS["card"]
        )
        self.macro_count_label.pack(side="left")
        tk.Label(
            toolbar,
            text="  选中宏后按 F8 回放；双击宏列表回放，双击下方事件可编辑",
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
        ).pack(side="left")

        self.macro_import_btn = FlatButton(
            toolbar, "导入", self.import_macro, kind="ghost", padx=12, pady=6, font=FONTS["small"]
        )
        self.macro_rename_btn = FlatButton(
            toolbar, "重命名", self.rename_macro, kind="ghost", padx=12, pady=6, font=FONTS["small"]
        )
        self.macro_delete_btn = FlatButton(
            toolbar, "删除", self.delete_macro, kind="soft_danger", padx=12, pady=6, font=FONTS["small"]
        )
        self.macro_delete_btn.pack(side="right")
        self.macro_rename_btn.pack(side="right", padx=(0, 6))
        self.macro_import_btn.pack(side="right", padx=(0, 6))


        content = tk.Frame(page, bg=BG)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=4)
        content.grid_columnconfigure(1, weight=6)
        content.grid_rowconfigure(0, weight=1)

        left = Card(content, "全部宏", padx=13, pady=13)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tree_wrap = tk.Frame(left.body, bg=CARD_BG)
        tree_wrap.pack(fill="both", expand=True)
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)
        self.macro_tree = ttk.Treeview(
            tree_wrap, columns=("name", "count", "dur"), show="headings", selectmode="browse"
        )
        self.macro_tree.heading("name", text="名称", anchor="w")
        self.macro_tree.heading("count", text="动作", anchor="center")
        self.macro_tree.heading("dur", text="时长", anchor="center")
        self.macro_tree.column("name", width=200, minwidth=120, anchor="w", stretch=True)
        self.macro_tree.column("count", width=52, minwidth=40, anchor="center", stretch=False)
        self.macro_tree.column("dur", width=64, minwidth=50, anchor="center", stretch=False)
        self.macro_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.macro_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.macro_tree.configure(yscrollcommand=sb.set)
        self.macro_tree.bind("<<TreeviewSelect>>", self._on_macro_select)
        self.macro_tree.bind("<Double-1>", lambda _e: self.play_selected(from_ui=True))
        self.macro_tree.bind("<Return>", lambda _e: self.play_selected(from_ui=True))
        tk.Label(
            left.body,
            text="录制完成后会自动出现在这里",
            bg=CARD_BG,
            fg="#A0A8B8",
            font=FONTS["tiny"],
        ).pack(anchor="w", pady=(7, 0))

        self.macro_detail = Card(content, padx=16, pady=14)
        self.macro_detail.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        head = tk.Frame(self.macro_detail.body, bg=CARD_BG)
        head.pack(fill="x")
        self.macro_name_label = tk.Label(
            head, text="未选择宏", bg=CARD_BG, fg=TEXT, font=FONTS["big"], anchor="w"
        )
        self.macro_name_label.pack(side="left")
        self.macro_meta_label = tk.Label(
            head, text="", bg=CARD_BG, fg=MUTED, font=FONTS["small"], anchor="w"
        )
        self.macro_meta_label.pack(side="right", pady=(6, 0))

        self.detail_area = tk.Frame(self.macro_detail.body, bg=CARD_BG)
        self.detail_area.pack(fill="both", expand=True, pady=(10, 0))
        self.detail_area.grid_columnconfigure(0, weight=1)
        self.detail_area.grid_rowconfigure(3, weight=1)

        controls = tk.Frame(self.detail_area, bg=CARD_BG)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.play_btn = FlatButton(
            controls, "▶ 播放   F8", lambda: self.play_selected(from_ui=True), kind="primary", padx=14, pady=6
        )
        self.play_btn.pack(side="left")
        self.play_stop_btn = FlatButton(
            controls, "■ 停止", self.stop_playback, kind="ghost", padx=10, pady=6, font=FONTS["small"]
        )
        self.play_stop_btn.pack(side="left", padx=(6, 14))
        tk.Label(controls, text="循环", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
        self.play_loops_spin = make_spin(controls, self.play_loops_var, 1, 100000, width=6)
        self.play_loops_spin.pack(side="left", padx=(5, 3), ipady=2)
        tk.Label(controls, text="次", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(side="left", padx=(0, 10))
        make_check(controls, "无限", self.play_infinite_var).pack(side="left")
        tk.Label(controls, text="速度", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left", padx=(14, 5)
        )
        self.play_speed_combo = ttk.Combobox(
            controls,
            textvariable=self.play_speed_var,
            values=("0.25x", "0.5x", "0.75x", "1.0x", "1.5x", "2.0x", "3.0x", "4.0x"),
            state="readonly",
            width=5,
            font=FONTS["small"],
        )
        self.play_speed_combo.pack(side="left")

        progress_box = tk.Frame(self.detail_area, bg=CARD_BG)
        progress_box.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        progress_box.grid_columnconfigure(0, weight=1)
        self.play_progress = ttk.Progressbar(
            progress_box, style="Thin.Horizontal.TProgressbar", mode="determinate", maximum=100
        )
        self.play_progress.grid(row=0, column=0, sticky="ew", pady=(3, 0))
        self.play_progress_label = tk.Label(
            progress_box, text="未播放", bg=CARD_BG, fg=MUTED, font=FONTS["tiny"], width=26, anchor="e"
        )
        self.play_progress_label.grid(row=0, column=1, sticky="e", padx=(8, 0))

        ev_head = tk.Frame(self.detail_area, bg=CARD_BG)
        ev_head.grid(row=2, column=0, sticky="ew", pady=(4, 4))
        tk.Label(ev_head, text="事件分解", bg=CARD_BG, fg=TEXT, font=FONTS["body_bold"]).pack(side="left")
        self.event_count_label = tk.Label(ev_head, text="", bg=CARD_BG, fg=MUTED, font=FONTS["tiny"])
        self.event_count_label.pack(side="left", padx=(8, 0))
        tk.Label(
            ev_head,
            text="删除/改键/偏移时间后，可重新组合成新的宏",
            bg=CARD_BG,
            fg="#A0A8B8",
            font=FONTS["tiny"],
        ).pack(side="right")

        ev_wrap = tk.Frame(self.detail_area, bg=CARD_BG)
        ev_wrap.grid(row=3, column=0, sticky="nsew")
        ev_wrap.grid_rowconfigure(0, weight=1)
        ev_wrap.grid_columnconfigure(0, weight=1)
        self.event_tree = ttk.Treeview(
            ev_wrap,
            columns=("n", "time", "gap", "action"),
            show="headings",
            selectmode="browse",
        )
        self.event_tree.heading("n", text="#", anchor="center")
        self.event_tree.heading("time", text="秒", anchor="center")
        self.event_tree.heading("gap", text="间隔", anchor="center")
        self.event_tree.heading("action", text="动作", anchor="w")
        self.event_tree.column("n", width=38, minwidth=32, anchor="center", stretch=False)
        self.event_tree.column("time", width=62, minwidth=50, anchor="center", stretch=False)
        self.event_tree.column("gap", width=58, minwidth=45, anchor="center", stretch=False)
        self.event_tree.column("action", width=260, minwidth=140, anchor="w", stretch=True)
        self.event_tree.grid(row=0, column=0, sticky="nsew")
        ev_sb = ttk.Scrollbar(ev_wrap, orient="vertical", command=self.event_tree.yview)
        ev_sb.grid(row=0, column=1, sticky="ns")
        self.event_tree.configure(yscrollcommand=ev_sb.set)
        self.event_tree.bind("<Double-1>", lambda _e: self.edit_macro_events())

        actions = tk.Frame(self.detail_area, bg=CARD_BG)
        actions.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.edit_events_btn = FlatButton(
            actions, "编辑事件…", self.edit_macro_events, kind="soft", padx=10, pady=4, font=FONTS["tiny"]
        )
        self.edit_events_btn.pack(side="left")
        self.merge_btn = FlatButton(
            actions, "合并宏…", self.merge_macro, kind="ghost", padx=10, pady=4, font=FONTS["tiny"]
        )
        self.merge_btn.pack(side="left", padx=(5, 0))
        self.append_btn = FlatButton(
            actions, "追加录制", self.append_record, kind="ghost", padx=10, pady=4, font=FONTS["tiny"]
        )
        self.append_btn.pack(side="left", padx=(5, 0))
        self.export_script_btn = FlatButton(
            actions, "导出脚本", self.export_script, kind="ghost", padx=10, pady=4, font=FONTS["tiny"]
        )
        self.export_script_btn.pack(side="right")
        self.export_json_btn = FlatButton(
            actions, "导出 JSON", self.export_json, kind="ghost", padx=10, pady=4, font=FONTS["tiny"]
        )
        self.export_json_btn.pack(side="right", padx=(0, 5))

        self.macro_empty = tk.Frame(self.detail_area, bg=CARD_BG)
        tk.Label(
            self.macro_empty, text="还没有可用的宏", bg=CARD_BG, fg=TEXT, font=FONTS["card"]
        ).pack(pady=(40, 6))
        tk.Label(
            self.macro_empty,
            text="按 F7 录制一段操作，或从其它电脑导入宏文件。\n录制结束后会自动保存到这里。",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["small"],
            justify="center",
        ).pack(pady=(0, 12))
        FlatButton(
            self.macro_empty,
            "去录制",
            lambda: (self.switch_tab("record"), self.toggle_recording(from_ui=True)),
            kind="primary",
            padx=16,
            pady=7,
        ).pack()

    # -------------------------------------------------------------- 设置页
    def _build_settings_page(self, page):
        grid = tk.Frame(page, bg=BG)
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1, uniform="setcol")
        grid.grid_columnconfigure(1, weight=1, uniform="setcol")
        grid.grid_rowconfigure(1, weight=1)

        playback = Card(grid, "回放", "对连点和宏回放都生效的安全设置")
        playback.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 10))
        b = playback.body
        row = tk.Frame(b, bg=CARD_BG)
        row.pack(fill="x", pady=4)
        form_label(row, "开始前等待").pack(side="left")
        make_spin(row, self.play_lead_var, 0, 10000, width=7).pack(side="left", padx=(8, 4), ipady=2)
        tk.Label(row, text="毫秒", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
        tk.Label(
            b,
            text="回放 / 宏开始前留一点时间，方便把焦点切到目标窗口。",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["tiny"],
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        row = tk.Frame(b, bg=CARD_BG)
        row.pack(fill="x", pady=4)
        form_label(row, "循环间隔").pack(side="left")
        make_spin(row, self.play_gap_var, 0, 10000, width=7).pack(side="left", padx=(8, 4), ipady=2)
        tk.Label(row, text="毫秒", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
        tk.Label(
            b,
            text="宏循环播放时，每一轮之间停顿的时间。",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["tiny"],
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        make_check(b, "回放宏时最小化本窗口", self.play_minimize_var).pack(anchor="w", pady=3)
        make_check(
            b, "从「开始连点」按钮启动时先倒计时（跟随鼠标 2 秒 / 固定坐标 1 秒）", self.click_ui_countdown_var
        ).pack(anchor="w", pady=3)

        window = Card(grid, "窗口与数据", "配置保存在程序目录，不写注册表")
        window.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 10))
        b2 = window.body
        make_check(b2, "窗口置顶", self.topmost_var).pack(anchor="w", pady=3)
        tk.Label(
            b2,
            text="数据位置：%s" % BASE_DIR,
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["tiny"],
            anchor="w",
            wraplength=int(390 * ui_scale(self)),
        ).pack(fill="x", pady=(8, 7))
        row = tk.Frame(b2, bg=CARD_BG)
        row.pack(fill="x")
        FlatButton(row, "打开程序目录", self.open_base_dir, kind="ghost", padx=11, pady=5, font=FONTS["small"]).pack(
            side="left"
        )
        FlatButton(row, "打开宏目录", self.open_macro_dir, kind="ghost", padx=11, pady=5, font=FONTS["small"]).pack(
            side="left", padx=(6, 0)
        )
        FlatButton(
            b2, "恢复默认设置", self.reset_settings, kind="soft_danger", padx=11, pady=5, font=FONTS["small"]
        ).pack(anchor="w", pady=(10, 0))

        about = Card(grid, "关于 / 安全提示")
        about.grid(row=1, column=0, columnspan=2, sticky="nsew")
        lines = (
            "本工具通过 pynput 调用 Windows 的模拟输入和全局键鼠钩子，不联网、不写注册表。",
            "录制内容、宏和设置都保存在本目录（macros/ 与 config.json），把整个文件夹拷走就能带走全部数据。",
            "对以管理员身份运行的窗口发送按键/点击时会无效；如有需要，请右键本工具选择「以管理员身份运行」。",
            "部分游戏或安全软件会拦截模拟输入，这是对方程序的保护机制，与本工具无关。",
            "任何时候按 F9 都可以立即停止连点、录制和回放；停止时会自动松开按住的键和鼠标。",
        )
        for text in lines:
            tk.Label(
                about.body,
                text="· " + text,
                bg=CARD_BG,
                fg=MUTED,
                font=FONTS["small"],
                justify="left",
                anchor="w",
                wraplength=int(900 * ui_scale(self)),
            ).pack(fill="x", pady=2)

    # -------------------------------------------------------------- 连点操作
    def toggle_clicker_from_ui(self):
        self.toggle_clicker(from_ui=True)

    def toggle_clicker(self, from_ui=False):
        if self._toast is not None:
            if self._countdown_kind == "click":
                self.cancel_countdown()
            return
        if self.clicker is not None:
            self.stop_clicker()
            return
        if self.recorder is not None:
            self.set_status("正在录制，请先按 F7 停止录制。")
            return
        if self.player is not None:
            self.set_status("正在回放宏，请先按 F9 停止。")
            return
        if self._modal_depth:
            return
        if not self._validate_click_settings():
            return
        settings = self._collect_settings()
        if from_ui and settings.get("click_ui_countdown", True):
            self._click_minimized_by_us = False
            if self.state() != "iconic":
                try:
                    self.iconify()
                    self._click_minimized_by_us = True
                except Exception:
                    pass
            if settings["click_position"] == "fixed":
                seconds = 1
                hint = "固定坐标 (%s, %s)，1 秒后开始 · F9 取消" % (settings["fixed_x"], settings["fixed_y"])
            else:
                seconds = 2
                hint = "把鼠标移到目标位置，2 秒后开始 · F9 取消"
            self._begin_toast(
                seconds,
                "即将开始连点",
                hint,
                self._launch_clicker,
                "click",
                self._restore_after_click,
            )
        else:
            self._launch_clicker()

    def _validate_click_settings(self):
        interval = self._validate_int_entry(self.interval_var, "点击间隔", 1, 3600000)
        if interval is None:
            return False
        if self.click_repeat_var.get() == "count":
            if self._validate_int_entry(self.click_count_var, "重复次数", 1, 10000000) is None:
                return False
        if self.click_position_var.get() == "fixed":
            if self._validate_int_entry(self.fixed_x_var, "固定坐标 X", -32768, 32767) is None:
                return False
            if self._validate_int_entry(self.fixed_y_var, "固定坐标 Y", -32768, 32767) is None:
                return False
        return True

    def _validate_int_entry(self, var, label, lo, hi):
        try:
            value = int(float(str(var.get()).strip()))
        except (TypeError, ValueError):
            messagebox.showwarning("设置不正确", "「%s」需要填写整数。" % label, parent=self)
            return None
        if value < lo or value > hi:
            messagebox.showwarning(
                "设置不正确", "「%s」需要在 %s 到 %s 之间。" % (label, lo, hi), parent=self
            )
            return None
        var.set(str(value))
        return value

    def _launch_clicker(self):
        settings = self._collect_settings()
        self.click_count_label.configure(text="0")
        clicker = Clicker(self.hub, settings, None, None)
        clicker.on_progress = lambda n: self.post(lambda: self._on_clicker_progress(clicker, n))
        clicker.on_done = lambda n, stopped: self.post(
            lambda: self._on_clicker_done(clicker, n, stopped)
        )
        self.clicker = clicker
        clicker.start()
        self.set_status(
            "连点中：%s · %s ms · %s"
            % (BTN_LABELS.get(settings["click_button"], "左键"), settings["click_interval_ms"],
               "无限" if settings["click_repeat"] == "infinite" else "%d 次" % settings["click_count"])
        )
        self.refresh_states()

    def _on_clicker_progress(self, clicker, count):
        if self.clicker is clicker:
            self.click_count_label.configure(text=format(count, ","))

    def _on_clicker_done(self, clicker, count, stopped):
        if self.clicker is not clicker:
            return
        self.clicker = None
        self.click_count_label.configure(text=format(count, ","))
        self.refresh_states()
        self._restore_after_click()
        if stopped:
            self.set_status("已停止连点，共点击 %s 次。" % format(count, ","))
        else:
            self.set_status("连点完成，共点击 %s 次。" % format(count, ","))

    def stop_clicker(self):
        clicker = self.clicker
        if clicker is None:
            return
        self.clicker = None
        clicker.stop()
        clicker.join(0.5)
        self.click_count_label.configure(text=format(clicker.count, ","))
        self.refresh_states()
        self._restore_after_click()
        self.set_status("已停止连点，共点击 %s 次。" % format(clicker.count, ","))

    def _restore_after_click(self):
        if self._click_minimized_by_us:
            self._click_minimized_by_us = False
            try:
                self.deiconify()
                self.lift()
            except Exception:
                pass

    def pick_coordinate(self):
        if self._toast is not None or self.recorder is not None or self.player is not None or self.clicker is not None:
            return
        self._pick_minimized_by_us = False
        if self.state() != "iconic":
            try:
                self.iconify()
                self._pick_minimized_by_us = True
            except Exception:
                pass
        self._begin_toast(
            3,
            "拾取固定坐标",
            "把鼠标移到目标位置，3 秒后自动记录 · F9 取消",
            self._capture_position,
            "pick",
            self._restore_after_pick,
        )

    def _capture_position(self):
        try:
            pos = pm.Controller().position
            x, y = int(pos[0]), int(pos[1])
            self.fixed_x_var.set(str(x))
            self.fixed_y_var.set(str(y))
            self.click_position_var.set("fixed")
            self._collect_settings()
            self.set_status("已记录固定坐标：(%d, %d)" % (x, y))
        except Exception:
            log.exception("拾取坐标失败")
            self.set_status("拾取坐标失败。")
        self._restore_after_pick()

    def _restore_after_pick(self):
        if self._pick_minimized_by_us:
            self._pick_minimized_by_us = False
            try:
                self.deiconify()
                self.lift()
            except Exception:
                pass

    def use_current_position(self):
        try:
            pos = pm.Controller().position
            self.fixed_x_var.set(str(int(pos[0])))
            self.fixed_y_var.set(str(int(pos[1])))
            self.click_position_var.set("fixed")
            self.set_status("已填入当前坐标：(%d, %d)" % (int(pos[0]), int(pos[1])))
        except Exception:
            log.exception("读取鼠标位置失败")

    # -------------------------------------------------------------- 录制操作
    def toggle_recording(self, from_ui=False):
        if self._toast is not None:
            if self._countdown_kind == "record":
                self.cancel_countdown()
            return
        if self.recorder is not None:
            self.stop_recording(from_ui=from_ui)
            return
        if self.player is not None:
            self.set_status("正在回放宏，请先按 F9 停止。")
            return
        if self._modal_depth:
            return
        if self.clicker is not None:
            self.stop_clicker()
        self.start_recording(from_ui=from_ui)

    def _validate_record_settings(self):
        if not (self.rec_moves_var.get() or self.rec_clicks_var.get() or self.rec_keys_var.get()):
            messagebox.showwarning(
                "录制设置", "至少要勾选一项要记录的内容（鼠标轨迹 / 点击 / 键盘）。", parent=self
            )
            return False
        if self._validate_int_entry(self.rec_sample_var, "轨迹采样", 1, 100) is None:
            return False
        if self._validate_int_entry(self.rec_countdown_var, "开始倒计时", 0, 10) is None:
            return False
        return True

    def start_recording(self, append_id=None, from_ui=False):
        if self.recorder is not None or self._toast is not None:
            return
        if not self._validate_record_settings():
            return
        settings = self._collect_settings()
        if append_id and append_id in self.macros:
            self._rec_append_id = append_id
        else:
            self._rec_append_id = None
        self._rec_started_from_ui = from_ui
        self._rec_restore_on_stop = from_ui or self._is_foreground_window()
        self._rec_return_tab = "macro" if self._rec_append_id else None
        self._update_rec_append_label()
        self._rec_minimized_by_us = False
        if settings.get("record_minimize", True) and self.state() != "iconic":
            try:
                self.iconify()
                self._rec_minimized_by_us = True
            except Exception:
                pass
        countdown = int(settings["record_countdown"])
        if countdown > 0:
            self._begin_toast(
                countdown,
                "准备录制",
                "倒计时结束后开始记录 · F9 取消",
                self._begin_recording,
                "record",
                self._recording_countdown_cancelled,
            )
        else:
            self._begin_recording()

    def _recording_countdown_cancelled(self):
        self._rec_append_id = None
        self._rec_return_tab = None
        self._update_rec_append_label()
        self._restore_after_recording()
        self.set_status("已取消录制。")

    def _begin_recording(self):
        if self.recorder is not None:
            return
        s = self._collect_settings()
        rec = Recorder(
            sample_px=s["record_sample_px"],
            record_moves=s["record_moves"],
            record_clicks=s["record_clicks"],
            record_keys=s["record_keys"],
            on_limit=lambda: self.post(lambda: self.stop_recording(limit_hit=True)),
        )
        rec.start()
        try:
            listener = pm.Listener(
                on_move=lambda x, y: rec.record_move(x, y),
                on_click=lambda x, y, button, pressed: rec.record_button(x, y, button, pressed),
                on_scroll=lambda x, y, dx, dy: rec.record_scroll(x, y, dx, dy),
            )
            listener.daemon = True
            listener.start()
        except Exception:
            log.exception("启动鼠标监听失败")
            rec.stop()
            self._restore_after_recording()
            messagebox.showerror(
                "无法开始录制",
                "启动鼠标监听失败。请检查安全软件是否拦截了本工具，或尝试以管理员身份运行。",
                parent=self,
            )
            self.refresh_states()
            return
        self.recorder = rec
        self.hub.recorder = rec
        self.mouse_listener = listener
        self._last_live_count = -1
        self.rec_count_label.configure(text="0 个事件")
        self.rec_time_label.configure(text="0.0 秒")
        self.set_status("录制中… 完成操作后按 F7 或 F9 停止。")
        self.refresh_states()

    def stop_recording(self, from_ui=False, save=True, limit_hit=False):
        rec = self.recorder
        if rec is None:
            return
        self.recorder = None
        self.hub.recorder = None
        events, duration = rec.stop()
        listener = self.mouse_listener
        self.mouse_listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        self._restore_after_recording()
        self._last_live_count = -1
        self.rec_count_label.configure(text="%s 个事件" % format(len(events), ","))
        self.rec_time_label.configure(text=format_duration(duration))

        append_id = self._rec_append_id
        return_tab = self._rec_return_tab
        self._rec_append_id = None
        self._rec_return_tab = None
        self._update_rec_append_label()

        if save:
            self._clean_recorded_events(events, from_ui)
        if not save:
            self.refresh_states()
            self.set_status("已退出录制（本次内容未保存）。")
            return
        if not events:
            self.refresh_states()
            self.set_status("没有录制到任何操作，本次未保存。")
            return

        now = datetime.datetime.now()
        target = self.macros.get(append_id) if append_id else None
        if target is not None:
            offset = float(target.get("duration") or 0.0) + 500.0
            copied = []
            for ev in events:
                item = dict(ev)
                item["t"] = round(float(item["t"]) + offset, 1)
                copied.append(item)
            target["events"].extend(copied)
            target["events"].sort(key=lambda e: e["t"])
            target["duration"] = target["events"][-1]["t"] if target["events"] else 0.0
            target["created_ts"] = time.time()
            try:
                save_macro_file(target)
            except Exception as exc:
                log.exception("追加录制保存失败")
                messagebox.showerror("保存失败", "写入宏文件失败：\n%s" % exc, parent=self)
                self.refresh_states()
                return
            self.selected_id = target["id"]
            saved_name = target["name"]
            extra = "（追加到已有宏）"
        else:
            base_name = "录制 " + now.strftime("%m-%d %H:%M")
            name = unique_macro_name({m.get("name") for m in self.macros.values()}, base_name)
            macro = {
                "version": 1,
                "id": uuid.uuid4().hex[:12],
                "name": name,
                "created": now.strftime("%Y-%m-%d %H:%M:%S"),
                "created_ts": now.timestamp(),
                "duration": round(events[-1]["t"], 1),
                "events": events,
                "source": "record",
            }
            try:
                save_macro_file(macro)
            except Exception as exc:
                log.exception("保存录制失败")
                messagebox.showerror("保存失败", "写入宏文件失败：\n%s" % exc, parent=self)
                self.refresh_states()
                return
            self.macros[macro["id"]] = macro
            self.selected_id = macro["id"]
            saved_name = name
            extra = ""

        self._collect_settings()
        self.schedule_save()
        self.refresh_macro_list()
        self.refresh_macro_detail()
        self.refresh_latest()
        self.refresh_states()
        if limit_hit:
            self.set_status(
                "已达到 15 万条事件上限，自动停止并保存为「%s」%s。" % (saved_name, extra), timeout=12000
            )
        else:
            self.set_status(
                "录制完成，已保存为「%s」%s · %s 个事件 · %s"
                % (saved_name, extra, format(len(events), ","), format_duration(events[-1]["t"])),
                timeout=12000,
            )
        if return_tab:
            self.switch_tab(return_tab)

    def _clean_recorded_events(self, events, from_ui):
        if not events:
            return
        if from_ui and self.state() != "iconic":
            try:
                x0, y0 = self.winfo_rootx(), self.winfo_rooty()
                x1, y1 = x0 + self.winfo_width(), y0 + self.winfo_height()
                end = events[-1]["t"]
                for i in range(len(events) - 1, -1, -1):
                    ev = events[i]
                    if ev["t"] < end - 600:
                        break
                    if ev.get("type") == "button" and ev.get("pressed"):
                        if x0 <= ev.get("x", -99999) <= x1 and y0 <= ev.get("y", -99999) <= y1:
                            del events[i:]
                        break
            except Exception:
                pass
        # 去掉结尾用于停止录制的组合键残留（尤其是 Ctrl / Shift 等修饰键）
        end = events[-1]["t"]
        while events:
            ev = events[-1]
            if ev["t"] < end - 600:
                break
            if ev.get("type") != "key":
                break
            if ev.get("key") in MODIFIERS or ev.get("key") == STOP_HOTKEY:
                events.pop()
            else:
                break

    def _update_rec_append_label(self):
        if not hasattr(self, "rec_append_label"):
            return
        target = self.macros.get(self._rec_append_id) if self._rec_append_id else None
        if target is not None:
            self.rec_append_label.configure(text="追加录制到「%s」" % target.get("name"))
        else:
            self.rec_append_label.configure(text="")

    def _restore_after_recording(self):
        if self._rec_minimized_by_us:
            self._rec_minimized_by_us = False
            if getattr(self, "_rec_restore_on_stop", False):
                try:
                    self.deiconify()
                    self.lift()
                    if getattr(self, "_rec_started_from_ui", False):
                        self.focus_force()
                except Exception:
                    pass

    # -------------------------------------------------------------- 回放操作
    def play_selected(self, from_ui=False):
        if self.player is not None:
            return
        if self.recorder is not None or self._toast is not None:
            self.set_status("正在录制或倒计时，无法回放。")
            return
        if self._modal_depth:
            return
        macro = self.macros.get(self.selected_id)
        if macro is None or not macro.get("events"):
            self.set_status("没有可回放的宏，请先录制一段操作。")
            return
        if self.clicker is not None:
            self.stop_clicker()
        s = self._collect_settings()
        speed = self._parse_speed(self.play_speed_var.get(), 1.0)
        loops = self._read_int(self.play_loops_var, 1, 1, 100000)
        if self.play_infinite_var.get():
            loops = 1
        player = Player(
            self.hub,
            macro,
            speed=speed,
            loops=loops,
            infinite=bool(self.play_infinite_var.get()),
            lead_ms=s["play_lead_ms"],
            gap_ms=s["play_gap_ms"],
        )
        player.on_progress = lambda idx, total, loop, t: self.post(
            lambda: self._on_play_progress(player, idx, total, loop, t)
        )
        player.on_done = lambda loop, stopped, stopflag: self.post(
            lambda: self._on_player_done(player, loop, stopped)
        )
        self.player = player
        self._play_minimized_by_us = False
        if s.get("play_minimize") and self.state() != "iconic" and self._is_foreground_window():
            try:
                self.iconify()
                self._play_minimized_by_us = True
            except Exception:
                pass
        self.play_progress.configure(value=0)
        self.play_progress_label.configure(text="准备回放…")
        self.refresh_states()
        player.start()
        self.set_status(
            "正在回放「%s」 · %s 倍速 · %s · F9 停止"
            % (macro.get("name"), ("%.2f" % speed).rstrip("0").rstrip("."), "无限循环" if self.play_infinite_var.get() else "%d 轮" % loops)
        )

    def _on_play_progress(self, player, index, total, loop, t):
        if self.player is not player:
            return
        macro = player.macro
        duration = max(1.0, float(macro.get("duration") or 0.0))
        percent = max(0.0, min(100.0, float(t) / duration * 100.0))
        self.play_progress.configure(value=percent)
        self.play_progress_label.configure(text="第 %d 轮 · %d/%d 事件" % (loop, index, total))

    def _on_player_done(self, player, loops, stopped):
        if self.player is not player:
            return
        self.player = None
        if not stopped:
            self.play_progress.configure(value=100)
            self.play_progress_label.configure(text="播放完成 · %d 轮" % loops)
        else:
            self.play_progress_label.configure(text="已停止")
        self.refresh_states()
        self._restore_after_play()
        if stopped:
            self.set_status("已停止回放。")
        else:
            self.set_status("宏回放完成，共 %d 轮。" % loops)

    def stop_playback(self):
        player = self.player
        if player is None:
            return
        self.player = None
        player.stop()
        player.join(0.8)
        self.play_progress_label.configure(text="已停止")
        self.refresh_states()
        self._restore_after_play()
        self.set_status("已停止回放。")

    def _restore_after_play(self):
        if self._play_minimized_by_us:
            self._play_minimized_by_us = False
            try:
                self.deiconify()
                self.lift()
            except Exception:
                pass

    # -------------------------------------------------------------- 全局控制
    def _begin_toast(self, seconds, title, hint, on_done, kind, on_cancel=None):
        def done():
            self._toast = None
            self._countdown_kind = None
            try:
                on_done()
            finally:
                self.refresh_states()

        def cancel():
            self._toast = None
            self._countdown_kind = None
            if on_cancel is not None:
                on_cancel()
            self.refresh_states()

        self._countdown_kind = kind
        self._toast = CountdownToast(self, seconds, title, hint, done, cancel)
        self.refresh_states()

    def cancel_countdown(self):
        toast = self._toast
        if toast is not None:
            toast.cancel()

    def _on_global_action(self, action):
        if not self._ready:
            return
        if action == "stop":
            self.stop_all()
            return
        if self._modal_depth:
            return
        if self._toast is not None:
            if (action == "click" and self._countdown_kind == "click") or (
                action == "record" and self._countdown_kind == "record"
            ):
                self.cancel_countdown()
            return
        if action == "click":
            self.toggle_clicker(from_ui=False)
        elif action == "record":
            self.toggle_recording(from_ui=False)
        elif action == "play":
            if self.player is not None:
                self.stop_playback()
            else:
                self.play_selected(from_ui=False)

    def stop_all(self):
        active = self._toast is not None or self.recorder is not None or self.clicker is not None or self.player is not None
        if self._toast is not None:
            self.cancel_countdown()
        if self.recorder is not None:
            self.stop_recording(from_ui=False)
        if self.clicker is not None:
            self.stop_clicker()
        if self.player is not None:
            self.stop_playback()
        self.refresh_states()
        if not active:
            self.set_status("当前没有正在运行的操作。")

    # -------------------------------------------------------------- 快捷键
    def edit_hotkey(self, action):
        if self._modal_depth:
            return
        for act, label, conf_key, default in self.HOTKEY_ACTIONS:
            if act != action:
                continue
            current = self._norm_hotkey(self.cfg["settings"].get(conf_key), default)

            def save(combo, conf_key=conf_key, label=label):
                return self._apply_hotkey(conf_key, label, combo)

            HotkeyDialog(self, label, current, default, save)
            return

    def _apply_hotkey(self, conf_key, label, combo):
        if "+" not in combo and not re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", combo):
            return "为避免打字时误触发，单键快捷键只支持 F1–F24；其它按键请配合 Ctrl / Alt / Shift / Win 使用。"
        used = {STOP_HOTKEY}
        for act, _label, key, default in self.HOTKEY_ACTIONS:
            if key != conf_key:
                used.add(self._norm_hotkey(self.cfg["settings"].get(key), default))
        if combo in used:
            return "快捷键 %s 已经被其它功能占用（或与紧急停止 F9 冲突）。" % pretty_combo(combo)
        self.cfg["settings"][conf_key] = combo
        self.hub.set_hotkeys(self._hotkey_map())
        self._update_hotkey_labels()
        self.refresh_states()
        self.schedule_save()
        self.set_status("%s 的快捷键已改为 %s。" % (label, pretty_combo(combo)))
        return None

    # -------------------------------------------------------------- 宏列表
    def _sorted_macros(self):
        return sorted(
            self.macros.values(),
            key=lambda m: (m.get("created_ts") or 0, m.get("created") or ""),
            reverse=True,
        )

    def refresh_macro_list(self):
        if not hasattr(self, "macro_tree"):
            return
        self._selecting = True
        try:
            for iid in self.macro_tree.get_children():
                self.macro_tree.delete(iid)
            macros = self._sorted_macros()
            for macro in macros:
                count = len(macro.get("events") or [])
                self.macro_tree.insert(
                    "",
                    "end",
                    iid=macro["id"],
                    values=(
                        macro.get("name") or "未命名宏",
                        format(count, ","),
                        format_duration(macro.get("duration", 0), short=True),
                    ),
                )
            self.macro_count_label.configure(text="共 %d 个宏" % len(macros))
            if self.selected_id in self.macros:
                self.macro_tree.selection_set(self.selected_id)
                self.macro_tree.see(self.selected_id)
            elif macros:
                self.selected_id = macros[0]["id"]
                self.macro_tree.selection_set(self.selected_id)
                self.macro_tree.see(self.selected_id)
            else:
                self.selected_id = ""
        finally:
            self._selecting = False

    def _on_macro_select(self, _event=None):
        if self._selecting:
            return
        sel = self.macro_tree.selection()
        if not sel:
            return
        mid = sel[0]
        if self.player is not None and mid != self.selected_id:
            self.macro_tree.selection_set(self.selected_id)
            self.set_status("正在回放宏，先按 F9 停止后再切换。")
            return
        if mid != self.selected_id:
            self.selected_id = mid
            self.refresh_macro_detail()
            self.refresh_states()
            self.schedule_save()

    def refresh_macro_detail(self):
        if not hasattr(self, "event_tree"):
            return
        macro = self.macros.get(self.selected_id)
        if macro is None:
            self.macro_name_label.configure(text="未选择宏")
            self.macro_meta_label.configure(text="")
            self.event_count_label.configure(text="")
            for iid in self.event_tree.get_children():
                self.event_tree.delete(iid)
            self.macro_empty.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.macro_empty.lift()
            self.play_progress.configure(value=0)
            self.play_progress_label.configure(text="未播放")
            return
        self.macro_empty.place_forget()
        events = macro.get("events") or []
        self.macro_name_label.configure(text=macro.get("name") or "未命名宏")
        self.macro_meta_label.configure(
            text="%s 个事件 · %s · %s"
            % (format(len(events), ","), format_duration(macro.get("duration", 0)), macro.get("created", ""))
        )
        for iid in self.event_tree.get_children():
            self.event_tree.delete(iid)
        limit = 800
        prev = 0.0
        for i, ev in enumerate(events[:limit]):
            gap = max(0.0, ev["t"] - prev)
            prev = ev["t"]
            self.event_tree.insert(
                "",
                "end",
                values=(
                    i + 1,
                    "%.2f" % (ev["t"] / 1000.0),
                    "%.2f" % (gap / 1000.0),
                    event_action_text(ev),
                ),
            )
        note = "共 %s 条" % format(len(events), ",")
        if len(events) > limit:
            note += " · 预览前 %d 条" % limit
        self.event_count_label.configure(text=note)
        if self.player is None:
            self.play_progress.configure(value=0)
            self.play_progress_label.configure(text="未播放")

    def refresh_latest(self):
        if not hasattr(self, "latest_name"):
            return
        macros = self._sorted_macros()
        if not macros:
            self._latest_id = ""
            self.latest_name.configure(text="还没有录制")
            self.latest_meta.configure(text="录制完成后会显示在这里")
            self.latest_view_btn.set_enabled(False)
            self.latest_play_btn.set_enabled(False)
            return
        macro = macros[0]
        self._latest_id = macro["id"]
        self.latest_name.configure(text=macro.get("name") or "未命名宏")
        self.latest_meta.configure(
            text="%s 个事件 · %s"
            % (format(len(macro.get("events") or []), ","), format_duration(macro.get("duration", 0)))
        )
        self.latest_view_btn.set_enabled(True)
        self.latest_play_btn.set_enabled(bool(macro.get("events")))

    # -------------------------------------------------------------- 初始状态
    def _choose_initial_macro(self):
        selected = self.cfg["settings"].get("selected_macro") or ""
        if selected in self.macros:
            self.selected_id = selected
            return
        if self.macros:
            newest = max(self.macros.values(), key=lambda m: m.get("created_ts") or 0)
            self.selected_id = newest["id"]
        else:
            self.selected_id = ""

    def refresh_all(self):
        self._update_hotkey_labels()
        self._update_click_summary()
        self._sync_fixed_controls()
        self._sync_repeat_controls()
        self._sync_loop_controls()
        self.refresh_macro_list()
        self.refresh_macro_detail()
        self.refresh_latest()
        self.refresh_states()

    def _hotkey_map(self):
        s = self.cfg["settings"]
        return {
            self._norm_hotkey(s.get("hotkey_click"), "f6"): "click",
            self._norm_hotkey(s.get("hotkey_record"), "f7"): "record",
            self._norm_hotkey(s.get("hotkey_play"), "f8"): "play",
            STOP_HOTKEY: "stop",
        }

    def _norm_hotkey(self, value, default):
        return normalize_combo(value, default)

    def _update_hotkey_labels(self):
        if not getattr(self, "hotkey_value_labels", None):
            return
        s = self.cfg["settings"]
        for action, _label, conf_key, default in self.HOTKEY_ACTIONS:
            lbl = self.hotkey_value_labels.get(action)
            if lbl is not None:
                lbl.configure(text=pretty_combo(self._norm_hotkey(s.get(conf_key), default)))
        # 记录页按钮上的提示
        try:
            rec_key = pretty_combo(self._norm_hotkey(s.get("hotkey_record"), "f7"))
            self.rec_hint_label.configure(text="按 %s 或点右侧按钮开始录制" % rec_key)
        except Exception:
            pass

    # -------------------------------------------------------------- 状态刷新
    def _states(self):
        return {
            "countdown": self._toast is not None,
            "recording": self.recorder is not None,
            "playing": self.player is not None,
            "clicking": self.clicker is not None,
        }

    def refresh_states(self):
        if not self._ready:
            return
        st = self._states()
        if st["countdown"]:
            state_text, state_bg, state_fg = "准备中", AMBER_BG, AMBER
        elif st["recording"]:
            state_text, state_bg, state_fg = "录制中", RED_BG, RED_FG
        elif st["playing"]:
            state_text, state_bg, state_fg = "回放中", CHIP_BG, CHIP_FG
        elif st["clicking"]:
            state_text, state_bg, state_fg = "连点中", GREEN_BG, GREEN
        else:
            state_text, state_bg, state_fg = "空闲", STATUS_BG, MUTED
        self.state_pill.configure(text="● " + state_text, bg=state_bg, fg=state_fg)
        self.stop_all_btn.set_enabled(True)

        click_key = pretty_combo(self._norm_hotkey(self.cfg["settings"].get("hotkey_click"), "f6"))
        if st["clicking"]:
            self.click_toggle_btn.set_text("■ 停止连点   " + click_key)
            self.click_toggle_btn.set_kind("danger")
        else:
            self.click_toggle_btn.set_text("▶ 开始连点   " + click_key)
            self.click_toggle_btn.set_kind("primary")
        self.click_toggle_btn.set_enabled(not st["recording"] and not st["playing"] and not st["countdown"])

        rec_key = pretty_combo(self._norm_hotkey(self.cfg["settings"].get("hotkey_record"), "f7"))
        if st["recording"]:
            self.rec_btn.set_text("■ 停止录制   " + rec_key)
            self.rec_btn.set_kind("ghost")
        elif st["countdown"] and self._countdown_kind == "record":
            self.rec_btn.set_text("取消录制")
            self.rec_btn.set_kind("ghost")
        else:
            self.rec_btn.set_text("● 开始录制   " + rec_key)
            self.rec_btn.set_kind("danger")
        self.rec_btn.set_enabled(
            not st["playing"] and (not st["countdown"] or self._countdown_kind == "record")
        )

        self.rec_dot.configure(fg=RED if st["recording"] else (AMBER if st["countdown"] and self._countdown_kind == "record" else MUTED))
        if st["recording"]:
            self.rec_state_label.configure(text="正在录制")
            self.rec_hint_label.configure(text="按 %s 或 F9 停止并保存" % rec_key)
        elif st["countdown"] and self._countdown_kind == "record":
            self.rec_state_label.configure(text="倒计时中")
            self.rec_hint_label.configure(text="准备切换到目标窗口，F9 可取消")
        else:
            self.rec_state_label.configure(text="未录制")
            self.rec_hint_label.configure(text="按 %s 或点右侧按钮开始录制" % rec_key)

        self.click_state_label.configure(text=state_text)
        self.hero_dot.configure(fg=state_fg)

        has_macro = bool(self.selected_id and self.selected_id in self.macros)
        macro = self.macros.get(self.selected_id) if has_macro else None
        has_events = bool(macro and macro.get("events"))
        self.play_btn.set_enabled(
            has_events and not st["recording"] and not st["countdown"] and not st["playing"]
        )
        self.play_stop_btn.set_enabled(st["playing"])
        self.play_btn.set_text(
            "▶ 播放   " + pretty_combo(self._norm_hotkey(self.cfg["settings"].get("hotkey_play"), "f8"))
        )
        edit_enabled = has_macro and not st["playing"] and not st["recording"] and not st["countdown"]
        for btn in (
            self.edit_events_btn,
            self.merge_btn,
            self.export_script_btn,
            self.export_json_btn,
            self.macro_rename_btn,
            self.macro_delete_btn,
        ):
            btn.set_enabled(edit_enabled)
        self.append_btn.set_enabled(edit_enabled and not st["countdown"])
        self.macro_import_btn.set_enabled(not st["playing"] and not st["recording"] and not st["countdown"])
        latest = self.macros.get(getattr(self, "_latest_id", ""))
        latest_events = bool(latest and latest.get("events"))
        self.latest_play_btn.set_enabled(
            latest_events and not st["recording"] and not st["playing"] and not st["countdown"]
        )
        self.latest_view_btn.set_enabled(latest is not None)

    # -------------------------------------------------------------- 宏操作
    def _is_foreground_window(self):
        if os.name != "nt":
            return True
        try:
            root = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2)  # GA_ROOT
            return bool(root) and ctypes.windll.user32.GetForegroundWindow() == root
        except Exception:
            return False

    def play_latest(self):
        mid = getattr(self, "_latest_id", "")
        if mid not in self.macros:
            self.set_status("还没有可回放的宏。")
            return
        self.selected_id = mid
        self.refresh_macro_list()
        self.refresh_macro_detail()
        self.refresh_states()
        self.switch_tab("macro")
        self.play_selected(from_ui=True)

    def view_latest(self):
        mid = getattr(self, "_latest_id", "")
        if mid in self.macros:
            self.selected_id = mid
            self.refresh_macro_list()
            self.refresh_macro_detail()
            self.refresh_states()
            self.schedule_save()
        self.switch_tab("macro")

    def rename_macro(self):
        macro = self.macros.get(self.selected_id)
        if macro is None:
            return

        def done(new_name):
            new_name = (new_name or "").strip()
            if not new_name:
                return "名称不能为空。"
            if len(new_name) > 80:
                return "名称最多 80 个字符。"
            others = {m.get("name") for m in self.macros.values() if m["id"] != macro["id"]}
            if new_name in others:
                return "已经有同名宏，请换一个名称。"
            macro["name"] = new_name
            try:
                save_macro_file(macro)
            except Exception as exc:
                log.exception("重命名宏失败")
                return "保存失败：%s" % exc
            self.refresh_macro_list()
            self.refresh_macro_detail()
            self.refresh_latest()
            self.set_status("宏已重命名为「%s」。" % new_name)
            return None

        InputDialog(self, "重命名宏", "宏名称", macro.get("name") or "", done)

    def delete_macro(self):
        macro = self.macros.get(self.selected_id)
        if macro is None:
            return
        if self.player is not None:
            self.stop_playback()
        if self.recorder is not None:
            self.set_status("正在录制，无法删除宏。")
            return
        if not messagebox.askyesno(
            "删除宏",
            "确定删除「%s」吗？\n\n共 %s 个事件，删除后无法恢复。"
            % (macro.get("name"), format(len(macro.get("events") or []), ",")),
            parent=self,
        ):
            return
        delete_macro_file(macro["id"])
        self.macros.pop(macro["id"], None)
        remaining = self._sorted_macros()
        self.selected_id = remaining[0]["id"] if remaining else ""
        self.refresh_macro_list()
        self.refresh_macro_detail()
        self.refresh_latest()
        self.refresh_states()
        self.schedule_save()
        self.set_status("已删除宏「%s」。" % macro.get("name"))

    def import_macro(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="导入宏",
            filetypes=(("宏 JSON 文件", "*.json"), ("所有文件", "*.*")),
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("导入失败", "无法读取这个文件：\n%s" % exc, parent=self)
            return
        macro = sanitize_macro(data)
        if macro is None:
            messagebox.showerror("导入失败", "文件内容不是有效的宏。", parent=self)
            return
        if not macro.get("events"):
            if not messagebox.askyesno(
                "宏是空的", "这个宏没有任何事件，导入后无法回放。仍然导入吗？", parent=self
            ):
                return
        if macro["id"] in self.macros:
            macro["id"] = uuid.uuid4().hex[:12]
        macro["name"] = unique_macro_name({m.get("name") for m in self.macros.values()}, macro["name"])
        try:
            save_macro_file(macro)
        except Exception as exc:
            messagebox.showerror("导入失败", "保存宏文件失败：\n%s" % exc, parent=self)
            return
        self.macros[macro["id"]] = macro
        self.selected_id = macro["id"]
        self.refresh_macro_list()
        self.refresh_macro_detail()
        self.refresh_latest()
        self.refresh_states()
        self.switch_tab("macro")
        self.schedule_save()
        self.set_status("已导入宏「%s」。" % macro["name"])

    def merge_macro(self):
        target = self.macros.get(self.selected_id)
        if target is None:
            return
        others = [m for m in self._sorted_macros() if m["id"] != target["id"] and m.get("events")]
        if not others:
            messagebox.showinfo("没有可合并的宏", "至少需要另外一个包含事件的宏。", parent=self)
            return

        def done(source_id, gap_ms):
            source = self.macros.get(source_id)
            if source is None:
                return
            offset = (float(target.get("duration") or 0.0) + gap_ms) if target.get("events") else 0.0
            copied = []
            for ev in source.get("events") or []:
                item = dict(ev)
                item["t"] = round(float(item["t"]) + offset, 1)
                copied.append(item)
            target.setdefault("events", []).extend(copied)
            target["events"].sort(key=lambda e: e["t"])
            target["duration"] = target["events"][-1]["t"] if target["events"] else 0.0
            target["created_ts"] = time.time()
            try:
                save_macro_file(target)
            except Exception as exc:
                messagebox.showerror("合并失败", "保存宏文件失败：\n%s" % exc, parent=self)
                return
            self.refresh_macro_list()
            self.refresh_macro_detail()
            self.refresh_latest()
            self.refresh_states()
            self.set_status(
                "已把「%s」合并到「%s」，现在共 %s 个事件。"
                % (source.get("name"), target.get("name"), format(len(target["events"]), ","))
            )

        MergeDialog(self, others, done)

    def append_record(self):
        macro = self.macros.get(self.selected_id)
        if macro is None:
            self.set_status("请先选择一个宏。")
            return
        if self.player is not None:
            self.stop_playback()
        if self.recorder is not None or self._toast is not None:
            return
        if self.clicker is not None:
            self.stop_clicker()
        self.switch_tab("record")
        self.start_recording(append_id=macro["id"], from_ui=True)

    def edit_macro_events(self):
        macro = self.macros.get(self.selected_id)
        if macro is None:
            return
        if self.player is not None or self.recorder is not None:
            return
        MacroEditor(self, macro)

    def save_edited_macro(self, macro_id, events):
        macro = self.macros.get(macro_id)
        if macro is None:
            return False
        clean = []
        for ev in events:
            item = sanitize_event(ev)
            if item is not None:
                clean.append(item)
        clean.sort(key=lambda e: e["t"])
        macro["events"] = clean
        macro["duration"] = round(clean[-1]["t"], 1) if clean else 0.0
        try:
            save_macro_file(macro)
        except Exception as exc:
            log.exception("保存编辑后的宏失败")
            messagebox.showerror("保存失败", "写入宏文件失败：\n%s" % exc, parent=self)
            return False
        self.refresh_macro_list()
        self.refresh_macro_detail()
        self.refresh_latest()
        self.refresh_states()
        self.set_status("宏「%s」已更新，共 %s 个事件。" % (macro.get("name"), format(len(clean), ",")))
        return True

    def export_json(self):
        macro = self.macros.get(self.selected_id)
        if macro is None:
            return
        initialdir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(initialdir):
            initialdir = BASE_DIR
        path = filedialog.asksaveasfilename(
            parent=self,
            title="导出宏 JSON",
            initialdir=initialdir,
            initialfile=safe_filename(macro.get("name")) + ".json",
            defaultextension=".json",
            filetypes=(("JSON 文件", "*.json"), ("所有文件", "*.*")),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(macro, f, ensure_ascii=False, indent=2)
                f.write("\n")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            return
        self.set_status("已导出宏 JSON：%s" % path)

    def export_script(self):
        macro = self.macros.get(self.selected_id)
        if macro is None:
            return
        if not macro.get("events"):
            messagebox.showinfo("宏是空的", "这个宏没有事件，无法生成脚本。", parent=self)
            return
        initialdir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(initialdir):
            initialdir = BASE_DIR
        path = filedialog.asksaveasfilename(
            parent=self,
            title="导出 Python 回放脚本",
            initialdir=initialdir,
            initialfile=safe_filename(macro.get("name")) + ".py",
            defaultextension=".py",
            filetypes=(("Python 脚本", "*.py"), ("所有文件", "*.*")),
        )
        if not path:
            return
        try:
            script = build_python_script(macro)
            with open(path, "w", encoding="utf-8") as f:
                f.write(script)
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            return
        self.set_status("已生成独立回放脚本：%s（运行前需 pip install pynput）" % path)

    # -------------------------------------------------------------- 设置 / 退出
    def enter_modal(self):
        self._modal_depth += 1

    def exit_modal(self):
        self._modal_depth = max(0, self._modal_depth - 1)

    def reset_settings(self):
        if self.recorder is not None or self.player is not None or self._toast is not None:
            self.set_status("请先停止正在进行的录制 / 回放。")
            return
        if not messagebox.askyesno(
            "恢复默认设置",
            "确定把所有设置恢复为默认值吗？\n\n宏文件不会被删除。",
            parent=self,
        ):
            return
        selected = self.selected_id
        self.cfg = default_config()
        self.cfg["settings"]["selected_macro"] = selected
        self._load_settings_into_ui()
        self._apply_topmost()
        self.hub.set_hotkeys(self._hotkey_map())
        self.refresh_states()
        self.schedule_save()
        self.set_status("已恢复默认设置。")

    def open_base_dir(self):
        try:
            os.startfile(BASE_DIR)
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc), parent=self)

    def open_macro_dir(self):
        try:
            os.makedirs(MACROS_DIR, exist_ok=True)
            os.startfile(MACROS_DIR)
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc), parent=self)

    def report_callback_exception(self, exc, val, tb):
        log.error("界面回调异常", exc_info=(exc, val, tb))
        try:
            messagebox.showerror(
                "程序出错了",
                "发生了一个错误：\n%s\n\n详细信息已写入 logs\\error.log。" % val,
                parent=self,
            )
        except Exception:
            pass

    def _on_close(self):
        if self.recorder is not None:
            try:
                self.deiconify()
            except Exception:
                pass
            if not messagebox.askyesno(
                "正在录制",
                "当前正在录制，退出会丢弃这一段录制内容。\n确定退出吗？",
                parent=self,
            ):
                return
            self.stop_recording(save=False)
        if self._toast is not None:
            self.cancel_countdown()
        if self.clicker is not None:
            self.stop_clicker()
        if self.player is not None:
            self.stop_playback()
        try:
            self.cfg["settings"]["window_geometry"] = self.geometry()
            self._collect_settings()
            write_json_atomic(CONFIG_PATH, self.cfg)
        except Exception:
            log.exception("退出时保存配置失败")
        try:
            self.hub.stop()
        except Exception:
            pass
        self.destroy()


# ================================================================== 对话框
class ModalDialog(tk.Toplevel):
    def __init__(self, app, title, width=460, parent=None):
        super().__init__(parent or app)
        self.app = app
        self._parent = parent or app
        self._closed = False
        self._registered = True
        self.app.enter_modal()
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        try:
            self.transient(self._parent)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._width = width
        self._body = tk.Frame(self, bg=BG)
        self._body.pack(fill="both", expand=True, padx=20, pady=18)

    def show(self):
        self.update_idletasks()
        scale = ui_scale(self)
        w = min(max(int(self._width * scale), self.winfo_reqwidth()), max(320, self.winfo_screenwidth() - 40))
        h = min(self.winfo_reqheight(), max(220, self.winfo_screenheight() - 80))
        try:
            px = self._parent.winfo_rootx()
            py = self._parent.winfo_rooty()
            pw = self._parent.winfo_width()
            ph = self._parent.winfo_height()
        except Exception:
            px = py = 0
            pw = ph = 0
        x = px + max(0, (pw - w) // 2)
        y = py + max(40, (ph - h) // 3)
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))
        self.grab_set()
        self.after(50, self.focus_force)

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except Exception:
            pass
        if self._registered:
            self._registered = False
            self.app.exit_modal()
        super().destroy()


class InputDialog(ModalDialog):
    def __init__(self, app, title, label, initial, on_ok):
        super().__init__(app, title, 460)
        self.on_ok = on_ok
        tk.Label(self._body, text=label, bg=BG, fg=MUTED, font=FONTS["small"]).pack(anchor="w")
        self.var = tk.StringVar(value=initial)
        entry = make_entry(self._body, self.var, width=40)
        entry.pack(fill="x", pady=(6, 8), ipady=5, ipadx=4)
        self.error = tk.Label(self._body, text=" ", bg=BG, fg=RED_FG, font=FONTS["small"], anchor="w")
        self.error.pack(fill="x")
        foot = tk.Frame(self._body, bg=BG)
        foot.pack(fill="x", pady=(10, 0))
        FlatButton(foot, "确定", self._ok, kind="primary", padx=18, pady=6).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=6).pack(
            side="right", padx=(0, 8)
        )
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.show()
        self.after(100, entry.focus_force)
        entry.select_range(0, "end")

    def _ok(self):
        error = self.on_ok(self.var.get())
        if error:
            self.error.configure(text=error)
            return
        self.destroy()


class HotkeyDialog(ModalDialog):
    def __init__(self, app, label, current, default, on_save):
        super().__init__(app, "修改快捷键 · " + label, 520)
        self.on_save = on_save
        self.default = default
        self.combo = current
        self._capturing = False

        tk.Label(self._body, text="当前快捷键", bg=BG, fg=MUTED, font=FONTS["small"]).pack(anchor="w")
        self.display = tk.Label(
            self._body,
            text=pretty_combo(current),
            bg=BG,
            fg=ACCENT,
            font=(FONTS["title"][0], 24, "bold"),
            anchor="w",
        )
        self.display.pack(fill="x", pady=(2, 4))
        self.hint = tk.Label(
            self._body,
            text="请直接按下新的快捷键。单键只支持 F1–F24，其它按键请配合 Ctrl / Alt / Shift / Win；Esc 取消。",
            bg=BG,
            fg=MUTED,
            font=FONTS["small"],
            anchor="w",
            justify="left",
            wraplength=int(450 * ui_scale(self)),
        )
        self.hint.pack(fill="x", pady=(0, 4))
        self.error = tk.Label(self._body, text=" ", bg=BG, fg=RED_FG, font=FONTS["small"], anchor="w")
        self.error.pack(fill="x")

        foot = tk.Frame(self._body, bg=BG)
        foot.pack(fill="x", pady=(10, 0))
        FlatButton(foot, "保存", self._save, kind="primary", padx=18, pady=6).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=6).pack(
            side="right", padx=(0, 8)
        )
        FlatButton(foot, "重新按键", self._start_capture, kind="ghost", padx=12, pady=6).pack(
            side="right", padx=(0, 8)
        )
        FlatButton(
            foot, "恢复默认 %s" % pretty_combo(default), self._reset, kind="soft", padx=12, pady=6
        ).pack(side="left")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.show()
        self.after(80, self._start_capture)

    def _start_capture(self):
        if self._closed:
            return
        self._capturing = True
        self.hint.configure(text="请按下新的快捷键…（单键或带 Ctrl/Alt/Shift/Win 的组合）")
        self.app.hub.capture_next(self._captured, self._capture_cancelled)

    def _captured(self, combo):
        if self._closed:
            return
        self._capturing = False
        self.combo = combo
        self.display.configure(text=pretty_combo(combo))
        self.error.configure(text=" ")
        self.hint.configure(text="已捕获。点「保存」生效，或点「重新按键」重来。")

    def _capture_cancelled(self):
        if not self._closed:
            self.destroy()

    def _reset(self):
        self._captured(self.default)

    def _save(self):
        if not self.combo:
            self.error.configure(text="请先按下一个快捷键。")
            return
        error = self.on_save(self.combo)
        if error:
            self.error.configure(text=error)
            return
        self.destroy()

    def destroy(self):
        self.app.hub.clear_capture()
        super().destroy()


class MergeDialog(ModalDialog):
    def __init__(self, app, macros, on_ok):
        super().__init__(app, "合并宏", 520)
        self.on_ok = on_ok
        self._map = {}
        displays = []
        for macro in macros:
            display = macro.get("name") or "未命名宏"
            if display in self._map:
                display = "%s · %s" % (display, macro["id"][:4])
            self._map[display] = macro["id"]
            displays.append(display)

        tk.Label(self._body, text="把另一个宏追加到当前选中宏的末尾", bg=BG, fg=TEXT, font=FONTS["body"]).pack(
            anchor="w"
        )
        self.var = tk.StringVar(value=displays[0])
        combo = ttk.Combobox(
            self._body, textvariable=self.var, values=displays, state="readonly", font=FONTS["body"]
        )
        combo.pack(fill="x", pady=(8, 6), ipady=3)
        self.info = tk.Label(self._body, text="", bg=BG, fg=MUTED, font=FONTS["small"], anchor="w")
        self.info.pack(fill="x")

        row = tk.Frame(self._body, bg=BG)
        row.pack(fill="x", pady=(10, 0))
        tk.Label(row, text="两段之间等待", bg=BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
        self.gap_var = tk.StringVar(value="500")
        make_spin(row, self.gap_var, 0, 60000, width=7).pack(side="left", padx=(8, 4), ipady=2)
        tk.Label(row, text="毫秒", bg=BG, fg=MUTED, font=FONTS["small"]).pack(side="left")

        self.error = tk.Label(self._body, text=" ", bg=BG, fg=RED_FG, font=FONTS["small"], anchor="w")
        self.error.pack(fill="x", pady=(6, 0))

        foot = tk.Frame(self._body, bg=BG)
        foot.pack(fill="x", pady=(8, 0))
        FlatButton(foot, "合并", self._ok, kind="primary", padx=18, pady=6).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=6).pack(
            side="right", padx=(0, 8)
        )
        combo.bind("<<ComboboxSelected>>", lambda _e: self._update_info())
        self._update_info()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.show()

    def _update_info(self):
        mid = self._map.get(self.var.get())
        macro = None
        for item in self.app.macros.values():
            if item["id"] == mid:
                macro = item
                break
        if macro:
            self.info.configure(
                text="源：%s 个事件 · %s"
                % (format(len(macro.get("events") or []), ","), format_duration(macro.get("duration", 0)))
            )

    def _ok(self):
        mid = self._map.get(self.var.get())
        if not mid:
            self.error.configure(text="请选择要合并的宏。")
            return
        try:
            gap = max(0, min(60000, int(float(self.gap_var.get()))))
        except (TypeError, ValueError):
            self.error.configure(text="等待时间需要填写整数毫秒。")
            return
        self.on_ok(mid, gap)
        self.destroy()


def normalize_key_name_input(text):
    t = (text or "").strip()
    if not t:
        return None
    aliases = {
        "空格": "space",
        "回车": "enter",
        "退格": "backspace",
        "删除": "delete",
        "插入": "insert",
        "制表": "tab",
        "退出": "esc",
        "上": "up",
        "下": "down",
        "左": "left",
        "右": "right",
        "主页": "home",
        "结束": "end",
    }
    if t in aliases:
        t = aliases[t]
    t = t.lower()
    if t in SPECIAL_KEY_NAMES:
        return t
    if len(t) == 1:
        return t
    return None


class EventEditDialog(ModalDialog):
    def __init__(self, app, ev, prev_t, on_ok, parent=None):
        super().__init__(app, "修改事件", 520, parent=parent)
        self.ev = dict(ev)
        self.prev_t = max(0.0, float(prev_t))
        self.on_ok = on_ok
        self.kind = ev.get("type")
        self.x_var = self.y_var = self.dx_var = self.dy_var = self.key_var = None

        tk.Label(self._body, text="事件时间", bg=BG, fg=TEXT, font=FONTS["body_bold"]).pack(anchor="w")
        row = tk.Frame(self._body, bg=BG)
        row.pack(fill="x", pady=(4, 2))
        tk.Label(row, text="距上一个事件", bg=BG, fg=MUTED, font=FONTS["small"], width=12, anchor="w").pack(
            side="left"
        )
        self.delay_var = tk.StringVar(value="%.0f" % max(0.0, ev["t"] - prev_t))
        make_spin(row, self.delay_var, 0, 86400000, width=10).pack(side="left", ipady=2)
        tk.Label(row, text="毫秒", bg=BG, fg=MUTED, font=FONTS["small"]).pack(side="left", padx=(6, 0))
        tk.Label(
            self._body,
            text="修改后会同步移动这个事件以及它后面的事件",
            bg=BG,
            fg="#A0A8B8",
            font=FONTS["tiny"],
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        line = tk.Frame(self._body, bg=BORDER, height=1)
        line.pack(fill="x", pady=(0, 8))

        if self.kind in ("move", "button", "scroll"):
            row = tk.Frame(self._body, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text="坐标", bg=BG, fg=MUTED, font=FONTS["small"], width=12, anchor="w").pack(
                side="left"
            )
            tk.Label(row, text="X", bg=BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
            self.x_var = tk.StringVar(value=str(ev.get("x", 0)))
            make_entry(row, self.x_var, width=8).pack(side="left", padx=(4, 12), ipady=3)
            tk.Label(row, text="Y", bg=BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
            self.y_var = tk.StringVar(value=str(ev.get("y", 0)))
            make_entry(row, self.y_var, width=8).pack(side="left", padx=(4, 0), ipady=3)

        if self.kind == "button":
            row = tk.Frame(self._body, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text="鼠标按键", bg=BG, fg=MUTED, font=FONTS["small"], width=12, anchor="w").pack(
                side="left"
            )
            self.button_var = tk.StringVar(value=BTN_LABELS.get(ev.get("button"), "左键"))
            ttk.Combobox(
                row,
                textvariable=self.button_var,
                values=("左键", "右键", "中键", "侧键1", "侧键2"),
                state="readonly",
                width=8,
                font=FONTS["body"],
            ).pack(side="left")
            self.pressed_var = tk.StringVar(value="按下" if ev.get("pressed") else "松开")
            ttk.Combobox(
                row,
                textvariable=self.pressed_var,
                values=("按下", "松开"),
                state="readonly",
                width=7,
                font=FONTS["body"],
            ).pack(side="left", padx=(8, 0))
        elif self.kind == "scroll":
            row = tk.Frame(self._body, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text="滚动量", bg=BG, fg=MUTED, font=FONTS["small"], width=12, anchor="w").pack(
                side="left"
            )
            tk.Label(row, text="水平", bg=BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
            self.dx_var = tk.StringVar(value=str(ev.get("dx", 0)))
            make_spin(row, self.dx_var, -100, 100, width=5).pack(side="left", padx=(4, 14), ipady=2)
            tk.Label(row, text="垂直", bg=BG, fg=MUTED, font=FONTS["small"]).pack(side="left")
            self.dy_var = tk.StringVar(value=str(ev.get("dy", 0)))
            make_spin(row, self.dy_var, -100, 100, width=5).pack(side="left", padx=(4, 0), ipady=2)
        elif self.kind == "key":
            row = tk.Frame(self._body, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text="按键", bg=BG, fg=MUTED, font=FONTS["small"], width=12, anchor="w").pack(
                side="left"
            )
            self.key_var = tk.StringVar(value=ev.get("text") or ev.get("key") or "")
            make_entry(row, self.key_var, width=12).pack(side="left", ipady=3)
            tk.Label(
                self._body,
                text="可填：单个字母/数字/符号，或 ctrl、shift、space、enter、f6、page_down 等",
                bg=BG,
                fg="#A0A8B8",
                font=FONTS["tiny"],
                anchor="w",
            ).pack(fill="x", pady=(2, 0))

        self.error = tk.Label(self._body, text=" ", bg=BG, fg=RED_FG, font=FONTS["small"], anchor="w")
        self.error.pack(fill="x", pady=(8, 0))
        foot = tk.Frame(self._body, bg=BG)
        foot.pack(fill="x", pady=(8, 0))
        FlatButton(foot, "确定", self._ok, kind="primary", padx=18, pady=6).pack(side="right")
        FlatButton(foot, "取消", self.destroy, kind="ghost", padx=16, pady=6).pack(
            side="right", padx=(0, 8)
        )
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.show()

    def _read_int(self, var, label, lo=-32768, hi=32767):
        try:
            value = int(float(var.get()))
        except (TypeError, ValueError):
            raise ValueError("「%s」需要填写整数。" % label)
        if value < lo or value > hi:
            raise ValueError("「%s」需要在 %s 到 %s 之间。" % (label, lo, hi))
        return value

    def _ok(self):
        try:
            delay = self._read_int(self.delay_var, "间隔", 0, 86400000)
            ev = dict(self.ev)
            if self.kind in ("move", "button", "scroll"):
                ev["x"] = self._read_int(self.x_var, "X")
                ev["y"] = self._read_int(self.y_var, "Y")
            if self.kind == "button":
                rev = {v: k for k, v in BTN_LABELS.items()}
                ev["button"] = rev.get(self.button_var.get(), "left")
                ev["pressed"] = self.pressed_var.get() == "按下"
            elif self.kind == "scroll":
                ev["dx"] = self._read_int(self.dx_var, "水平滚动", -100, 100)
                ev["dy"] = self._read_int(self.dy_var, "垂直滚动", -100, 100)
            elif self.kind == "key":
                name = normalize_key_name_input(self.key_var.get())
                if not name:
                    raise ValueError("无法识别这个按键，请填写单个字符或 ctrl / shift / enter / f6 等名称。")
                old_key = self.ev.get("key")
                if name != old_key:
                    ev.pop("vk", None)
                    ev.pop("text", None)
                    ev["key"] = name
                    if len(name) == 1:
                        ev["text"] = name
            ev["t"] = round(self.prev_t + delay, 1)
            self.on_ok(ev, ev["t"])
            self.destroy()
        except ValueError as exc:
            self.error.configure(text=str(exc))


class MacroEditor(ModalDialog):
    LIMIT = 20000

    def __init__(self, app, macro):
        super().__init__(app, "编辑宏 · " + (macro.get("name") or ""), 980)
        self.macro = macro
        self.events = json.loads(json.dumps(macro.get("events") or []))
        self._dirty = False
        self.resizable(True, True)
        scale = ui_scale(self)
        w = min(int(980 * scale), self.winfo_screenwidth() - 80)
        h = min(int(640 * scale), self.winfo_screenheight() - 120)
        self.minsize(min(int(820 * scale), w), min(int(520 * scale), h))

        info = tk.Frame(self._body, bg=BG)
        info.pack(fill="x", pady=(0, 8))
        self.info = tk.Label(
            info, text="", bg=BG, fg=MUTED, font=FONTS["small"], anchor="w"
        )
        self.info.pack(side="left")
        tk.Label(
            info,
            text="双击某一行修改；删除动作不会移动其它动作的时间",
            bg=BG,
            fg="#A0A8B8",
            font=FONTS["tiny"],
        ).pack(side="right")

        wrap = tk.Frame(self._body, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="both", expand=True)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            wrap,
            columns=("n", "time", "gap", "action", "detail"),
            show="headings",
            selectmode="browse",
        )
        for key, text, width, anchor, stretch in (
            ("n", "#", 50, "center", False),
            ("time", "秒", 72, "center", False),
            ("gap", "间隔", 72, "center", False),
            ("action", "动作", 220, "w", False),
            ("detail", "详情", 420, "w", True),
        ):
            self.tree.heading(key, text=text, anchor=anchor)
            self.tree.column(key, width=width, minwidth=40, anchor=anchor, stretch=stretch)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda _e: self._modify())

        btns = tk.Frame(self._body, bg=BG)
        btns.pack(fill="x", pady=(10, 0))
        self.del_btn = FlatButton(
            btns, "删除选中", self._delete, kind="soft_danger", padx=12, pady=5, font=FONTS["small"]
        )
        self.del_btn.pack(side="left")
        self.early_btn = FlatButton(
            btns, "提前 0.1s", lambda: self._shift(-100), kind="ghost", padx=12, pady=5, font=FONTS["small"]
        )
        self.early_btn.pack(side="left", padx=(6, 0))
        self.late_btn = FlatButton(
            btns, "延后 0.1s", lambda: self._shift(100), kind="ghost", padx=12, pady=5, font=FONTS["small"]
        )
        self.late_btn.pack(side="left", padx=(6, 0))
        self.mod_btn = FlatButton(
            btns, "修改选中…", self._modify, kind="soft", padx=12, pady=5, font=FONTS["small"]
        )
        self.mod_btn.pack(side="left", padx=(6, 0))
        FlatButton(btns, "保存", self._save, kind="primary", padx=18, pady=5, font=FONTS["small"]).pack(
            side="right"
        )
        FlatButton(btns, "取消", self._cancel, kind="ghost", padx=14, pady=5, font=FONTS["small"]).pack(
            side="right", padx=(0, 6)
        )

        self.show()
        self.update_idletasks()
        scale = ui_scale(self)
        w = min(int(980 * scale), self.winfo_screenwidth() - 80)
        h = min(int(640 * scale), self.winfo_screenheight() - 120)
        self.geometry("%dx%d" % (w, h))
        self._center_large()
        self._refresh(0)

    def _center_large(self):
        self.update_idletasks()
        try:
            px = self.app.winfo_rootx()
            py = self.app.winfo_rooty()
            pw = self.app.winfo_width()
            ph = self.app.winfo_height()
        except Exception:
            px = py = 0
            pw = ph = 0
        w, h = self.winfo_width(), self.winfo_height()
        x = px + max(0, (pw - w) // 2)
        y = py + max(40, (ph - h) // 3)
        self.geometry("+%d+%d" % (x, y))

    def _refresh(self, select_index=0):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        prev = 0.0
        for i, ev in enumerate(self.events[: self.LIMIT]):
            gap = max(0.0, ev["t"] - prev)
            prev = ev["t"]
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    i + 1,
                    "%.3f" % (ev["t"] / 1000.0),
                    "%.3f" % (gap / 1000.0),
                    event_action_text(ev),
                    event_detail_text(ev),
                ),
            )
        count = len(self.events)
        text = "共 %s 个事件 · %s" % (format(count, ","), format_duration(self.events[-1]["t"] if self.events else 0))
        if count > self.LIMIT:
            text += " · 只显示前 %s 条（保存时仍保留全部）" % self.LIMIT
        self.info.configure(text=text)
        has_events = bool(self.events)
        for btn in (self.del_btn, self.early_btn, self.late_btn, self.mod_btn):
            btn.set_enabled(has_events)
        if self.events:
            idx = max(0, min(int(select_index), min(count, self.LIMIT) - 1))
            iid = str(idx)
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _delete(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.events):
            return
        del self.events[idx]
        self._dirty = True
        self._refresh(min(idx, len(self.events) - 1))

    def _shift(self, delta):
        idx = self._selected_index()
        if idx is None or idx >= len(self.events):
            return
        prev = self.events[idx - 1]["t"] if idx > 0 else 0.0
        if self.events[idx]["t"] + delta < prev:
            delta = round(prev - self.events[idx]["t"], 1)
        if not delta:
            return
        for j in range(idx, len(self.events)):
            self.events[j]["t"] = round(max(0.0, self.events[j]["t"] + delta), 1)
        self._dirty = True
        self._refresh(idx)

    def _modify(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.events):
            return
        prev = self.events[idx - 1]["t"] if idx > 0 else 0.0

        def apply(ev, new_t):
            old_t = float(self.events[idx]["t"])
            delta = round(new_t - old_t, 1)
            if delta:
                for j in range(idx, len(self.events)):
                    self.events[j]["t"] = round(max(0.0, self.events[j]["t"] + delta), 1)
            ev["t"] = round(new_t, 1)
            self.events[idx] = ev
            self._dirty = True
            self._refresh(idx)

        EventEditDialog(self.app, self.events[idx], prev, apply, parent=self)

    def _can_close(self):
        if not self._dirty:
            return True
        return messagebox.askyesno("放弃修改？", "有未保存的修改，确定放弃吗？", parent=self)

    def _cancel(self):
        if self._can_close():
            self.destroy()

    def _save(self):
        if not self.events:
            if not messagebox.askyesno("宏是空的", "所有事件都被删除了，保存后这个宏无法回放。确定保存吗？", parent=self):
                return
        if self.app.save_edited_macro(self.macro["id"], self.events):
            self._dirty = False
            self.destroy()
    def destroy(self):
        if not self._closed and not self._can_close():
            return
        self._dirty = False
        super().destroy()


def main():
    enable_dpi_awareness()
    setup_logging()
    try:
        app = App()
    except Exception as exc:
        log.exception("启动失败")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("启动失败", "鼠标点击器启动失败：\n\n%s" % exc)
            root.destroy()
        except Exception:
            pass
        return
    app.mainloop()


if __name__ == "__main__":
    main()




