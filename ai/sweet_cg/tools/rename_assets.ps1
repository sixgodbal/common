param(
  [string]$Map = ".\\tools\\rename_map.json"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path ".").Path
$items = [IO.File]::ReadAllText((Resolve-Path $Map).Path, [Text.Encoding]::UTF8) | ConvertFrom-Json

foreach ($it in $items) {
  $dir = Join-Path $root $it.dir
  $src = Join-Path $dir $it.src
  $dst = Join-Path $dir $it.dst
  if (-not (Test-Path $src)) { Write-Output "MISS $($it.src)"; continue }
  if (Test-Path $dst) { Remove-Item $dst -Force }
  Move-Item -Path $src -Destination $dst
  Write-Output "OK  $($it.src) -> $($it.dst)"
}
