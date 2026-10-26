# sweet_editor APK 打包实现说明

本文记录 `D:\ai\git_tools\common\sweet_editor` 这个独立 Android 工程的打包实现，以及它相对原 `MapEditor` 工程做了哪些变化。

## 一、背景

原工程：

```
D:\sixgod\gitproject\test\Code\MapEditor
Unity 2022.3.27f1c1
```

原来的 Android 打包方式：

1. `BuildAndroid.ps1` 把 `Assets`、`ProjectSettings`、`Packages` 同步到构建副本
   `D:\sixgod\gitproject\test\Code\MapEditor_AndroidBuild`；
2. 用 `C:\Program Files\Unity\Hub\Editor\2022.3.25f1\Editor\Unity.exe`
   以 `-buildTarget Android -executeMethod BuildAndroid.BuildApk` 构建；
3. 把 APK 复制回原工程的 `Builds\Android\MapEditor.apk`。

现在把构建副本整理成了独立工程：

```
D:\ai\git_tools\common\sweet_editor
Unity 2022.3.25f1（原地构建，不再复制副本）
```

它的目的：

- Android 工程可以脱离原工程单独存在；
- 图片/地图资源路径集中记录在 `资源路径.txt`，改完直接打包；
- 不再依赖原工程的 `BuildAndroid.ps1` 和构建副本。

## 二、相对源工程的主要变化

| 项目 | 原工程 / 原流程 | sweet_editor |
|---|---|---|
| 工程位置 | `D:\sixgod\gitproject\test\Code\MapEditor` | `D:\ai\git_tools\common\sweet_editor` |
| Unity 版本 | 2022.3.27f1c1（没有 Android 模块） | 2022.3.25f1（含 Android 支持） |
| 构建方式 | 同步到同级 `MapEditor_AndroidBuild` 再构建 | **原地构建**，不再生成构建副本 |
| 打包入口 | `BuildAndroid.ps1` | `BuildStandalone.ps1` |
| 双击入口 | 源工程的 `一键打包.bat` | 本工程的 `一键打包.bat` / `一键打包并清理.bat` |
| 资源路径 | `-SeedSourceRoot` / 自动查找 Demo | **`资源路径.txt`（优先）** + JSON 兜底 |
| 资源落点 | `Assets/StreamingAssets/MapEditorSeed.zip` | 相同 |
| 运行时代码 | 源工程最新代码 | 原构建副本快照，含“导出当前/导出全部” |
| APK 输出 | 源工程 `Builds\Android\MapEditor.apk` | 本工程 `Builds\Android\MapEditor.apk` |
| 源码同步 | — | **不自动同步**，本工程是独立副本 |

说明：

- `sweet_editor` 的 `Assets` 来自原工程的 Android 构建副本，是**运行时快照**，包含：
  - 触屏输入、双指缩放、删除模式；
  - “导出当前 / 导出全部”；
  - 地图列表缩略图惰性加载；
  - 首次启动解压内置资源；
  - Android 下跳过 pngquant。
- 原工程仍然是 `2022.3.27f1c1` 的桌面工程；本工程是 `2022.3.25f1` 的 Android 工程。
- 本工程不包含原工程的 `BuildAndroid.ps1`、原版 bat、`AGENTS.md` 等根目录文件；改用下面的新文件。

## 三、目录结构

```
D:\ai\git_tools\common\sweet_editor\
├─ Assets\
│  ├─ Scenes\Main.unity
│  ├─ Scripts\                     ← 地图编辑器运行时代码
│  ├─ Editor\BuildAndroid.cs       ← Mono/ARMv7 构建参数
│  ├─ Editor\AndroidSeedBuilder.cs ← Unity 菜单里的资源包生成（可选）
│  └─ StreamingAssets\
│     ├─ MapEditorSeed.zip         ← 内置资源包（首次启动解压到手机）
│     └─ libs\Pngyu\               ← Windows 工具，Android 不调用
├─ ProjectSettings\
├─ Packages\
├─ Builds\Android\
│  ├─ MapEditor.apk
│  ├─ MapEditor.apk.sha256
│  └─ build.log
├─ 资源路径.txt                     ← 资源路径（优先）
├─ android-build.config.json        ← Unity 路径 / 行为选项
├─ BuildStandalone.ps1              ← 原地打包脚本
├─ 一键打包.bat                     ← 保留缓存
├─ 一键打包并清理.bat               ← 打包后删 Library/Temp/zip
├─ ANDROID.md                       ← 使用说明
└─ APK打包实现说明.md               ← 本文
```

