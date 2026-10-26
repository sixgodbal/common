# -*- coding: utf-8 -*-
"""文本快搜（Text Quick Search）

在指定文件夹里快速搜索文件内容，找到文字出现在哪些文件、哪一行。
点击按钮才扫描，不建常驻索引，不联网。

依赖：Python 3.8+ 标准库（tkinter）。
数据：程序目录下 config.json。
"""

import bisect
import codecs
import csv
import html
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import zipfile
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "文本快搜"
APP_VERSION = "1.0"

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
RED = "#E0455C"
RED_BG = "#FDECEC"
RED_FG = "#C0392B"
RED_HOVER = "#F8DADA"
AMBER = "#C77700"
AMBER_BG = "#FFF4E0"
GREEN = "#0E9F6E"
STATUS_BG = "#E9EDF5"
SOFT_BG = "#F7F9FD"
HIGHLIGHT_BG = "#FFF1A8"

FONTS = {}

DEFAULT_EXTENSIONS = (
    "txt,md,markdown,log,csv,tsv,json,jsonl,xml,html,htm,css,js,jsx,ts,tsx,"
    "py,java,c,cc,cpp,cxx,h,hpp,cs,go,rs,php,rb,sql,sh,bat,cmd,ps1,yml,yaml,"
    "ini,cfg,conf,toml,properties,env,tex,rst,adoc,eml,srt,vtt,"
    "docx,docm,xlsx,xlsm,pptx,pptm,epub,odt,ods,odp"
)
DEFAULT_EXCLUDES = ".git,node_modules,__pycache__,.venv,venv,env,dist,build,target,out,.idea,.vs"

OFFICE_EXTS = {
    ".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm",
    ".epub", ".odt", ".ods", ".odp",
}

MAX_MATCHES_PER_FILE = 5000
MAX_SNIPPETS_PER_FILE = 80
MAX_EXTRACT_BYTES = 64 * 1024 * 1024
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HARD_EXCLUDES = {"$recycle.bin", "system volume information"}
_CONTROL_TABLE = bytes(
    1 if (i < 32 and i not in (9, 10, 11, 12, 13)) or i == 127 else 0
    for i in range(256)
)
_BAD_CHAR_TABLE = {i: None for i in list(range(0, 9)) + list(range(14, 32)) + [127]}


def default_paths():
    home = os.path.expanduser("~")
    found = []
    for name in ("Documents", "Desktop"):
        path = os.path.join(home, name)
        if os.path.isdir(path):
            found.append(path)
    return found or ([home] if home else [])


DEFAULT_SETTINGS = {
    "paths": [],
    "extensions": DEFAULT_EXTENSIONS,
    "exclude_dirs": DEFAULT_EXCLUDES,
    "recursive": True,
    "case_sensitive": False,
    "search_office": True,
    "skip_hidden": True,
    "max_size_mb": 20,
    "max_results": 3000,
    "workers": 0,
    "always_on_top": False,
    "window_geometry": "",
}


# ------------------------------------------------------------------ 基础工具
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
    FONTS["title"] = (family, 18, "bold")
    FONTS["subtitle"] = (family, 9)
    FONTS["card"] = (family, 11, "bold")
    FONTS["section"] = (family, 9, "bold")
    FONTS["body"] = (family, 10)
    FONTS["body_bold"] = (family, 10, "bold")
    FONTS["small"] = (family, 9)
    FONTS["tiny"] = (family, 8)
    FONTS["button"] = (family, 10, "bold")
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
        background=SOFT_BG,
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
        "Horizontal.TScrollbar",
        background="#C8D1E0",
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=MUTED,
        relief="flat",
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


def resolve_path(path):
    if not path:
        return ""
    p = str(path).strip().strip('"').strip("'")
    p = os.path.expandvars(os.path.expanduser(p))
    if not os.path.isabs(p):
        p = os.path.join(BASE_DIR, p)
    return os.path.normpath(p)


def format_size(size):
    try:
        size = float(size)
    except (TypeError, ValueError):
        size = 0.0
    if size < 1024:
        return "%d B" % int(size)
    if size < 1024 * 1024:
        return "%.1f KB" % (size / 1024.0)
    if size < 1024 * 1024 * 1024:
        return "%.1f MB" % (size / (1024.0 * 1024.0))
    return "%.2f GB" % (size / (1024.0 * 1024.0 * 1024.0))


def format_mtime(mtime):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(mtime)))
    except (TypeError, ValueError, OSError):
        return ""


# ------------------------------------------------------------------ 配置
def normalize_config(data):
    if not isinstance(data, dict):
        data = {}
    raw = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    s = dict(DEFAULT_SETTINGS)

    paths = raw.get("paths")
    if isinstance(paths, list):
        cleaned = []
        for p in paths[:50]:
            if isinstance(p, str) and p.strip():
                cleaned.append(p.strip())
        s["paths"] = cleaned
    else:
        s["paths"] = default_paths()

    if not s["paths"]:
        s["paths"] = default_paths()

    if isinstance(raw.get("extensions"), str):
        s["extensions"] = raw["extensions"][:4000]
    if isinstance(raw.get("exclude_dirs"), str):
        s["exclude_dirs"] = raw["exclude_dirs"][:2000]

    for key in ("recursive", "case_sensitive", "search_office", "skip_hidden", "always_on_top"):
        if isinstance(raw.get(key), bool):
            s[key] = raw[key]

    try:
        s["max_size_mb"] = max(1, min(1024, int(raw.get("max_size_mb", 20))))
    except (TypeError, ValueError):
        s["max_size_mb"] = 20
    try:
        s["max_results"] = max(100, min(50000, int(raw.get("max_results", 3000))))
    except (TypeError, ValueError):
        s["max_results"] = 3000
    try:
        s["workers"] = max(0, min(64, int(raw.get("workers", 0))))
    except (TypeError, ValueError):
        s["workers"] = 0

    if isinstance(raw.get("window_geometry"), str):
        s["window_geometry"] = raw["window_geometry"]

    return {"version": 1, "settings": s}


def write_config(data):
    tmp = CONFIG_PATH + ".tmp"
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
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
    data = normalize_config({"settings": {"paths": default_paths()}})
    try:
        write_config(data)
    except Exception:
        pass
    return data


# ------------------------------------------------------------------ 搜索范围
def parse_extensions(raw):
    """把 'txt, md, *.py' 解析成 {'.txt', '.md', '.py'}；空/星号表示全部。"""
    if not raw or not raw.strip():
        return set()
    out = set()
    for token in re.split(r"[,;\s]+", raw):
        token = token.strip().lower()
        if not token or token in ("*", "*.*", "all"):
            continue
        token = token.lstrip("*")
        if token and not token.startswith("."):
            token = "." + token
        if token and token != ".":
            out.add(token)
    return out


def parse_excludes(raw):
    out = set()
    if not raw:
        return out
    for token in re.split(r"[,;\r\n]+", raw):
        token = token.strip().strip("\\/").lower()
        if token:
            out.add(token)
    return out


