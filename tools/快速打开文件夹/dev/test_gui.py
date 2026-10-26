# -*- coding: utf-8 -*-
"""界面回归测试：卡片布局、自动换行、筛选、空状态、弹窗可构造。

不打开任何资源管理器窗口，不改写 config.json。
用法：python dev\\test_gui.py
"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYW = os.path.join(BASE, "快速打开.pyw")
spec = importlib.util.spec_from_file_location("quick_open", PYW)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

errors = []


def cards(app):
    return [w for w in app.inner.winfo_children() if isinstance(w, mod.GroupCard)]


def find_flow(widget):
    for child in widget.winfo_children():
        if isinstance(child, mod.FlowFrame):
            return child
        found = find_flow(child)
        if found:
            return found
    return None


def check_layout(app, tag):
    app.update()
    cs = cards(app)
    print("%s: %d 张卡片" % (tag, len(cs)))
    for card in cs:
        if card.winfo_height() < 60:
            errors.append("%s 卡片过矮：%s" % (tag, card.group["name"]))
        flow = find_flow(card)
        if not flow:
            continue
        boxes = [
            (k.winfo_x(), k.winfo_y(), k.winfo_width(), k.winfo_height())
            for k in flow.winfo_children()
        ]
        for i, (x, y, w, h) in enumerate(boxes):
            if w <= 0 or h <= 0:
                errors.append("%s 芯片尺寸为 0：%s" % (tag, card.group["name"]))
            if x + w > flow.winfo_width() + 1:
                errors.append("%s 芯片超出容器：%s" % (tag, card.group["name"]))
            for j in range(i + 1, len(boxes)):
                x2, y2, w2, h2 = boxes[j]
                if x < x2 + w2 and x2 < x + w and y < y2 + h2 and y2 < y + h:
                    errors.append("%s 芯片重叠：%s" % (tag, card.group["name"]))
            if y + h > flow.winfo_height() + 1:
                errors.append("%s FlowFrame 裁切：%s" % (tag, card.group["name"]))


def main():
    app = mod.App()
    try:
        app.geometry("860x700")
        app.update()
        check_layout(app, "初始")
        if len(cards(app)) != len(app.data["groups"]):
            errors.append("卡片数与分组数不一致")

        # 加一个含 14 个文件夹的分组，验证自动换行
        app.data["groups"].insert(
            0,
            {
                "id": "layout_test",
                "name": "布局压力测试",
                "color": mod.PALETTE[3],
                "items": [
                    {"id": "lt%d" % i, "name": "文件夹 %02d 名称稍长" % i, "path": "%TEMP%"}
                    for i in range(14)
                ],
            },
        )
        app.rebuild()
        app.update()
        check_layout(app, "窄窗口")
        card = app.inner.winfo_children()[0]
        flow = find_flow(card)
        rows = {k.winfo_y() for k in flow.winfo_children()}
        print("压力卡片高度=%d，芯片 %d 个，%d 行" % (card.winfo_height(), len(flow.winfo_children()), len(rows)))
        if len(rows) < 2:
            errors.append("14 个文件夹没有换行")

        # 筛选
        app.search_var.set("文件夹 03")
        app.update()
        if len(cards(app)) != 1:
            errors.append("按文件夹名筛选结果不对：%d" % len(cards(app)))

        app.search_var.set("zzz-不存在")
        app.update()
        if cards(app):
            errors.append("无匹配时应显示空状态")
        if not any(isinstance(w, mod.tk.Frame) for w in app.inner.winfo_children()):
            errors.append("空状态卡片缺失")

        app.search_var.set("")
        app.update()
        if len(cards(app)) != len(app.data["groups"]):
            errors.append("清空筛选后卡片未恢复")

        # 弹窗能构造（不保存）
        dlg = mod.ConfigDialog(app)
        app.update()
        dlg.destroy()
        app.update()
        sd = mod.SettingsDialog(app)
        app.update()
        sd.destroy()
        print("配置/设置弹窗构造正常")
    finally:
        app.destroy()

    if errors:
        print("FAILED:")
        for e in dict.fromkeys(errors):
            print(" -", e)
        return 1
    print("GUI OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
