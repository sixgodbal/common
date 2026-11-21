param(
  [string]$Out   = ".\\scenes\\light_overlay.png",
  [int]$W        = 2560,
  [int]$H        = 1440,
  [int]$SrcX     = 1180,
  [int]$SrcY     = 470
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
function Full($p) { Join-Path $root ($p -replace '^\.\\', '') }

$bmp = [System.Drawing.Bitmap]::new($W, $H, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Transparent)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

function Add-Halo($cx, $cy, $rx, $ry, $alpha) {
  $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
  $path.AddEllipse([int]($cx - $rx), [int]($cy - $ry), [int]($rx * 2), [int]($ry * 2))
  $pgb = [System.Drawing.Drawing2D.PathGradientBrush]::new($path)
  $pgb.CenterColor = [System.Drawing.Color]::FromArgb($alpha, 255, 255, 250)
  $pgb.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 255, 255, 250))
  $pgb.CenterPoint = [System.Drawing.PointF]::new([single]$cx, [single]$cy)
  $g.FillEllipse($pgb, [System.Drawing.Rectangle]::new([int]($cx - $rx), [int]($cy - $ry), [int]($rx * 2), [int]($ry * 2)))
  $pgb.Dispose(); $path.Dispose()
}

Add-Halo $SrcX $SrcY 1050 420 80
Add-Halo $SrcX $SrcY 620 250 130
Add-Halo $SrcX $SrcY 330 130 200
Add-Halo $SrcX $SrcY 160 70 255

function Add-Ray($cx, $cy, $deg, $halfDeg, $len, $alpha) {
  $a1 = ($deg - $halfDeg) * [math]::PI / 180
  $a2 = ($deg + $halfDeg) * [math]::PI / 180
  $p1 = [System.Drawing.Point]::new([int]($cx + $len * [math]::Cos($a1)), [int]($cy + $len * [math]::Sin($a1)))
  $p2 = [System.Drawing.Point]::new([int]($cx + $len * [math]::Cos($a2)), [int]($cy + $len * [math]::Sin($a2)))
  $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
  $path.AddPolygon(@([System.Drawing.Point]::new($cx, $cy), $p1, $p2))
  $pgb = [System.Drawing.Drawing2D.PathGradientBrush]::new($path)
  $pgb.CenterColor = [System.Drawing.Color]::FromArgb($alpha, 255, 254, 245)
  $pgb.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 255, 254, 245))
  $pgb.CenterPoint = [System.Drawing.PointF]::new([single]$cx, [single]$cy)
  $g.FillPath($pgb, $path)
  $pgb.Dispose(); $path.Dispose()
}

foreach ($r in @(
  @(-96, 3.2, 42), @(-78, 3.0, 48), @(-58, 2.4, 36),
  @(-36, 3.6, 54), @(-16, 3.0, 46), @(4, 4.2, 62),
  @(22, 3.4, 50), @(44, 2.8, 42), @(66, 2.6, 36),
  @(88, 2.2, 30), @(110, 1.8, 26)
)) { Add-Ray $SrcX $SrcY $r[0] $r[1] 2400 $r[2] }

$bandH = 520
$bandRect = [System.Drawing.Rectangle]::new(0, [int]($SrcY - $bandH / 2), $W, $bandH)
$band = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
  $bandRect,
  [System.Drawing.Color]::FromArgb(0, 255, 250, 235),
  [System.Drawing.Color]::FromArgb(0, 255, 250, 235),
  [single]90)
$blend = New-Object System.Drawing.Drawing2D.ColorBlend
$blend.Colors = @(
  [System.Drawing.Color]::FromArgb(0, 255, 250, 235),
  [System.Drawing.Color]::FromArgb(60, 255, 250, 235),
  [System.Drawing.Color]::FromArgb(0, 255, 250, 235)
)
$blend.Positions = @([single]0, [single]0.5, [single]1.0)
$band.InterpolationColors = $blend
$g.FillRectangle($band, $bandRect)
$band.Dispose()

$bmp.Save((Full $Out), [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "OK -> $Out"
