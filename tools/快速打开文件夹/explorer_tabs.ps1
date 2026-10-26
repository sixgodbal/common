param(
  [Parameter(Mandatory = $true)][int]$Hwnd,
  [Parameter(Mandatory = $true)][string]$PathsFile
)

# Opens a group of folders as tabs in ONE existing Explorer window.
#
# Both steps work in the background - no focus stealing, no keystrokes,
# no clipboard usage:
#   1. UI Automation clicks Explorer's "new tab" button (InvokePattern).
#   2. The new tab shows up as a Shell.Windows item whose LocationURL is empty;
#      Shell.Application's Navigate2 then loads the folder into that tab.
#
# Output: one line of JSON {"opened":n,"total":n,"errors":[],"ms_per_tab":0}

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$hwndValue = $Hwnd
$target = [IntPtr]$Hwnd
$errors = New-Object System.Collections.ArrayList
$times = New-Object System.Collections.ArrayList

function Get-Win {
  param([IntPtr]$handle)
  for ($i = 0; $i -lt 20; $i++) {
    try { return [System.Windows.Automation.AutomationElement]::FromHandle($handle) } catch { Start-Sleep -Milliseconds 80 }
  }
  return $null
}

function Get-TabItems {
  param($win)
  if (-not $win) { return @() }
  $top = $win.Current.BoundingRectangle.Top
  $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)
  $out = @()
  foreach ($t in $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)) {
    if ($t.Current.ClassName -ne "ListViewItem") { continue }
    $r = $t.Current.BoundingRectangle
    if (($r.Top - $top) -gt 90) { continue }
    $out += $t
  }
  return $out
}

function Get-SelectedTabName {
  param($win)
  foreach ($t in Get-TabItems $win) {
    try {
      if ($t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected) {
        return [string]$t.Current.Name
      }
    } catch { }
  }
  return ""
}

$paths = @()
try {
  $json = [System.IO.File]::ReadAllText($PathsFile, [System.Text.Encoding]::UTF8)
  foreach ($p in ($json | ConvertFrom-Json)) { $paths += [string]$p }
} catch {
  Write-Output (@{ opened = 0; total = 0; errors = @("read paths failed"); ms_per_tab = 0 } | ConvertTo-Json -Compress)
  exit 0
}

$total = $paths.Count
if ($total -eq 0) {
  Write-Output (@{ opened = 0; total = 0; errors = @("no paths"); ms_per_tab = 0 } | ConvertTo-Json -Compress)
  exit 0
}

$shell = New-Object -ComObject Shell.Application

function Get-WindowTabs {
  $out = @()
  foreach ($s in $shell.Windows()) {
    try { if ([int]$s.HWND -eq $hwndValue) { $out += $s } } catch { }
  }
  return $out
}

$opened = 1
$addCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, "AddButton")

for ($i = 1; $i -lt $total; $i++) {
  $path = $paths[$i]
  $leaf = Split-Path -Path $path -Leaf
  if ([string]::IsNullOrEmpty($leaf)) { $leaf = $path }
  $sw = [System.Diagnostics.Stopwatch]::StartNew()

  $win = Get-Win $target
  if (-not $win) { $errors.Add("window lost") | Out-Null; break }

  $btn = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $addCond)
  if (-not $btn) { $errors.Add("no add button") | Out-Null; break }

  try {
    $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  } catch {
    $errors.Add("invoke add failed") | Out-Null
    break
  }

  $entry = $null
  for ($k = 0; $k -lt 40; $k++) {
    Start-Sleep -Milliseconds 80
    $empty = @(Get-WindowTabs | Where-Object { [string]::IsNullOrEmpty($_.LocationURL) })
    if ($empty.Count -gt 0) { $entry = $empty[$empty.Count - 1]; break }
  }
  if (-not $entry) { $errors.Add("tab not created") | Out-Null; break }

  $arrived = $false
  for ($attempt = 1; $attempt -le 2 -and -not $arrived; $attempt++) {
    try { $entry.Navigate2($path) } catch { }
    for ($k = 0; $k -lt 40; $k++) {
      Start-Sleep -Milliseconds 80
      $name = ""
      try { $name = [string]$entry.LocationName } catch { }
      if ($name -and $name.IndexOf($leaf, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
        $arrived = $true
        break
      }
      $selected = Get-SelectedTabName (Get-Win $target)
      if ($selected -and $selected.IndexOf($leaf, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
        $arrived = $true
        break
      }
    }
  }

  if ($arrived) {
    $opened = $opened + 1
    $times.Add($sw.Elapsed.TotalMilliseconds) | Out-Null
  } else {
    $errors.Add("navigation timeout") | Out-Null
  }
}

$msPerTab = 0
if ($times.Count -gt 0) {
  $sum = 0
  foreach ($t in $times) { $sum += $t }
  $msPerTab = [int]($sum / $times.Count)
}

$result = @{ opened = $opened; total = $total; errors = @($errors); ms_per_tab = $msPerTab }
Write-Output ($result | ConvertTo-Json -Compress)
