[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $projectRoot "docker-compose.app.yml"

Set-Location $projectRoot
docker compose -f $composeFile down

Write-Host "IntelliBasket application services stopped; MySQL volume was preserved." -ForegroundColor Green
