param(
  [Parameter(Mandatory=$true)][string]$Dir,
  [Parameter(Mandatory=$true)][string]$Out,
  [string]$Title = "资源选择表",
  [string]$Labels = "",
  [string]$Files = "",
  [int]$Cols = 4,
  [int]$Rows = 3,
  [int]$Cell = 256,
  [string]$Note = "每格 256 x 256   透明背景"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$labelList = @()
if ($Labels) { $labelList = @($Labels -split "\|" | ForEach-Object { $_.Trim() }) }
$fileList = @()
if ($Files) { $fileList = @($Files -split "\|" | ForEach-Object { $_.Trim() }) }

$gap = 16
$pad = 20
$headH = 52
$capH = 26

$W = $pad * 2 + $Cols * $Cell + ($Cols - 1) * $gap
$H = $headH + $Rows * ($Cell + $capH) + ($Rows - 1) * $gap + $pad

$bmp = [System.Drawing.Bitmap]::new($W, $H)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::FromArgb(255, 246, 240, 228))
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

$titleFont = [System.Drawing.Font]::new("Microsoft YaHei", 18, [System.Drawing.FontStyle]::Bold)
$labelFont = [System.Drawing.Font]::new("Microsoft YaHei", 12, [System.Drawing.FontStyle]::Bold)
$noteFont = [System.Drawing.Font]::new("Microsoft YaHei", 11, [System.Drawing.FontStyle]::Regular)
$ink = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 74, 58, 42))
$sub = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 130, 110, 90))
$sep = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(255, 220, 208, 190), 1)
$g.DrawString($Title, $titleFont, $ink, [single]$pad, [single]10)

$nameFmt = [System.Drawing.StringFormat]::new()
$nameFmt.Alignment = [System.Drawing.StringAlignment]::Center
$nameFmt.LineAlignment = [System.Drawing.StringAlignment]::Center

for ($r = 0; $r -lt $Rows; $r++) {
  for ($c = 0; $c -lt $Cols; $c++) {
    $i = $r * $Cols + $c
    if ($i -ge $labelList.Count -and $fileList.Count -eq 0) { continue }

    $label = if ($i -lt $labelList.Count) { $labelList[$i] } else { "" }
    $file = if ($i -lt $fileList.Count) { $fileList[$i] } else { $label }
    if (-not $file) { $file = "r$($r+1)c$($c+1)" }
    $path = Join-Path $Dir ("{0}.png" -f $file)

    $x = $pad + $c * ($Cell + $gap)
    $y = $headH + $r * ($Cell + $capH + $gap)

    $g.DrawRectangle($sep, $x, $y, $Cell, $Cell)
    if (Test-Path $path) {
      $img = [System.Drawing.Image]::FromFile($path)
      $g.DrawImage($img, $x, $y, $Cell, $Cell)
      $img.Dispose()
    } else {
      Write-Output "WARN missing $path"
    }
    if ($label) {
      $g.DrawString($label, $labelFont, $ink, [System.Drawing.RectangleF]::new([single]$x, [single]($y + $Cell + 2), [single]$Cell, [single]$capH), $nameFmt)
    }
  }
}

$g.DrawString($Note, $noteFont, $sub, [single]$pad, [single]($H - 22))

$g.Dispose()
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
$titleFont.Dispose(); $labelFont.Dispose(); $noteFont.Dispose()
$ink.Dispose(); $sub.Dispose(); $sep.Dispose()
Write-Output "OK $Out  ($W x $H)"
