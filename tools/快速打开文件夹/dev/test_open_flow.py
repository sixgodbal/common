# -*- coding: utf-8 -*-
"""打开流程测试：缺失路径确认、全部缺失、空分组。

用 monkeypatch 替换 open_path 与 messagebox，不会真的弹出资源管理器窗口。
用法：python dev\\test_open_flow.py
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYW = os.path.join(BASE, "快速打开.pyw")
spec = importlib.util.spec_from_file_location("quick_open", PYW)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

opened = []
warnings = []
asks = []

mod.open_path = lambda p: opened.append(p)
mod.messagebox.showwarning = lambda title, msg, **kw: warnings.append((title, msg))
mod.messagebox.showinfo = lambda title, msg, **kw: warnings.append((title, msg))


def fake_ask(title, msg, **kw):
    asks.append((title, msg))
    return True


mod.messagebox.askyesno = fake_ask

errors = []
dirs = [tempfile.mkdtemp(prefix="打开流程_%d_" % i) for i in range(3)]
missing = os.path.join(dirs[0], "不存在的子目录")


def main():
    app = mod.App()
    app.withdraw()
    try:
        app.data["settings"]["open_mode"] = "windows"
        app.data["settings"]["open_delay_ms"] = 0
        group = {
            "id": "flow",
            "name": "流程测试",
            "color": mod.PALETTE[0],
            "items": [{"id": "d%d" % i, "name": "目录%d" % i, "path": d} for i, d in enumerate(dirs)]
            + [{"id": "m", "name": "缺失", "path": missing}],
        }

        # 3 个存在 + 1 个缺失：确认后打开 3 个
        app.open_items(group, group["items"])
        deadline = time.time() + 5
        while time.time() < deadline and len(opened) < 3:
            app.update()
            time.sleep(0.05)
        print("打开 %d 个，确认框 %d 个" % (len(opened), len(asks)))
        if len(opened) != 3:
            errors.append("应打开 3 个，实际 %d" % len(opened))
        if len(asks) != 1:
            errors.append("应弹出 1 次确认框")
        elif "路径不存在" not in asks[0][0]:
            errors.append("确认框标题不正确")

        # 只剩缺失项：只警告，不打开
        opened.clear()
        warnings.clear()
        app.open_items(group, [{"id": "m", "name": "缺失", "path": missing}])
        app.update()
        if opened:
            errors.append("全部缺失时不应打开任何文件夹")
        if not warnings or "路径不存在" not in warnings[0][0]:
            errors.append("全部缺失时应给出警告")

        # 空分组：提示，不打开
        opened.clear()
        warnings.clear()
        app.open_items(group, [])
        app.update()
        if opened:
            errors.append("空分组不应打开任何文件夹")
        if not warnings:
            errors.append("空分组应给出提示")

        # 相对路径解析
        rel = mod.resolve_path(".")
        if os.path.normcase(rel) != os.path.normcase(mod.BASE_DIR):
            errors.append("相对路径解析错误：%s" % rel)
        env = mod.resolve_path("%TEMP%")
        if not os.path.isdir(env):
            errors.append("环境变量解析错误：%s" % env)
    finally:
        app.destroy()

    if errors:
        print("FAILED:")
        for e in dict.fromkeys(errors):
            print(" -", e)
        return 1
    print("OPEN FLOW OK")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)
    sys.exit(code)
