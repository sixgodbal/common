param(
  [Parameter(Mandatory=$true)][string]$DirectionFile,
  [Parameter(Mandatory=$true)][string]$LedgerFile
)

$map = [ordered]@{
  "1-1" = "0:00-0:08"; "1-2" = "0:08-0:11"; "1-3" = "0:11-0:14";
  "2-1" = "0:14-0:17"; "2-2" = "0:17-0:19";
  "3-1" = "0:19-0:21"; "3-2" = "0:21-0:23";
  "4-1" = "0:23-0:26"; "4-2" = "0:26-0:28"; "4-3" = "0:28-0:30";
  "5-1" = "0:30-0:36"; "5-2" = "0:36-0:39"; "5-3" = "0:39-0:41";
  "5-4" = "0:41-0:43"; "5-5" = "0:43-0:45";
  "6-1" = "0:45-0:47"; "6-2" = "0:47-0:49";
  "7-1" = "0:49-0:51"; "7-2" = "0:51-0:53"; "7-3" = "0:53-0:54";
  "8-1" = "0:54-0:57"; "9-1" = "0:57-1:00"; "9-2" = "1:00-1:02";
  "10-1" = "1:02-1:04"; "10-2" = "1:04-1:07"; "11-1" = "1:07-1:09"
}

$ids = ($map.Keys -join "|")
$pattern = "(?m)^\| (" + $ids + ") \| [^|]+ \|"

$evaluator = [System.Text.RegularExpressions.MatchEvaluator]{
  param($m)
  $id = $m.Groups[1].Value
  $t = $map[$id] -replace "-", [string][char]0x2013
  return "| " + $id + " | " + $t + " |"
}

foreach ($file in @($DirectionFile, $LedgerFile)) {
  $c = [IO.File]::ReadAllText($file, [Text.Encoding]::UTF8)
  $c = [regex]::Replace($c, $pattern, $evaluator)
  [IO.File]::WriteAllText($file, $c, (New-Object Text.UTF8Encoding($false)))
  Write-Output ("updated " + [IO.Path]::GetFileName($file))
}
