============================================================
 Cloudflare R2 拖拽上传便携工具包 (开箱即用版)
============================================================

【新电脑首次使用步骤】
1. 将压缩包解压到任意固定目录（建议不要放在临时目录，解压后不要随意移动文件夹位置；若移动了目录，重新运行一次第 2 步即可）。
2. 双击运行：
   setup-desktop-shortcuts.bat
   它会自动完成两件事：
   - 解除跨电脑拷贝文件的 Windows 安全锁定；
   - 在当前电脑桌面上生成「upload-to-r2.bat」和「download-launcher-manifest.bat」两个快捷方式。

------------------------------------------------------------
【日常使用方式】

1. 拖拽上传任意文件：
   把一个或多个文件直接拖到桌面上的「upload-to-r2.bat」快捷方式（或本目录下的 upload-to-r2.bat）上：
   - 普通文件默认上传至：
     https://download.supercrazy.site/guotang-star/<文件名>
   - 若拖入的文件名为 LauncherManifest.xml，会自动识别并覆盖上传至：
     https://download.supercrazy.site/launcher/LauncherManifest.xml
   - 上传成功后，公网下载直链会自动复制到剪贴板（可直接 Ctrl+V 粘贴）。

2. 下载线上 LauncherManifest.xml：
   双击桌面上的「download-launcher-manifest.bat」快捷方式（或本目录下的同名文件），
   会将线上最新的 LauncherManifest.xml 下载到当前电脑的桌面上。

3. 一键更新桌面上的 LauncherManifest.xml：
   修改完桌面上的 LauncherManifest.xml 后：
   - 方式 A：直接把它拖到桌面的「upload-to-r2.bat」快捷方式上；
   - 方式 B：双击本目录下的「update-launcher-manifest.bat」。

------------------------------------------------------------
【目录与配置说明】
- scripts\r2-upload.local.ps1
  已内置当前 R2 密钥与桶配置，桌面路径已改为自动识别当前电脑登录用户的桌面，无需手动修改。
  注意：本压缩包内含私有上传密钥，仅限内部信任电脑使用，请勿公开外传！
- tools\rclone\rclone.exe
  已内置 rclone 命令行客户端，无需安装或联网下载，离线内网/弱网环境均可直接使用。
