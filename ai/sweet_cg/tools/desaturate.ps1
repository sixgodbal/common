param(
  [string]$InDir   = ".\\characters",
  [string]$Pattern = "*_立绘*.png",
  [double]$Sat     = 0.80,
  [string]$Suffix  = "_soft",
  [int]$Bright     = 0
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
$files = Get-ChildItem -Path $InDir -Filter $Pattern -File | Where-Object { $_.Name -notlike "*_soft.png" }
if (-not $files) { throw "no input files" }

$lr = 0.3086; $lg = 0.6094; $lb = 0.0820
$s = [single]$Sat
$c = [single](1.0 - $s)

foreach ($f in $files) {
  $src = [System.Drawing.Bitmap]::new($f.FullName)
  $dst = [System.Drawing.Bitmap]::new($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($dst)

  $cm = New-Object System.Drawing.Imaging.ColorMatrix
  $cm.Matrix00 = $lr * $c + $s; $cm.Matrix01 = $lr * $c;       $cm.Matrix02 = $lr * $c
  $cm.Matrix10 = $lg * $c;       $cm.Matrix11 = $lg * $c + $s; $cm.Matrix12 = $lg * $c
  $cm.Matrix20 = $lb * $c;       $cm.Matrix21 = $lb * $c;      $cm.Matrix22 = $lb * $c + $s
  $cm.Matrix33 = 1.0
  $cm.Matrix40 = [single]($Bright / 255.0)
  $cm.Matrix41 = [single]($Bright / 255.0)
  $cm.Matrix42 = [single]($Bright / 255.0)
  $cm.Matrix44 = 1.0

  $ia = New-Object System.Drawing.Imaging.ImageAttributes
  $ia.SetColorMatrix($cm)
  $rect = [System.Drawing.Rectangle]::new(0, 0, $src.Width, $src.Height)
  $g.DrawImage($src, $rect, 0, 0, $src.Width, $src.Height, [System.Drawing.GraphicsUnit]::Pixel, $ia)

  $out = [IO.Path]::Combine([IO.Path]::GetDirectoryName($f.FullName), [IO.Path]::GetFileNameWithoutExtension($f.Name) + $Suffix + ".png")
  $dst.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
  Write-Output "OK $([IO.Path]::GetFileName($out))  sat=$Sat"

  $ia.Dispose(); $g.Dispose(); $dst.Dispose(); $src.Dispose()
}
