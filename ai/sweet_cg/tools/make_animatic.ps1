param(
  [string]$List = ".\\shots\\_animatic_list.txt",
  [string]$Out  = ".\\clip\\animatic_v1.mp4",
  [int]$Fps = 24,
  [int]$W = 1920,
  [int]$H = 1080,
  [int]$Crf = 20,
  [string]$WhiteFadeShot = "",
  [double]$WhiteFadeDur = 1.5
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$root = (Resolve-Path ".").Path
$listPath = (Resolve-Path $List).Path

$ff = $null
$c = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($c) { $ff = $c.Source }
if (-not $ff) {
  $cand = Get-ChildItem "$env:TEMP\ffmpeg_bin" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($cand) { $ff = $cand.FullName }
}
if (-not $ff) { throw "ffmpeg not found" }

$raw = [IO.File]::ReadAllLines($listPath, [Text.Encoding]::UTF8)
$items = @()
for ($i = 0; $i -lt $raw.Count; $i++) {
  if ($raw[$i] -match "^file '(.+)'$") {
    $p = $Matches[1]
    $dur = 1.0
    if ($i + 1 -lt $raw.Count -and $raw[$i + 1] -match "^duration\s+([\d\.]+)") { $dur = [double]$Matches[1] }
    if (-not (Test-Path $p)) { throw "missing image: $p" }
    $items += [pscustomobject]@{ Path = $p; Dur = $dur }
  }
}
if ($items.Count -eq 0) { throw "no items in $listPath" }

$argv = @("-y")
foreach ($it in $items) {
  $argv += @("-loop", "1", "-t", $it.Dur.ToString([Globalization.CultureInfo]::InvariantCulture), "-i", $it.Path)
}

$parts = @()
$labels = @()
$inv = [Globalization.CultureInfo]::InvariantCulture
for ($i = 0; $i -lt $items.Count; $i++) {
  $it = $items[$i]
  $chain = ("[{0}:v]scale={1}:{2}:force_original_aspect_ratio=decrease,pad={1}:{2}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={3}" -f $i, $W, $H, $Fps)
  if ($WhiteFadeShot -and ([IO.Path]::GetFileNameWithoutExtension($it.Path) -eq $WhiteFadeShot)) {
    $st = [Math]::Max(0.0, $it.Dur - $WhiteFadeDur)
    $chain += (",fade=t=out:st={0}:d={1}:color=white" -f $st.ToString($inv), $WhiteFadeDur.ToString($inv))
  }
  $parts += ($chain + ("[v{0}]" -f $i))
  $labels += ("[v{0}]" -f $i)
}
$filter = ($parts -join ";") + ";" + ($labels -join "") + ("concat=n={0}:v=1:a=0[out]" -f $items.Count)
$mapLabel = "[out]"

$outPath = Join-Path $root $Out
$od = Split-Path -Parent $outPath
if (-not (Test-Path $od)) { New-Item -ItemType Directory -Path $od -Force | Out-Null }

$argv += @("-filter_complex", $filter, "-map", $mapLabel, "-c:v", "libx264", "-crf", $Crf, "-preset", "veryfast", "-pix_fmt", "yuv420p", $outPath)

$oldEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$log = & $ff @argv 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = $oldEap
if ($code -ne 0) {
  $log | Select-Object -Last 15
  throw "ffmpeg failed with exit code $code"
}
$log | Select-Object -Last 2

$total = ($items | Measure-Object -Property Dur -Sum).Sum
Write-Output ("OK  {0} shots / {1}s expected -> {2}" -f $items.Count, $total, $Out)