`Library`、`Temp`、`Logs`、`UserSettings` 都是 Unity 生成/本地缓存，可以删除或忽略。

## 四、资源路径

### 1. 资源路径.txt（优先）

打包脚本优先读取工程根目录的 `资源路径.txt`：

```text
MapElem=D:\sixgod\gitproject\test\Code\Demo\Assets\Data\Sprites\MapElem
Map=D:\sixgod\gitproject\test\Code\Demo\Assets\Data\Map
MapPreview=D:\sixgod\gitproject\test\Code\Demo\Assets\Data\Sprites\MapPreview
```

也支持只填根目录：

```text
DataRoot=D:\sixgod\gitproject\test\Code\Demo\Assets\Data
```

脚本会自动拼：

- `DataRoot\Sprites\MapElem`
- `DataRoot\Map`
- `DataRoot\Sprites\MapPreview`

规则：

- 以 `#`、`;`、`//` 开头的行是注释；
- 路径可以带引号，也可以不带；
- 建议把 txt 保存为 UTF-8，避免中文路径乱码；
- 三个显式目录优先级高于 `DataRoot`。

优先级顺序：

1. `资源路径.txt` 的 `MapElem` / `Map` / `MapPreview`
2. `android-build.config.json` 的同名字段（兼容旧配置，可留空）
3. `资源路径.txt` 或 JSON 的 `DataRoot` 自动拼接
4. 脚本默认路径

脚本每次启动会打印：

```
资源路径文件: ...\资源路径.txt
MapElem: ...
Map: ...
MapPreview: ...
```

### 2. 资源打包方式

只把以下文件打成一个 zip：

- `MapElem/**/*.png`
- `MapElem/MapElemVisualConfig.json`
- `Map/**/*.bytes`
- `MapPreview/**/*.png`

输出：

```
Assets\StreamingAssets\MapEditorSeed.zip
```

注意：

- **不会**把散文件复制进工程，也不会修改资源源目录；
- `.meta` 文件会被过滤掉；
- zip 使用 `NoCompression`，保证打包速度；
- APK 内包含这个 zip；手机首次启动解压到应用目录。

如果资源目录不存在：

- 工程里已有 `MapEditorSeed.zip` → 提示并继续用现有 zip；
- 两者都没有 → 打包失败，并提示检查 `资源路径.txt`。

## 五、打包流程

双击 `一键打包.bat` 后：

1. 读取 `android-build.config.json`：
   - Unity 路径；
   - 是否刷新资源；
   - 是否在成功后删除 zip / Library。
2. 读取 `资源路径.txt`，确定三个资源目录。
3. 检查目录，生成 `Assets\StreamingAssets\MapEditorSeed.zip`。
4. 检查：
   - 工程根目录是否有 `Assets`；
   - Unity 是否存在；
   - 这个工程是否正在 Unity 中打开；
   - `Temp\UnityLockfile` 是否存在。
5. 备份旧 APK 到 `MapEditor.apk.bak`，然后移走旧 APK，强制本次写出新产物。
6. 启动：

```
Unity.exe -batchmode -nographics -quit -buildTarget Android
  -projectPath <sweet_editor>
  -executeMethod BuildAndroid.BuildApk
  -logFile Builds\Android\build.log
```

7. 通过日志中的 `Build Finished, Result: Success` / `BuildAndroid ... MB` 判断成功；
   失败时恢复上一次 APK。
8. 计算 SHA256，写入 `Builds\Android\MapEditor.apk.sha256`。
9. 可选清理：
   - `-DeleteSeedAfterBuild`：删除工程内 `MapEditorSeed.zip`；
   - `-CleanLibraryAfterBuild`：删除 `Library`、`Temp`；
   - **不会删除工程、Assets、ProjectSettings、APK**。
10. bat 打开 `Builds\Android` 并暂停。

## 六、Android 构建参数

构建参数在 `Assets/Editor/BuildAndroid.cs`，本工程沿用之前的配置：

| 参数 | 值 |
|---|---|
| 包名 | `com.sixgod.mapeditor` |
| 版本 | `1.0.0`，versionCode 1 |
| minSdk | 24（Android 7.0） |
| targetSdk / compileSdk | 32 |
| 脚本后端 | Mono（`Mono2x`） |
| CPU | `armeabi-v7a`（ARMv7，32 位） |
| 托管裁剪 | Disabled + `Assets/link.xml` |
| 图形 API | OpenGL ES 3 |
| 屏幕方向 | 横屏自动旋转（左/右） |
| 场景 | `Assets/Scenes/Main.unity` |
| 输出 | `Builds/Android/MapEditor.apk` |
| 签名 | `%USERPROFILE%\.android\mapeditor.keystore`，密码/别名 `mapeditor` |

