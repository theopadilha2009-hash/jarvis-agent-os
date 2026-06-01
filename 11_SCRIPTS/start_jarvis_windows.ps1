param(
  [int]$Port = 8787,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ApiUrl = "http://127.0.0.1:$Port"

Set-Location $Repo

function Write-Step($Text) {
  Write-Host ""
  Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Get-JarvisPython {
  $candidates = @(
    @{ Name = "python"; Args = @() },
    @{ Name = "py"; Args = @("-3") },
    @{ Name = "python3"; Args = @() }
  )

  foreach ($c in $candidates) {
    try {
      $cmd = Get-Command $c.Name -ErrorAction Stop
      $args = @($c.Args) + @("--version")
      $out = & $cmd.Source @args 2>&1

      if ("$out" -match "Python") {
        return @{
          Exe = $cmd.Source
          Args = @($c.Args)
          Label = (($c.Name + " " + ($c.Args -join " ")).Trim())
          Version = "$out"
        }
      }
    } catch {
      continue
    }
  }

  return $null
}

function Invoke-JarvisPython {
  param(
    [hashtable]$Python,
    [string]$Script,
    [string[]]$ScriptArgs = @()
  )

  $allArgs = @($Python.Args) + @($Script) + $ScriptArgs
  & $Python.Exe @allArgs
}

function Test-JarvisApi {
  try {
    Invoke-RestMethod "$ApiUrl/status" -TimeoutSec 2 | Out-Null
    return $true
  } catch {
    return $false
  }
}

Write-Host ""
Write-Host "JARVIS Windows Launcher" -ForegroundColor Magenta
Write-Host "Repo: $Repo"
Write-Host "API:  $ApiUrl"
Write-Host "Status real: local only. No deploy. No automatic push. No secrets."

Write-Step "Python Detection"
$Py = Get-JarvisPython

if (-not $Py) {
  Write-Host "Python was not found in this Windows user PATH." -ForegroundColor Red
  Write-Host ""
  Write-Host "Try one of these:" -ForegroundColor Yellow
  Write-Host "1) winget install -e --id Python.Python.3.12 --scope user"
  Write-Host "2) Install Python from Microsoft Store"
  Write-Host "3) Reopen PowerShell after install"
  Write-Host ""
  Write-Host "Repo is still OK. Only Python execution is blocked on this machine." -ForegroundColor Yellow
  exit 1
}

Write-Host "Using: $($Py.Label)" -ForegroundColor Green
Write-Host "Version: $($Py.Version)"

Write-Step "Git"
git status -sb

Write-Step "API"
if (Test-JarvisApi) {
  Write-Host "API already online." -ForegroundColor Green
} else {
  Write-Host "API offline. Opening API terminal..." -ForegroundColor Yellow

  $pyArgs = @($Py.Args) -join " "
  if ($pyArgs.Length -gt 0) {
    $cmd = "cd `"$Repo`"; & `"$($Py.Exe)`" $pyArgs 11_SCRIPTS\jarvis_api.py --port $Port"
  } else {
    $cmd = "cd `"$Repo`"; & `"$($Py.Exe)`" 11_SCRIPTS\jarvis_api.py --port $Port"
  }

  Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd
  Start-Sleep -Seconds 4
}

Write-Step "Doctor"
Invoke-JarvisPython -Python $Py -Script "11_SCRIPTS\jarvis_cli.py" -ScriptArgs @("doctor")

if (-not $NoBrowser) {
  Write-Step "Opening Cockpit"
  Start-Process $ApiUrl
}

Write-Host ""
Write-Host "Ready. Keep API terminal open." -ForegroundColor Green
