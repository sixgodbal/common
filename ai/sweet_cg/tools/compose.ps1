param(
  [string]$InDir = ".\renders_v1",
  [string]$Out   = ".\renders_v1\_lineup.png",
  [int]$Height   = 1500
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$files = Get-ChildItem -Path $InDir -Filter *.png | Where-Object { $_.Name -notlike "_*" } | Sort-Object Name
if (-not $files) { throw "no png found" }

$imgs = @()
foreach ($f in $files) { $imgs += ,([System.Drawing.Image]::FromFile($f.FullName)) }

$widths = @()
foreach ($i in $imgs) { $widths += [int]($i.Width * $Height / $i.Height) }
$totalW = ($widths | Measure-Object -Sum).Sum

$bmp = [System.Drawing.Bitmap]::new([int]$totalW, [int]$Height)
$g   = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::FromArgb(255, 250, 246, 238))
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

$x = 0
for ($n = 0; $n -lt $imgs.Count; $n++) {
  $g.DrawImage($imgs[$n], $x, 0, $widths[$n], $Height)
  $x += $widths[$n]
}

$bmp.Save((Join-Path (Resolve-Path $InDir).Path (Split-Path $Out -Leaf)), [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
foreach ($i in $imgs) { $i.Dispose() }
Write-Output "OK $totalW x $Height"
