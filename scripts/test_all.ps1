[CmdletBinding()]
param(
    [switch]$includeDockerBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pytestDirectory = Join-Path $projectRoot "runtime\pytest-all"

function writeStep([string]$message) {
    Write-Host "`n[IntelliBasket] $message" -ForegroundColor Cyan
}

Set-Location $projectRoot
if (-not (Test-Path $pythonExecutable)) {
    throw "Python environment is missing. Run .\scripts\setup_environment.ps1 first."
}

writeStep "Checking Python formatting and lint rules"
& $pythonExecutable -m ruff format --check src tests
& $pythonExecutable -m ruff check src tests

writeStep "Running backend unit and API tests"
& $pythonExecutable -m pytest tests -q --basetemp=$pytestDirectory -p no:cacheprovider

writeStep "Type-checking and building the Vue dashboard"
Push-Location (Join-Path $projectRoot "frontend")
try {
    npm run build
    npm audit
}
finally {
    Pop-Location
}

writeStep "Validating Docker Compose"
docker compose -f docker-compose.app.yml config --quiet

if ($includeDockerBuild) {
    writeStep "Building production containers"
    docker compose -f docker-compose.app.yml build api web
}

Write-Host "`nAll IntelliBasket checks passed." -ForegroundColor Green
