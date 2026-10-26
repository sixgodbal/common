# sweet_editor 独立 Android 打包说明

这个目录是一份**独立的 Unity Android 工程**（从原 `MapEditor` 的构建副本整理而来），自带：

- `Assets` / `ProjectSettings` / `Packages`
- 最新的地图编辑代码（含“导出当前”）
- `Assets/StreamingAssets/MapEditorSeed.zip`（内置图片/地图资源）
- `Builds/Android/MapEditor.apk`（可安装的 APK）

它不再依赖原工程的构建脚本，可以直接在这里打包。

## 一、一键打包

双击：

- **`一键打包.bat`**：按配置重新生成资源包 → Unity 原地构建 → 输出 APK。保留 `Library` 和 `MapEditorSeed.zip`，下次构建更快。
- **`一键打包并清理.bat`**：流程相同，成功后删除 `Library`、`Temp` 和 `MapEditorSeed.zip`，但**不会删除工程、Assets、ProjectSettings 和 APK**。下次打包会重新导入并重新生成，速度会慢一些。

产物：

```
Builds\Android\MapEditor.apk
Builds\Android\MapEditor.apk.sha256
Builds\Android\build.log
```

> 打包时请先关闭这个工程的 Unity，否则脚本会提示项目被占用。

## 二、资源配置：资源路径.txt（优先）

打包脚本会优先读取根目录的 `资源路径.txt`，改完直接再次双击打包即可。

```text
MapElem=D:\sixgod\gitproject\test\Code\Demo\Assets\Data\Sprites\MapElem
Map=D:\sixgod\gitproject\test\Code\Demo\Assets\Data\Map
MapPreview=D:\sixgod\gitproject\test\Code\Demo\Assets\Data\Sprites\MapPreview
```

支持：

- `MapElem` / `Map` / `MapPreview` 三个目录
- 或者只填 `DataRoot`，脚本自动拼 `Sprites/MapElem`、`Map`、`Sprites/MapPreview`
- `#` / `;` / `//` 开头为注释
- 路径可以带引号，也可以不带
- 建议保存为 UTF-8，避免中文路径乱码

优先级：

1. `资源路径.txt` 里显式写的目录
2. `android-build.config.json` 里的同名目录（可选，兼容旧配置）
3. `资源路径.txt` / JSON 里的 `DataRoot` 自动拼接
4. 脚本默认路径

如果三个目录不在同一个根下，直接在 txt 里分别写：

```text
MapElem=E:\MyResources\MapElem
Map=E:\MyResources\Map
MapPreview=E:\MyResources\MapPreview
```

`android-build.config.json` 现在只保留 Unity 路径和行为选项：

```json
{
  "unityPath": "C:\\Program Files\\Unity\\Hub\\Editor\\2022.3.25f1\\Editor\\Unity.exe",
  "refreshSeed": true,
  "deleteSeedAfterBuild": false,
  "cleanLibraryAfterBuild": false
}
```

| 字段 | 含义 |
|---|---|
| `unityPath` | Unity 2022.3.25f1 的安装路径；换电脑时改这里 |
| `refreshSeed` | 是否在打包前重新生成 `MapEditorSeed.zip` |
| `deleteSeedAfterBuild` | 打包成功后是否删除工程内的 zip（APK 内已包含） |
| `cleanLibraryAfterBuild` | 打包成功后是否删除 Library/Temp |

打包时脚本会把三个目录里的：

- `MapElem/**/*.png` 和 `MapElemVisualConfig.json`
- `Map/**/*.bytes`
- `MapPreview/**/*.png`

打成一个 `Assets/StreamingAssets/MapEditorSeed.zip`。**不会**把散文件复制进工程，也不会修改源目录。脚本启动时会打印实际读取的 `资源路径.txt` 和三个最终目录，方便确认。

如果资源目录不存在但工程里已经有 `MapEditorSeed.zip`，脚本会提示并继续用现有 zip 打包；两者都没有才会失败。

更完整的实现细节见 `APK打包实现说明.md`。

## 三、直接运行脚本

```powershell
# 按配置打包
.\BuildStandalone.ps1

# 强制重新生成资源包
.\BuildStandalone.ps1 -RefreshSeed

# 跳过资源刷新，直接用现有 zip
.\BuildStandalone.ps1 -SkipSeed

# 打包成功后清理缓存和 zip
.\BuildStandalone.ps1 -DeleteSeedAfterBuild -CleanLibraryAfterBuild
```

脚本以自己所在目录为工程根目录，移动到任何路径都能用。

## 四、和原工程的关系

- 这份工程是**独立副本**，原工程 `D:\sixgod\gitproject\test\Code\MapEditor` 仍然存在，互不影响。
- 以后在这个目录里改代码、改场景，只影响这份 Android 工程；不会自动同步回原工程。
- 如果希望只维护一份源码，可以把这份工程作为新的主工程，或者把原工程的改动手动同步过来。
- 原工程的一键打包脚本（`BuildAndroid.ps1`）和两个 bat 不需要复制过来；这里用的是 `BuildStandalone.ps1`。

## 五、手机安装与功能

```powershell
adb install -r "D:\ai\git_tools\common\sweet_editor\Builds\Android\MapEditor.apk"
```

App 功能和之前一致：

- 首次启动解压内置资源到应用目录
- 单指绘制、双指平移/缩放
- 删除模式、撤销、保存、选取、缩放、适应
- **导出当前**：当前正在编辑的地图导出为 `<ID>.bytes` 到 `Download/MapEditor/`
- **导出全部**：Map + MapPreview 打包 ZIP
- 保存地图时生成预览图；Android 上跳过 pngquant

## 六、排查

- 提示“项目正在 Unity 中打开”：关闭这个工程的 Unity 再打包。
- 提示“资源目录不存在”：改 `android-build.config.json`，或先放一个可用的 `Assets/StreamingAssets/MapEditorSeed.zip`。
- 构建失败：看 `Builds/Android/build.log`，或运行 `adb logcat -s Unity` 看手机端日志。
- 第一次 `/ 清理后` 构建会重新导入资源，耗时比平时长；之后保留 `Library` 就会快。
