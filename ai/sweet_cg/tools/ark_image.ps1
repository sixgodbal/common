param(
  [string]$Prompts = ".\tools\prompts.json",
  [string]$OutDir  = ".\renders_v1",
  [string]$Model   = "doubao-seedream-5-5-261028",
  [string]$Size  = "1728x2304,2K"
)

$ErrorActionPreference = "Stop"
$sizes = $Size -split ","
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$key = [IO.File]::ReadAllText("$env:USERPROFILE\.config\opencode\ark.key").Trim()
if (-not $key) { throw "ark.key is empty or missing" }
$uri = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

$items = [IO.File]::ReadAllText((Resolve-Path $Prompts).Path, [Text.Encoding]::UTF8) | ConvertFrom-Json
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

foreach ($it in $items) {
  $ok = $false
  foreach ($s in $sizes) {
    $body = @{
      model           = $Model
      prompt          = $it.prompt
      size            = $s
      response_format = "url"
      watermark       = $false
    }
    if ($it.image) {
      $img = [string]$it.image
      if (Test-Path $img) {
        $ext = [IO.Path]::GetExtension($img).TrimStart('.').ToLower()
        if ($ext -eq "jpg") { $ext = "jpeg" }
        $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path $img).Path))
        $body.image = "data:image/$ext;base64,$b64"
      }
      else { $body.image = $img }
    }
    if ($it.seed)  { $body.seed  = [int]$it.seed }

    $json  = $body | ConvertTo-Json -Compress -Depth 6
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)

    try {
      $resp = Invoke-RestMethod -Uri $uri -Method Post `
        -Headers @{ Authorization = "Bearer $key" } `
        -ContentType "application/json; charset=utf-8" `
        -Body $bytes -TimeoutSec 300

      $url = $resp.data[0].url
      if ($url) {
        $out = Join-Path $OutDir ($it.name + ".png")
        Invoke-WebRequest -Uri $url -OutFile $out -TimeoutSec 180
        Write-Output "OK   $($it.name)  [$s]"
        $ok = $true
        break
      }
      Write-Output "ERR  $($it.name)  [$s]  empty response"
    }
    catch {
      $msg = $_.ErrorDetails.Message
      if (-not $msg) { $msg = $_.Exception.Message }
      Write-Output "ERR  $($it.name)  [$s]  $msg"
    }
  }
  if (-not $ok) { Write-Output "FAIL $($it.name)" }
}
