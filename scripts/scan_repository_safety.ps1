[CmdletBinding()]
param(
    [string]$BaseRef = 'origin/master',
    [string]$ReportPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

function Get-GitLines {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(
            & git -c core.quotepath=false @Arguments 2>&1 |
                ForEach-Object { [string]$_ }
        )
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw "Git 命令失败：git $($Arguments -join ' ')`n$($output -join [Environment]::NewLine)"
    }
    return @(
        $output |
            Where-Object { $_ -and ([string]$_).Trim() -and $_ -notmatch '^warning:' } |
            ForEach-Object { ([string]$_).Trim() }
    )
}

function Test-GitHistoryPattern {
    param(
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][string]$RepoPath,
        [Parameter(Mandatory = $true)][string]$Pattern
    )

    $blobSpec = "${Commit}:$RepoPath"
    & git cat-file -e $blobSpec *> $null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & git grep --quiet -I -i -E -e $Pattern $Commit -- $RepoPath *> $null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -eq 0) {
        return $true
    }
    if ($exitCode -eq 1) {
        return $false
    }
    throw "Git 历史扫描失败：commit=$Commit path=$RepoPath"
}

function Normalize-RepoPath {
    param([string]$Path)
    $normalized = $Path -replace '\\', '/'
    if ($normalized.StartsWith('./')) {
        return $normalized.Substring(2)
    }
    return $normalized
}

function Add-Finding {
    param(
        [string]$Rule,
        [string]$Path,
        [string]$Scope,
        [int]$Line = 0,
        [string]$Commit = ''
    )
    $script:findings.Add([pscustomobject]@{
        rule = $Rule
        path = $Path
        scope = $Scope
        line = $Line
        commit = $Commit
    })
}

$tracked = Get-GitLines -Arguments @('ls-files')
$unstaged = Get-GitLines -Arguments @('diff', '--name-only', '--diff-filter=ACMR')
$staged = Get-GitLines -Arguments @('diff', '--cached', '--name-only', '--diff-filter=ACMR')
$untracked = Get-GitLines -Arguments @('ls-files', '--others', '--exclude-standard')

& git rev-parse --verify --quiet $BaseRef *> $null
if ($LASTEXITCODE -ne 0) {
    throw "基础引用不存在：$BaseRef"
}
$baseDiff = Get-GitLines -Arguments @('diff', '--name-only', '--diff-filter=ACMR', "$BaseRef...HEAD")

$changedSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($item in @($unstaged + $staged + $untracked + $baseDiff)) {
    $null = $changedSet.Add((Normalize-RepoPath $item))
}

$allSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($item in @($tracked + $changedSet)) {
    $null = $allSet.Add((Normalize-RepoPath $item))
}

$findings = [Collections.Generic.List[object]]::new()
$maxBytes = 50MB
$textExtensions = @(
    '.cfg', '.csv', '.ini', '.json', '.md', '.ps1', '.psm1', '.py',
    '.toml', '.tsv', '.txt', '.xml', '.yaml', '.yml'
)
$restrictedBinaryExtensions = @(
    '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.pdf'
)
$restrictedBinaryRule = '未经授权的二进制图片或 PDF'

$secretRules = @(
    @{ Name = 'GitHub Token'; Pattern = '(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})' },
    @{ Name = '私钥'; Pattern = '-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----' },
    @{ Name = '疑似 32 位明文 Key'; Pattern = '(?i)(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])' },
    @{ Name = '明文凭据赋值'; Pattern = '(?i)(?<![A-Za-z0-9_])(?:amap[_-]?)?(?:key|token|password|secret|credential)(?![A-Za-z0-9_])\s*[:=]\s*(?:["''][A-Za-z0-9_./+=-]{12,}["'']|[A-Za-z0-9_+=/-]{20,}\s*(?:#.*)?$)' }
)
$historyRules = @(
    @{ Name = 'GitHub Token'; Pattern = '(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})' },
    @{ Name = '私钥'; Pattern = '-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----' },
    @{ Name = '疑似 32 位明文 Key'; Pattern = '(^|[^0-9A-Fa-f])[0-9A-Fa-f]{32}([^0-9A-Fa-f]|$)' },
    @{ Name = '明文凭据赋值'; Pattern = '(amap[_-]?)?(key|token|password|secret|credential)[[:space:]]*[:=][[:space:]]*["'']?[A-Za-z0-9_./+=-]{12,}' },
    @{ Name = '手机号形态'; Pattern = '(^|[^0-9])1[3-9][0-9]{9}([^0-9]|$)' },
    @{ Name = '经纬度业务证据形态'; Pattern = '(^|[^0-9])(7[3-9]|8[0-9]|9[0-9]|1[0-3][0-9])\.[0-9]{4,}[[:space:]]*[,，][[:space:]]*(1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])\.[0-9]{4,}([^0-9]|$)' },
    @{ Name = '完整业务地址形态'; Pattern = '(客户|仓库|工厂|收货|发货).{0,90}(省|市|区|县|镇|街道|路|街|大道).{0,90}(号|门|库房)' }
)

