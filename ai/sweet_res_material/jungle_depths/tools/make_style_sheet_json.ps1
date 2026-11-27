param(
  [Parameter(Mandatory=$true)][string]$Sheet,
  [Parameter(Mandatory=$true)][string]$Out,
  [Parameter(Mandatory=$true)][string]$Config,
  [int]$Cols = 2,
  [int]$Rows = 2
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$cfg = Get-Content -LiteralPath $Config -Raw -Encoding UTF8 | ConvertFrom-Json
$src = [System.Drawing.Image]::FromFile((Resolve-Path $Sheet).Path)
$cellW = [int]($src.Width / $Cols)
$cellH = [int]($src.Height / $Rows)

$pad      = 32
$gap      = 24
$labelH   = 86
$titleH   = 96
$bg       = [System.Drawing.Color]::FromArgb(255, 247, 241, 227)
$titleCol = [System.Drawing.Color]::FromArgb(255, 54, 42, 30)
$subCol   = [System.Drawing.Color]::FromArgb(255, 120, 104, 84)

$cellOutW = 720
$cellOutH = [int]($cellOutW * $cellH / $cellW)
$W = $pad * 2 + $cellOutW * $Cols + $gap * ($Cols - 1)
$H = $titleH + $pad + ($cellOutH + $labelH) * $Rows + $gap * ($Rows - 1) + $pad

$bmp = [System.Drawing.Bitmap]::new($W, $H)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear($bg)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

$fTitle = [System.Drawing.Font]::new("Microsoft YaHei", 26, [System.Drawing.FontStyle]::Bold)
$fTag   = [System.Drawing.Font]::new("Microsoft YaHei", 22, [System.Drawing.FontStyle]::Bold)
$fName  = [System.Drawing.Font]::new("Microsoft YaHei", 16, [System.Drawing.FontStyle]::Bold)
$fSub   = [System.Drawing.Font]::new("Microsoft YaHei", 11, [System.Drawing.FontStyle]::Regular)
$bTitle = [System.Drawing.SolidBrush]::new($titleCol)
$bSub   = [System.Drawing.SolidBrush]::new($subCol)
$bTagBg = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 82, 118, 76))
$bWhite = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)

$g.DrawString($cfg.title, $fTitle, $bTitle, $pad, 28)
$g.DrawString($cfg.subtitle, $fSub, $bSub, ($pad + 4), 70)

$y = $titleH + $pad
for ($r = 0; $r -lt $Rows; $r++) {
  $x = $pad
  for ($c = 0; $c -lt $Cols; $c++) {
    $idx = $r * $Cols + $c
    $srcRect = [System.Drawing.Rectangle]::new($c * $cellW, $r * $cellH, $cellW, $cellH)
    $dstRect = [System.Drawing.Rectangle]::new($x, $y, $cellOutW, $cellOutH)
    $g.DrawImage($src, $dstRect, $srcRect, [System.Drawing.GraphicsUnit]::Pixel)

    $L = $cfg.labels[$idx]
    $lx = $x + 6
    $ly = $y + $cellOutH + 8
    $tagRect = [System.Drawing.RectangleF]::new($lx, $ly, 44, 36)
    $g.FillRectangle($bTagBg, $tagRect)
    $sf = [System.Drawing.StringFormat]::new()
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString($L.tag, $fTag, $bWhite, $tagRect, $sf)
    $g.DrawString("$($L.name)  $($L.en)", $fName, $bTitle, ($lx + 54), ($ly + 1))
    $g.DrawString($L.sub, $fSub, $bSub, ($lx + 54), ($ly + 32))

    $x += $cellOutW + $gap
  }
  $y += $cellOutH + $labelH + $gap
}

$outPath = [System.IO.Path]::GetFullPath($Out)
$dir = Split-Path $outPath -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output "OK $W x $H -> $outPath"

foreach ($p in @($fTitle,$fTag,$fName,$fSub,$bTitle,$bSub,$bTagBg,$bWhite)) { $p.Dispose() }
$g.Dispose(); $bmp.Dispose(); $src.Dispose()
