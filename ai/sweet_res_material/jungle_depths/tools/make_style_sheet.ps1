param(
  [string]$Sheet = "D:\ai\git_tools\common\ai\sweet_res_material\jungle_depths\out\jungle_depths_mapstyle_a.png",
  [string]$Out   = "D:\ai\git_tools\common\ai\sweet_res_material\jungle_depths\out\_style_options_10x10.png",
  [int]$Cols = 2,
  [int]$Rows = 2
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

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

$labels = @(
  @{ Tag = "A"; Name = "苔石遗迹"; En = "MOSSY STONE RUIN"; Sub = "灰绿湿石 + 树根/蕨类，冷调，蛇纹砖只做点缀" },
  @{ Tag = "B"; Name = "树根密林"; En = "ROOT HOLLOW"; Sub = "泥土落叶 + 巨根/树桩，暖绿，蛇雕在树桩上" },
  @{ Tag = "C"; Name = "蛇神庙";   En = "SERPENT TEMPLE"; Sub = "暖砂岩 + 青玉/旧金，蛇元素最明显，适合关卡主体" },
  @{ Tag = "D"; Name = "荧光沼泽"; En = "GLOW SWAMP"; Sub = "深青泥沼 + 发光蘑菇/水洼，冷调高对比" }
)

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

$fTitle = [System.Drawing.Font]::new("Microsoft YaHei", 30, [System.Drawing.FontStyle]::Bold)
$fTag   = [System.Drawing.Font]::new("Microsoft YaHei", 22, [System.Drawing.FontStyle]::Bold)
$fName  = [System.Drawing.Font]::new("Microsoft YaHei", 16, [System.Drawing.FontStyle]::Bold)
$fSub   = [System.Drawing.Font]::new("Microsoft YaHei", 11, [System.Drawing.FontStyle]::Regular)
$bTitle = [System.Drawing.SolidBrush]::new($titleCol)
$bSub   = [System.Drawing.SolidBrush]::new($subCol)
$bTagBg = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 82, 118, 76))
$bWhite = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)

$g.DrawString("丛林（森林）深处 · 10×10 风格选型", $fTitle, $bTitle, $pad, 28)
$g.DrawString("seed 812  ·  同一张图 4 个方案，选定后再出 40×40 大地图", $fSub, $bSub, ($pad + 4), 70)

$y = $titleH + $pad
for ($r = 0; $r -lt $Rows; $r++) {
  $x = $pad
  for ($c = 0; $c -lt $Cols; $c++) {
    $idx = $r * $Cols + $c
    $srcRect = [System.Drawing.Rectangle]::new($c * $cellW, $r * $cellH, $cellW, $cellH)
    $dstRect = [System.Drawing.Rectangle]::new($x, $y, $cellOutW, $cellOutH)
    $g.DrawImage($src, $dstRect, $srcRect, [System.Drawing.GraphicsUnit]::Pixel)

    $L = $labels[$idx]
    $lx = $x + 6
    $ly = $y + $cellOutH + 8
    $tagRect = [System.Drawing.RectangleF]::new($lx, $ly, 44, 36)
    $g.FillRectangle($bTagBg, $tagRect)
    $sf = [System.Drawing.StringFormat]::new()
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString($L.Tag, $fTag, $bWhite, $tagRect, $sf)
    $g.DrawString("$($L.Name)  $($L.En)", $fName, $bTitle, ($lx + 54), ($ly + 1))
    $g.DrawString($L.Sub, $fSub, $bSub, ($lx + 54), ($ly + 32))

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
