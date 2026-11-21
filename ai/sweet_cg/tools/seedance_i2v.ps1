param(
  [string]$Image  = ".\\scenes\\shot_2-1_h.png",
  [string]$Prompt = "丛林深处透出白色光芒，光线缓慢脉动闪烁，树叶被微风吹动轻轻摇摆，光束中浮尘缓缓漂浮，镜头极缓慢向前推进，神秘不安的氛围，保持画面风格完全不变，不出现人物",
  [string]$Model  = "doubao-seedance-2-5-260628",
  [string]$Out    = ".\\clip\\seedance_2-1.mp4",
  [int]$Duration  = 5,
  [string]$Ratio  = "16:9",
  [string]$Role   = "first_frame",
  [int]$PollSec   = 6
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$key  = [IO.File]::ReadAllText("$env:USERPROFILE\.config\opencode\ark.key").Trim()
$base = "https://ark.cn-beijing.volces.com/api/v3"
$hdr  = @{ Authorization = "Bearer $key" }

$root = (Resolve-Path ".").Path
function Resolve-Full($p) { Join-Path $root ($p -replace '^\.\\', '') }

$imgPath = Resolve-Full $Image
if (-not (Test-Path $imgPath)) { throw "image not found: $imgPath" }
$ext = [IO.Path]::GetExtension($imgPath).TrimStart('.').ToLower()
if ($ext -eq "jpg") { $ext = "jpeg" }
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($imgPath))
Write-Output ("image: {0}  base64 {1:N1} MB" -f (Split-Path $imgPath -Leaf), ($b64.Length / 1MB))

$payload = @{
  model   = $Model
  content = @(
    @{ type = "text"; text = $Prompt },
    @{ type = "image_url"; image_url = @{ url = "data:image/$ext;base64,$b64" }; role = $Role }
  )
  duration  = $Duration
  watermark = $false
}
# first_frame / first-last-frame 模式下输出比例跟随首帧图，不能传 ratio
if ($Role -eq "reference_image") { $payload["ratio"] = $Ratio }

$json  = $payload | ConvertTo-Json -Depth 8 -Compress
$bytes = [Text.Encoding]::UTF8.GetBytes($json)

Write-Output "creating task..."
try {
  $resp = Invoke-RestMethod -Uri "$base/contents/generations/tasks" -Method Post -Headers $hdr `
    -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec 600
}
catch {
  $msg = $_.ErrorDetails.Message; if (-not $msg) { $msg = $_.Exception.Message }
  throw "create failed: $msg"
}

$id = $resp.id
Write-Output "task: $id"

$deadline = (Get-Date).AddMinutes(20)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds $PollSec
  try {
    $t = Invoke-RestMethod -Uri "$base/contents/generations/tasks/$id" -Headers $hdr -TimeoutSec 60
  }
  catch {
    $msg = $_.ErrorDetails.Message; if (-not $msg) { $msg = $_.Exception.Message }
    Write-Output "poll error: $msg"
    continue
  }
  Write-Output ("status: {0}" -f $t.status)
  if ($t.status -eq "succeeded") {
    $url = $t.content.video_url
    $outPath = Resolve-Full $Out
    $od = Split-Path -Parent $outPath
    if (-not (Test-Path $od)) { New-Item -ItemType Directory -Path $od -Force | Out-Null }
    Invoke-WebRequest -Uri $url -OutFile $outPath -TimeoutSec 600
    Write-Output "OK -> $Out"
    exit 0
  }
  if ($t.status -eq "failed") {
    Write-Output ("failed: " + ($t.error | ConvertTo-Json -Compress))
    exit 1
  }
}
throw "timeout waiting for task $id"
