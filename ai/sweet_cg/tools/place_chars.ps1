param(
  [string]$Config = ".\\tools\\shot_layout.json",
  [string]$Out    = ".\\scenes\\shot_1-1.png",
  [int]$Step      = 2
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
$cfg  = [IO.File]::ReadAllText((Resolve-Path $Config).Path, [Text.Encoding]::UTF8) | ConvertFrom-Json

$bgPath = Join-Path $root ($cfg.bg -replace '^\.\\', '')
$bg = [System.Drawing.Bitmap]::new($bgPath)
$g  = [System.Drawing.Graphics]::FromImage($bg)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$g.PixelOffsetMode   = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

function Get-AlphaBox($bmp, [int]$step) {
  $w = $bmp.Width; $h = $bmp.Height
  $minX = $w; $maxX = 0; $minY = $h; $maxY = 0
  for ($y = 0; $y -lt $h; $y += $step) {
    for ($x = 0; $x -lt $w; $x += $step) {
      if ($bmp.GetPixel($x, $y).A -gt 16) {
        if ($x -lt $minX) { $minX = $x }; if ($x -gt $maxX) { $maxX = $x }
        if ($y -lt $minY) { $minY = $y }; if ($y -gt $maxY) { $maxY = $y }
      }
    }
  }
  return [pscustomobject]@{ X = $minX; Y = $minY; W = ($maxX - $minX); H = ($maxY - $minY) }
}

foreach ($it in $cfg.chars) {
  $p = Join-Path $root ($it.file -replace '^\.\\', '')
  $img = [System.Drawing.Image]::FromFile($p)
  $bb = Get-AlphaBox $img $Step
  if ($bb.W -le 0) { Write-Output "skip $($it.name)"; $img.Dispose(); continue }

  $targetH = [int]$it.h
  $targetW = [int]($bb.W * $targetH / $bb.H)
  $dx = [int]([double]$it.x - $targetW / 2)
  $dy = [int]([double]$it.y - $targetH)

  # contact shadow
  $sh = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(38, 90, 70, 60))
  $g.FillEllipse($sh, [float]($dx + $targetW * 0.12), [float]($it.y - 10), [float]($targetW * 0.76), [float]22)
  $sh.Dispose()

  $g.DrawImage($img,
    [System.Drawing.Rectangle]::new($dx, $dy, $targetW, $targetH),
    [System.Drawing.Rectangle]::new($bb.X, $bb.Y, $bb.W, $bb.H),
    [System.Drawing.GraphicsUnit]::Pixel)

  Write-Output ("placed {0} at {1},{2} size {3}x{4}" -f $it.name, $dx, $dy, $targetW, $targetH)
  $img.Dispose()
}

$outPath = Join-Path $root ($Out -replace '^\.\\', '')
$dir = Split-Path -Parent $outPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$bg.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bg.Dispose()
Write-Output "OK -> $Out"
