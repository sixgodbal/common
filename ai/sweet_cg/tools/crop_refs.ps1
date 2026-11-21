param(
  [double]$FromX = 0.50,
  [string]$Pattern = "selRole_*_introduction.png",
  [string]$OutDir = ".\tools\refs"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$root = (Resolve-Path ".").Path

$files = Get-ChildItem -Path "." -Recurse -Filter $Pattern -File | Sort-Object Name
foreach ($f in $files) {
  $src = [System.Drawing.Image]::FromFile($f.FullName)
  $x   = [int]($src.Width * $FromX)
  $w   = $src.Width - $x
  $h   = $src.Height
  $bmp = [System.Drawing.Bitmap]::new($w, $h)
  $g   = [System.Drawing.Graphics]::FromImage($bmp)
  $g.DrawImage($src, [System.Drawing.Rectangle]::new(0, 0, $w, $h), [System.Drawing.Rectangle]::new($x, 0, $w, $h), [System.Drawing.GraphicsUnit]::Pixel)

  $name = $f.BaseName -replace "_introduction$", ""
  $out  = Join-Path (Join-Path $root $OutDir.TrimStart(".\")) ($name + ".png")
  $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)

  $g.Dispose(); $bmp.Dispose(); $src.Dispose()
  Write-Output "OK  $name  ${w}x${h}"
}
