param(
  [string]$Shots  = ".\\tools\\shots_batch1.json",
  [string]$OutDir = ".\\shots",
  [string]$Size   = "1920x1080",
  [string]$Only   = "",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$root = (Resolve-Path ".").Path
$key  = [IO.File]::ReadAllText("$env:USERPROFILE\.config\opencode\ark.key").Trim()
if (-not $key) { throw "ark.key is empty or missing" }
$uri  = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

$style = "high-quality Japanese chibi anime illustration, cinematic 16:9 keyframe, " +
         "flat 2D look, thick soft dark line art, 3-tone cel shading with one warm rim light, " +
         "candy-saturated color palette, clean simple background, no 3D render, no PBR, no realistic skin."

$suffix = "Keep the EXACT same character designs, faces, hairstyles, outfits and colors " +
          "as the reference images. Match the reference art style, line weight and lighting. " +
          "No text, no UI, no watermark, no logo."

function ToDataUrl([string]$path) {
  $full = (Resolve-Path $path).Path
  $ext = [IO.Path]::GetExtension($full).TrimStart('.').ToLower()
  if ($ext -eq "jpg") { $ext = "jpeg" }
  return "data:image/$ext;base64," + [Convert]::ToBase64String([IO.File]::ReadAllBytes($full))
}

$items = [IO.File]::ReadAllText((Resolve-Path $Shots).Path, [Text.Encoding]::UTF8) | ConvertFrom-Json
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$okCount = 0; $skipCount = 0; $failCount = 0

:shot foreach ($it in $items) {
  if ($Only) {
    $names = $Only -split ","
    if ($names -notcontains $it.name) { continue shot }
  }
  $out = Join-Path $OutDir ($it.name + ".png")
  if ((Test-Path $out) -and (-not $Force)) {
    Write-Output "SKIP $($it.name)  (exists)"
    $skipCount++
    continue shot
  }

  $images = @()
  if ($it.scene) {
    $scenePath = Join-Path $root ("scenes\" + $it.scene + ".png")
    if (-not (Test-Path $scenePath)) { Write-Output "FAIL $($it.name)  missing scene $scenePath"; $failCount++; continue shot }
    $images += (ToDataUrl $scenePath)
  }
  foreach ($c in @($it.chars)) {
    if (-not $c) { continue }
    $cp = Join-Path $root ("角色参考\" + $c + ".png")
    if (-not (Test-Path $cp)) { Write-Output "FAIL $($it.name)  missing char $cp"; $failCount++; continue shot }
    $images += (ToDataUrl $cp)
  }
  foreach ($r in @($it.refs)) {
    if (-not $r) { continue }
    $rp = Join-Path $root $r
    if (-not (Test-Path $rp)) { Write-Output "FAIL $($it.name)  missing ref $rp"; $failCount++; continue shot }
    $images += (ToDataUrl $rp)
  }

  $shotStyle = $style
  if ($it.style) { $shotStyle = $it.style }

  $prompt = $shotStyle + " " + $it.prompt + " " + $suffix
  if ($images.Count -eq 0) {
    $prompt = $shotStyle + " " + $it.prompt + " Match the film's art style: flat 2D, thick soft dark line art, warm rim light, candy palette. No text, no UI, no watermark, no logo."
  }

  $body = @{
    model           = "doubao-seedream-5-5-261028"
    prompt          = $prompt
    size            = $Size
    response_format = "url"
    watermark       = $false
  }
  if ($images.Count -eq 1) { $body.image = $images[0] } else { $body.image = $images }
  if ($it.seed) { $body.seed = [int]$it.seed }

  $json  = $body | ConvertTo-Json -Compress -Depth 6
  $bytes = [Text.Encoding]::UTF8.GetBytes($json)

  try {
    $resp = Invoke-RestMethod -Uri $uri -Method Post `
      -Headers @{ Authorization = "Bearer $key" } `
      -ContentType "application/json; charset=utf-8" `
      -Body $bytes -TimeoutSec 300

    $url = $resp.data[0].url
    if ($url) {
      Invoke-WebRequest -Uri $url -OutFile $out -TimeoutSec 180
      Write-Output ("OK   {0}  [{1}]" -f $it.name, $resp.data[0].size)
      $okCount++
    } else {
      Write-Output "ERR  $($it.name)  empty response"
      $failCount++
    }
  } catch {
    $msg = $_.ErrorDetails.Message
    if (-not $msg) { $msg = $_.Exception.Message }
    Write-Output "ERR  $($it.name)  $msg"
    $failCount++
  }
}

Write-Output ""
Write-Output "done: ok=$okCount skip=$skipCount fail=$failCount -> $OutDir"
