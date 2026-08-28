# Остановка сервисов, запущенных start_services.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root "scripts\.service_pids.txt"

if (-not (Test-Path $PidFile)) {
    Write-Host "PID file not found: $PidFile"
    exit 0
}

Get-Content $PidFile | ForEach-Object {
    $processId = [int]$_
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $processId -Force
        Write-Host "stopped pid $processId"
    }
}

# На случай «зависших» uvicorn после сбоя stop — освобождаем порты сервисов
foreach ($port in @(8000, 8010, 8020)) {
    $matches = netstat -ano | Select-String ":$port\s+.*LISTENING"
    foreach ($line in $matches) {
        $processId = [int](($line -split '\s+')[-1])
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "stopped listener on :$port (pid $processId)"
        }
    }
}

Remove-Item $PidFile
Write-Host "Done."
