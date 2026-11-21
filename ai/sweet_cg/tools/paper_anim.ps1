param(
  [string]$Config = ".\\tools\\paper_anim_5-1.json",
  [string]$Out = ".\\clip\\paper_5-1.mp4",
  [int]$Fps = 24,
  [double]$Duration = 6,
  [int]$W = 1920,
  [int]$H = 1080,
  [int]$StepFps = 12,
  [int]$Crf = 20,
  [switch]$KeepFrames
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
$cfg = [IO.File]::ReadAllText((Resolve-Path $Config).Path, [Text.Encoding]::UTF8) | ConvertFrom-Json

$bgPath = Join-Path $root ($cfg.bg -replace '^\.\\', '')
$bg = [System.Drawing.Bitmap]::new($bgPath)
$bgW = $bg.Width; $bgH = $bg.Height

function Get-AlphaBox($img, [int]$step) {
  $w = $img.Width; $h = $img.Height
  $minX = $w; $maxX = -1; $minY = $h; $maxY = -1
  for ($y = 0; $y -lt $h; $y += $step) {
    for ($x = 0; $x -lt $w; $x += $step) {
      if ($img.GetPixel($x, $y).A -gt 16) {
        if ($x -lt $minX) { $minX = $x }; if ($x -gt $maxX) { $maxX = $x }
        if ($y -lt $minY) { $minY = $y }; if ($y -gt $maxY) { $maxY = $y }
      }
    }
  }
  if ($maxX -lt 0) { return $null }
  return [pscustomobject]@{ X = $minX; Y = $minY; W = ($maxX - $minX); H = ($maxY - $minY) }
}

$chars = @()
foreach ($c in $cfg.chars) {
  $p = Join-Path $root ($c.file -replace '^\.\\', '')
  if (-not (Test-Path $p)) { throw "missing character: $p" }
  $img = [System.Drawing.Image]::FromFile($p)
  $bb = Get-AlphaBox $img 2
  $chH = [double]$c.h
  $chW = $chH * $bb.W / $bb.H
  $chars += [pscustomobject]@{
    Img = $img; BB = $bb; H = $chH; W = $chW
    X = [double]$c.x; Y = [double]$c.y; Phase = [double]$c.phase
  }
}

if (-not $cfg.speed) { $cfg | Add-Member -NotePropertyName speed -NotePropertyValue 80 }
if (-not $cfg.bounce) { $cfg | Add-Member -NotePropertyName bounce -NotePropertyValue 16 }
if (-not $cfg.sway) { $cfg | Add-Member -NotePropertyName sway -NotePropertyValue 2.5 }
if (-not $cfg.zoom) { $cfg | Add-Member -NotePropertyName zoom -NotePropertyValue 1.10 }
if (-not $cfg.zoomEnd) { $cfg | Add-Member -NotePropertyName zoomEnd -NotePropertyValue ($cfg.zoom + 0.02) }
if (-not $cfg.panX) { $cfg | Add-Member -NotePropertyName panX -NotePropertyValue -40 }
if (-not $cfg.panY) { $cfg | Add-Member -NotePropertyName panY -NotePropertyValue -8 }
if (-not $cfg.dust) { $cfg | Add-Member -NotePropertyName dust -NotePropertyValue $true }
if (-not $cfg.cadence) { $cfg | Add-Member -NotePropertyName cadence -NotePropertyValue 1.4 }
if (-not $cfg.lean) { $cfg | Add-Member -NotePropertyName lean -NotePropertyValue 0 }
if (-not $cfg.squash) { $cfg | Add-Member -NotePropertyName squash -NotePropertyValue 0 }

$frames = Join-Path $root "clip\_paper_frames"
if (Test-Path $frames) { Get-ChildItem $frames -Filter *.png | Remove-Item -Force }
else { New-Item -ItemType Directory -Path $frames -Force | Out-Null }

$total = [int]($Fps * $Duration)
$canvas = [System.Drawing.Bitmap]::new($W, $H, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$g = [System.Drawing.Graphics]::FromImage($canvas)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

$rng = New-Object System.Random(20261121)
$parts = @()
for ($i = 0; $i -lt 36; $i++) {
  $parts += [pscustomobject]@{
    X = $rng.Next(0, $W); Y = $rng.Next(120, 900)
    VX = ($rng.NextDouble() - 0.3) * 18; VY = -6 - $rng.NextDouble() * 14
    R = 1.2 + $rng.NextDouble() * 2.6; A = 34 + $rng.Next(0, 46)
  }
}

for ($f = 0; $f -lt $total; $f++) {
  $t = $f / [double]$Fps
  $qt = [math]::Floor($t * $StepFps) / [double]$StepFps
  $prog = $t / $Duration

  $g.Clear([System.Drawing.Color]::Black)

  $z = $cfg.zoom + ($cfg.zoomEnd - $cfg.zoom) * $prog
  $sw = $bgW / $z; $sh = $bgH / $z
  $sx = ($bgW - $sw) / 2 + $cfg.panX * $prog
  $sy = ($bgH - $sh) / 2 + $cfg.panY * $prog
  if ($sx -lt 0) { $sx = 0 }; if ($sx + $sw -gt $bgW) { $sx = $bgW - $sw }
  if ($sy -lt 0) { $sy = 0 }; if ($sy + $sh -gt $bgH) { $sy = $bgH - $sh }

  $g.DrawImage($bg, [System.Drawing.Rectangle]::new(0, 0, $W, $H),
    [System.Drawing.Rectangle]::new([int]$sx, [int]$sy, [int]$sw, [int]$sh),
    [System.Drawing.GraphicsUnit]::Pixel)

  foreach ($p in $parts) {
    $px = (($p.X + $p.VX * $t) % $W + $W) % $W
    $py = $p.Y + $p.VY * $t
    $b = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb([int]$p.A, 255, 246, 190))
    $g.FillEllipse($b, [float]($px - $p.R), [float]($py - $p.R), [float]($p.R * 2), [float]($p.R * 2))
    $b.Dispose()
  }

  foreach ($c in $chars) {
    $x = $c.X + $cfg.speed * $t
    $hop = [math]::Abs([math]::Sin(2 * [math]::PI * $cfg.cadence * $qt + $c.Phase)) * $cfg.bounce
    $rot = $cfg.lean + [math]::Sin(2 * [math]::PI * 0.7 * $qt + $c.Phase) * $cfg.sway

    $shAlpha = 34 - [int]($hop)
    if ($shAlpha -lt 10) { $shAlpha = 10 }
    $sb = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($shAlpha, 60, 45, 35))
    $g.FillEllipse($sb, [float]($x - $c.W * 0.34), [float]($c.Y - 14), [float]($c.W * 0.68), [float]24)
    $sb.Dispose()

    if ($cfg.dust) {
      $dirSign = [Math]::Sign($cfg.speed)
      if ($dirSign -eq 0) { $dirSign = 1 }
      for ($k = 0; $k -lt 3; $k++) {
        $dx = -$dirSign * ($c.W * 0.30 + (($t * 90 + $k * 26) % 80))
        $alpha = [int](46 * (1 - (($t * 90 + $k * 26) % 80) / 90))
        if ($alpha -lt 0) { $alpha = 0 }
        $db = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($alpha, 225, 205, 170))
        $r = 10 + $k * 3
        $g.FillEllipse($db, [float]($x + $dx - $r), [float]($c.Y - 18 - $k * 4), [float]($r * 2), [float]($r * 1.2))
        $db.Dispose()
      }
    }

    $state = $g.Save()
    $g.TranslateTransform([float]$x, [float]($c.Y - $hop))
    $g.RotateTransform([float]$rot)
    if ($cfg.squash -gt 0) {
      $k2 = (($hop / $cfg.bounce) * 2 - 1) * $cfg.squash
      $g.ScaleTransform([float](1 - $k2 * 0.6), [float](1 + $k2))
    }
    $g.DrawImage($c.Img,
      [System.Drawing.RectangleF]::new([float](-$c.W / 2), [float](-$c.H), [float]$c.W, [float]$c.H),
      [System.Drawing.Rectangle]::new($c.BB.X, $c.BB.Y, $c.BB.W, $c.BB.H),
      [System.Drawing.GraphicsUnit]::Pixel)
    $g.Restore($state)
  }

  $wa = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(10, 255, 214, 140))
  $g.FillRectangle($wa, 0, 0, $W, $H)
  $wa.Dispose()

  $canvas.Save((Join-Path $frames ("f{0:d4}.png" -f $f)), [System.Drawing.Imaging.ImageFormat]::Png)
}

$g.Dispose(); $canvas.Dispose(); $bg.Dispose()
foreach ($c in $chars) { $c.Img.Dispose() }
Write-Output "frames: $total -> $frames"

$ff = $null
$cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($cmd) { $ff = $cmd.Source }
if (-not $ff) {
  $cand = Get-ChildItem "$env:TEMP\ffmpeg_bin" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($cand) { $ff = $cand.FullName }
}
if (-not $ff) { throw "ffmpeg not found" }

$outPath = Join-Path $root $Out
$od = Split-Path -Parent $outPath
if (-not (Test-Path $od)) { New-Item -ItemType Directory -Path $od -Force | Out-Null }

$oldEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$log = & $ff -y -framerate $Fps -i (Join-Path $frames "f%04d.png") -c:v libx264 -pix_fmt yuv420p -crf $Crf -preset veryfast $outPath 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = $oldEap
if ($code -ne 0) { $log | Select-Object -Last 12; throw "ffmpeg failed ($code)" }
Write-Output "OK -> $Out"
if (-not $KeepFrames) { Remove-Item $frames -Recurse -Force -ErrorAction SilentlyContinue }
