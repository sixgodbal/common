param(
    [string]$ProjectPath = "",
    [string]$UnityPath = "",
    [string]$ConfigPath = "",
    [switch]$RefreshSeed,
    [switch]$SkipSeed,
    [switch]$DeleteSeedAfterBuild,
    [switch]$CleanLibraryAfterBuild
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = $PSScriptRoot
}
$ProjectPath = [System.IO.Path]::GetFullPath($ProjectPath)
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = [System.IO.Path]::Combine($ProjectPath, "android-build.config.json")
}

$config = $null
if (Test-Path -LiteralPath $ConfigPath) {
    try {
        $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    }
    catch {
        throw "配置文件解析失败: $ConfigPath`n$($_.Exception.Message)"
    }
}

function Get-ConfigValue {
    param([string]$Name, $Default)
    if ($config -ne $null -and $config.PSObject.Properties.Name -contains $Name) {
        $value = $config.$Name
        if ($null -ne $value) {
            return $value
        }
    }
    return $Default
}

if ([string]::IsNullOrWhiteSpace($UnityPath)) {
    $UnityPath = [string](Get-ConfigValue -Name "unityPath" -Default "C:\Program Files\Unity\Hub\Editor\2022.3.25f1\Editor\Unity.exe")
}

$dataRoot = [string](Get-ConfigValue -Name "dataRoot" -Default "D:\sixgod\gitproject\test\Code\Demo\Assets\Data")
$mapElemDirectory = [string](Get-ConfigValue -Name "mapElemDirectory" -Default "")
$mapDirectory = [string](Get-ConfigValue -Name "mapDirectory" -Default "")
$mapPreviewDirectory = [string](Get-ConfigValue -Name "mapPreviewDirectory" -Default "")

# 资源路径优先读工程根目录的 资源路径.txt，方便直接手改。
# 支持：DataRoot / MapElem / Map / MapPreview，格式为 key=value，# 或 ; 开头为注释。
$resourcePathFile = [System.IO.Path]::Combine($ProjectPath, "资源路径.txt")
$resourcePathFileUsed = $false
$resourcePaths = @{}
if (Test-Path -LiteralPath $resourcePathFile) {
    $resourcePathFileUsed = $true
    foreach ($line in Get-Content -LiteralPath $resourcePathFile -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#") -or $trimmed.StartsWith(";") -or $trimmed.StartsWith("//")) {
            continue
        }

        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2).Trim()
        }
        if ($key.Length -gt 0 -and $value.Length -gt 0) {
            $resourcePaths[$key] = $value
        }
    }
}

if ($resourcePaths.ContainsKey("DataRoot")) {
    $dataRoot = $resourcePaths["DataRoot"]
}
if ($resourcePaths.ContainsKey("MapElem")) {
    $mapElemDirectory = $resourcePaths["MapElem"]
}
if ($resourcePaths.ContainsKey("Map")) {
    $mapDirectory = $resourcePaths["Map"]
}
if ($resourcePaths.ContainsKey("MapPreview")) {
    $mapPreviewDirectory = $resourcePaths["MapPreview"]
}

if ([string]::IsNullOrWhiteSpace($mapElemDirectory)) {
    $mapElemDirectory = [System.IO.Path]::Combine($dataRoot, "Sprites", "MapElem")
}
if ([string]::IsNullOrWhiteSpace($mapDirectory)) {
    $mapDirectory = [System.IO.Path]::Combine($dataRoot, "Map")
}
if ([string]::IsNullOrWhiteSpace($mapPreviewDirectory)) {
    $mapPreviewDirectory = [System.IO.Path]::Combine($dataRoot, "Sprites", "MapPreview")
}

$refreshSeedConfig = [bool](Get-ConfigValue -Name "refreshSeed" -Default $true)
$deleteSeedConfig = [bool](Get-ConfigValue -Name "deleteSeedAfterBuild" -Default $false)
$cleanLibraryConfig = [bool](Get-ConfigValue -Name "cleanLibraryAfterBuild" -Default $false)

$refreshSeed = if ($SkipSeed) { $false } elseif ($RefreshSeed) { $true } else { $refreshSeedConfig }
$deleteSeed = $DeleteSeedAfterBuild -or $deleteSeedConfig
$cleanLibrary = $CleanLibraryAfterBuild -or $cleanLibraryConfig