> Mono 的 Android 后端只支持 32 位 ARMv7。64 位-only 手机上安装会报
> `INSTALL_FAILED_NO_MATCHING_ABIS`，需要改成 `IL2CPP + ARM64` 重新构建。

## 七、运行时代码（相对源工程）

本工程的运行时代码与源工程的 Android 版本一致，主要包括：

- `AndroidSupport.cs`
  - 应用目录：`Application.persistentDataPath/MapEditor`
  - 用 `UnityWebRequest` 读取 APK 内 `StreamingAssets/MapEditorSeed.zip`
  - 后台线程解压资源
  - `MediaStore` 导出到 `Download/MapEditor`
  - BinaryFormatter 启动自检
- `MapEditorBootstrap.cs`
  - 首次启动解压进度/重试
  - 导出进度
  - 横屏和屏幕常亮
- `MobileControlsPanel.cs`
  - 左下角 9 个按钮：删除、撤销、保存、选取、缩小、放大、适应、导出全部、导出当前
- `ViewManager.cs`
  - 单指绘制、双指平移/缩放
  - 按下不立即落笔，超过阈值或抬起才落笔，避免双指误画
  - 删除模式
  - 地图预览图按可视区域加载
  - 单张地图导出
- `MapItem.cs` / `MapEditorThumbnailCache.cs`
  - 320px 缩略图 + 引用计数释放，避免 425 张预览图 OOM
- `MapEditorSettings.cs` / `MapEditorSettingsPanel.cs`
  - Android 默认使用应用目录
  - 触屏字号/布局
- `PngCompressor.cs`
  - Android 跳过 pngquant 和 explorer.exe
- `Assets/link.xml`
  - 保留 `Assembly-CSharp`，保护 BinaryFormatter 反射

这些代码不是本次重写的，而是从原工程 Android 构建副本继承；本次新增的是独立打包工具和资源配置。

## 八、APK 校验结果

最近一次构建：

- 路径：`Builds\Android\MapEditor.apk`
- 大小：94.4 MB
- SHA256：`8CE86B0BCF361918AFB2ED8B94D470D1628AD6220A173781E6A29C14C223297A`
- `aapt`：包名 `com.sixgod.mapeditor`，minSdk 24，targetSdk 32，`armeabi-v7a`
- `apksigner`：release 签名校验通过
- `Assembly-CSharp.dll` 中确认存在 `ExportCurrentMap`、`导出当前`、`导出全部`
- `assets/MapEditorSeed.zip` 已打进 APK

目前只做了构建和静态校验，**还没有在手机上实机运行验证**。实机安装后建议先确认：

1. 首次启动解压资源；
2. 加载一张地图；
3. 单指绘制、双指缩放；
4. 保存地图；
5. “导出当前”生成 `Download/MapEditor/<ID>.bytes`。

## 九、常用命令

```powershell
# 按 资源路径.txt 打包（保留 Library）
.\BuildStandalone.ps1

# 强制重新生成 zip
.\BuildStandalone.ps1 -RefreshSeed

# 跳过资源刷新
.\BuildStandalone.ps1 -SkipSeed

# 成功后清理 Library/Temp 和 zip
.\BuildStandalone.ps1 -DeleteSeedAfterBuild -CleanLibraryAfterBuild
```

## 十、维护注意事项

- 本工程请用 **Unity 2022.3.25f1** 打开；不要用 2022.3.27f1c1 打开后保存，否则工程版本会升级，25 的构建可能提示版本不兼容。
- 本工程是源工程的独立副本，**不会自动双向同步**。如果后续在源工程改代码，需要手动同步到本工程的 `Assets`，或者以后直接把本工程当主工程。
- 修改 `资源路径.txt` 后不需要改脚本；下一次双击打包会生效。
- 修改 `android-build.config.json` 的 `unityPath` 可适配另一台电脑/Unity 安装路径。
- 换电脑后签名文件 `%USERPROFILE%\.android\mapeditor.keystore` 不在工程里：
  - 覆盖安装旧 APK 会因签名不同失败；
  - 需要先卸载，或把旧 keystore 拷到新电脑同一路径。
- `Library` 约 1GB，属于缓存，可随时删除；删除后下一次构建会重新导入，速度变慢。
- 如果编辑过 `.bat`，请保持 **GBK/ANSI + CRLF** 行尾；用 UTF-8/LF 保存可能导致 cmd 报语法异常。
- 构建失败看 `Builds\Android\build.log`；手机端问题用 `adb logcat -s Unity`。
