# -*- coding: utf-8 -*-
"""Win11 标签页真机测试。

会短暂创建 1 个资源管理器窗口（n 个标签），校验后自动关闭，并删除临时目录。
用法：python dev\\test_tabs.py
非 Windows 11（22H2+）或缺少 explorer_tabs.ps1 时自动跳过。
"""
import ctypes
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYW = os.path.join(BASE, "快速打开.pyw")
spec = importlib.util.spec_from_file_location("quick_open", PYW)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

PS_QUERY = r'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$w = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]%d)
"TITLE=" + $w.Current.Name
$top = $w.Current.BoundingRectangle.Top
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)
foreach ($t in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)) {
  if ($t.Current.ClassName -ne "ListViewItem") { continue }
  $r = $t.Current.BoundingRectangle
  if (($r.Top - $top) -gt 90) { continue }
  "TAB=" + $t.Current.Name
}
'''


def read_tabs(hwnd):
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS_QUERY % hwnd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    title = ""
    tabs = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("TITLE="):
            title = line[6:]
        elif line.startswith("TAB="):
            tabs.append(line[4:])
    return title, tabs


def main():
    if not mod.tabs_supported():
        print("SKIP：当前系统不支持资源管理器标签页")
        return 0
    if not os.path.isfile(mod.TABS_SCRIPT):
        print("SKIP：缺少 %s" % mod.TABS_SCRIPT)
        return 0

    counts = 4
    dirs = [tempfile.mkdtemp(prefix="标签测试_%d_" % i) for i in range(counts)]
    leaves = [os.path.basename(d) for d in dirs]
    errors = []
    hwnd = 0
    try:
        before = mod._explorer_windows()
        t0 = time.time()
        opened, open_errors = mod.open_in_tabs(dirs)
        elapsed = time.time() - t0
        print("打开 %d/%d，耗时 %.2fs（%.2fs/标签）" % (opened, counts, elapsed, elapsed / (counts - 1)))
        if open_errors:
            errors.extend(open_errors)

        new = mod._explorer_windows() - before
        print("新增资源管理器窗口：%d" % len(new))
        if len(new) != 1:
            errors.append("应只新增 1 个窗口，实际 %d" % len(new))
        if new:
            hwnd = list(new)[0]

        if opened != counts:
            errors.append("应打开 %d 个标签，实际 %d" % (counts, opened))

        if hwnd:
            title, tabs = read_tabs(hwnd)
            print("窗口标题：%s" % title)
            print("标签：%s" % " | ".join(tabs))
            for leaf in leaves:
                if not any(leaf == t or leaf in t for t in tabs):
                    errors.append("缺少标签：%s" % leaf)
            if len(tabs) != counts:
                errors.append("标签数应为 %d，实际 %d" % (counts, len(tabs)))
    finally:
        if hwnd:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            time.sleep(0.4)
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)

    if errors:
        print("FAILED:")
        for e in dict.fromkeys(errors):
            print(" -", e)
        return 1
    print("TABS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
