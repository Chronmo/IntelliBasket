param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ClientScript = "E:\bigdata\tier4_stu\client.bat",
    [string]$ClientContainer = "tier4_stu_client"
)

$ErrorActionPreference = "Stop"
$sqlFile = (Resolve-Path (Join-Path $ProjectRoot "sql\hive\07_export_analytics.sql")).Path
$containerSqlFile = "/tmp/intellibasket_07_export_analytics.sql"
$processedDirectory = Join-Path $ProjectRoot "data\processed\hive"
New-Item -ItemType Directory -Force $processedDirectory | Out-Null

docker cp $sqlFile "${ClientContainer}:$containerSqlFile"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy analytics export SQL into $ClientContainer"
}

& $ClientScript beeline -f $containerSqlFile
if ($LASTEXITCODE -ne 0) {
    throw "Hive analytics export SQL failed"
}

$exports = @(
    @{ HdfsPath = "/data/intellibasket/exports/basket_items"; FileName = "basket_items.tsv" },
    @{ HdfsPath = "/data/intellibasket/exports/monthly_sales"; FileName = "monthly_sales.tsv" },
    @{ HdfsPath = "/data/intellibasket/exports/data_quality"; FileName = "data_quality.tsv" }
)

foreach ($export in $exports) {
    $containerFile = "/tmp/$($export.FileName)"
    & $ClientScript hdfs dfs -getmerge $export.HdfsPath $containerFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to merge Hive export $($export.HdfsPath)"
    }
    docker cp "${ClientContainer}:$containerFile" (Join-Path $processedDirectory $export.FileName)
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy $($export.FileName) to the project"
    }
}

Get-ChildItem $processedDirectory | Select-Object Name, Length, LastWriteTime