def normalize_roots(paths):
    """展开路径、去重，并去掉被父目录包含的子目录。返回 (可用路径, 不存在路径)。"""
    resolved = []
    missing = []
    for raw in paths:
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = resolve_path(raw)
        if os.path.isdir(path):
            resolved.append(path)
        else:
            missing.append(path)

    unique = []
    seen = set()
    for path in resolved:
        key = os.path.normcase(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)

    unique.sort(key=lambda p: len(os.path.normcase(p)))
    roots = []
    for path in unique:
        key = os.path.normcase(path)
        nested = False
        for parent in roots:
            pkey = os.path.normcase(parent)
            if key == pkey or key.startswith(pkey + os.sep):
                nested = True
                break
        if not nested:
            roots.append(path)
    return roots, missing


def iter_files(roots, opts, stop_event):
    """递归枚举候选文件，返回 (path, size, mtime, ext)。"""
    extensions = opts["extensions"]
    max_bytes = opts["max_bytes"]
    excludes = opts["exclude_dirs"]
    recursive = opts["recursive"]
    skip_hidden = opts["skip_hidden"]

    for root in roots:
        if stop_event.is_set():
            return
        stack = [root]
        while stack:
            folder = stack.pop()
            if stop_event.is_set():
                return
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        if stop_event.is_set():
                            return
                        try:
                            stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            continue
                        attrs = getattr(stat, "st_file_attributes", 0)
                        if skip_hidden and (attrs & 0x2 or attrs & 0x4):
                            continue
                        try:
                            is_dir = entry.is_dir(follow_symlinks=False)
                            is_file = entry.is_file(follow_symlinks=False)
                        except OSError:
                            continue
                        if is_dir:
                            if entry.is_symlink():
                                continue
                            name = entry.name.lower()
                            if name in excludes or name in HARD_EXCLUDES:
                                continue
                            if recursive:
                                stack.append(entry.path)
                        elif is_file:
                            size = stat.st_size
                            if size <= 0 or size > max_bytes:
                                continue
                            ext = os.path.splitext(entry.name)[1].lower()
                            if extensions and ext not in extensions:
                                continue
                            yield (entry.path, size, stat.st_mtime, ext)
            except OSError:
                continue


# ------------------------------------------------------------------ 编码 / 文本
def _detect_unicode_encoding(data, sample):
    if data.startswith(codecs.BOM_UTF32_LE) or data.startswith(codecs.BOM_UTF32_BE):
        return "utf-32"
    if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        return "utf-16"
    if data.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if b"\x00" in sample and len(sample) >= 8:
        half = len(sample) // 2
        even_zero = sample[0::2].count(0)
        odd_zero = sample[1::2].count(0)
        if odd_zero > half * 0.3 and even_zero < half * 0.08:
            return "utf-16-le"
        if even_zero > half * 0.3 and odd_zero < half * 0.08:
            return "utf-16-be"
    return None


