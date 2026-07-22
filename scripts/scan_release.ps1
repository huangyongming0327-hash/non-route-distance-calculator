param(
    [string]$ReleaseRoot = "",
    [string]$ZipPath = "",
    [string]$EvidencePath = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExpectedRelease = [System.IO.Path]::GetFullPath(
    (Join-Path $ProjectRoot "release\非线路运距计算工具_V1.0")
)
$ExpectedZip = [System.IO.Path]::GetFullPath(
    (Join-Path $ProjectRoot "release\非线路运距计算工具_V1.0_便携版.zip")
)
if (-not $ReleaseRoot) { $ReleaseRoot = $ExpectedRelease }
if (-not $ZipPath) { $ZipPath = $ExpectedZip }
if (-not $EvidencePath) {
    $EvidencePath = Join-Path $ProjectRoot "docs\evidence\task008\security_scan_v1.json"
}
$ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
$ZipPath = [System.IO.Path]::GetFullPath($ZipPath)
$EvidencePath = [System.IO.Path]::GetFullPath($EvidencePath)
if ($ReleaseRoot -ne $ExpectedRelease -or $ZipPath -ne $ExpectedZip) {
    throw "只允许扫描当前项目的 V1.0 正式发布目录和 ZIP。"
}
if (-not (Test-Path -LiteralPath $ReleaseRoot -PathType Container)) {
    throw "正式发布目录不存在：$ReleaseRoot"
}
if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
    throw "正式 ZIP 不存在：$ZipPath"
}

$RequiredTopLevel = @(
    "非线路运距计算工具.exe", "_internal", "config", "cache", "logs", "outputs", "temp",
    "USER_GUIDE.md", "使用说明.pdf", "VERSION.txt", "CHANGELOG.md", "KNOWN_ISSUES.md"
)
$RuntimeDirectories = @("config", "cache", "logs", "outputs", "temp")
$ForbiddenExtensions = @(
    ".xls", ".xlsx", ".xlsm", ".xlsb", ".sqlite", ".sqlite3", ".db", ".db3", ".env", ".credential"
)
$TextExtensions = @(".txt", ".md", ".json", ".log", ".ini", ".cfg", ".xml", ".yaml", ".yml")

function Scan-Tree([string]$Scope, [string]$Root) {
    $hits = [System.Collections.Generic.List[object]]::new()
    $files = @(Get-ChildItem -LiteralPath $Root -File -Recurse -Force)
    $topLevel = @(Get-ChildItem -LiteralPath $Root -Force | ForEach-Object { $_.Name })
    foreach ($required in $RequiredTopLevel) {
        if ($required -notin $topLevel) {
            $hits.Add([pscustomobject]@{ scope = $Scope; path = $required; rule = "缺少发布项"; excerpt = "" })
        }
    }
    foreach ($name in $RuntimeDirectories) {
        $directory = Join-Path $Root $name
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
            $hits.Add([pscustomobject]@{ scope = $Scope; path = $name; rule = "运行目录不存在"; excerpt = "" })
        } elseif (Get-ChildItem -LiteralPath $directory -Force | Select-Object -First 1) {
            $hits.Add([pscustomobject]@{ scope = $Scope; path = $name; rule = "运行目录非空"; excerpt = "" })
        }
    }
    foreach ($forbiddenDirectory in @("src", ".venv")) {
        if (Test-Path -LiteralPath (Join-Path $Root $forbiddenDirectory)) {
            $hits.Add([pscustomobject]@{ scope = $Scope; path = $forbiddenDirectory; rule = "包含源码或虚拟环境"; excerpt = "" })
        }
    }
    foreach ($file in $files) {
        $rootPrefix = $Root.TrimEnd('\') + '\'
        $relative = $file.FullName.Substring($rootPrefix.Length)
        $lowerName = $file.Name.ToLowerInvariant()
        if ($ForbiddenExtensions -contains $file.Extension.ToLowerInvariant() -or $lowerName -eq ".env") {
            $hits.Add([pscustomobject]@{ scope = $Scope; path = $relative; rule = "禁止文件类型"; excerpt = "" })
        }
        if ($lowerName -match "地址.*清单|清单.*地址|业务.*日志|route.*cache|confirmed.*address") {
            $hits.Add([pscustomobject]@{ scope = $Scope; path = $relative; rule = "疑似地址清单、业务日志或缓存"; excerpt = "" })
        }
        if ($TextExtensions -contains $file.Extension.ToLowerInvariant() -and $file.Length -le 5MB) {
            $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
            if ($null -eq $content) { continue }
            $patterns = [ordered]@{
                "疑似凭据赋值" = '(?im)(?:key|token|password|secret|credential)\s*[=:]\s*["'']?[A-Za-z0-9_\-]{12,}'
                "真实请求 URL 携带凭据" = '(?i)https?://[^\s"'']+[?&](?:key|sig|token|password)=[^&\s"'']+'
                "疑似中国大陆手机号" = '(?<!\d)1[3-9]\d{9}(?!\d)'
            }
            foreach ($entry in $patterns.GetEnumerator()) {
                $match = [regex]::Match($content, $entry.Value)
                if ($match.Success) {
                    $excerpt = $match.Value
                    if ($excerpt.Length -gt 120) { $excerpt = $excerpt.Substring(0, 120) }
                    $hits.Add([pscustomobject]@{ scope = $Scope; path = $relative; rule = $entry.Key; excerpt = $excerpt })
                }
            }
        }
    }
    return [pscustomobject]@{
        scope = $Scope
        root = $Root
        file_count = $files.Count
        hits = @($hits)
    }
}

