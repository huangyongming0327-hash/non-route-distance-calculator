param(
    [string]$ReleaseRoot = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExpectedRelease = [System.IO.Path]::GetFullPath(
    (Join-Path $ProjectRoot "release\非线路运距计算工具_V1.0_RC2")
)
if (-not $ReleaseRoot) {
    $ReleaseRoot = $ExpectedRelease
}
$ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
if ($ReleaseRoot -ne $ExpectedRelease) {
    throw "拒绝清理非预期目录：$ReleaseRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $ReleaseRoot "非线路运距计算工具.exe"))) {
    throw "发布目录缺少 EXE，拒绝继续：$ReleaseRoot"
}

foreach ($name in @("config", "cache", "logs", "outputs", "temp")) {
    $directory = Join-Path $ReleaseRoot $name
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    Get-ChildItem -LiteralPath $directory -Force | Remove-Item -Recurse -Force
}

$ForbiddenExtensions = @(".xls", ".xlsx", ".xlsm", ".xlsb", ".sqlite", ".sqlite3", ".db", ".credential", ".env")
$ForbiddenFiles = Get-ChildItem -LiteralPath $ReleaseRoot -File -Recurse | Where-Object {
    $ForbiddenExtensions -contains $_.Extension.ToLowerInvariant()
}
if ($ForbiddenFiles) {
    throw "发布包发现禁止文件：$($ForbiddenFiles.FullName -join '；')"
}

$ZipPath = Join-Path $ProjectRoot "release\非线路运距计算工具_V1.0_RC2_便携版.zip"
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $ReleaseRoot -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Output "RELEASE_ROOT=$ReleaseRoot"
Write-Output "ZIP_PATH=$ZipPath"
