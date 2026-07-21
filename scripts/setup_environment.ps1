[CmdletBinding()]
param(
    [switch]$skipFrontend
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$virtualEnvironment = Join-Path $projectRoot ".venv"
$pythonExecutable = Join-Path $virtualEnvironment "Scripts\python.exe"

function writeStep([string]$message) {
    Write-Host "`n[IntelliBasket] $message" -ForegroundColor Cyan
}

Set-Location $projectRoot

writeStep "Checking required commands"
foreach ($commandName in @("python", "docker", "git")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $commandName"
    }
}

if (-not (Test-Path $pythonExecutable)) {
    writeStep "Creating Python virtual environment"
    python -m venv $virtualEnvironment
}

writeStep "Installing backend and test dependencies"
& $pythonExecutable -m pip install --upgrade pip
& $pythonExecutable -m pip install -e ".[dev]"

if (-not $skipFrontend) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: npm"
    }
    writeStep "Installing deterministic frontend dependencies"
    Push-Location (Join-Path $projectRoot "frontend")
    try {
        npm ci
    }
    finally {
        Pop-Location
    }
}

writeStep "Validating Docker Compose configuration"
docker compose -f docker-compose.app.yml config --quiet

Write-Host "`nEnvironment setup completed." -ForegroundColor Green
Write-Host "Next: .\scripts\start_demo.ps1"
