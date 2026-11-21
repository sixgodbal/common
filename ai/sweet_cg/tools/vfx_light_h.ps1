param(
  [string]$In    = ".\\scenes\\ent.png",
  [string]$Out   = ".\\scenes\\shot_2-1_h.png",
  [int]$SrcX     = 1180,
  [int]$SrcY     = 470,
  [double]$Rays  = 1.0,
  [int]$Dim      = 118
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
function Full($p) { Join-Path $root ($p -replace '^\.\\', '') }

$bmp = [System.Drawing.Bitmap]::new((Full $In))
$W = $bmp.Width; $H = $bmp.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

# ---- dim the scene ----
$vp = [System.Drawing.Drawing2D.GraphicsPath]::new()
$vp.AddEllipse([int](-$W * 0.35), [int](-$H * 0.40), [int]($W * 1.7), [int]($H * 1.8))
$vpgb = [System.Drawing.Drawing2D.PathGradientBrush]::new($vp)
$vpgb.CenterColor = [System.Drawing.Color]::FromArgb(0, 22, 20, 34)
$vpgb.SurroundColors = @([System.Drawing.Color]::FromArgb($Dim, 22, 20, 34))
$g.FillRectangle($vpgb, 0, 0, $W, $H)
$vpgb.Dispose(); $vp.Dispose()

# ---- horizontal halo, wide and flat ----
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

$global:scene = $g

Add-Halo $SrcX $SrcY 1050 420 70
Add-Halo $SrcX $SrcY 620 250 120
Add-Halo $SrcX $SrcY 330 130 190
Add-Halo $SrcX $SrcY 160 70 255

# ---- rays fanning out from the source, mostly sideways ----
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
  @(-96, 3.2, 40), @(-78, 3.0, 46), @(-58, 2.4, 34),
  @(-36, 3.6, 52), @(-16, 3.0, 44), @(4, 4.2, 60),
  @(22, 3.4, 48), @(44, 2.8, 40), @(66, 2.6, 34),
  @(88, 2.2, 28), @(110, 1.8, 24)
)) {
  Add-Ray $SrcX $SrcY $r[0] $r[1] 2400 ([int]($r[2] * $Rays))
}

# ---- warm haze band across the source height ----
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
  [System.Drawing.Color]::FromArgb(55, 255, 250, 235),
  [System.Drawing.Color]::FromArgb(0, 255, 250, 235)
)
$blend.Positions = @([single]0, [single]0.5, [single]1.0)
$band.InterpolationColors = $blend
$g.FillRectangle($band, $bandRect)
$band.Dispose()

$outPath = Full $Out
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "OK -> $Out  (${W}x${H})"
