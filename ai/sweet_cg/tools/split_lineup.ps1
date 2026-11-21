param(
  [string]$OutDir = ".\\tools\\refs4",
  [int]$Luma     = 238,
  [int]$MinGap   = 18,
  [int]$MinFill  = 6
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path ".").Path
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# find the wide PNG that is not inside renders_*
$cand = Get-ChildItem -Path "." -Recurse -Filter *.png -File |
  Where-Object { $_.FullName -notmatch '\\renders_' -and $_.FullName -notmatch '\\tools\\' } |
  ForEach-Object {
    $b = [System.Drawing.Image]::FromFile($_.FullName)
    $o = [pscustomobject]@{ File = $_; W = $b.Width; H = $b.Height }
    $b.Dispose()
    $o
  } | Where-Object { $_.W -gt $_.H } | Sort-Object W -Descending

if (-not $cand) { throw "wide lineup png not found" }
$lineup = $cand[0].File
Write-Output "lineup: $($lineup.Name)  $($cand[0].W)x$($cand[0].H)"

$bmp = [System.Drawing.Bitmap]::new($lineup.FullName)
$W = $bmp.Width; $H = $bmp.Height
$isChar = New-Object bool[] $W

for ($x = 0; $x -lt $W; $x += 2) {
  $count = 0
  for ($y = 0; $y -lt $H; $y += 2) {
    $p = $bmp.GetPixel($x, $y)
    $l = 0.299 * $p.R + 0.587 * $p.G + 0.114 * $p.B
    $sat = [math]::Max($p.R, [math]::Max($p.G, $p.B)) - [math]::Min($p.R, [math]::Min($p.G, $p.B))
    if ($l -lt $Luma -or $sat -gt 40) { $count++ }
  }
  if ($count -ge $MinFill) { $isChar[$x] = $true }
}

# group columns into runs, merging small gaps
$runs = @()
$start = -1
$gap = 0
for ($x = 0; $x -lt $W; $x++) {
  if ($isChar[$x]) {
    if ($start -lt 0) { $start = $x }
    $gap = 0
  }
  else {
    if ($start -ge 0) {
      $gap++
      if ($gap -ge $MinGap) {
        $runs += [pscustomobject]@{ Start = $start; End = ($x - $gap) }
        $start = -1; $gap = 0
      }
    }
  }
}
if ($start -ge 0) { $runs += [pscustomobject]@{ Start = $start; End = ($W - 1) } }

$runs = $runs | Where-Object { ($_.End - $_.Start) -gt 80 } | Sort-Object Start
Write-Output ("runs: " + (($runs | ForEach-Object { "$($_.Start)-$($_.End)" }) -join ", "))
if ($runs.Count -ne 4) { Write-Output "WARN: expected 4 runs" }

$i = 0
foreach ($r in $runs) {
  $i++
  $x0 = $r.Start; $x1 = $r.End
  $top = $H; $bot = 0
  for ($x = $x0; $x -le $x1; $x += 2) {
    for ($y = 0; $y -lt $H; $y += 2) {
      $p = $bmp.GetPixel($x, $y)
      $l = 0.299 * $p.R + 0.587 * $p.G + 0.114 * $p.B
      $sat = [math]::Max($p.R, [math]::Max($p.G, $p.B)) - [math]::Min($p.R, [math]::Min($p.G, $p.B))
      if ($l -lt $Luma -or $sat -gt 40) {
        if ($y -lt $top) { $top = $y }
        if ($y -gt $bot) { $bot = $y }
      }
    }
  }
  $pad = 10
  $cx = [int][math]::Max(0, $x0 - $pad)
  $cy = [int][math]::Max(0, $top - $pad)
  $cw = [int][math]::Min($W - $cx, ($x1 - $x0) + 2 * $pad)
  $ch = [int][math]::Min($H - $cy, ($bot - $top) + 2 * $pad)

  $out = New-Object System.Drawing.Bitmap $cw, $ch
  $g = [System.Drawing.Graphics]::FromImage($out)
  $g.DrawImage($bmp, [System.Drawing.Rectangle]::new(0, 0, $cw, $ch), [System.Drawing.Rectangle]::new($cx, $cy, $cw, $ch), [System.Drawing.GraphicsUnit]::Pixel)
  $g.Dispose()
  $path = Join-Path (Join-Path $root $OutDir.TrimStart(".\")) ("char_$i.png")
  $out.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $out.Dispose()
  Write-Output "saved char_$i.png  ${cw}x${ch}"
}

$bmp.Dispose()
