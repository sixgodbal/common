[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Paths,
    [string]$RemotePrefix = "",
    [string]$RemoteKey = "",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "r2-common.ps1")

$inputPaths = @(@($Paths) | Where-Object { $null -ne $_ -and -not [string]::IsNullOrWhiteSpace($_) })

if ($inputPaths.Count -eq 0) {
    throw "No input files were provided. Drag one or more files onto upload-to-r2.bat (or its desktop shortcut)."
}

if (($inputPaths.Count -gt 1) -and (-not [string]::IsNullOrWhiteSpace($RemoteKey))) {
    throw "RemoteKey can only be used when uploading a single file."
}

$config = Import-R2LocalConfig
$rcloneExe = Get-RcloneExe
$remoteName = Initialize-RcloneR2Remote -Config $config

$basePrefix = if ([string]::IsNullOrWhiteSpace($RemotePrefix)) { $config.DefaultPrefix } else { $RemotePrefix.Trim().Trim("/") }
$uploadedUrls = New-Object System.Collections.Generic.List[string]

foreach ($rawPath in $inputPaths) {
    if (-not (Test-Path -LiteralPath $rawPath)) {
        throw "File not found: $rawPath"
    }

    $item = Get-Item -LiteralPath $rawPath
    if ($item.PSIsContainer) {
        throw "Directory upload is blocked to prevent accidental overwrite: $($item.FullName)`nPlease drag files (e.g. .zip / .xml) instead of folders."
    }

    $targetKey = if ([string]::IsNullOrWhiteSpace($RemoteKey)) {
        if ($item.Name -ieq "LauncherManifest.xml") {
            $config.LauncherManifestRemoteKey
        } else {
            Join-RemotePath -Prefix $basePrefix -Name $item.Name
        }
    } else {
        $RemoteKey.Trim().Trim("/")
    }

    $remoteObject = "{0}:{1}/{2}" -f $remoteName, $config.Bucket, $targetKey
    $publicUrl = "{0}/{1}" -f $config.PublicBaseUrl, $targetKey

    Write-Host ("Uploading: {0}" -f $item.FullName) -ForegroundColor Cyan
    Write-Host ("Target   : {0}/{1}" -f $config.Bucket, $targetKey) -ForegroundColor DarkGray
    if ($DryRun.IsPresent -or ($env:R2_DRY_RUN -eq "1")) {
        Write-Host ("[DryRun] Would upload to: {0}" -f $publicUrl) -ForegroundColor Magenta
    } else {
        Invoke-Rclone -RcloneExe $rcloneExe -RcloneArgs @("copyto", $item.FullName, $remoteObject, "--progress") | Out-Null
        Write-Host ("Upload complete: {0}" -f $publicUrl) -ForegroundColor Green
    }
    $uploadedUrls.Add($publicUrl)
}

if ($uploadedUrls.Count -gt 0) {
    try {
        Set-Clipboard -Value ($uploadedUrls -join [Environment]::NewLine)
        Write-Host "Public URL(s) copied to clipboard." -ForegroundColor Yellow
    } catch {
        # Ignore clipboard errors in non-interactive sessions
    }
}

Start-Sleep -Milliseconds 1200
