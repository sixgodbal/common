param(
  [string]$BasePath = ".\\shots\\8-1.png",
  [string]$SrcPath  = ".\\shots\\old\\8-1.png",
  [string]$OutPath  = ".\\shots\\8-1_v2.png",
  [string]$RectFile = ".\\tools\\patch_rects.json"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
function Resolve-Full($p) { Join-Path $root ($p -replace '^\.\\', '') }

$dst = [System.Drawing.Bitmap]::new((Resolve-Full $BasePath))
$src = [System.Drawing.Bitmap]::new((Resolve-Full $SrcPath))
$g = [System.Drawing.Graphics]::FromImage($dst)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

$list = [IO.File]::ReadAllText((Resolve-Full $RectFile), [Text.Encoding]::UTF8) | ConvertFrom-Json
foreach ($r in $list) {
  $rect = [System.Drawing.Rectangle]::new([int]$r.x, [int]$r.y, [int]$r.w, [int]$r.h)
  $g.DrawImage($src, $rect, $rect, [System.Drawing.GraphicsUnit]::Pixel)
  Write-Output ("patched {0},{1} {2}x{3}" -f $r.x, $r.y, $r.w, $r.h)
}

$out = Resolve-Full $OutPath
$dst.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $dst.Dispose(); $src.Dispose()
Write-Output "OK -> $OutPath"
