大厅服：放sweetmanager后台，lobby server、hotfix
125.208.22.224
Administrator
jiGPpcE0TJLkPQ4M


战斗服：放battle server
121.196.158.62
Administrator
QQqianda66

打包部署游戏服：
打包前记得更新服务器的xls，\SweetServer_IOCP\Configs
\SweetServer_IOCP\BuildTools\build_all_release.ps1 运行打包后会生成battle server和lobby server，放到各自的服务器，先启动lobbyserver的run.bat再启动battle server的run.bat即可


打包部署后台：
打包前记得更新xls：\sweet_manager\conf\qa\json
\sweet_manager\scripts\package_sweetmanager.bat 打包后会生成sweet_manager的文件夹，直接拖到服务器上即可使用。run.bat启动（会自动查找已启动的sweet manager关闭进程，并重启当前目录的sweetmanager）



发布启动器版本，更多参考R2-Upload-Portable.zip：
unity上菜单->build->导出启动器客户端包
打包完成后生成LauncherManifest.Client.windows.template.xml和windows_sweetman_版本号.zip
LauncherManifest.Client.windows.template.xml里存放的是此包的hash，把它复制覆盖到LauncherManifest.xml对应位置里，然后把LauncherManifest.xml拖动到upload-to-r2.bat它会自动上传到远端服务器上。
windows_sweetman_版本号.zip就是客户端包，拖动到upload-to-r2.bat它会自动上传到远端服务器上。


LauncherManifest.xml解释
它是启动器的配置，包含了mac、windows的启动器自身版本配置文件以及游戏客户端版本的配置文件。
配置里的字段：
    PackageUrl 下载地址，每次更新地址前面都不变只是改下版本号就可以。
    PackageHash 从LauncherManifest.Client.windows.template.xml里复制即可。
    PackageName、MinVersion 必须填对名字以及当前版本号
    

