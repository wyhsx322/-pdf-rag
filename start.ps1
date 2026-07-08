param(
    [switch]$NoRestart,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BackendLog = Join-Path $Root "server.log"
$BackendErr = Join-Path $Root "server.err.log"
$FrontendLog = Join-Path $Root "frontend.log"
$FrontendErr = Join-Path $Root "frontend.err.log"

$BackendUrl = "http://127.0.0.1:8000"
$FrontendUrl = "http://127.0.0.1:5173"

function Get-PortOwners {
    param([int]$Port)
    $owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($ownerId in $owners) {
        Get-Process -Id $ownerId -ErrorAction SilentlyContinue
    }
}

function Stop-PortOwner {
    param([int]$Port)
    $procs = @(Get-PortOwners -Port $Port)
    foreach ($proc in $procs) {
        Write-Host "Stopping port $Port owner: $($proc.ProcessName)($($proc.Id))" -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force
    }
    if ($procs.Count -gt 0) { Start-Sleep -Seconds 1 }
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }
    return $false
}

function Start-Backend {
    if (-not (Test-Path $Python)) {
        throw "Python venv not found: $Python"
    }
    if (@(Get-PortOwners -Port 8000).Count -gt 0) {
        Write-Host "Backend port 8000 is already listening; skip start." -ForegroundColor Yellow
        return
    }
    Write-Host "Starting backend: $BackendUrl" -ForegroundColor Cyan
    Set-Content -Path $BackendLog -Value "" -Encoding utf8
    Set-Content -Path $BackendErr -Value "" -Encoding utf8
    Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $Root `
        -WindowStyle Hidden
}

function Start-Frontend {
    if (-not (Test-Path (Join-Path $Frontend "package.json"))) {
        throw "Frontend package.json not found: $Frontend"
    }
    if (@(Get-PortOwners -Port 5173).Count -gt 0) {
        Write-Host "Frontend port 5173 is already listening; skip start." -ForegroundColor Yellow
        return
    }
    Write-Host "Starting frontend: $FrontendUrl" -ForegroundColor Cyan
    Set-Content -Path $FrontendLog -Value "" -Encoding utf8
    Set-Content -Path $FrontendErr -Value "" -Encoding utf8
    Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
        -WorkingDirectory $Frontend `
        -WindowStyle Hidden
}

if (-not $NoRestart) {
    Stop-PortOwner -Port 5173
    Stop-PortOwner -Port 8000
}

Start-Backend
Start-Frontend

Write-Host "Waiting for services..." -ForegroundColor Cyan
$backendReady = Wait-Http -Url "$BackendUrl/api/health" -TimeoutSeconds 40
$frontendReady = Wait-Http -Url "$FrontendUrl/writing" -TimeoutSeconds 40

if (-not $backendReady) {
    Write-Host "Backend failed or timed out. See: $BackendErr" -ForegroundColor Red
    exit 1
}
if (-not $frontendReady) {
    Write-Host "Frontend failed or timed out. See: $FrontendErr" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Services are ready:" -ForegroundColor Green
Write-Host "  Frontend: $FrontendUrl/writing" -ForegroundColor Green
Write-Host "  Backend:  $BackendUrl/api/health" -ForegroundColor Green
Write-Host "  API docs: $BackendUrl/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Default behavior: stop existing 5173/8000 owners, then start fresh." -ForegroundColor DarkGray
Write-Host "Use -NoRestart only when you want to reuse already-running services." -ForegroundColor DarkGray

if (-not $NoBrowser) {
    Start-Process "$FrontendUrl/writing"
}
