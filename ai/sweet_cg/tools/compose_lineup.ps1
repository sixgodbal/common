param(
  [string]$Config = ".\\tools\\lineup.json",
  [string]$Out    = ".\\renders_v5\\_lineup.png",
  [int]$Height    = 1500,
  [int]$Gap       = 30,
  [int]$Step      = 3,
  [int]$Threshold = 30
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root  = (Resolve-Path ".").Path
$items = [IO.File]::ReadAllText((Resolve-Path $Config).Path, [Text.Encoding]::UTF8) | ConvertFrom-Json

function Get-BBox($img) {
  $w = $img.Width; $h = $img.Height
  $bg = $img.GetPixel(2, 2)
  $minX = $w; $maxX = 0; $minY = $h; $maxY = 0
  for ($y = 0; $y -lt $h; $y += $Step) {
    for ($x = 0; $x -lt $w; $x += $Step) {
      $p = $img.GetPixel($x, $y)
      $d = [math]::Abs($p.R - $bg.R) + [math]::Abs($p.G - $bg.G) + [math]::Abs($p.B - $bg.B)
      if ($d -gt $Threshold) {
        if ($x -lt $minX) { $minX = $x }
        if ($x -gt $maxX) { $maxX = $x }
        if ($y -lt $minY) { $minY = $y }
        if ($y -gt $maxY) { $maxY = $y }
      }
    }
  }
  $pad = 4
  $bx = [math]::Max(0, $minX - $pad); $by = [math]::Max(0, $minY - $pad)
  $bw = [math]::Min($w - $bx, ($maxX - $minX) + 2 * $pad)
  $bh = [math]::Min($h - $by, ($maxY - $minY) + 2 * $pad)
  return [pscustomobject]@{ X = $bx; Y = $by; W = $bw; H = $bh }
}

$loaded = @()
foreach ($it in $items) {
  $p = Join-Path $root ($it.file -replace '^\.\\', '')
  if (-not (Test-Path $p)) { throw "missing: $p" }
  $img = [System.Drawing.Image]::FromFile($p)
  $bb  = Get-BBox $img
  $th  = [int]$it.h
  $tw  = [int]($bb.W * $th / $bb.H)
  $loaded += [pscustomobject]@{ Img = $img; BB = $bb; W = $tw; H = $th; Name = $it.name }
  Write-Output ("box  {0}: {1}x{2} -> {3}x{4}" -f $it.name, $bb.W, $bb.H, $tw, $th)
}

$totalW = ($loaded | Measure-Object -Property W -Sum).Sum + ($Gap * ($loaded.Count + 1))
$bmp = [System.Drawing.Bitmap]::new([int]$totalW, $Height)
$g   = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::FromArgb(255, 250, 246, 238))
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

$groundY = $Height - 40
$x = $Gap
foreach ($o in $loaded) {
  $y = $groundY - $o.H
  $brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(34, 120, 100, 80))
  $g.FillEllipse($brush, [float]($x + $o.W * 0.10), [float]($groundY - 16), [float]($o.W * 0.80), [float]30)
  $brush.Dispose()
  $g.DrawImage($o.Img,
    [System.Drawing.Rectangle]::new([int]$x, [int]$y, [int]$o.W, [int]$o.H),
    [System.Drawing.Rectangle]::new($o.BB.X, $o.BB.Y, $o.BB.W, $o.BB.H),
    [System.Drawing.GraphicsUnit]::Pixel)
  $x += $o.W + $Gap
}

$outPath = Join-Path $root ($Out -replace '^\.\\', '')
$dir = Split-Path -Parent $outPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)

$g.Dispose(); $bmp.Dispose()
foreach ($o in $loaded) { $o.Img.Dispose() }
Write-Output "OK $totalW x $Height -> $Out"