$historyCommits = @(
    Get-GitLines -Arguments @('rev-list', "$BaseRef..HEAD")
)
foreach ($commit in $historyCommits) {
    if (-not $commit) {
        continue
    }
    $shortCommit = $commit.Substring(0, [Math]::Min(12, $commit.Length))
    $historyPaths = @(
        Get-GitLines -Arguments @(
            'diff-tree', '--root', '-m', '--no-commit-id', '--name-only',
            '-r', '--diff-filter=ACMR', $commit
        ) | Sort-Object -Unique
    )
    foreach ($repoPath in $historyPaths) {
        $extension = [IO.Path]::GetExtension($repoPath).ToLowerInvariant()
        if ($extension -in $restrictedBinaryExtensions) {
            Add-Finding `
                -Rule "$restrictedBinaryRule（提交历史）" `
                -Path $repoPath `
                -Scope 'history' `
                -Commit $shortCommit
            continue
        }
        if ($extension -notin $textExtensions) {
            continue
        }
        foreach ($rule in $historyRules) {
            if (
                $repoPath -eq 'scripts/scan_repository_safety.ps1' -and
                $rule.Name -eq '完整业务地址形态'
            ) {
                continue
            }
            if (Test-GitHistoryPattern -Commit $commit -RepoPath $repoPath -Pattern $rule.Pattern) {
                Add-Finding `
                    -Rule "$($rule.Name)（提交历史）" `
                    -Path $repoPath `
                    -Scope 'history' `
                    -Commit $shortCommit
            }
        }
    }
}