def _looks_binary(data):
    sample = data[:8192]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    control = sample.translate(_CONTROL_TABLE).count(1)
    return control > max(8, len(sample) // 50)


def _text_sanity(text):
    sample = text[:4096]
    if not sample:
        return True
    bad = len(sample) - len(sample.translate(_BAD_CHAR_TABLE))
    return bad <= max(4, len(sample) // 50)


def find_positions(hay, needle, cap, stop_event):
    """不重叠地查找 needle，最多 cap 个；返回 (位置列表, 是否还有更多)。"""
    if not needle:
        return [], False
    positions = []
    start = 0
    step = len(needle)
    while len(positions) < cap:
        index = hay.find(needle, start)
        if index < 0:
            return positions, False
        positions.append(index)
        start = index + step
        if len(positions) % 512 == 0 and stop_event.is_set():
            break
    truncated = hay.find(needle, start) >= 0
    return positions, truncated


def _snippet(text, line_start, line_end, pos, query_len):
    line = text[line_start:line_end].rstrip("\r\n")
    rel = pos - line_start
    if len(line) <= 260:
        return line.strip()
    left = max(0, rel - 100)
    right = min(len(line), rel + query_len + 100)
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(line) else ""
    return prefix + line[left:right].strip() + suffix


def hit_from_text(text, path, size, mtime, query, case_sensitive, stop_event, source="text"):
    if stop_event.is_set():
        return None
    hay = text if case_sensitive else text.lower()
    needle = query if case_sensitive else query.lower()
    positions, truncated = find_positions(hay, needle, MAX_MATCHES_PER_FILE, stop_event)
    if not positions:
        return None

    line_starts = [0]
    for match in re.finditer("\n", text):
        line_starts.append(match.end())

    snippets = []
    for pos in positions[:MAX_SNIPPETS_PER_FILE]:
        line_index = bisect.bisect_right(line_starts, pos) - 1
        line_start = line_starts[line_index]
        line_end = line_starts[line_index + 1] if line_index + 1 < len(line_starts) else len(text)
        snippets.append(
            (
                line_index + 1,
                pos - line_start + 1,
                _snippet(text, line_start, line_end, pos, len(query)),
            )
        )

    return {
        "path": path,
        "name": os.path.basename(path),
        "folder": os.path.dirname(path),
        "size": size,
        "mtime": mtime,
        "count": len(positions),
        "truncated": truncated,
        "snippets": snippets,
        "source": source,
    }


def search_text_file(path, size, mtime, query, opts, stop_event):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except (OSError, MemoryError):
        return None, size
    if not data:
        return None, 0
    if len(data) > opts["max_bytes"]:
        return None, len(data)
    if stop_event.is_set():
        return None, len(data)

    sample = data[:8192]
    unicode_encoding = _detect_unicode_encoding(data, sample)
    if unicode_encoding:
        try:
            text = data.decode(unicode_encoding)
        except (UnicodeDecodeError, LookupError):
            return None, len(data)
        if not _text_sanity(text):
            return None, len(data)
        hit = hit_from_text(
            text, path, size, mtime, query, opts["case_sensitive"], stop_event
        )
        return hit, len(data)

    if _looks_binary(data):
        return None, len(data)

    candidates = []
    for encoding in ("utf-8", "gb18030"):
        try:
            pattern = query.encode(encoding)
        except UnicodeEncodeError:
            continue
        if not any(enc == encoding and pat == pattern for enc, pat in candidates):
            candidates.append((encoding, pattern))
    if not candidates:
        return None, len(data)

    hay = data.lower() if (not opts["case_sensitive"] and query.isascii()) else data
    for encoding, pattern in candidates:
        if stop_event.is_set():
            break
        needle = pattern.lower() if hay is not data else pattern
        if hay.find(needle) < 0:
            continue
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if not _text_sanity(text):
            continue
        hit = hit_from_text(
            text, path, size, mtime, query, opts["case_sensitive"], stop_event
        )
        if hit:
            return hit, len(data)
    return None, len(data)


# ------------------------------------------------------------------ Office / EPUB 文本提取
def _xml_to_text(xml, kind):
    if kind == "docx":
        xml = re.sub(r"<w:tab\b[^>]*/>", "\t", xml, flags=re.I)
        xml = re.sub(r"<w:br\b[^>]*/>", "\n", xml, flags=re.I)
        xml = re.sub(r"</w:p>", "\n", xml, flags=re.I)
        xml = re.sub(r"</w:tr>", "\n", xml, flags=re.I)
    elif kind == "pptx":
        xml = re.sub(r"<a:br\b[^>]*/>", "\n", xml, flags=re.I)
        xml = re.sub(r"</a:p>", "\n", xml, flags=re.I)
    elif kind == "xlsx":
        xml = re.sub(r"</c>", "\t", xml, flags=re.I)
        xml = re.sub(r"</row>", "\n", xml, flags=re.I)
        xml = re.sub(r"</si>", "\n", xml, flags=re.I)
    elif kind == "epub":
        xml = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", xml, flags=re.I | re.S)
        xml = re.sub(r"<br\s*/?>", "\n", xml, flags=re.I)
        xml = re.sub(
            r"</(p|div|h[1-6]|li|tr|section|article|blockquote|pre|title)>",
            "\n",
            xml,
            flags=re.I,
        )
    elif kind == "odf":
        xml = re.sub(r"<text:tab\b[^>]*/>", "\t", xml, flags=re.I)
        xml = re.sub(r"<text:line-break\b[^>]*/>", "\n", xml, flags=re.I)
        xml = re.sub(r"</text:(p|h)>", "\n", xml, flags=re.I)
        xml = re.sub(r"</table:table-row>", "\n", xml, flags=re.I)

    text = re.sub(r"<[^>]+>", "", xml)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def extract_office_text(path, ext):
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            targets = []
            kind = None
            if ext in (".docx", ".docm"):
                kind = "docx"
                targets = [
                    name
                    for name in names
                    if name == "word/document.xml"
                    or re.match(r"word/(header|footer|footnotes|endnotes)\d*\.xml$", name)
                ]
            elif ext in (".xlsx", ".xlsm"):
                kind = "xlsx"
                targets = [
                    name
                    for name in names
                    if name == "xl/sharedStrings.xml"
                    or re.match(r"xl/worksheets/sheet\d+\.xml$", name)
                ]
            elif ext in (".pptx", ".pptm"):
                kind = "pptx"
                targets = [
                    name
                    for name in names
                    if re.match(r"ppt/(slides|notesSlides)/[^/]+\.xml$", name)
                ]
            elif ext == ".epub":
                kind = "epub"
                targets = [
                    name
                    for name in names
                    if name.lower().endswith((".xhtml", ".html", ".htm"))
                ][:300]
            elif ext in (".odt", ".ods", ".odp"):
                kind = "odf"
                targets = ["content.xml"] if "content.xml" in names else []

            if not targets:
                return None

            total = 0
            parts = []
            for name in targets:
                try:
                    info = archive.getinfo(name)
                except KeyError:
                    continue
                total += info.file_size
                if total > MAX_EXTRACT_BYTES:
                    return None
                raw = archive.read(name)
                xml = raw.decode("utf-8", "ignore")
                text = _xml_to_text(xml, kind)
                if text:
                    parts.append(text)
            return "\n".join(parts) if parts else None
    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError):
        return None


def search_office_file(path, ext, size, mtime, query, opts, stop_event):
    if stop_event.is_set() or not opts["search_office"]:
        return None, size
    text = extract_office_text(path, ext)
    if not text:
        return None, size
    hit = hit_from_text(
        text, path, size, mtime, query, opts["case_sensitive"], stop_event, source="office"
    )
    return hit, size


def search_one(item, query, opts, stop_event):
    path, size, mtime, ext = item
    if stop_event.is_set():
        return None, 0
    try:
        if ext in OFFICE_EXTS:
            return search_office_file(path, ext, size, mtime, query, opts, stop_event)
        return search_text_file(path, size, mtime, query, opts, stop_event)
    except Exception:
        return None, size


# ------------------------------------------------------------------ 通用控件
class FlatButton(tk.Label):
    def __init__(self, master, text, command=None, kind="ghost", padx=12, pady=6, font=None, **kw):
        palettes = {
            "primary": (ACCENT, "#FFFFFF", ACCENT_HOVER),
            "ghost": (CARD_BG, TEXT, "#EDF1F8"),
            "soft": (CHIP_BG, CHIP_FG, CHIP_HOVER),
            "danger": (RED_BG, RED_FG, RED_HOVER),
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
        self._fg = fg
        self._hover = hover
        self._command = command
        self._enabled = True
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

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if self._enabled:
            self.configure(bg=self._bg, fg=self._fg, cursor="hand2")
        else:
            self.configure(bg="#EEF1F6", fg="#B5BDCB", cursor="arrow")


def make_card(parent):
    return tk.Frame(
        parent,
        bg=CARD_BG,
        highlightbackground=BORDER,
        highlightthickness=1,
    )


def card_title(parent, text, hint=""):
    row = tk.Frame(parent, bg=CARD_BG)
    row.pack(fill="x")
    tk.Label(row, text=text, bg=CARD_BG, fg=TEXT, font=FONTS["card"], anchor="w").pack(side="left")
    if hint:
        tk.Label(row, text=hint, bg=CARD_BG, fg=MUTED, font=FONTS["tiny"]).pack(
            side="left", padx=(8, 0)
        )
    return row


# ------------------------------------------------------------------ 主窗口
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        enable_dpi_awareness()
        setup_fonts(self)
        setup_style(self)
        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.minsize(int(940 * ui_scale(self)), int(700 * ui_scale(self)))

        self.data = load_config()
        self.settings = self.data["settings"]
        self.paths = list(self.settings["paths"])

        self.searching = False
        self.stop_event = threading.Event()
        self.queue = queue.Queue()
        self.worker = None
        self.pump_id = None
        self.results = []
        self.result_by_iid = {}
        self.sort_col = "folder"
        self.sort_desc = False
        self.max_results = int(self.settings["max_results"])
        self.truncated_results = False
        self.worker_error = ""
        self.search_started = 0.0

        self.scanned = 0
        self.total = 0
        self.hit_files = 0
        self.hit_count = 0
        self.bytes_scanned = 0
        self.current_hit = None

        self._build_ui()
        self._refresh_paths()
        self._apply_window()
        self._apply_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-f>", lambda _e: self._focus_query())
        self.bind("<Control-o>", lambda _e: self.add_path())
        self.bind("<Escape>", lambda _e: self.stop_search())
        self.bind("<F5>", lambda _e: self.start_search())

        self.deiconify()
        self.after(80, self._focus_query)

    # -------------------------------------------------- 界面
    def _build_ui(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        status_bar = tk.Frame(outer, bg=STATUS_BG)
        status_bar.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar(value="就绪：添加文件夹，输入文字，点「开始查找」")
        tk.Label(
            status_bar,
            textvariable=self.status_var,
            bg=STATUS_BG,
            fg=MUTED,
            font=FONTS["small"],
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=20, pady=6)
        self.progress = ttk.Progressbar(
            status_bar,
            style="Thin.Horizontal.TProgressbar",
            length=220,
            mode="determinate",
        )
        self.progress.pack(side="right", padx=(8, 20), pady=8)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", padx=20, pady=(14, 8))
        hl = tk.Frame(header, bg=BG)
        hl.pack(side="left", anchor="w")
        tk.Label(hl, text=APP_TITLE, bg=BG, fg=TEXT, font=FONTS["title"]).pack(anchor="w")
        tk.Label(
            hl,
            text="在指定文件夹里搜索文件内容，找到文字出现在哪个文件、哪一行",
            bg=BG,
            fg=MUTED,
            font=FONTS["subtitle"],
        ).pack(anchor="w", pady=(1, 0))

        hr = tk.Frame(header, bg=BG)
        hr.pack(side="right", anchor="e")
        tk.Label(
            hr,
            text="纯本地 · 不建常驻索引 · 不联网",
            bg=BG,
            fg=MUTED,
            font=FONTS["tiny"],
        ).pack(side="right")

        body = tk.Frame(outer, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, minsize=int(286 * ui_scale(self)), weight=0)
        body.columnconfigure(1, weight=1)

        sidebar = tk.Frame(body, bg=BG, width=int(286 * ui_scale(self)))
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        sidebar.grid_propagate(False)

        content = tk.Frame(body, bg=BG)
        content.grid(row=0, column=1, sticky="nsew")
        content.rowconfigure(0, weight=0)
        content.rowconfigure(1, weight=1)

        self._build_sidebar(sidebar)
        self._build_search_card(content)
        self._build_result_area(content)

    def _build_sidebar(self, parent):
        # 搜索范围
        scope = make_card(parent)
        scope.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(scope, bg=CARD_BG)
        inner.pack(fill="x", padx=12, pady=10)

        row = card_title(inner, "搜索范围")
        self.path_count_label = tk.Label(
            row, text="", bg=CARD_BG, fg=MUTED, font=FONTS["tiny"]
        )
        self.path_count_label.pack(side="right")

        list_box = tk.Frame(inner, bg=CARD_BG)
        list_box.pack(fill="x", pady=(7, 5))
        self.path_list = tk.Listbox(
            list_box,
            height=6,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            bg=SOFT_BG,
            fg=TEXT,
            selectbackground="#DCE8FD",
            selectforeground=TEXT,
            font=FONTS["small"],
            activestyle="none",
            exportselection=False,
        )
        self.path_list.pack(side="left", fill="both", expand=True)
        path_sb = ttk.Scrollbar(
            list_box, orient="vertical", command=self.path_list.yview
        )
        path_sb.pack(side="right", fill="y")
        self.path_list.configure(yscrollcommand=path_sb.set)
        self.path_list.bind("<Double-Button-1>", lambda _e: self.open_selected_path())
        self.path_list.bind("<Delete>", lambda _e: self.remove_path())

        path_xsb = ttk.Scrollbar(inner, orient="horizontal", command=self.path_list.xview)
        path_xsb.pack(fill="x")
        self.path_list.configure(xscrollcommand=path_xsb.set)

        path_buttons = tk.Frame(inner, bg=CARD_BG)
        path_buttons.pack(fill="x", pady=(5, 0))
        FlatButton(
            path_buttons, "＋ 添加文件夹", self.add_path, kind="soft", padx=10, pady=5
        ).pack(side="left")
        FlatButton(
            path_buttons, "移除", self.remove_path, kind="ghost", padx=10, pady=5
        ).pack(side="left", padx=(6, 0))

        self.recursive_var = tk.BooleanVar(value=bool(self.settings["recursive"]))
        tk.Checkbutton(
            inner,
            text="包含子文件夹",
            variable=self.recursive_var,
            bg=CARD_BG,
            fg=TEXT,
            font=FONTS["body"],
            activebackground=CARD_BG,
            activeforeground=TEXT,
            selectcolor=CARD_BG,
            highlightthickness=0,
            bd=0,
            anchor="w",
        ).pack(anchor="w", pady=(6, 0))

        self.skip_hidden_var = tk.BooleanVar(value=bool(self.settings["skip_hidden"]))
        tk.Checkbutton(
            inner,
            text="跳过隐藏/系统文件",
            variable=self.skip_hidden_var,
            bg=CARD_BG,
            fg=TEXT,
            font=FONTS["body"],
            activebackground=CARD_BG,
            activeforeground=TEXT,
            selectcolor=CARD_BG,
            highlightthickness=0,
            bd=0,
            anchor="w",
        ).pack(anchor="w")

        # 搜索选项
        options = make_card(parent)
        options.pack(fill="both", expand=True)
        opt = tk.Frame(options, bg=CARD_BG)
        opt.pack(fill="both", expand=True, padx=12, pady=10)
        card_title(opt, "搜索选项")

        self.case_var = tk.BooleanVar(value=bool(self.settings["case_sensitive"]))
        self.office_var = tk.BooleanVar(value=bool(self.settings["search_office"]))
        for text, var in (
            ("区分大小写", self.case_var),
            ("搜索 Office / EPUB 文档", self.office_var),
        ):
            tk.Checkbutton(
                opt,
                text=text,
                variable=var,
                bg=CARD_BG,
                fg=TEXT,
                font=FONTS["body"],
                activebackground=CARD_BG,
                activeforeground=TEXT,
                selectcolor=CARD_BG,
                highlightthickness=0,
                bd=0,
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))

        size_row = tk.Frame(opt, bg=CARD_BG)
        size_row.pack(fill="x", pady=(8, 0))
        tk.Label(
            size_row, text="最大文件", bg=CARD_BG, fg=MUTED, font=FONTS["small"]
        ).pack(side="left")
        self.max_size_var = tk.StringVar(value=str(self.settings["max_size_mb"]))
        tk.Spinbox(
            size_row,
            from_=1,
            to=1024,
            increment=5,
            textvariable=self.max_size_var,
            width=6,
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=FONTS["small"],
            buttonbackground=CARD_BG,
            justify="right",
        ).pack(side="left", padx=(6, 4))
        tk.Label(size_row, text="MB", bg=CARD_BG, fg=MUTED, font=FONTS["small"]).pack(
            side="left"
        )

        limit_row = tk.Frame(opt, bg=CARD_BG)
        limit_row.pack(fill="x", pady=(6, 0))
        tk.Label(
            limit_row, text="结果上限", bg=CARD_BG, fg=MUTED, font=FONTS["small"]
        ).pack(side="left")
        self.max_results_var = tk.StringVar(value=str(self.settings["max_results"]))
        tk.Spinbox(
            limit_row,
            from_=100,
            to=50000,
            increment=500,
            textvariable=self.max_results_var,
            width=6,
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=FONTS["small"],
            buttonbackground=CARD_BG,
            justify="right",
        ).pack(side="left", padx=(6, 4))
        tk.Label(
            limit_row, text="个文件", bg=CARD_BG, fg=MUTED, font=FONTS["small"]
        ).pack(side="left")

        tk.Label(
            opt, text="文件类型（逗号分隔，留空 = 全部）", bg=CARD_BG, fg=MUTED, font=FONTS["tiny"]
        ).pack(anchor="w", pady=(10, 2))
        self.ext_text = tk.Text(
            opt,
            height=4,
            width=28,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            bg=SOFT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            font=("Consolas", 8),
            wrap="word",
            padx=6,
            pady=5,
        )
        self.ext_text.pack(fill="x")
        self.ext_text.insert("1.0", self.settings["extensions"])

        tk.Label(
            opt, text="排除目录（逗号分隔）", bg=CARD_BG, fg=MUTED, font=FONTS["tiny"]
        ).pack(anchor="w", pady=(8, 2))
        self.exclude_var = tk.StringVar(value=self.settings["exclude_dirs"])
        tk.Entry(
            opt,
            textvariable=self.exclude_var,
            bg=SOFT_BG,
            fg=TEXT,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=FONTS["small"],
            insertbackground=TEXT,
        ).pack(fill="x", ipady=4, ipadx=4)

        tk.Label(
            opt,
            text="提示：Ctrl+O 添加文件夹 · F5 开始搜索 · Esc 停止",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["tiny"],
            justify="left",
            wraplength=int(250 * ui_scale(self)),
        ).pack(anchor="w", pady=(10, 0))

    def _build_search_card(self, parent):
        card = make_card(parent)
        card.grid(row=0, column=0, sticky="ew")
        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill="x", padx=14, pady=12)

        tk.Label(
            inner, text="搜索内容", bg=CARD_BG, fg=MUTED, font=FONTS["small"]
        ).pack(anchor="w")

        row = tk.Frame(inner, bg=CARD_BG)
        row.pack(fill="x", pady=(5, 0))
        entry_box = tk.Frame(
            row,
            bg=SOFT_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        entry_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            entry_box, text="🔍", bg=SOFT_BG, fg=MUTED, font=FONTS["body"]
        ).pack(side="left", padx=(9, 2))
        self.query_entry = tk.Entry(
            entry_box,
            bd=0,
            relief="flat",
            bg=SOFT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            font=(FONTS["body"][0], 12),
        )
        self.query_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self.query_entry.bind("<Return>", lambda _e: self.start_search())

        self.search_btn = FlatButton(
            row, "开始查找", self.start_search, kind="primary", padx=18, pady=8
        )
        self.search_btn.pack(side="left", padx=(8, 0))
        self.stop_btn = FlatButton(
            row, "停止", self.stop_search, kind="danger", padx=14, pady=8
        )
        self.stop_btn.pack(side="left", padx=(6, 0))
        self.stop_btn.set_enabled(False)

        tk.Label(
            inner,
            text="回车开始 · 只搜索文字内容，不搜索文件名；Office 文档会提取文字后搜索",
            bg=CARD_BG,
            fg=MUTED,
            font=FONTS["tiny"],
        ).pack(anchor="w", pady=(6, 0))

    def _build_result_area(self, parent):
        paned = tk.PanedWindow(
            parent,
            orient="vertical",
            bg=BG,
            sashwidth=9,
            bd=0,
            relief="flat",
            showhandle=False,
        )
        paned.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.paned = paned

        result_card = make_card(paned)
        result_card.rowconfigure(1, weight=1)
        result_card.columnconfigure(0, weight=1)
        paned.add(result_card, stretch="always", minsize=int(220 * ui_scale(self)))

        head = tk.Frame(result_card, bg=CARD_BG)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(9, 6))
        tk.Label(
            head, text="搜索结果", bg=CARD_BG, fg=TEXT, font=FONTS["card"]
        ).pack(side="left")
        self.result_label = tk.Label(
            head, text="", bg=CARD_BG, fg=MUTED, font=FONTS["tiny"]
        )
        self.result_label.pack(side="left", padx=(8, 0))
        FlatButton(
            head, "导出 CSV", self.export_csv, kind="ghost", padx=10, pady=4,
            font=FONTS["small"],
        ).pack(side="right")

        tree_box = tk.Frame(result_card, bg=CARD_BG)
        tree_box.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 10))
        tree_box.rowconfigure(0, weight=1)
        tree_box.columnconfigure(0, weight=1)

        columns = ("name", "count", "first", "size", "mtime", "folder")
        self.tree = ttk.Treeview(
            tree_box,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        headings = {
            "name": ("文件名", 170, "w"),
            "count": ("匹配", 55, "e"),
            "first": ("首个位置", 75, "center"),
            "size": ("大小", 75, "e"),
            "mtime": ("修改时间", 118, "center"),
            "folder": ("所在文件夹", 280, "w"),
        }
        for col, (text, width, anchor) in headings.items():
            self.tree.heading(
                col,
                text=text,
                command=lambda c=col: self.sort_results(c),
            )
            self.tree.column(col, width=int(width * ui_scale(self)), anchor=anchor, stretch=(col == "folder"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("odd", background="#FBFCFE")
        self.tree.tag_configure("even", background=CARD_BG)

        vsb = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(tree_box, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-Button-1>", lambda _e: self.open_selected())
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        # 预览
        preview_card = make_card(paned)
        preview_card.rowconfigure(1, weight=1)
        preview_card.columnconfigure(0, weight=1)
        paned.add(preview_card, stretch="always", minsize=int(150 * ui_scale(self)))

        preview_head = tk.Frame(preview_card, bg=CARD_BG)
        preview_head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 5))
        tk.Label(
            preview_head, text="匹配内容预览", bg=CARD_BG, fg=TEXT, font=FONTS["card"]
        ).pack(side="left")
        self.preview_title = tk.Label(
            preview_head, text="", bg=CARD_BG, fg=MUTED, font=FONTS["tiny"], anchor="w"
        )
        self.preview_title.pack(side="left", padx=(8, 0), fill="x", expand=True)

        self.open_btn = FlatButton(
            preview_head, "打开文件", self.open_selected, kind="soft", padx=10, pady=4,
            font=FONTS["small"],
        )
        self.open_btn.pack(side="right")
        self.open_btn.set_enabled(False)
        self.folder_btn = FlatButton(
            preview_head, "所在文件夹", self.reveal_selected, kind="ghost", padx=10, pady=4,
            font=FONTS["small"],
        )
        self.folder_btn.pack(side="right", padx=(0, 6))
        self.folder_btn.set_enabled(False)

        text_box = tk.Frame(preview_card, bg=CARD_BG)
        text_box.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 10))
        text_box.rowconfigure(0, weight=1)
        text_box.columnconfigure(0, weight=1)
        self.preview = tk.Text(
            text_box,
            bd=0,
            relief="flat",
            highlightthickness=0,
            bg=CARD_BG,
            fg=TEXT,
            font=FONTS["body"],
            wrap="word",
            padx=2,
            pady=2,
            spacing1=1,
            spacing3=2,
            cursor="arrow",
            insertwidth=0,
            selectbackground=CARD_BG,
            selectforeground=TEXT,
            inactiveselectbackground=CARD_BG,
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        preview_sb = ttk.Scrollbar(text_box, orient="vertical", command=self.preview.yview)
        preview_sb.grid(row=0, column=1, sticky="ns")
        self.preview.configure(yscrollcommand=preview_sb.set)
        self.preview.tag_configure("path", font=FONTS["body_bold"], foreground=TEXT)
        self.preview.tag_configure("meta", font=FONTS["small"], foreground=MUTED)
        self.preview.tag_configure("ln", font=FONTS["mono"], foreground=MUTED)
        self.preview.tag_configure("hl", background=HIGHLIGHT_BG, foreground=TEXT)
        self.preview.tag_configure("note", font=FONTS["small"], foreground=AMBER)
        self.preview.tag_configure("empty", font=FONTS["small"], foreground=MUTED)
        self._set_preview_message("选择上方结果，这里会显示匹配的行和上下文。")

    # -------------------------------------------------- 窗口 / 配置
    def _apply_window(self):
        geometry = self.settings.get("window_geometry") or ""
        match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry)
        if match and int(match.group(1)) >= 600 and int(match.group(2)) >= 400:
            try:
                self.geometry(geometry)
                self.after(40, self._clamp_window)
                return
            except tk.TclError:
                pass
        scale = ui_scale(self)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(int(1180 * scale), sw - 80)
        h = min(int(780 * scale), sh - 140)
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

    def _apply_settings(self):
        try:
            self.attributes("-topmost", bool(self.settings.get("always_on_top")))
        except tk.TclError:
            pass

    def _save_settings(self):
        settings = self.data.setdefault("settings", {})
        settings["paths"] = list(self.paths)
        settings["extensions"] = self.ext_text.get("1.0", "end-1c").strip()
        settings["exclude_dirs"] = self.exclude_var.get().strip()
        settings["recursive"] = bool(self.recursive_var.get())
        settings["case_sensitive"] = bool(self.case_var.get())
        settings["search_office"] = bool(self.office_var.get())
        settings["skip_hidden"] = bool(self.skip_hidden_var.get())
        try:
            settings["max_size_mb"] = max(1, min(1024, int(float(self.max_size_var.get()))))
        except (TypeError, ValueError):
            settings["max_size_mb"] = 20
            self.max_size_var.set("20")
        try:
            settings["max_results"] = max(100, min(50000, int(float(self.max_results_var.get()))))
        except (TypeError, ValueError):
            settings["max_results"] = 3000
            self.max_results_var.set("3000")
        try:
            if self.state() != "iconic":
                settings["window_geometry"] = self.geometry()
        except tk.TclError:
            pass
        try:
            write_config(self.data)
        except Exception:
            pass

    def _on_close(self):
        self.stop_event.set()
        self._save_settings()
        self.destroy()

    # -------------------------------------------------- 路径管理
    def _refresh_paths(self):
        self.path_list.delete(0, "end")
        for path in self.paths:
            self.path_list.insert("end", path)
            if not os.path.isdir(resolve_path(path)):
                self.path_list.itemconfig("end", foreground=RED_FG)
        self.path_count_label.configure(text="%d 个" % len(self.paths))

    def add_path(self):
        initial = self.paths[-1] if self.paths else os.path.expanduser("~")
        initial = resolve_path(initial)
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        chosen = filedialog.askdirectory(
            parent=self, title="选择要搜索的文件夹", initialdir=initial, mustexist=True
        )
        if not chosen:
            return
        chosen = os.path.normpath(chosen)
        existing = {os.path.normcase(resolve_path(p)) for p in self.paths}
        if os.path.normcase(chosen) in existing:
            messagebox.showinfo("提示", "这个文件夹已经在搜索范围里了。", parent=self)
            return
        self.paths.append(chosen)
        self._refresh_paths()
        self._save_settings()
        self._set_status("已添加：" + chosen)

    def remove_path(self):
        selection = list(self.path_list.curselection())
        if not selection:
            return
        for index in reversed(selection):
            if 0 <= index < len(self.paths):
                self.paths.pop(index)
        self._refresh_paths()
        self._save_settings()

    def open_selected_path(self):
        selection = self.path_list.curselection()
        if not selection:
            return
        path = resolve_path(self.paths[selection[0]])
        if not os.path.isdir(path):
            messagebox.showwarning("文件夹不存在", path, parent=self)
            return
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc), parent=self)

    # -------------------------------------------------- 搜索
    def _focus_query(self):
        self.query_entry.focus_set()
        self.query_entry.select_range(0, "end")

    def _collect_options(self):
        try:
            max_size = max(1, min(1024, int(float(self.max_size_var.get()))))
        except (TypeError, ValueError):
            max_size = 20
            self.max_size_var.set("20")
        try:
            max_results = max(100, min(50000, int(float(self.max_results_var.get()))))
        except (TypeError, ValueError):
            max_results = 3000
            self.max_results_var.set("3000")
        try:
            workers = max(0, min(64, int(self.settings.get("workers", 0))))
        except (TypeError, ValueError):
            workers = 0
        return {
            "recursive": bool(self.recursive_var.get()),
            "case_sensitive": bool(self.case_var.get()),
            "search_office": bool(self.office_var.get()),
            "skip_hidden": bool(self.skip_hidden_var.get()),
            "max_bytes": max_size * 1024 * 1024,
            "max_results": max_results,
            "extensions": parse_extensions(self.ext_text.get("1.0", "end-1c")),
            "exclude_dirs": parse_excludes(self.exclude_var.get()),
            "workers": workers,
        }

    def start_search(self):
        if self.searching:
            return
        query = self.query_entry.get().strip()
        if not query:
            messagebox.showinfo("提示", "请先输入要搜索的文字。", parent=self)
            self.query_entry.focus_set()
            return

        roots, missing = normalize_roots(self.paths)
        if not roots:
            messagebox.showwarning(
                "没有可搜索的文件夹",
                "请先在左侧添加一个存在的文件夹。",
                parent=self,
            )
            return

        opts = self._collect_options()
        self.max_results = opts["max_results"]
        self._save_settings()
        self._reset_results()

        self.searching = True
        self.worker_error = ""
        self.search_started = time.perf_counter()
        self.stop_event = threading.Event()
        self.worker = threading.Thread(
            target=self._search_worker,
            args=(query, roots, opts, self.stop_event),
            daemon=True,
        )
        self.worker.start()

        self.search_btn.set_enabled(False)
        self.stop_btn.set_enabled(True)
        self.progress.configure(mode="indeterminate", maximum=100, value=0)
        self.progress.start(12)
        if missing:
            self._set_status(
                "开始搜索…（%d 个路径不存在，已跳过）" % len(missing)
            )
        else:
            self._set_status("正在扫描目录…")
        self._schedule_pump()

    def stop_search(self):
        if not self.searching:
            return
        self.stop_event.set()
        self.stop_btn.set_enabled(False)
        self._set_status("正在停止…")

    def _reset_results(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results = []
        self.result_by_iid = {}
        self.current_hit = None
        self.truncated_results = False
        self.scanned = 0
        self.total = 0
        self.hit_files = 0
        self.hit_count = 0
        self.bytes_scanned = 0
        self.sort_col = "folder"
        self.sort_desc = False
        self._update_headings()
        self.result_label.configure(text="")
        self.preview_title.configure(text="")
        self.open_btn.set_enabled(False)
        self.folder_btn.set_enabled(False)
        self._set_preview_message("正在搜索…")
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=0)

    def _search_worker(self, query, roots, opts, stop_event):
        start = time.perf_counter()
        self.queue.put(("phase", "正在扫描目录…"))
        files = []
        try:
            for item in iter_files(roots, opts, stop_event):
                files.append(item)
                if len(files) % 500 == 0:
                    self.queue.put(("discovered", len(files)))
                if stop_event.is_set():
                    break
        except Exception as exc:
            self.queue.put(("error", "扫描目录失败：%s" % exc))

        if stop_event.is_set():
            self.queue.put(
                (
                    "done",
                    {
                        "stopped": True,
                        "total": len(files),
                        "done": 0,
                        "hits": 0,
                        "matches": 0,
                        "bytes": 0,
                        "elapsed": time.perf_counter() - start,
                    },
                )
            )
            return

        total = len(files)
        self.queue.put(("total", total))
        if not total:
            self.queue.put(
                (
                    "done",
                    {
                        "stopped": False,
                        "total": 0,
                        "done": 0,
                        "hits": 0,
                        "matches": 0,
                        "bytes": 0,
                        "elapsed": time.perf_counter() - start,
                    },
                )
            )
            return

        cpu = os.cpu_count() or 4
        workers = opts["workers"] or min(32, max(4, cpu * 2))
        completed = 0
        hits = 0
        matches = 0
        scanned = 0
        sent_hits = 0
        last_emit = 0.0
        search_start = time.perf_counter()

        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tqs")
        pending = {}
        iterator = iter(files)

        def submit_next():
            try:
                item = next(iterator)
            except StopIteration:
                return False
            future = executor.submit(search_one, item, query, opts, stop_event)
            pending[future] = item
            return True

        for _ in range(min(len(files), workers * 3)):
            submit_next()

        try:
            while pending and not stop_event.is_set():
                done, _ = wait(
                    tuple(pending.keys()),
                    timeout=0.12,
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    item = pending.pop(future, None)
                    if item is None:
                        continue
                    try:
                        hit, read_bytes = future.result()
                    except Exception:
                        hit, read_bytes = None, 0
                    completed += 1
                    scanned += read_bytes
                    if hit:
                        hits += 1
                        matches += hit["count"]
                        # 只把前 max_results 条送给界面，避免一次搜索几十万条时
                        # 大量队列事件拖慢界面；总数仍然准确统计。
                        if sent_hits < opts["max_results"]:
                            self.queue.put(("hit", hit))
                            sent_hits += 1
                    submit_next()
                now = time.perf_counter()
                if now - last_emit >= 0.1:
                    last_emit = now
                    self.queue.put(
                        (
                            "progress",
                            {
                                "done": completed,
                                "total": total,
                                "hits": hits,
                                "matches": matches,
                                "bytes": scanned,
                                "elapsed": now - search_start,
                            },
                        )
                    )
        finally:
            for future in pending:
                future.cancel()
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:  # Python 3.8
                executor.shutdown(wait=False)

        elapsed = time.perf_counter() - start
        self.queue.put(
            (
                "done",
                {
                    "stopped": stop_event.is_set(),
                    "total": total,
                    "done": completed,
                    "hits": hits,
                    "matches": matches,
                    "bytes": scanned,
                    "elapsed": elapsed,
                },
            )
        )

    def _schedule_pump(self):
        if self.pump_id is None:
            self.pump_id = self.after(60, self._pump)

    def _pump(self):
        self.pump_id = None
        processed = 0
        while processed < 300:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            if kind == "phase":
                self._set_status(payload)
            elif kind == "discovered":
                self._set_status("正在扫描目录… 已发现 %d 个文件" % payload)
            elif kind == "total":
                self.total = payload
                self.progress.stop()
                self.progress.configure(mode="determinate", maximum=max(1, self.total), value=0)
                self._set_status("发现 %d 个文件，开始搜索…" % self.total)
            elif kind == "hit":
                self._add_hit(payload)
            elif kind == "progress":
                self.scanned = payload["done"]
                self.total = payload["total"]
                self.hit_files = payload["hits"]
                self.hit_count = payload["matches"]
                self.bytes_scanned = payload["bytes"]
                self._update_progress()
                self._update_result_label()
                if not self.stop_event.is_set():
                    speed = self.bytes_scanned / (1024.0 * 1024.0) / max(
                        0.001, payload.get("elapsed", 0)
                    )
                    self._set_status(
                        "正在搜索… %d/%d 个文件 · 命中 %d 个文件（%d 处）· %.1f MB/s"
                        % (
                            self.scanned,
                            self.total,
                            self.hit_files,
                            self.hit_count,
                            speed,
                        )
                    )
            elif kind == "error":
                self.worker_error = payload
            elif kind == "done":
                self._finish_search(payload)

        if self.searching or not self.queue.empty():
            self._schedule_pump()

    def _add_hit(self, hit):
        self.hit_files += 1
        self.hit_count += hit["count"]
        if len(self.results) >= self.max_results:
            self.truncated_results = True
            self._update_result_label()
            return

        iid = "r%d" % len(self.results)
        self.results.append(hit)
        self.result_by_iid[iid] = hit
        count = str(hit["count"]) + ("+" if hit["truncated"] else "")
        first_line, first_col, _ = hit["snippets"][0]
        self.tree.insert(
            "",
            "end",
            iid=iid,
            values=(
                hit["name"],
                count,
                "%d:%d" % (first_line, first_col),
                format_size(hit["size"]),
                format_mtime(hit["mtime"]),
                hit["folder"],
            ),
            tags=("odd" if (len(self.results) - 1) % 2 else "even",),
        )
        self._update_result_label()

    def _finish_search(self, payload):
        self.searching = False
        self.stop_btn.set_enabled(False)
        self.search_btn.set_enabled(True)
        self.progress.stop()
        self.scanned = payload.get("done", self.scanned)
        self.total = payload.get("total", self.total)
        self.hit_files = payload.get("hits", self.hit_files)
        self.hit_count = payload.get("matches", self.hit_count)
        self.bytes_scanned = payload.get("bytes", self.bytes_scanned)
        self.truncated_results = self.hit_files > len(self.results)

        if self.total:
            self.progress.configure(maximum=max(1, self.total), value=self.scanned)
        else:
            self.progress.configure(maximum=100, value=0)

        elapsed = max(0.001, payload.get("elapsed", 0))
        speed = self.bytes_scanned / (1024.0 * 1024.0) / elapsed
        if payload.get("stopped"):
            self._set_status(
                "已停止：扫描 %d 个文件，命中 %d 个文件（%d 处）"
                % (self.scanned, self.hit_files, self.hit_count)
            )
        elif self.total == 0:
            self._set_status("没有找到符合条件的文件。检查路径、文件类型和大小限制。")
        else:
            self._set_status(
                "完成：扫描 %d 个文件，命中 %d 个文件（%d 处），用时 %.2f 秒，%.1f MB/s"
                % (
                    self.scanned,
                    self.hit_files,
                    self.hit_count,
                    elapsed,
                    speed,
                )
            )

        self._update_result_label()
        if self.results:
            self.sort_results(self.sort_col, self.sort_desc, quiet=True)
            if not self.tree.selection():
                self._set_preview_message(
                    "找到 %d 个文件，选择一行查看匹配内容。" % len(self.results)
                )
        else:
            self._set_preview_message("没有找到匹配的文字。")
        if self.worker_error:
            messagebox.showerror("搜索出错", self.worker_error, parent=self)
            self.worker_error = ""
        self.worker = None

    def _update_progress(self):
        if self.total:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=self.total, value=min(self.scanned, self.total))

    def _update_result_label(self):
        text = ""
        if self.searching or self.total or self.hit_files:
            text = "%d 个文件 · %d 处匹配" % (self.hit_files, self.hit_count)
            if self.truncated_results:
                text += " · 仅显示前 %d 个" % self.max_results
        self.result_label.configure(text=text)

    def _set_status(self, text):
        self.status_var.set(text)

    # -------------------------------------------------- 结果 / 预览
    def sort_results(self, column, desc=None, quiet=False):
        if column not in ("name", "count", "first", "size", "mtime", "folder", "path"):
            return
        if desc is None:
            desc = (self.sort_col == column and not self.sort_desc)
        self.sort_col = column
        self.sort_desc = bool(desc)

        def key(hit):
            if column == "name":
                return hit["name"].lower()
            if column == "count":
                return hit["count"]
            if column == "first":
                return hit["snippets"][0][0]
            if column == "size":
                return hit["size"]
            if column == "mtime":
                return hit["mtime"]
            return hit["path"].lower()

        self.results.sort(key=key, reverse=self.sort_desc)
        self._rebuild_tree()
        self._update_headings()
        if not quiet:
            self._set_status("已按「%s」排序" % self._column_label(column))

    def _column_label(self, column):
        return {
            "name": "文件名",
            "count": "匹配数",
            "first": "首个位置",
            "size": "大小",
            "mtime": "修改时间",
            "folder": "文件夹",
            "path": "路径",
        }.get(column, column)

    def _update_headings(self):
        labels = {
            "name": "文件名",
            "count": "匹配",
            "first": "首个位置",
            "size": "大小",
            "mtime": "修改时间",
            "folder": "所在文件夹",
        }
        for column, text in labels.items():
            if column == self.sort_col:
                text += " ▼" if self.sort_desc else " ▲"
            self.tree.heading(column, text=text)

    def _rebuild_tree(self):
        selected_path = self.current_hit["path"] if self.current_hit else None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.result_by_iid = {}
        selected_iid = None
        for index, hit in enumerate(self.results):
            iid = "r%d" % index
            self.result_by_iid[iid] = hit
            count = str(hit["count"]) + ("+" if hit["truncated"] else "")
            first_line, first_col, _ = hit["snippets"][0]
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    hit["name"],
                    count,
                    "%d:%d" % (first_line, first_col),
                    format_size(hit["size"]),
                    format_mtime(hit["mtime"]),
                    hit["folder"],
                ),
                tags=("odd" if index % 2 else "even",),
            )
            if selected_path and hit["path"] == selected_path:
                selected_iid = iid

        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
            self.current_hit = self.result_by_iid[selected_iid]
            self.open_btn.set_enabled(True)
            self.folder_btn.set_enabled(True)
        else:
            self.current_hit = None
            self.open_btn.set_enabled(False)
            self.folder_btn.set_enabled(False)
            self.preview_title.configure(text="")
            self._set_preview_message("选择上方结果，这里会显示匹配的行和上下文。")

    def _selected_hit(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self.result_by_iid.get(selection[0])

    def _on_tree_select(self, _event=None):
        hit = self._selected_hit()
        if not hit:
            self.current_hit = None
            self.open_btn.set_enabled(False)
            self.folder_btn.set_enabled(False)
            return
        self.current_hit = hit
        self.open_btn.set_enabled(True)
        self.folder_btn.set_enabled(True)
        self._show_preview(hit)

    def _set_preview_message(self, message):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", message, "empty")
        self.preview.configure(state="disabled")

    def _show_preview(self, hit):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview_title.configure(text=hit["name"])

        self.preview.insert("end", hit["path"] + "\n", "path")
        meta = "%s · 修改于 %s · 命中 %d 处" % (
            format_size(hit["size"]),
            format_mtime(hit["mtime"]),
            hit["count"],
        )
        if hit.get("source") == "office":
            meta += " · 从文档提取的文字"
        self.preview.insert("end", meta + "\n\n", "meta")

        query = self.query_entry.get().strip()
        for line_no, col, snippet in hit["snippets"]:
            self.preview.insert("end", "%6d:%-4d  " % (line_no, col), "ln")
            self._insert_highlighted(snippet, query)
            self.preview.insert("end", "\n")

        if hit["truncated"] or len(hit["snippets"]) < hit["count"]:
            self.preview.insert(
                "end",
                "\n仅显示前 %d 处匹配。\n" % len(hit["snippets"]),
                "note",
            )
        self.preview.configure(state="disabled")
        self.preview.yview_moveto(0)

    def _insert_highlighted(self, snippet, query):
        if not query:
            self.preview.insert("end", snippet)
            return
        case_sensitive = bool(self.case_var.get())
        hay = snippet if case_sensitive else snippet.lower()
        needle = query if case_sensitive else query.lower()
        start = 0
        while True:
            index = hay.find(needle, start)
            if index < 0:
                self.preview.insert("end", snippet[start:])
                break
            self.preview.insert("end", snippet[start:index])
            self.preview.insert("end", snippet[index:index + len(needle)], "hl")
            start = index + len(needle)
        return

    def _on_tree_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row not in self.tree.selection():
            self.tree.selection_set(row)
            self.tree.focus(row)
        hit = self.result_by_iid.get(row)
        if not hit:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="打开文件", command=self.open_selected)
        menu.add_command(label="在资源管理器中显示", command=self.reveal_selected)
        menu.add_command(label="复制文件路径", command=self.copy_selected_path)
        menu.add_separator()
        menu.add_command(label="复制匹配内容", command=self.copy_selected_matches)
        code = shutil.which("code")
        if code:
            menu.add_command(
                label="用 VS Code 打开（跳到行）",
                command=lambda h=hit: self.open_in_vscode(h),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # -------------------------------------------------- 打开 / 复制
    def open_selected(self):
        hit = self._selected_hit()
        if not hit:
            return
        try:
            if os.name == "nt":
                os.startfile(hit["path"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", hit["path"]])
            else:
                subprocess.Popen(["xdg-open", hit["path"]])
        except Exception as exc:
            messagebox.showerror("打开失败", "%s\n\n%s" % (hit["path"], exc), parent=self)

    def reveal_selected(self):
        hit = self._selected_hit()
        if not hit:
            return
        path = os.path.normpath(hit["path"])
        try:
            if os.name == "nt":
                subprocess.Popen('explorer /select,"%s"' % path.replace('"', ""))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc), parent=self)

    def copy_selected_path(self):
        hit = self._selected_hit()
        if not hit:
            return
        self.clipboard_clear()
        self.clipboard_append(hit["path"])
        self._set_status("已复制路径：" + hit["path"])

    def copy_selected_matches(self):
        hit = self._selected_hit()
        if not hit:
            return
        lines = [hit["path"], "命中 %d 处" % hit["count"], ""]
        for line_no, col, snippet in hit["snippets"]:
            lines.append("%d:%d  %s" % (line_no, col, snippet))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self._set_status("已复制 %d 处匹配内容" % len(hit["snippets"]))

    def open_in_vscode(self, hit):
        line = hit["snippets"][0][0]
        code = shutil.which("code")
        if not code:
            messagebox.showinfo("提示", "没有找到 VS Code 的 code 命令。", parent=self)
            return
        try:
            command = 'code -g "%s:%d"' % (hit["path"].replace('"', ""), line)
            subprocess.Popen(
                command,
                shell=True,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc), parent=self)

    # -------------------------------------------------- 导出
    def export_csv(self):
        if not self.results:
            messagebox.showinfo("提示", "还没有结果可以导出。", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="导出搜索结果",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            initialfile="文本快搜结果.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["文件名", "匹配数", "首个位置", "大小(字节)", "修改时间", "完整路径", "首个匹配内容"]
                )
                for hit in self.results:
                    first_line, first_col, snippet = hit["snippets"][0]
                    writer.writerow(
                        [
                            hit["name"],
                            hit["count"],
                            "%d:%d" % (first_line, first_col),
                            hit["size"],
                            format_mtime(hit["mtime"]),
                            hit["path"],
                            snippet,
                        ]
                    )
            self._set_status("已导出 %d 条结果：%s" % (len(self.results), path))
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
