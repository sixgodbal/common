Set-StrictMode -Version Latest

function Get-PortableRoot {
    return (Split-Path -Parent $PSScriptRoot)
}

function Join-RemotePath {
    param(
        [string]$Prefix,
        [string]$Name
    )

    $cleanPrefix = if ($null -ne $Prefix) { $Prefix.Trim().Trim("/") } else { "" }
    $cleanName = if ($null -ne $Name) { $Name.Trim().Trim("/") } else { "" }

    if ([string]::IsNullOrWhiteSpace($cleanPrefix)) {
        return $cleanName
    }
    if ([string]::IsNullOrWhiteSpace($cleanName)) {
        return $cleanPrefix
    }

    return "$cleanPrefix/$cleanName"
}

function Import-R2LocalConfig {
    param(
        [string]$ConfigPath = (Join-Path $PSScriptRoot "r2-upload.local.ps1")
    )

    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        throw "Missing local config file: $ConfigPath`nPlease copy r2-upload.local.example.ps1 to r2-upload.local.ps1 and fill in R2 credentials."
    }

    $R2AccountId = ""
    $R2Bucket = ""
    $R2AccessKeyId = ""
    $R2SecretAccessKey = ""
    $R2PublicBaseUrl = ""
    $R2DefaultPrefix = "guotang-star"
    $LauncherManifestSourcePath = ""
    $LauncherManifestRemoteKey = "launcher/LauncherManifest.xml"

    . $ConfigPath

    if ([string]::IsNullOrWhiteSpace($R2AccountId) -or $R2AccountId -eq "your-account-id" -or
        [string]::IsNullOrWhiteSpace($R2Bucket) -or
        [string]::IsNullOrWhiteSpace($R2AccessKeyId) -or $R2AccessKeyId -eq "your-access-key-id" -or
        [string]::IsNullOrWhiteSpace($R2SecretAccessKey) -or $R2SecretAccessKey -eq "your-secret-access-key" -or
        [string]::IsNullOrWhiteSpace($R2PublicBaseUrl)) {
        throw "R2 config is incomplete or still using placeholder values. Check: $ConfigPath"
    }

    $desktopDir = [Environment]::GetFolderPath("Desktop")
    $resolvedManifestLocal = $LauncherManifestSourcePath
    if ([string]::IsNullOrWhiteSpace($resolvedManifestLocal)) {
        $resolvedManifestLocal = Join-Path $desktopDir "LauncherManifest.xml"
    } else {
        $parentDir = Split-Path -Parent $resolvedManifestLocal
        if ([string]::IsNullOrWhiteSpace($parentDir) -or (-not (Test-Path -LiteralPath $parentDir))) {
            $resolvedManifestLocal = Join-Path $desktopDir "LauncherManifest.xml"
        }
    }

    $resolvedDefaultPrefix = if ([string]::IsNullOrWhiteSpace($R2DefaultPrefix)) { "guotang-star" } else { $R2DefaultPrefix }
    $resolvedManifestRemote = if ([string]::IsNullOrWhiteSpace($LauncherManifestRemoteKey)) { "launcher/LauncherManifest.xml" } else { $LauncherManifestRemoteKey }

    return [PSCustomObject]@{
        AccountId                  = $R2AccountId.Trim()
        Bucket                     = $R2Bucket.Trim()
        AccessKeyId                = $R2AccessKeyId.Trim()
        SecretAccessKey            = $R2SecretAccessKey.Trim()
        PublicBaseUrl              = $R2PublicBaseUrl.Trim().TrimEnd("/")
        DefaultPrefix              = $resolvedDefaultPrefix.Trim().Trim("/")
        LauncherManifestSourcePath = $resolvedManifestLocal
        LauncherManifestRemoteKey  = $resolvedManifestRemote.Trim().Trim("/")
    }
}

function Get-RcloneExe {
    param(
        [string]$ProjectRoot = (Get-PortableRoot)
    )

    $localExe = Join-Path $ProjectRoot "tools\rclone\rclone.exe"
    if (Test-Path -LiteralPath $localExe) {
        Unblock-File -LiteralPath $localExe -ErrorAction SilentlyContinue
        return $localExe
    }

    $cmd = Get-Command rclone -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        return $cmd.Source
    }

    $toolsDir = Join-Path $ProjectRoot "tools"
    $zipPath = Join-Path $toolsDir "rclone-current-windows-amd64.zip"
    $extractDir = Join-Path $toolsDir "rclone-extract"
    $targetDir = Join-Path $toolsDir "rclone"

    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null

    Write-Host "rclone.exe not found locally, downloading from downloads.rclone.org..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "https://downloads.rclone.org/rclone-current-windows-amd64.zip" -OutFile $zipPath

    if (Test-Path -LiteralPath $extractDir) {
        Remove-Item -LiteralPath $extractDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $targetDir) {
        Remove-Item -LiteralPath $targetDir -Recurse -Force
    }

    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force
    $downloadedDir = Get-ChildItem -LiteralPath $extractDir -Directory | Select-Object -First 1
    Move-Item -LiteralPath $downloadedDir.FullName -Destination $targetDir
    Remove-Item -LiteralPath $zipPath -Force
    Remove-Item -LiteralPath $extractDir -Recurse -Force

    Unblock-File -LiteralPath $localExe -ErrorAction SilentlyContinue
    return $localExe
}

function Initialize-RcloneR2Remote {
    param(
        [Parameter(Mandatory = $true)]
        $Config,
        [string]$RemoteName = "r2temp"
    )

    $endpoint = "https://$($Config.AccountId).r2.cloudflarestorage.com"
    Set-Item -Path ("Env:RCLONE_CONFIG_{0}_TYPE" -f $RemoteName) -Value "s3"
    Set-Item -Path ("Env:RCLONE_CONFIG_{0}_PROVIDER" -f $RemoteName) -Value "Cloudflare"
    Set-Item -Path ("Env:RCLONE_CONFIG_{0}_ACCESS_KEY_ID" -f $RemoteName) -Value $Config.AccessKeyId
    Set-Item -Path ("Env:RCLONE_CONFIG_{0}_SECRET_ACCESS_KEY" -f $RemoteName) -Value $Config.SecretAccessKey
    Set-Item -Path ("Env:RCLONE_CONFIG_{0}_ENDPOINT" -f $RemoteName) -Value $endpoint

    return $RemoteName
}

function Invoke-Rclone {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RcloneExe,
        [Parameter(Mandatory = $true)]
        [string[]]$RcloneArgs,
        [int[]]$AllowedExitCodes = @(0)
    )

    $allArgs = @("--log-level", "ERROR") + $RcloneArgs
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $RcloneExe @allArgs
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference

    if ($AllowedExitCodes -notcontains $exitCode) {
        throw "rclone command failed. Exit code: $exitCode"
    }

    return $exitCode
}
