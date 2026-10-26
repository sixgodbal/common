# 文本快搜

在指定文件夹里搜索**文件内部的文字**，找出文字出现在哪个文件、哪一行。
和 Everything 的区别：Everything 搜文件名，本工具搜文件内容。

- 点「开始查找」才扫描，不建常驻索引，不占后台资源
- 多线程读取文件，具体速度取决于磁盘、文件大小和是否命中；小文件很多时主要受文件系统影响
- 纯 Python 标准库（tkinter），不需要安装任何依赖
- 不联网、不写注册表，配置只保存在本目录的 `config.json`

## 启动

1. 双击 `文本快搜.pyw`（推荐，不会弹出黑色命令行窗口）
2. 或者双击 `启动.bat`

需要本机有 Python 3.8 及以上版本（安装时勾选 tcl/tk，默认就有）。

想放到桌面 / 任务栏：右键 `文本快搜.pyw` → 发送到 → 桌面快捷方式；
再右键快捷方式 → 固定到任务栏即可。

## 使用

1. 左侧「搜索范围」添加一个或多个文件夹（Ctrl+O 也可以）
2. 输入要查找的文字，按回车或点「开始查找」
3. 下方列表就是命中的文件；点一行，右下角显示匹配的行号和内容

| 操作 | 效果 |
| --- | --- |
| 双击结果行 | 用系统默认程序打开文件 |
| 右键结果行 | 打开文件 / 在资源管理器中显示 / 复制路径 / 复制匹配内容 |
| 点表头 | 按文件名、匹配数、位置、大小、修改时间、文件夹排序 |
| 双击左侧路径 | 在资源管理器中打开该文件夹 |
| 「导出 CSV」 | 把当前结果导出成 Excel 能直接打开的 CSV |

快捷键：`Enter` 开始搜索，`Esc` 停止，`F5` 再次搜索，`Ctrl+O` 添加文件夹，`Ctrl+F` 聚焦搜索框。

## 支持的文件

默认搜索这些类型（可以在左侧「文件类型」里改，逗号分隔；留空表示所有文件）：

- 文本 / 代码：txt、md、log、csv、json、xml、html、css、js、ts、py、java、c/cpp、cs、go、rs、php、sql、sh、bat、ps1、yml、ini、toml、tex 等
- Office：docx、docm、xlsx、xlsm、pptx、pptm
- 电子书 / 开放文档：epub、odt、ods、odp
- 邮件文本：eml

Office / EPUB 会先解压并提取文字再搜索，所以比纯文本慢一些；不需要时取消勾选「搜索 Office / EPUB 文档」可以更快。

## 速度说明

- 搜索在后台线程池里并行读取，界面不会卡住
- 默认最多读取 20 MB 的文件，可在「最大文件」里调整
- 默认跳过隐藏 / 系统文件，并排除 `.git`、`node_modules`、`__pycache__`、`venv` 等目录
- 只对命中的文件做完整解码和行号计算，未命中的文件只做一次字节查找
- 支持 UTF-8、GB18030（GBK）、UTF-16/UTF-32（带 BOM 或可识别）编码

## 配置文件

位置：本目录下的 `config.json`（第一次运行自动生成）。

```json
{
  "version": 1,
  "settings": {
    "paths": ["C:\\Users\\你的名字\\Documents"],
    "extensions": "txt,md,py,docx,xlsx,pptx",
    "exclude_dirs": ".git,node_modules,__pycache__,.venv,venv",
    "recursive": true,
    "case_sensitive": false,
    "search_office": true,
    "skip_hidden": true,
    "max_size_mb": 20,
    "max_results": 3000,
    "workers": 0,
    "always_on_top": false,
    "window_geometry": ""
  }
}
```

- `workers`：0 表示自动（最多 32 个线程）；机械硬盘可以改成 8 左右，减少来回寻道
- `max_results`：界面最多显示多少个命中文件；命中更多时仍会统计总数
- `paths` 支持环境变量（`%USERPROFILE%\Desktop`）和相对本程序目录的相对路径
- 手动改完 `config.json` 后重启工具生效
- 配置文件写坏时，会把原文件备份成 `config.json.broken`，再生成一份默认配置

## 限制

- 不支持 PDF、旧版 doc/xls/ppt（二进制格式需要额外的解析库）
- 不支持压缩包内部的文件（zip/rar/7z 等）
- 加密文档、损坏文档会跳过
- Office 文档提取的是文字层，行号是提取后文本的行号，不是 Word/Excel 里的页码
- 默认跳过大于 20 MB 的文件；需要时在界面里调大

## 开发 / 维护

功能清单、代码地图、性能陷阱和测试方法见 `开发文档.md`。

## 备份 / 迁移

整个 `文本快搜` 目录拷到新电脑就能用（路径不同的话改 `config.json` 即可）。

## 卸载

直接删掉这个目录即可，不会留下其它东西。
