# Creative Loop — Bootstrap script (Windows PowerShell)
#
# What this does:
#   1. Validates prerequisites (Python 3.12+, Node 20+)
#   2. Creates .env from .env.example if missing, generates keys
#   3. Creates Python venv and installs deps
#   4. Optionally starts Postgres + Redis via Docker
#   5. Runs Alembic migrations
#   6. Loads fictitious seed data
#   7. Starts the full stack
#
# Usage:
#   .\scripts\bootstrap.ps1
#   .\scripts\bootstrap.ps1 -SkipDocker     # assume Postgres+Redis already running
#   .\scripts\bootstrap.ps1 -SkipSeed       # skip seed (already seeded)
#   .\scripts\bootstrap.ps1 -DockerOnly     # start infra only, no app services

param(
    [switch]$SkipDocker,
    [switch]$SkipSeed,
    [switch]$DockerOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$ApiDir = "$Root\apps\api"
$WebDir = "$Root\apps\web"

function Check-Command($cmd) {
    return $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Creative Loop — Bootstrap                  ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Prerequisites ───────────────────────────────────────────────
Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Green

if (-not (Check-Command "python")) {
    Write-Host "ERROR: Python not found. Install Python 3.12+ from https://www.python.org" -ForegroundColor Red
    exit 1
}
$pyVer = & python --version 2>&1
Write-Host "  Python: $pyVer"

if (-not (Check-Command "node")) {
    Write-Host "ERROR: Node.js not found. Install Node 20+ from https://nodejs.org" -ForegroundColor Red
    exit 1
}
$nodeVer = & node --version 2>&1
Write-Host "  Node: $nodeVer"

$hasDocker = Check-Command "docker"
if (-not $hasDocker -and -not $SkipDocker) {
    Write-Host "[!] Docker not found — assuming Postgres+Redis are already running externally." -ForegroundColor Yellow
    $SkipDocker = $true
}

# ── 2. .env setup ──────────────────────────────────────────────────
Write-Host "[2/7] Configuring environment..." -ForegroundColor Green

if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\.env.example" "$Root\.env"
    Write-Host "  .env created." -ForegroundColor Yellow

    Write-Host "  Generating SECRET_KEY and ENCRYPTION_KEY..." -ForegroundColor Yellow
    $keys = & python "$Root\scripts\gen_keys.py" 2>&1
    foreach ($line in $keys) {
        if ($line -match "^(SECRET_KEY|ENCRYPTION_KEY)=(.+)$") {
            $varName = $Matches[1]
            $varVal  = $Matches[2]
            # Replace PREENCHER_ placeholder in .env
            (Get-Content "$Root\.env") -replace "^${varName}=PREENCHER_.*$", "${varName}=${varVal}" |
                Set-Content "$Root\.env" -Encoding utf8
            Write-Host "  Set $varName" -ForegroundColor Green
        }
    }
    Write-Host "  [!] Review .env — fill in API keys when ready to use real providers." -ForegroundColor Yellow
} else {
    Write-Host "  .env already exists — skipping." -ForegroundColor DarkGray
}

# ── 3. Python venv + deps ──────────────────────────────────────────
Write-Host "[3/7] Installing Python dependencies..." -ForegroundColor Green

if (-not (Test-Path "$ApiDir\.venv")) {
    & python -m venv "$ApiDir\.venv"
}
$PythonExe  = "$ApiDir\.venv\Scripts\python.exe"
$PipExe     = "$ApiDir\.venv\Scripts\pip.exe"
$AlembicExe = "$ApiDir\.venv\Scripts\alembic.exe"

& $PipExe install -e "$ApiDir[dev]" --quiet
Write-Host "  Done." -ForegroundColor Green

# ── 4. Node deps ───────────────────────────────────────────────────
Write-Host "[4/7] Installing Node.js dependencies..." -ForegroundColor Green
if (-not (Test-Path "$WebDir\node_modules")) {
    & npm install --prefix $WebDir --silent
}
Write-Host "  Done." -ForegroundColor Green

# ── 5. Infra (Postgres + Redis) ────────────────────────────────────
if (-not $SkipDocker -and $hasDocker) {
    Write-Host "[5/7] Starting Postgres + Redis via Docker..." -ForegroundColor Green
    & docker compose -f "$Root\docker-compose.yml" up -d postgres redis
    Write-Host "  Waiting for Postgres health check..." -ForegroundColor DarkGray
    $retries = 0
    while ($retries -lt 30) {
        $pg = & docker compose -f "$Root\docker-compose.yml" ps postgres 2>&1
        if ($pg -match "healthy") { break }
        Start-Sleep 2
        $retries++
    }
    Write-Host "  Postgres ready." -ForegroundColor Green
} else {
    Write-Host "[5/7] Skipping Docker infra (using external Postgres/Redis)." -ForegroundColor DarkGray
}

if ($DockerOnly) {
    Write-Host "Done (Docker-only mode). Infra is up." -ForegroundColor Cyan
    exit 0
}

# ── 6. Migrations ──────────────────────────────────────────────────
Write-Host "[6/7] Running Alembic migrations..." -ForegroundColor Green
Push-Location $ApiDir
& $AlembicExe upgrade head
Pop-Location

# ── 7. Seed ────────────────────────────────────────────────────────
if (-not $SkipSeed) {
    Write-Host "[7/7] Loading fictitious seed data..." -ForegroundColor Green
    & $PythonExe "$Root\scripts\seed.py"
} else {
    Write-Host "[7/7] Skipping seed." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Bootstrap complete!                                 ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  Start the full stack:                               ║" -ForegroundColor Green
Write-Host "║    .\scripts\run-local.ps1                           ║" -ForegroundColor Green
Write-Host "║                                                      ║" -ForegroundColor Green
Write-Host "║  API:   http://localhost:8000                        ║" -ForegroundColor Green
Write-Host "║  Docs:  http://localhost:8000/docs                   ║" -ForegroundColor Green
Write-Host "║  Web:   http://localhost:3000                        ║" -ForegroundColor Green
Write-Host "║                                                      ║" -ForegroundColor Green
Write-Host "║  Login: admin@demo.example / demo1234               ║" -ForegroundColor Green
Write-Host "║  [FICTITIOUS credentials — development only]        ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
