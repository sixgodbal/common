param(
  [string]$InDir = ".\renders_v2",
  [string]$Out   = ".\tools\ref_lineup.png",
  [int]$Width    = 1280
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$f = Get-ChildItem -Path $InDir -Filter *.png | Where-Object { $_.Name -notlike "_*" } | Select-Object -First 1
if (-not $f) { throw "no input png" }

$src = [System.Drawing.Image]::FromFile($f.FullName)
$h   = [int]($src.Height * $Width / $src.Width)
$bmp = [System.Drawing.Bitmap]::new($Width, $h)
$g   = [System.Drawing.Graphics]::FromImage($bmp)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.DrawImage($src, 0, 0, $Width, $h)

$dir = Split-Path -Parent $Out
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$bmp.Save((Join-Path (Resolve-Path ".").Path $Out.TrimStart(".\")), [System.Drawing.Imaging.ImageFormat]::Png)

$g.Dispose(); $bmp.Dispose(); $src.Dispose()
Write-Output "OK $Width x $h -> $Out"
