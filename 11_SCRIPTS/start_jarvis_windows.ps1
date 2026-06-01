param([int]$Port = 8787)

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ApiUrl = "http://127.0.0.1:$Port"

Set-Location $Repo

Write-Host "JARVIS Windows Launcher" -ForegroundColor Magenta
Write-Host "Repo: $Repo"
Write-Host "API: $ApiUrl"

try {
  Invoke-RestMethod "$ApiUrl/status" -TimeoutSec 2 | Out-Null
  Write-Host "API already online." -ForegroundColor Green
} catch {
  Write-Host "API offline. Opening API terminal..." -ForegroundColor Yellow
  Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$Repo`"; python 11_SCRIPTS\jarvis_api.py --port $Port"
  Start-Sleep -Seconds 4
}

Write-Host "Running doctor..." -ForegroundColor Cyan
python 11_SCRIPTS\jarvis_cli.py doctor

Write-Host "Opening cockpit..." -ForegroundColor Cyan
Start-Process $ApiUrl

Write-Host "Ready. Keep API terminal open." -ForegroundColor Green
