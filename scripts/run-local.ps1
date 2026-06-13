# Creative Loop — Local runner (Windows PowerShell, no Docker required)
#
# Usage:
#   .\scripts\run-local.ps1                  # full stack
#   .\scripts\run-local.ps1 -MigrateOnly     # migrations only
#   .\scripts\run-local.ps1 -SeedOnly        # seed only (after migrate)
#   .\scripts\run-local.ps1 -ApiOnly         # API only (no frontend, no worker)
#   .\scripts\run-local.ps1 -WebOnly         # frontend only
#   .\scripts\run-local.ps1 -NoWorker        # API + frontend, no Celery
#
# Prerequisites: Python 3.12+, Node.js 20+
# Worker/Beat: requires Redis running on localhost:6379.
#   Start with:  docker run -d -p 6379:6379 redis:7-alpine
#
param(
    [switch]$MigrateOnly,
    [switch]$SeedOnly,
    [switch]$ApiOnly,
    [switch]$WebOnly,
    [switch]$NoWorker
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$ApiDir = "$Root\apps\api"
$WebDir = "$Root\apps\web"

Write-Host "=== Creative Loop — Local Start ===" -ForegroundColor Cyan

# ── Copy .env if not present ───────────────────────────────────────
if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\.env.example" "$Root\.env"
    Write-Host "[!] .env created from .env.example." -ForegroundColor Yellow
    Write-Host "    Run 'python scripts/gen_keys.py' and paste SECRET_KEY + ENCRYPTION_KEY into .env." -ForegroundColor Yellow
    Write-Host "    Press Enter to continue after editing .env, or Ctrl+C to abort." -ForegroundColor Yellow
    $null = Read-Host
}

# ── Python venv ────────────────────────────────────────────────────
if (-not (Test-Path "$ApiDir\.venv")) {
    Write-Host "[*] Creating Python venv..." -ForegroundColor Green
    & python -m venv "$ApiDir\.venv"
}
$PythonExe = "$ApiDir\.venv\Scripts\python.exe"
$PipExe    = "$ApiDir\.venv\Scripts\pip.exe"
$AlembicExe = "$ApiDir\.venv\Scripts\alembic.exe"

Write-Host "[*] Installing Python deps..." -ForegroundColor Green
& $PipExe install -e "$ApiDir[dev]" --quiet

# ── Migrations ─────────────────────────────────────────────────────
Write-Host "[*] Running Alembic migrations..." -ForegroundColor Green
Push-Location $ApiDir
& $AlembicExe upgrade head
Pop-Location

if ($MigrateOnly) { Write-Host "Done (migrate only)." ; exit 0 }

# ── Seed ───────────────────────────────────────────────────────────
Write-Host "[*] Running seed..." -ForegroundColor Green
& $PythonExe "$Root\scripts\seed.py"
if ($SeedOnly) { Write-Host "Done (seed only)." ; exit 0 }

# ── Check Redis (for worker) ───────────────────────────────────────
$RedisOk = $false
try {
    $r = Test-NetConnection -ComputerName 127.0.0.1 -Port 6379 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    $RedisOk = $r.TcpTestSucceeded
} catch {}

if (-not $RedisOk -and -not $WebOnly -and -not $NoWorker -and -not $ApiOnly) {
    Write-Host "[!] Redis not detected on :6379." -ForegroundColor Yellow
    Write-Host "    Celery worker/beat will be skipped." -ForegroundColor Yellow
    Write-Host "    Start Redis with: docker run -d -p 6379:6379 redis:7-alpine" -ForegroundColor Yellow
    $NoWorker = $true
}

$jobs = @()

# ── Start API ──────────────────────────────────────────────────────
if (-not $WebOnly) {
    Write-Host "[*] Starting API on http://localhost:8000 ..." -ForegroundColor Green
    $ApiJob = Start-Job -ScriptBlock {
        param($d, $py)
        Set-Location $d
        & $py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    } -ArgumentList $ApiDir, $PythonExe
    $jobs += $ApiJob
    Write-Host "    API job: $($ApiJob.Id)"
}

# ── Start Worker + Beat ─────────────────────────────────────────────
if (-not $WebOnly -and -not $ApiOnly -and -not $NoWorker -and $RedisOk) {
    Write-Host "[*] Starting Celery worker..." -ForegroundColor Green
    $WorkerJob = Start-Job -ScriptBlock {
        param($d, $py)
        Set-Location $d
        & $py -m celery -A app.worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo
    } -ArgumentList $ApiDir, $PythonExe
    $jobs += $WorkerJob
    Write-Host "    Worker job: $($WorkerJob.Id)"

    Write-Host "[*] Starting Celery beat..." -ForegroundColor Green
    $BeatJob = Start-Job -ScriptBlock {
        param($d, $py)
        Set-Location $d
        & $py -m celery -A app.worker.celery_app beat --loglevel=info
    } -ArgumentList $ApiDir, $PythonExe
    $jobs += $BeatJob
    Write-Host "    Beat job: $($BeatJob.Id)"
}

# ── Start Web ──────────────────────────────────────────────────────
if (-not $ApiOnly) {
    if (-not (Test-Path "$WebDir\node_modules")) {
        Write-Host "[*] Installing Node deps..." -ForegroundColor Green
        & npm install --prefix $WebDir
    }
    Write-Host "[*] Starting Next.js on http://localhost:3000 ..." -ForegroundColor Green
    $WebJob = Start-Job -ScriptBlock {
        param($d)
        & npm run dev --prefix $d
    } -ArgumentList $WebDir
    $jobs += $WebJob
    Write-Host "    Web job: $($WebJob.Id)"
}

Write-Host ""
Write-Host "=== Services started ===" -ForegroundColor Cyan
Write-Host "  API:     http://localhost:8000"
Write-Host "  Docs:    http://localhost:8000/docs"
Write-Host "  Web:     http://localhost:3000"
Write-Host "  Login:   admin@demo.example / demo1234  [FICTITIOUS — dev only]"
Write-Host ""
Write-Host "To view logs: Receive-Job -Id <job_id> -Keep"
Write-Host "To stop:      Get-Job | Stop-Job | Remove-Job" -ForegroundColor Yellow

Wait-Job -Any