foreach ($repoPath in ($allSet | Sort-Object)) {
    if (-not $repoPath) {
        continue
    }
    $fullPath = Join-Path $repoRoot ($repoPath -replace '/', '\')
    $scope = if ($changedSet.Contains($repoPath)) { 'changed' } else { 'tracked' }
    $lower = $repoPath.ToLowerInvariant()
    $extension = [IO.Path]::GetExtension($repoPath).ToLowerInvariant()
    $leafName = [IO.Path]::GetFileName($repoPath).ToLowerInvariant()

    if ($lower -match '(^|/)\.env(?:\.|$)') {
        Add-Finding -Rule '.env 文件' -Path $repoPath -Scope $scope
    }
    if ($leafName -match '^(credentials?|secrets?)(?:[._-]|$)' -or $extension -in @('.key', '.pem', '.p12', '.pfx')) {
        Add-Finding -Rule '凭据或私钥文件' -Path $repoPath -Scope $scope
    }
    if ($lower -match '^(cache|logs|outputs|temp|release)/') {
        Add-Finding -Rule '禁止的运行或发布目录' -Path $repoPath -Scope $scope
    }
    if ($extension -in @('.sqlite', '.sqlite3', '.db', '.db3', '.exe', '.zip', '.bundle')) {
        Add-Finding -Rule '禁止的数据库、二进制或历史包' -Path $repoPath -Scope $scope
    }
    if ($changedSet.Contains($repoPath) -and $extension -in $restrictedBinaryExtensions) {
        Add-Finding -Rule $restrictedBinaryRule -Path $repoPath -Scope $scope
    }
    if ($extension -in @('.xls', '.xlsx', '.xlsm', '.xlsb')) {
        $allowedFixture = (
            $lower -match '^tests/fixtures/' -and
            $extension -eq '.xlsm' -and
            $leafName -match '(synthetic|fixture|mock|合成|测试)'
        )
        if (-not $allowedFixture) {
            Add-Finding -Rule '业务或结果 Excel' -Path $repoPath -Scope $scope
        }
    }

    if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
        $item = Get-Item -LiteralPath $fullPath
        if ($item.Length -gt $maxBytes) {
            Add-Finding -Rule '文件大于 50 MiB' -Path $repoPath -Scope $scope
        }
    }

    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf) -or $extension -notin $textExtensions) {
        continue
    }

    $text = [IO.File]::ReadAllText($fullPath, [Text.Encoding]::UTF8)
    $lines = $text -split "`r?`n"
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $line = $lines[$index]
        if ($repoPath -eq 'scripts/scan_repository_safety.ps1' -and $line -match 'Pattern\s*=') {
            continue
        }
        foreach ($rule in $secretRules) {
            if ($line -match $rule.Pattern) {
                Add-Finding -Rule $rule.Name -Path $repoPath -Scope $scope -Line ($index + 1)
            }
        }
    }

    if (-not $changedSet.Contains($repoPath) -or $repoPath -eq 'scripts/scan_repository_safety.ps1') {
        continue
    }
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $line = $lines[$index]
        if ($line -match '(?<!\d)1[3-9]\d{9}(?!\d)') {
            Add-Finding -Rule '手机号形态' -Path $repoPath -Scope $scope -Line ($index + 1)
        }
        if ($line -match '(?<!\d)(?:7[3-9]|8\d|9\d|1[0-3]\d)\.\d{4,}\s*[,，]\s*(?:1\d|2\d|3\d|4\d|5\d)\.\d{4,}(?!\d)') {
            Add-Finding -Rule '经纬度业务证据形态' -Path $repoPath -Scope $scope -Line ($index + 1)
        }
        if ($line -match '(?:客户|仓库|工厂|收货|发货).{0,30}(?:省|市|区|县|镇|街道|路|街|大道).{0,30}(?:号|门|库房)') {
            Add-Finding -Rule '完整业务地址形态' -Path $repoPath -Scope $scope -Line ($index + 1)
        }
    }
}

$uniqueFindings = @(
    $findings |
        Sort-Object rule, path, line, scope, commit -Unique
)
$summary = [ordered]@{
    scanned_at = (Get-Date).ToUniversalTime().ToString('o')
    base_ref = $BaseRef
    tracked_file_count = $tracked.Count
    changed_file_count = $changedSet.Count
    scanned_file_count = $allSet.Count
    finding_count = $uniqueFindings.Count
    allowed_to_push = ($uniqueFindings.Count -eq 0)
    findings = $uniqueFindings
}

if ($ReportPath) {
    $resolvedReport = if ([IO.Path]::IsPathRooted($ReportPath)) {
        $ReportPath
    } else {
        Join-Path $repoRoot $ReportPath
    }
    $reportParent = Split-Path -Parent $resolvedReport
    if ($reportParent -and -not (Test-Path -LiteralPath $reportParent)) {
        New-Item -ItemType Directory -Path $reportParent -Force | Out-Null
    }
    $json = $summary | ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText($resolvedReport, $json, (New-Object Text.UTF8Encoding($false)))
}

Write-Host "安全扫描：已检查 $($summary.scanned_file_count) 个文件，其中 $($summary.changed_file_count) 个属于当前差异。"
if ($uniqueFindings.Count -gt 0) {
    Write-Host "发现 $($uniqueFindings.Count) 项禁止内容；未显示任何完整敏感值："
    foreach ($finding in $uniqueFindings) {
        $lineSuffix = if ($finding.line -gt 0) { ":$($finding.line)" } else { '' }
        $commitSuffix = if ($finding.commit) { "；Commit=$($finding.commit)" } else { '' }
        Write-Host "  规则=$($finding.rule)；文件=$($finding.path)$lineSuffix$commitSuffix"
    }
    $binaryFindings = @(
        $uniqueFindings |
            Where-Object { $_.rule -like "$restrictedBinaryRule*" }
    )
    if ($binaryFindings.Count -gt 0) {
        Write-Host '二进制图片或PDF无法自动确认是否已脱敏。'
        Write-Host '普通开发任务禁止提交。'
        Write-Host '需要上传时必须另开明确授权的文档/发布任务并人工审核。'
    }
    exit 3
}

Write-Host '安全扫描通过：0 命中，允许进入后续推送步骤。'
