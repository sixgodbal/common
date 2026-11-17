param(
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "r2-common.ps1")

$config = Import-R2LocalConfig
$rcloneExe = Get-RcloneExe
$remoteName = Initialize-RcloneR2Remote -Config $config

$targetOutput = if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $config.LauncherManifestSourcePath
} else {
    $OutputPath
}

$parentDir = Split-Path -Parent $targetOutput
if (-not [string]::IsNullOrWhiteSpace($parentDir) -and (-not (Test-Path -LiteralPath $parentDir))) {
    New-Item -ItemType Directory -Force -Path $parentDir | Out-Null
}

$remoteObject = "{0}:{1}/{2}" -f $remoteName, $config.Bucket, $config.LauncherManifestRemoteKey

Write-Host ("Downloading: {0}/{1}" -f $config.Bucket, $config.LauncherManifestRemoteKey) -ForegroundColor Cyan
Write-Host ("Saving to  : {0}" -f $targetOutput) -ForegroundColor DarkGray
Invoke-Rclone -RcloneExe $rcloneExe -RcloneArgs @("copyto", $remoteObject, $targetOutput, "--progress") | Out-Null

Write-Host ("Download complete: {0}" -f $targetOutput) -ForegroundColor Green
Start-Sleep -Milliseconds 1200