function New-SeedZip {
    param(
        [string]$MapElemDir,
        [string]$MapDir,
        [string]$PreviewDir,
        [string]$Destination
    )

    foreach ($dir in @($MapElemDir, $MapDir, $PreviewDir)) {
        if (-not (Test-Path -LiteralPath $dir)) {
            throw "资源目录不存在: $dir"
        }
    }

    Add-Type -AssemblyName System.IO.Compression | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null

    $parent = [System.IO.Path]::GetDirectoryName($Destination)
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $temp = "$Destination.tmp"
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Force
    }

    $count = 0
    try {
        $archive = [System.IO.Compression.ZipFile]::Open(
            $temp,
            [System.IO.Compression.ZipArchiveMode]::Create)
        try {
            $sources = @(
                @{ Dir = $MapElemDir; Prefix = "MapElem"; Extensions = @(".png", ".json") },
                @{ Dir = $MapDir; Prefix = "Map"; Extensions = @(".bytes") },
                @{ Dir = $PreviewDir; Prefix = "MapPreview"; Extensions = @(".png") }
            )

            foreach ($source in $sources) {
                $base = (Resolve-Path -LiteralPath $source.Dir).Path
                $files = Get-ChildItem -LiteralPath $base -Recurse -File | Where-Object {
                    $source.Extensions -contains $_.Extension.ToLowerInvariant()
                }
                foreach ($file in $files) {
                    $relative = $file.FullName.Substring($base.Length).TrimStart([char[]]@('\', '/')) -replace '\\', '/'
                    $entryName = "$($source.Prefix)/$relative"
                    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                        $archive,
                        $file.FullName,
                        $entryName,
                        [System.IO.Compression.CompressionLevel]::NoCompression) | Out-Null
                    $count++
                }
            }
        }
        finally {
            $archive.Dispose()
        }
    }
    catch {
        if (Test-Path -LiteralPath $temp) {
            Remove-Item -LiteralPath $temp -Force
        }
        throw
    }

    if ($count -eq 0) {
        if (Test-Path -LiteralPath $temp) {
            Remove-Item -LiteralPath $temp -Force
        }
        throw "资源目录里没有可打包的图片/地图文件"
    }

    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Force
    }
    Move-Item -LiteralPath $temp -Destination $Destination -Force
    return $count
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectPath "Assets"))) {
    throw "这不是 Unity 工程根目录: $ProjectPath"
}
if (-not (Test-Path -LiteralPath $UnityPath)) {
    throw "Unity 不存在: $UnityPath"
}

$normalizedProject = ($ProjectPath -replace '\\', '/').TrimEnd('/')
$runningUnity = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and (($_.CommandLine -replace '\\', '/') -like "*$normalizedProject*")
}
if ($runningUnity) {
    throw "这个项目正在 Unity 中打开，请先关闭 Unity 再打包: $ProjectPath"
}
if (Test-Path -LiteralPath (Join-Path $ProjectPath "Temp\UnityLockfile")) {
    throw "检测到 Temp\UnityLockfile，请确认 Unity 已经关闭"
}

$seedZip = [System.IO.Path]::Combine($ProjectPath, "Assets", "StreamingAssets", "MapEditorSeed.zip")

if ($refreshSeed) {
    Write-Host "正在从配置的资源目录生成内置资源包..."
    if ($resourcePathFileUsed) {
        Write-Host "资源路径文件: $resourcePathFile"
    }
    else {
        Write-Host "资源路径文件未找到，使用 JSON/默认路径: $resourcePathFile"
    }
    Write-Host "MapElem: $mapElemDirectory"
    Write-Host "Map: $mapDirectory"
    Write-Host "MapPreview: $mapPreviewDirectory"
    try {
        $seedCount = New-SeedZip -MapElemDir $mapElemDirectory -MapDir $mapDirectory -PreviewDir $mapPreviewDirectory -Destination $seedZip
        Write-Host ("内置资源包: {0} 个文件, {1:F1} MB" -f $seedCount, ((Get-Item -LiteralPath $seedZip).Length / 1MB))
    }
    catch {
        if (Test-Path -LiteralPath $seedZip) {
            Write-Warning "重新生成资源包失败，继续使用现有 zip: $($_.Exception.Message)"
        }
        else {
            throw "重新生成资源包失败，且没有现有 zip: $($_.Exception.Message)"
        }
    }
}

if (-not (Test-Path -LiteralPath $seedZip)) {
    throw "内置资源包不存在: $seedZip。请检查 android-build.config.json 或使用 -RefreshSeed"
}

$logDirectory = [System.IO.Path]::Combine($ProjectPath, "Builds", "Android")
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logPath = [System.IO.Path]::Combine($logDirectory, "build.log")
if (Test-Path -LiteralPath $logPath) {
    Remove-Item -LiteralPath $logPath -Force
}

$apkPath = [System.IO.Path]::Combine($logDirectory, "MapEditor.apk")
$backupPath = "$apkPath.bak"
if (Test-Path -LiteralPath $backupPath) {
    Remove-Item -LiteralPath $backupPath -Force
}
if (Test-Path -LiteralPath $apkPath) {
    Copy-Item -LiteralPath $apkPath -Destination $backupPath -Force
    # 先移走旧 APK，强制 Unity 写出新的产物，避免误判旧文件为本次构建结果。
    Remove-Item -LiteralPath $apkPath -Force
}

