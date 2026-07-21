param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ClientScript = "E:\bigdata\tier4_stu\client.bat",
    [string]$ClientContainer = "tier4_stu_client",
    [string]$LocalCsv = "data\processed\online_retail_ii.csv",
    [string]$HdfsDirectory = "/data/intellibasket/ods/online_retail_ii"
)

$ErrorActionPreference = "Stop"
$resolvedCsv = (Resolve-Path (Join-Path $ProjectRoot $LocalCsv)).Path

if (-not (Test-Path $ClientScript)) {
    throw "Hadoop client script not found: $ClientScript"
}

docker cp $resolvedCsv "${ClientContainer}:/tmp/online_retail_ii.csv"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy prepared CSV into $ClientContainer"
}

& $ClientScript hdfs dfs -mkdir -p $HdfsDirectory
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create HDFS directory: $HdfsDirectory"
}

& $ClientScript hdfs dfs -put -f /tmp/online_retail_ii.csv "$HdfsDirectory/online_retail_ii.csv"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload prepared CSV to HDFS"
}

& $ClientScript hdfs dfs -ls $HdfsDirectory
if ($LASTEXITCODE -ne 0) {
    throw "Failed to verify HDFS upload"
}
