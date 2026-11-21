param(
  [string]$In   = ".\\scenes\\ent.png",
  [string]$Out  = ".\\scenes\\shot_2-1.png",
  [int]$SrcX    = 1255,
  [int]$SrcY    = 300,
  [int]$Strength = 250,
  [switch]$Birds
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
function Full($p) { Join-Path $root ($p -replace '^\.\\', '') }

$bmp = [System.Drawing.Bitmap]::new((Full $In))
$W = $bmp.Width; $H = $bmp.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

# ---- darken surroundings first, so the light reads ----
$vp = [System.Drawing.Drawing2D.GraphicsPath]::new()
$vp.AddEllipse([int](-$W * 0.30), [int](-$H * 0.35), [int]($W * 1.6), [int]($H * 1.7))
$vpgb = [System.Drawing.Drawing2D.PathGradientBrush]::new($vp)
$vpgb.CenterColor = [System.Drawing.Color]::FromArgb(0, 25, 22, 35)
$vpgb.SurroundColors = @([System.Drawing.Color]::FromArgb(120, 25, 22, 35))
$g.FillRectangle($vpgb, 0, 0, $W, $H)
$vpgb.Dispose(); $vp.Dispose()

# ---- main beam ----
function Add-Beam($x0, $x1h, $halfBottom, $topAlpha, $r, $gg, $h) {
  $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
  $path.AddPolygon(@(
    [System.Drawing.Point]::new([int]($x0 - $x1h), 0),
    [System.Drawing.Point]::new([int]($x0 + $x1h), 0),
    [System.Drawing.Point]::new([int]($x0 + $halfBottom), $h),
    [System.Drawing.Point]::new([int]($x0 - $halfBottom), $h)
  ))
  $rect = [System.Drawing.Rectangle]::new([int]($x0 - $halfBottom), 0, [int]($halfBottom * 2), $h)
  $lg = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    $rect,
    [System.Drawing.Color]::FromArgb($topAlpha, 255, 252, 238),
    [System.Drawing.Color]::FromArgb(0, 255, 252, 238),
    [single]90)
  $gg.FillPath($lg, $path)
  $lg.Dispose(); $path.Dispose()
}

Add-Beam $SrcX 40 470 $Strength $null $g $H
Add-Beam $SrcX 16 210 200 $null $g $H
Add-Beam ($SrcX + 150) 26 300 150 $null $g $H

# ---- hot core near the source ----
$core = [System.Drawing.Drawing2D.GraphicsPath]::new()
$core.AddEllipse($SrcX - 120, $SrcY - 120, 240, 240)
$cb = [System.Drawing.Drawing2D.PathGradientBrush]::new($core)
$cb.CenterColor = [System.Drawing.Color]::FromArgb(255, 255, 255, 255)
$cb.SurroundColors = @([System.Drawing.Color]::FromArgb(90, 255, 255, 245))
$g.FillEllipse($cb, [System.Drawing.Rectangle]::new($SrcX - 120, $SrcY - 120, 240, 240))
$cb.Dispose(); $core.Dispose()

# ---- glow halos ----
foreach ($glow in @(@(300, 170), @(620, 80), @(1000, 34))) {
  $r = $glow[0]; $a = $glow[1]
  $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
  $path.AddEllipse($SrcX - $r, $SrcY - $r, $r * 2, $r * 2)
  $pgb = [System.Drawing.Drawing2D.PathGradientBrush]::new($path)
  $pgb.CenterColor = [System.Drawing.Color]::FromArgb($a, 255, 255, 255)
  $pgb.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 255, 255, 255))
  $pgb.CenterPoint = [System.Drawing.PointF]::new([single]$SrcX, [single]$SrcY)
  $g.FillEllipse($pgb, [System.Drawing.Rectangle]::new($SrcX - $r, $SrcY - $r, $r * 2, $r * 2))
  $pgb.Dispose(); $path.Dispose()
}

# ---- optional birds, only in clear sky ----
if ($Birds) {
  $birdPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(180, 55, 42, 38), [single]3.4)
  foreach ($b in @(@(1265, 120), @(1345, 96), @(1420, 128), @(1500, 100))) {
    $bx = $b[0]; $by = $b[1]; $s = 14
    $g.DrawArc($birdPen, $bx - $s, $by, $s, $s, 200, 140)
    $g.DrawArc($birdPen, $bx, $by, $s, $s, 200, 140)
  }
  $birdPen.Dispose()
}

$outPath = Full $Out
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "OK -> $Out  (${W}x${H})"
