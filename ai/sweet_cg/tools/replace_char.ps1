param(
  [string]$BaseDir = ".\\renders_v3",
  [string]$CharDir = ".\\renders_v4",
  [string]$Out     = ".\\renders_v5\\_lineup_final.png",
  [double]$RegionX = 0.30,
  [double]$Scale   = 0.99,
  [int]$Step       = 2,
  [int]$Luma       = 232
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path

$baseFile = Get-ChildItem -Path $BaseDir -Filter *.png | Where-Object { $_.Name -notlike "_*" } | Select-Object -First 1
$charFile = Get-ChildItem -Path $CharDir -Filter *_cut.png | Select-Object -First 1
if (-not $baseFile) { throw "no base png in $BaseDir" }
if (-not $charFile) { throw "no *_cut.png in $CharDir" }
Write-Output "base: $($baseFile.Name)"
Write-Output "char: $($charFile.Name)"

$base = [System.Drawing.Bitmap]::new($baseFile.FullName)
$W = $base.Width; $H = $base.Height

# --- old character bbox: any pixel darker than the cream background ---
$x0 = 0; $x1 = [int]($W * $RegionX)
$minX = $x1; $maxX = $x0; $minY = $H; $maxY = 0
for ($y = 0; $y -lt $H; $y += $Step) {
  for ($x = $x0; $x -lt $x1; $x += $Step) {
    $p = $base.GetPixel($x, $y)
    if ((0.299 * $p.R + 0.587 * $p.G + 0.114 * $p.B) -lt $Luma) {
      if ($x -lt $minX) { $minX = $x }; if ($x -gt $maxX) { $maxX = $x }
      if ($y -lt $minY) { $minY = $y }; if ($y -gt $maxY) { $maxY = $y }
    }
  }
}
if ($maxX -le $minX) { throw "character region not detected" }
$boxW = $maxX - $minX; $boxH = $maxY - $minY
Write-Output ("old box: {0},{1} {2}x{3}" -f $minX, $minY, $boxW, $boxH)

# --- erase old character ---
$g = [System.Drawing.Graphics]::FromImage($base)
$pad = 18
$rect = [System.Drawing.Rectangle]::new([int]($minX - $pad), [int]($minY - $pad), [int]($boxW + 2 * $pad), [int]($boxH + 2 * $pad))
$cx = [int]($rect.Left + $rect.Width / 2)
$cTop = $base.GetPixel($cx, [math]::Max(1, [int]($rect.Top - 10)))
$cBot = $base.GetPixel($cx, [math]::Min($H - 2, [int]($rect.Bottom + 10)))
$lg = [System.Drawing.Drawing2D.LinearGradientBrush]::new($rect, $cTop, $cBot, [single]90)
$g.FillRectangle($lg, $rect)
$lg.Dispose()

# --- new character bbox from alpha ---
$src = [System.Drawing.Image]::FromFile($charFile.FullName)
$sW = $src.Width; $sH = $src.Height
$nMinX = $sW; $nMaxX = 0; $nMinY = $sH; $nMaxY = 0
for ($y = 0; $y -lt $sH; $y += 2) {
  for ($x = 0; $x -lt $sW; $x += 2) {
    if ($src.GetPixel($x, $y).A -gt 16) {
      if ($x -lt $nMinX) { $nMinX = $x }; if ($x -gt $nMaxX) { $nMaxX = $x }
      if ($y -lt $nMinY) { $nMinY = $y }; if ($y -gt $nMaxY) { $nMaxY = $y }
    }
  }
}
$nW = $nMaxX - $nMinX; $nH = $nMaxY - $nMinY
if ($nW -le 0) { throw "new character alpha bbox not found" }
Write-Output ("new box: {0},{1} {2}x{3}" -f $nMinX, $nMinY, $nW, $nH)

$targetH = [int]($boxH * $Scale)
$targetW = [int]($nW * $targetH / $nH)
$dstX = [int]($minX + $boxW / 2 - $targetW / 2)
$dstY = [int]($minY + $boxH - $targetH)

$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$g.DrawImage($src,
  [System.Drawing.Rectangle]::new($dstX, $dstY, $targetW, $targetH),
  [System.Drawing.Rectangle]::new($nMinX, $nMinY, $nW, $nH),
  [System.Drawing.GraphicsUnit]::Pixel)

$outPath = Join-Path $root ($Out -replace '^\.\\', '')
$dir = Split-Path -Parent $outPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$base.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)

$g.Dispose(); $base.Dispose(); $src.Dispose()
Write-Output ("OK new {0}x{1} at {2},{3}" -f $targetW, $targetH, $dstX, $dstY)
