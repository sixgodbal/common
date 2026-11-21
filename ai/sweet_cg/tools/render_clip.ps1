param(
  [string]$BasePath = ".\\scenes\\ent.png",
  [string]$OverlayPath = ".\\scenes\\light_overlay.png",
  [string]$FrameDir = ".\\clip\\frames",
  [string]$OutMp4   = ".\\clip\\preview_2-1.mp4",
  [int]$Fps        = 24,
  [double]$Seconds = 6.0,
  [int]$W          = 1280,
  [int]$H          = 720,
  [double]$ZoomAmt = 0.10,
  [switch]$NoEncode
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
function Resolve-Full($p) { Join-Path $root ($p -replace '^\.\\', '') }

$bgBmp = [System.Drawing.Bitmap]::new((Resolve-Full $BasePath))
$ovBmp = [System.Drawing.Bitmap]::new((Resolve-Full $OverlayPath))
$bgW = $bgBmp.Width
$bgH = $bgBmp.Height
$ovW = $ovBmp.Width
$ovH = $ovBmp.Height

$fd = Resolve-Full $FrameDir
if (-not (Test-Path $fd)) { New-Item -ItemType Directory -Path $fd -Force | Out-Null }
Get-ChildItem $fd -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force

$total = [int]($Fps * $Seconds)
$canvas = [System.Drawing.Bitmap]::new($W, $H, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$gfx = [System.Drawing.Graphics]::FromImage($canvas)
$gfx.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$gfx.PixelOffsetMode   = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

$attrs = New-Object System.Drawing.Imaging.ImageAttributes

for ($i = 0; $i -lt $total; $i++) {
  $t = $i / [double]($total - 1)
  if ($t -lt 0.5) { $ease = 2 * $t * $t } else { $ease = 1 - [math]::Pow(-2 * $t + 2, 2) / 2 }
  $z = 1.0 + $ZoomAmt * $ease

  $sw = $bgW / $z
  $sh = $bgH / $z
  $sx = ($bgW - $sw) / 2
  $sy = ($bgH - $sh) / 2 - ($bgH * 0.012) * $ease
  if ($sy -lt 0) { $sy = 0 }

  $gfx.DrawImage($bgBmp,
    [System.Drawing.Rectangle]::new(0, 0, $W, $H),
    [System.Drawing.Rectangle]::new([int]$sx, [int]$sy, [int]$sw, [int]$sh),
    [System.Drawing.GraphicsUnit]::Pixel)

  $pulse = 0.55 + 0.45 * (0.5 + 0.5 * [math]::Sin(2 * [math]::PI * ($t * 2.1)))
  $attrs = New-Object System.Drawing.Imaging.ImageAttributes
  $cm = New-Object System.Drawing.Imaging.ColorMatrix
  $cm.Matrix00 = 1; $cm.Matrix11 = 1; $cm.Matrix22 = 1
  $cm.Matrix33 = [single]$pulse; $cm.Matrix44 = 1
  $attrs.SetColorMatrix($cm)

  $gfx.DrawImage($ovBmp,
    [System.Drawing.Rectangle]::new(0, 0, $W, $H),
    0, 0, $ovW, $ovH,
    [System.Drawing.GraphicsUnit]::Pixel, $attrs)
  $attrs.Dispose()

  if ($t -gt 0.90) {
    $k = ($t - 0.90) / 0.10
    $a = [int](255 * [math]::Min(1.0, $k * $k))
    $flash = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb($a, 255, 255, 255))
    $gfx.FillRectangle($flash, 0, 0, $W, $H)
    $flash.Dispose()
  }

  $canvas.Save((Join-Path $fd ("f{0:d4}.png" -f $i)), [System.Drawing.Imaging.ImageFormat]::Png)
}

$gfx.Dispose(); $canvas.Dispose(); $bgBmp.Dispose(); $ovBmp.Dispose()
Write-Output "frames: $total -> $FrameDir"

if (-not $NoEncode) {
  $ffCandidates = @()
  $c1 = Get-Command ffmpeg -ErrorAction SilentlyContinue
  if ($c1) { $ffCandidates += $c1.Source }
  $c2 = Get-ChildItem "$env:TEMP\ffmpeg_bin" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($c2) { $ffCandidates += $c2.FullName }

  if ($ffCandidates.Count -gt 0) {
    $outPath = Resolve-Full $OutMp4
    $od = Split-Path -Parent $outPath
    if (-not (Test-Path $od)) { New-Item -ItemType Directory -Path $od -Force | Out-Null }
    & $ffCandidates[0] -y -framerate $Fps -i (Join-Path $fd "f%04d.png") -c:v libx264 -pix_fmt yuv420p -crf 20 $outPath 2>&1 | Select-Object -Last 3
    Write-Output "OK -> $OutMp4"
  }
  else {
    Write-Output "ffmpeg not found, frames only"
  }
}