$ExtractRoot = Join-Path $ProjectRoot "temp\release_security_scan_zip"
$expectedExtractRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "temp\release_security_scan_zip"))
$resolvedExtractRoot = [System.IO.Path]::GetFullPath($ExtractRoot)
if ($resolvedExtractRoot -ne $expectedExtractRoot) {
    throw "ZIP 扫描临时目录不符合预期。"
}
if (Test-Path -LiteralPath $ExtractRoot) {
    Remove-Item -LiteralPath $ExtractRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $ExtractRoot -Force | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractRoot -Force
$ExtractedRelease = Join-Path $ExtractRoot (Split-Path -Leaf $ReleaseRoot)
if (-not (Test-Path -LiteralPath $ExtractedRelease -PathType Container)) {
    throw "ZIP 未包含预期的正式发布根目录。"
}

$DirectoryScan = Scan-Tree "release_directory" $ReleaseRoot
$ZipScan = Scan-Tree "zip_archive" $ExtractedRelease
$AllHits = @($DirectoryScan.hits) + @($ZipScan.hits)
$Evidence = [ordered]@{
    scanned_at = (Get-Date).ToString("o")
    release_root = $ReleaseRoot
    zip_path = $ZipPath
    directory_file_count = $DirectoryScan.file_count
    zip_file_count = $ZipScan.file_count
    checks = @(
        "Key/token/password/secret/credential 赋值",
        ".env、SQLite、Excel 业务文件",
        "地址清单、业务日志、历史路线缓存",
        "中国大陆手机号码",
        "带 Key/sig/token/password 的真实请求 URL",
        "源码、.venv、非空运行目录和缺失发布项"
    )
    hits = $AllHits
    passed = $AllHits.Count -eq 0
}
New-Item -ItemType Directory -Path (Split-Path -Parent $EvidencePath) -Force | Out-Null
[System.IO.File]::WriteAllText(
    $EvidencePath,
    ($Evidence | ConvertTo-Json -Depth 8),
    [System.Text.UTF8Encoding]::new($false)
)
Remove-Item -LiteralPath $ExtractRoot -Recurse -Force

Write-Output "EVIDENCE=$EvidencePath"
Write-Output "DIRECTORY_FILES=$($DirectoryScan.file_count)"
Write-Output "ZIP_FILES=$($ZipScan.file_count)"
Write-Output "HITS=$($AllHits.Count)"
Write-Output "PASSED=$($Evidence.passed)"
if (-not $Evidence.passed) { exit 1 }
