# Запуск трёх микросервисов рекомендаций (Windows PowerShell).
# Использование из корня репозитория:
#   powershell -ExecutionPolicy Bypass -File .\scripts\start_services.ps1

$ErrorActionPreference = "Stop"

# Корень репозитория: scripts/ -> на уровень выше
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root "env_recsys_start\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

# Скачиваем отсутствующие parquet из S3, затем проверяем артефакты этапа 3
& $Python -c "from app.s3_storage import ensure_artifacts; ensure_artifacts(); print('artifacts ok')"
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось подготовить recsys/recommendations/*.parquet (этап 3 или S3 / .env.local)."
}

$PidFile = Join-Path $Root "scripts\.service_pids.txt"
if (Test-Path $PidFile) { Remove-Item $PidFile }

function Start-UvicornService {
    param(
        [string]$Module,
        [int]$Port
    )

    # Запускаем каждый сервис в отдельном фоновом процессе
    $proc = Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", $Module, "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $Root `
        -PassThru `
        -WindowStyle Minimized

    Add-Content -Path $PidFile -Value $proc.Id
    Write-Host "started $Module on :$Port (pid $($proc.Id))"
}

Write-Host "Starting services..."

# Event Store — без тяжёлой загрузки данных
Start-UvicornService "app.events_service:app" 8020

# Feature Store грузит ~500 MB similar.parquet — стартуем первым из «тяжёлых»
Start-UvicornService "app.features_service:app" 8010

function Wait-Health {
    param([string[]]$Urls, [int]$TimeoutMinutes = 10)
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $allUp = $true
        foreach ($url in $Urls) {
            try {
                $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
                if ($r.StatusCode -ne 200) { $allUp = $false; break }
            } catch {
                $allUp = $false
                break
            }
        }
        if ($allUp) { return $true }
        Start-Sleep -Seconds 5
    }
    return $false
}

if (-not (Wait-Health @("http://127.0.0.1:8020/health", "http://127.0.0.1:8010/health"))) {
    Write-Warning "Event/Feature Store не поднялись за 10 минут."
} else {
    Write-Host "Event + Feature stores are up."
}

# Recommendation Store грузит ~50M строк personal — после Feature Store (меньше пик RAM)
Start-UvicornService "app.recommendations_service:app" 8000

$healthUrls = @(
    "http://127.0.0.1:8020/health",
    "http://127.0.0.1:8010/health",
    "http://127.0.0.1:8000/health"
)
if (-not (Wait-Health $healthUrls 10)) {
    Write-Warning "Сервисы запущены, но health-check не прошёл за 10 минут. Проверьте логи процессов."
} else {
    Write-Host "All services are up."
}

Write-Host "PIDs saved to $PidFile"
Write-Host "Run tests: python test_service.py > test_service.log"
