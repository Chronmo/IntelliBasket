param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ClientScript = "E:\bigdata\tier4_stu\client.bat",
    [string]$ClientContainer = "tier4_stu_client"
)

$ErrorActionPreference = "Stop"
$sqlFiles = @(
    "sql\hive\00_create_database.sql",
    "sql\hive\01_ods.sql",
    "sql\hive\02_dwd.sql",
    "sql\hive\03_dimensions.sql",
    "sql\hive\04_dws.sql",
    "sql\hive\05_ads.sql",
    "sql\hive\06_quality_checks.sql"
)

foreach ($relativeSqlFile in $sqlFiles) {
    $sqlFile = (Resolve-Path (Join-Path $ProjectRoot $relativeSqlFile)).Path
    Write-Host "Running $relativeSqlFile"
    $containerSqlFile = "/tmp/intellibasket_$([System.IO.Path]::GetFileName($sqlFile))"
    docker cp $sqlFile "${ClientContainer}:$containerSqlFile"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy $relativeSqlFile into $ClientContainer"
    }
    & $ClientScript beeline -f $containerSqlFile
    if ($LASTEXITCODE -ne 0) {
        throw "Hive pipeline failed at $relativeSqlFile"
    }
}