Write-Host "启动 Unity 2022.3.25f1 原地构建 Android APK..."
$buildStartedAt = Get-Date
$unityArgs = @(
    "-batchmode",
    "-nographics",
    "-quit",
    "-buildTarget", "Android",
    "-projectPath", $ProjectPath,
    "-executeMethod", "BuildAndroid.BuildApk",
    "-logFile", $logPath
)

& $UnityPath @unityArgs
$exitCode = $LASTEXITCODE

$waitDeadline = (Get-Date).AddMinutes(30)
$apkItem = $null
$logSucceeded = $false
$logFailed = $false
while ((Get-Date) -lt $waitDeadline) {
    if (Test-Path -LiteralPath $apkPath) {
        $apkItem = Get-Item -LiteralPath $apkPath
        if ($apkItem.LastWriteTime -ge $buildStartedAt.AddSeconds(-5)) {
            break
        }
    }

    if (Test-Path -LiteralPath $logPath) {
        $tail = Get-Content -LiteralPath $logPath -Tail 200 -ErrorAction SilentlyContinue
        if ($tail) {
            $text = $tail -join "`n"
            if ($text -match "Build Finished, Result: Success|Build Successful|BuildAndroid.*MB") {
                $logSucceeded = $true
                break
            }
            if ($text -match "Build Finished, Result: Failure|Scripts have compiler errors|Exiting without the bug reporter") {
                $logFailed = $true
                break
            }
        }
    }
    elseif (((Get-Date) - $buildStartedAt).TotalSeconds -gt 90) {
        # Unity 没有生成日志，通常是启动失败。
        break
    }

    Start-Sleep -Seconds 2
}

$success = $false
if ($logSucceeded -and -not (Test-Path -LiteralPath $apkPath)) {
    # 日志已经报成功，给文件系统一点时间把 APK 落盘。
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path -LiteralPath $apkPath) {
            break
        }
    }
}
if (Test-Path -LiteralPath $apkPath) {
    $apkItem = Get-Item -LiteralPath $apkPath
    $success = $apkItem.LastWriteTime -ge $buildStartedAt.AddSeconds(-5)
}
if (-not $success -and $logSucceeded -and (Test-Path -LiteralPath $apkPath)) {
    $success = $true
}

if (-not $success) {
    Write-Host "构建失败，exit=$exitCode。日志尾部：" -ForegroundColor Red
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 120
    }
    if (Test-Path -LiteralPath $backupPath) {
        Copy-Item -LiteralPath $backupPath -Destination $apkPath -Force
        Remove-Item -LiteralPath $backupPath -Force
        Write-Host "已恢复上一次的 APK。"
    }
    elseif (Test-Path -LiteralPath $apkPath) {
        Remove-Item -LiteralPath $apkPath -Force
    }
    exit 1
}

if (Test-Path -LiteralPath $backupPath) {
    Remove-Item -LiteralPath $backupPath -Force
}

$hash = (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $logDirectory "MapEditor.apk.sha256") -Value $hash -Encoding ASCII
Write-Host ("构建成功: {0} ({1:F1} MB)" -f $apkPath, ((Get-Item -LiteralPath $apkPath).Length / 1MB)) -ForegroundColor Green
Write-Host "SHA256: $hash"

if ($cleanLibrary) {
    try {
        Start-Sleep -Seconds 2
        $library = Join-Path $ProjectPath "Library"
        $temp = Join-Path $ProjectPath "Temp"
        if (Test-Path -LiteralPath $library) {
            Remove-Item -LiteralPath $library -Recurse -Force
        }
        if (Test-Path -LiteralPath $temp) {
            Remove-Item -LiteralPath $temp -Recurse -Force
        }
        Write-Host "已清理 Library / Temp（下次构建会重新导入）"
    }
    catch {
        Write-Warning "清理 Library/Temp 失败，可稍后手动删除: $($_.Exception.Message)"
    }
}

if ($deleteSeed) {
    try {
        if (Test-Path -LiteralPath $seedZip) {
            Remove-Item -LiteralPath $seedZip -Force
        }
        $seedMeta = "$seedZip.meta"
        if (Test-Path -LiteralPath $seedMeta) {
            Remove-Item -LiteralPath $seedMeta -Force
        }
        Write-Host "已删除工程内的 MapEditorSeed.zip（APK 内已包含）"
    }
    catch {
        Write-Warning "删除 MapEditorSeed.zip 失败，可稍后手动删除: $($_.Exception.Message)"
    }
}
