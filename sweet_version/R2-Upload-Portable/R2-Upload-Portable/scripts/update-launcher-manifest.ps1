Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "r2-common.ps1")

$config = Import-R2LocalConfig

if (-not (Test-Path -LiteralPath $config.LauncherManifestSourcePath)) {
    throw ("LauncherManifest source file was not found: {0}`nRun download-launcher-manifest.bat first or place LauncherManifest.xml on your Desktop." -f $config.LauncherManifestSourcePath)
}

& (Join-Path $PSScriptRoot "upload-to-r2.ps1") -Paths @($config.LauncherManifestSourcePath) -RemoteKey $config.LauncherManifestRemoteKey

