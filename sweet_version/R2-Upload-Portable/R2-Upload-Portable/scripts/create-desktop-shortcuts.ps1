param(
    [string]$TargetDesktopDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "r2-common.ps1")

$portableRoot = Get-PortableRoot
$desktopDir = if ([string]::IsNullOrWhiteSpace($TargetDesktopDir)) {
    [Environment]::GetFolderPath("Desktop")
} else {
    $TargetDesktopDir
}

Write-Host "1. Unblocking portable files..." -ForegroundColor Cyan
Get-ChildItem -LiteralPath $portableRoot -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue
}

Write-Host "2. Validating R2 configuration and rclone..." -ForegroundColor Cyan
$config = Import-R2LocalConfig
$rcloneExe = Get-RcloneExe -ProjectRoot $portableRoot
Write-Host ("   Bucket        : {0}" -f $config.Bucket) -ForegroundColor Gray
Write-Host ("   Public Domain : {0}" -f $config.PublicBaseUrl) -ForegroundColor Gray
Write-Host ("   Default Prefix: {0}" -f $config.DefaultPrefix) -ForegroundColor Gray
Write-Host ("   Manifest Path : {0}" -f $config.LauncherManifestSourcePath) -ForegroundColor Gray
Write-Host ("   Rclone Binary : {0}" -f $rcloneExe) -ForegroundColor Gray

Write-Host "3. Creating Desktop shortcuts..." -ForegroundColor Cyan
$wsh = New-Object -ComObject WScript.Shell

$shortcuts = @(
    @{
        ShortcutName = "upload-to-r2.bat.lnk"
        TargetBat    = (Join-Path $portableRoot "upload-to-r2.bat")
        WorkingDir   = $portableRoot
        Description  = "Drag files onto this shortcut to upload to Cloudflare R2"
    },
    @{
        ShortcutName = "download-launcher-manifest.bat.lnk"
        TargetBat    = (Join-Path $portableRoot "download-launcher-manifest.bat")
        WorkingDir   = $desktopDir
        Description  = "Download LauncherManifest.xml from Cloudflare R2 to Desktop"
    }
)

foreach ($item in $shortcuts) {
    $lnkPath = Join-Path $desktopDir $item.ShortcutName
    $sc = $wsh.CreateShortcut($lnkPath)
    $sc.TargetPath = $item.TargetBat
    $sc.WorkingDirectory = $item.WorkingDir
    $sc.Description = $item.Description
    $sc.Save()
    Write-Host ("   Created: {0}" -f $lnkPath) -ForegroundColor Green
}

Write-Host ""
Write-Host "Setup complete! You can now drag files onto 'upload-to-r2.bat' on your Desktop." -ForegroundColor Green
