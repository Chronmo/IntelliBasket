[CmdletBinding()]
param(
    [switch]$skipBuild,
    [switch]$skipDataLoad
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $projectRoot "docker-compose.app.yml"
$cliExecutable = Join-Path $projectRoot ".venv\Scripts\intellibasket.exe"
$analyticsDirectory = Join-Path $projectRoot "outputs\analytics"

function writeStep([string]$message) {
    Write-Host "`n[IntelliBasket] $message" -ForegroundColor Cyan
}

Set-Location $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is unavailable. Start Docker Desktop and retry."
}
if (-not (Test-Path $cliExecutable)) {
    throw "Python environment is missing. Run .\scripts\setup_environment.ps1 first."
}
if ((-not $skipDataLoad) -and (-not (Test-Path $analyticsDirectory))) {
    throw "Analytics outputs are missing: $analyticsDirectory. Run the Hive export and analytics pipeline first."
}

writeStep "Starting MySQL"
docker compose -f $composeFile up -d mysql

writeStep "Waiting for MySQL health check"
$mysqlReady = $false
for ($attempt = 1; $attempt -le 40; $attempt++) {
    $healthStatus = docker inspect --format "{{.State.Health.Status}}" intellibasket_mysql 2>$null
    if ($healthStatus -eq "healthy") {
        $mysqlReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $mysqlReady) {
    throw "MySQL did not become healthy within 80 seconds."
}

if (-not $skipDataLoad) {
    writeStep "Loading analytical outputs into the serving database"
    & $cliExecutable load-serving-data
}

writeStep "Starting API and Web dashboard"
$composeArguments = @("compose", "-f", $composeFile, "up", "-d")
if (-not $skipBuild) {
    $composeArguments += "--build"
}
$composeArguments += @("api", "web")
docker @composeArguments

writeStep "Waiting for the Web health check"
$webReady = $false
for ($attempt = 1; $attempt -le 40; $attempt++) {
    $healthStatus = docker inspect --format "{{.State.Health.Status}}" intellibasket_web 2>$null
    if ($healthStatus -eq "healthy") {
        $webReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $webReady) {
    throw "Web dashboard did not become healthy within 80 seconds."
}

Write-Host "`nIntelliBasket demo is ready." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:8080"
Write-Host "OpenAPI:   http://localhost:8000/docs"
Write-Host "Stop:      .\scripts\stop_demo.ps1"
