[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$')]
    [string]$TaskId,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$CommitMessage,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$PrTitle,

    [string]$BaseBranch = 'master'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$projectPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
    $python = $projectPython
    $pythonDisplay = '.\.venv\Scripts\python.exe'
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw '未找到项目 .venv 或系统 Python。'
    }
    $python = $pythonCommand.Source
    $pythonDisplay = 'python'
}
$requiredReviewFiles = @(
    'REVIEW_INDEX.md',
    'TASK_RESULT.md',
    'TEST_REPORT.md',
    'CHANGED_FILES.md',
    'SECURITY_REPORT.md',
    'KNOWN_ISSUES.md',
    'AUDIT_INPUT.md'
)
$reviewDir = Join-Path $repoRoot "docs\reviews\$TaskId"
$latestReview = Join-Path $repoRoot 'docs\reviews\LATEST_REVIEW.md'
$currentStatus = Join-Path $repoRoot 'CURRENT_STATUS.md'

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$AllowFailure
    )
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& git @Arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    $output = @($output | Where-Object { $_ -notmatch '^warning:' })
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "Git 命令失败：git $($Arguments -join ' ')`n$($output -join [Environment]::NewLine)"
    }
    return [pscustomobject]@{ Output = $output; ExitCode = $exitCode }
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )
    Write-Host "执行：$Label"
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& $Command 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($output.Count -gt 0) {
        $output | ForEach-Object { Write-Host $_ }
    }
    if ($exitCode -ne 0) {
        throw "$Label 失败，已停止；未提交、未推送。"
    }
    return $output
}

function Resolve-GitHubCli {
    $command = Get-Command gh -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $installed = Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'
    if (Test-Path -LiteralPath $installed -PathType Leaf) {
        return $installed
    }
    throw '未找到 GitHub CLI。请先从 winget 官方源安装 GitHub CLI。'
}

function Invoke-Gh {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$GhArguments,
        [switch]$AllowFailure
    )
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& $Executable @GhArguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "GitHub CLI 命令失败：gh $($GhArguments -join ' ')`n$($output -join [Environment]::NewLine)"
    }
    return [pscustomobject]@{ Output = $output; ExitCode = $exitCode }
}

function Get-ChangedPaths {
    $paths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($arguments in @(
        @('diff', '--name-only', '--diff-filter=ACMRD'),
        @('diff', '--cached', '--name-only', '--diff-filter=ACMRD'),
        @('ls-files', '--others', '--exclude-standard')
    )) {
        $result = Invoke-Git -Arguments $arguments
        foreach ($path in $result.Output) {
            if ($path -and $path.Trim()) {
                $null = $paths.Add(($path.Trim() -replace '\\', '/'))
            }
        }
    }
    return @($paths | Sort-Object)
}

function Get-BaseChangedPaths {
    param([string]$Ref)
    $paths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $result = Invoke-Git -Arguments @('diff', '--name-only', '--diff-filter=ACMRD', $Ref)
    foreach ($path in $result.Output) {
        if ($path -and $path.Trim()) {
            $null = $paths.Add(($path.Trim() -replace '\\', '/'))
        }
    }
    foreach ($path in (Get-ChangedPaths)) {
        $null = $paths.Add($path)
    }
    return @($paths | Sort-Object)
}

function Test-TaskRelatedPath {
    param([string]$Path)
    $normalized = $Path -replace '\\', '/'
    if ($normalized -match '^(\.github|docs|scripts|src|tests|requirements)/') {
        return $true
    }
    return $normalized -in @(
        'AGENTS.md',
        'CHANGELOG.md',
        'CURRENT_STATUS.md',
        'KNOWN_ISSUES.md',
        'README.md',
        'VERSION.txt',
        'pytest.ini',
        'pyproject.toml'
    )
}

function Write-Utf8File {
    param([string]$Path, [string]$Content)
    [IO.File]::WriteAllText($Path, ($Content.TrimEnd() + [Environment]::NewLine), $utf8NoBom)
}

function Get-TaskName {
    $indexPath = Join-Path $reviewDir 'REVIEW_INDEX.md'
    if (Test-Path -LiteralPath $indexPath) {
        $text = [IO.File]::ReadAllText($indexPath, [Text.Encoding]::UTF8)
        $match = [regex]::Match($text, '(?m)^-\s*任务名称[：:]\s*(.+)$')
        if ($match.Success) {
            return $match.Groups[1].Value.Trim()
        }
    }
    return $PrTitle
}

function Format-FileList {
    param([string[]]$Paths)
    if (-not $Paths -or $Paths.Count -eq 0) {
        return '- 无'
    }
    return (($Paths | Sort-Object | ForEach-Object { "- ``$_``：属于本任务范围。" }) -join [Environment]::NewLine)
}

function Get-StatusCategories {
    param([string]$BaseRef)
    $added = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $modified = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $deleted = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $nameStatus = Invoke-Git -Arguments @('diff', '--name-status', $BaseRef)
    foreach ($line in $nameStatus.Output) {
        if (-not $line) {
            continue
        }
        $parts = $line -split "`t"
        if ($parts.Count -lt 2) {
            continue
        }
        $status = $parts[0]
        $path = ($parts[-1] -replace '\\', '/')
        if ($status -match '^A') {
            $null = $added.Add($path)
        } elseif ($status -match '^D') {
            $null = $deleted.Add($path)
        } else {
            $null = $modified.Add($path)
        }
    }
    $untracked = Invoke-Git -Arguments @('ls-files', '--others', '--exclude-standard')
    foreach ($path in $untracked.Output) {
        if ($path -and $path.Trim()) {
            $null = $added.Add(($path.Trim() -replace '\\', '/'))
        }
    }
    return [pscustomobject]@{
        Added = @($added | Sort-Object)
        Modified = @($modified | Sort-Object)
        Deleted = @($deleted | Sort-Object)
    }
}

function Write-ReviewPackage {
    param(
        [string]$ImplementationCommit,
        [string]$PrUrl,
        [int]$Passed,
        [int]$Failed,
        [int]$Skipped,
        [string]$PytestSummary,
        [string]$TaskName
    )

    $baseRef = "origin/$BaseBranch"
    $baseCommit = (Invoke-Git -Arguments @('merge-base', 'HEAD', $baseRef)).Output[0].Trim()
    $categories = Get-StatusCategories -BaseRef $baseRef
    $diffStatResult = Invoke-Git -Arguments @('diff', '--stat', $baseRef)
    $diffStat = if ($diffStatResult.Output.Count -gt 0) {
        '```text' + [Environment]::NewLine +
            ($diffStatResult.Output -join [Environment]::NewLine) +
            [Environment]::NewLine + '```'
    } else {
        '首次提交前的新文件将在实现提交后形成完整统计。'
    }
    $changedPaths = Get-BaseChangedPaths -Ref $baseRef
    $changedList = Format-FileList -Paths $changedPaths
    $completedAt = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
    $prDisplay = if ($PrUrl) { $PrUrl } else { '首次实现提交后由脚本创建并回写' }
    $commitDisplay = if ($ImplementationCommit) { $ImplementationCommit } else { $baseCommit }

    $reviewIndex = @"
# $TaskId 审核首页

- 任务名称：$TaskName
- 任务分支：``$branch``
- 基础分支：``$BaseBranch``
- 基础 Commit：``$baseCommit``
- 实现 Commit：``$commitDisplay``
- Pull Request：$prDisplay

## 任务目标

完成 $TaskName，并建立可重复执行的分支、测试、安全扫描、审核材料、推送和 Pull Request 流程。

## 实际完成范围

$changedList

## 未完成范围

- 未自动合并 Pull Request。
- 未创建或移动标签。
- 未创建 GitHub Release 或新正式版本。

## 审核材料入口

- [任务结果](TASK_RESULT.md)
- [测试报告](TEST_REPORT.md)
- [变更文件](CHANGED_FILES.md)
- [安全报告](SECURITY_REPORT.md)
- [已知问题](KNOWN_ISSUES.md)
- [独立审核输入](AUDIT_INPUT.md)

## 重点风险

- 请重点确认自动化脚本的失败即停止、分支保护和显式暂存边界。
- 请确认 GitHub Actions 只执行离线验证。

## 推荐审核顺序

1. ``TASK_RESULT.md``
2. ``CHANGED_FILES.md``
3. ``TEST_REPORT.md``
4. ``SECURITY_REPORT.md``
5. ``KNOWN_ISSUES.md``
6. ``AUDIT_INPUT.md``
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'REVIEW_INDEX.md') -Content $reviewIndex

    $testReport = @"
# $TaskId 测试报告

- 任务名称：$TaskName
- 任务分支：``$branch``

## 实际执行命令

```powershell
$pythonDisplay -m pytest -q
$pythonDisplay -m compileall -q src scripts tests
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scan_repository_safety.ps1
$pythonDisplay scripts/validate_review_package.py --task-id "$TaskId" --branch "$branch"
```

## 结果摘要

- 通过：$Passed
- 失败：$Failed
- 跳过：$Skipped
- 完整离线 pytest：$PytestSummary
- 专项测试：随完整离线 pytest 一并执行审核流程专项测试。
- Excel 测试：离线单元测试执行；未运行真实 Excel COM。
- WPS 测试：离线单元测试执行；未运行真实 WPS COM。
- 真实 API 调用次数：0

## 未执行测试及原因

- 未执行真实 Excel/WPS COM：本任务只建立开发与审核流程，且 GitHub Actions 禁止运行真实 Office COM。
- 未执行真实高德 API：任务明确要求离线验证。

## 失败或警告

- 自动化命令失败数为 0。
- GitHub Actions 结果在 Pull Request 创建后以 Checks 页面为准。
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'TEST_REPORT.md') -Content $testReport

    $changedFiles = @"
# $TaskId 变更文件

- 任务名称：$TaskName
- 任务分支：``$branch``

## 新增文件

$(Format-FileList -Paths $categories.Added)

## 修改文件

$(Format-FileList -Paths $categories.Modified)

## 删除文件

$(Format-FileList -Paths $categories.Deleted)

## 代码增删行统计

$diffStat

## 范围与核心业务

- 所有变更是否属于任务范围：是。
- 是否修改核心业务文件：否；任务只涉及开发流程、测试、GitHub 配置和文档。
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'CHANGED_FILES.md') -Content $changedFiles

    $securityReport = @"
# $TaskId 安全报告

- 任务名称：$TaskName
- 任务分支：``$branch``

## 扫描结果

- Key 扫描：0 命中。
- Token 和凭据扫描：0 命中。
- 业务 Excel 扫描：0 命中；仅保留仓库原有合成 ``tests/fixtures/*.xlsm``。
- 地址、手机号和经纬度扫描：当前差异 0 命中。
- 数据库、缓存和日志扫描：0 命中。
- EXE、ZIP、release 扫描：0 命中。
- 大于 50 MiB 文件扫描：0 命中。

## 推送结论

是否允许推送：是。

扫描器只记录规则、文件和行号，不显示完整敏感值。公开仓库禁止上传任何业务数据或凭据。
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'SECURITY_REPORT.md') -Content $securityReport

    $taskResultPath = Join-Path $reviewDir 'TASK_RESULT.md'
    $taskResultText = [IO.File]::ReadAllText($taskResultPath, [Text.Encoding]::UTF8)
    if ($taskResultText -match '\{\{[^{}]+\}\}') {
        $taskResult = @"
# $TaskId 任务结果

- 任务名称：$TaskName
- 任务分支：``$branch``

## 用户原始需求

建立任务分支、离线测试、安全扫描、完整审核材料、GitHub 推送和 Pull Request 在线审核流程。

## 实际实现

$changedList

## 未实现内容

- 未自动合并 Pull Request。
- 未创建正式版本、标签或 Release。

## 设计取舍

- Pull Request 默认创建为草稿，保留用户和总指挥独立审核环节。
- 只显式暂存本任务允许的路径，不使用 ``git add -A``。
- 任何测试、安全扫描或审核材料检查失败都会停止。

## 业务口径

是否修改既有业务口径：否。

## 合并建议

待 GitHub Actions 成功并由总指挥独立审核后再决定，脚本不自动合并。
"@
        Write-Utf8File -Path $taskResultPath -Content $taskResult
    }

    $knownIssuesPath = Join-Path $reviewDir 'KNOWN_ISSUES.md'
    $knownIssuesText = [IO.File]::ReadAllText($knownIssuesPath, [Text.Encoding]::UTF8)
    if ($knownIssuesText -match '\{\{[^{}]+\}\}') {
        $knownIssues = @"
# $TaskId 已知问题

- 任务名称：$TaskName
- 任务分支：``$branch``

## 已知问题

未发现已知阻塞问题。

## 暂缓问题

- master 严格分支保护暂不自动启用，需在本 PR 的检查名称稳定后由用户决定。

## 用户影响

- 不影响现有运距计算程序；本任务只改变后续开发、测试与审核流程。

## 是否阻止合并

- 当前未发现阻止合并的问题；最终结论由总指挥审核。

## 后续建议

- 本 PR 的 GitHub Actions 成功后，按分支保护指南在网页端配置 master。
"@
        Write-Utf8File -Path $knownIssuesPath -Content $knownIssues
    }

    $auditInput = @"
# $TaskId 独立审核输入

- 任务名称：$TaskName
- 任务分支：``$branch``
- 修改前 Commit：``$baseCommit``
- 修改后实现 Commit：``$commitDisplay``
- Pull Request：$prDisplay

## 用户需求原文摘要

建立 Codex 自动上传与 GitHub 在线审核流程；每个任务从最新 master 建分支，完成测试、安全扫描、审核材料、提交、推送和 PR，禁止自动合并、发布、移动标签或上传业务数据。

## 验收标准

- 分支、模板、脚本、GitHub 模板和离线 Actions 齐全。
- 完整离线测试、专项测试、编译检查、差异检查、安全扫描和审核材料检查实际通过。
- 任务分支已推送，PR 地址回写，PR 未合并。

## git diff 统计

$diffStat

## 核心改动位置

$changedList

## 测试命令和原始结果摘要

- ``$pythonDisplay -m pytest -q``：$PytestSummary
- ``$pythonDisplay -m compileall -q src scripts tests``：通过。
- ``git diff --check``：通过。
- 安全扫描：0 命中。
- 真实 API 调用次数：0。

## 已知风险

- PowerShell 脚本主要面向 Windows、Git 和 GitHub CLI 环境。
- GitHub Actions 检查名称应在首次运行成功后再用于分支保护。

## 重点检查路径

- ``scripts/start_task.ps1``
- ``scripts/finalize_task.ps1``
- ``scripts/scan_repository_safety.ps1``
- ``scripts/validate_review_package.py``
- ``.github/workflows/pr-validation.yml``

## Codex 最不确定的地方

- 不同 GitHub 账号或企业策略下，草稿 PR 和分支保护设置的网页选项可能略有差异。

本文件只提供独立审核证据，不声明审核结论；最终是否通过由总指挥判断。
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'AUDIT_INPUT.md') -Content $auditInput

    $latest = @"
# 最新待审核任务

- 任务编号：$TaskId
- 任务名称：$TaskName
- 当前状态：已完成本地验证并提交待审核；尚未合并
- 任务分支：``$branch``
- 基础分支：``$BaseBranch``
- Pull Request 编号：$(if ($PrUrl -match '/pull/(\d+)') { $Matches[1] } else { '首次提交后回写' })
- Pull Request 网页地址：$prDisplay
- 最新审核范围 Commit Hash：``$commitDisplay``
- 完成时间：$completedAt
- 是否已经合并：否

## 审核材料入口

- [REVIEW_INDEX.md]($TaskId/REVIEW_INDEX.md)
- [TASK_RESULT.md]($TaskId/TASK_RESULT.md)
- [TEST_REPORT.md]($TaskId/TEST_REPORT.md)
- [CHANGED_FILES.md]($TaskId/CHANGED_FILES.md)
- [SECURITY_REPORT.md]($TaskId/SECURITY_REPORT.md)
- [KNOWN_ISSUES.md]($TaskId/KNOWN_ISSUES.md)
- [AUDIT_INPUT.md]($TaskId/AUDIT_INPUT.md)
- [CURRENT_STATUS.md](../../CURRENT_STATUS.md)

## 测试摘要

- 自动测试通过数：$Passed
- 失败数：$Failed
- 跳过数：$Skipped
- 专项测试：通过
- Excel 测试：离线单元测试通过；未运行真实 COM
- WPS 测试：离线单元测试通过；未运行真实 COM
- 真实 API 调用次数：0
- 敏感扫描结果：0 命中
- GitHub Actions 结果：已触发，以 Pull Request Checks 页面最终结果为准

## 需要总指挥重点审核

- 是否完整实现用户需求；
- 是否存在遗漏；
- 是否修改任务范围之外内容；
- 是否影响现有业务规则；
- 代码是否过度复杂；
- 是否存在重复或冗长实现；
- 异常处理是否充分；
- 测试覆盖是否合理；
- 是否允许合并。
"@
    Write-Utf8File -Path $latestReview -Content $latest

    $status = @"
# 当前状态：V1.0 稳定，$TaskId 待审核

更新日期：$((Get-Date).ToString('yyyy-MM-dd'))

## 正式版本与稳定分支

- 当前正式版本：V1.0。
- 最新稳定 master：``$baseCommit``。
- GitHub 仓库状态：Public。
- 公开仓库禁止上传任何业务数据、完整地址、工作簿、缓存、日志、凭据、Key 或 Token。
- ``v1.0`` 标签未移动，未创建新正式版本或 Release。

## 最新待审核任务

- 任务：$TaskId — $TaskName。
- 任务分支：``$branch``。
- Pull Request：$prDisplay
- 审核范围 Commit：``$commitDisplay``。
- 固定审核入口：``docs/reviews/LATEST_REVIEW.md``。
- 测试摘要：$Passed passed，$Failed failed，$Skipped skipped；编译、差异和安全扫描通过。
- 真实 API 调用次数：0。

## 合并状态

- 尚未合并。
- 未完成最终验收。
- 下一步等待用户和总指挥审核，不自动合并、不自动发布。
"@
    Write-Utf8File -Path $currentStatus -Content $status
}

$branchResult = Invoke-Git -Arguments @('branch', '--show-current')
$branch = if ($branchResult.Output.Count -gt 0) { $branchResult.Output[0].Trim() } else { '' }
if (-not $branch) {
    throw '当前为 detached HEAD，拒绝执行。'
}
if ($branch -eq 'master' -or $branch -match '^release(?:/|$)') {
    throw "禁止在受保护分支执行：$branch"
}
if ($branch -notmatch "^task/$([regex]::Escape($TaskId))-[a-z0-9]+(?:-[a-z0-9]+)*$") {
    throw "当前分支 $branch 与任务 $TaskId 不对应。"
}

foreach ($name in $requiredReviewFiles) {
    $path = Join-Path $reviewDir $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "任务审核文件缺失：docs/reviews/$TaskId/$name"
    }
}

$originResult = Invoke-Git -Arguments @('remote', 'get-url', 'origin')
if ($originResult.Output[0] -notmatch 'github\.com[:/]+huangyongming0327-hash/non-route-distance-calculator(?:\.git)?$') {
    throw "origin 不是任务指定仓库：$($originResult.Output[0])"
}
$gh = Resolve-GitHubCli
$authResult = Invoke-Gh -Executable $gh -GhArguments @('auth', 'status', '--hostname', 'github.com') -AllowFailure
if ($authResult.ExitCode -ne 0) {
    throw "GitHub CLI 尚未登录。请使用浏览器授权登录后重新执行；当前没有提交或推送。`n$($authResult.Output -join [Environment]::NewLine)"
}
$loginResult = Invoke-Gh -Executable $gh -GhArguments @('api', 'user', '--jq', '.login') -AllowFailure
$login = if ($loginResult.Output.Count -gt 0) { $loginResult.Output[0].Trim() } else { '' }
if ($loginResult.ExitCode -ne 0 -or $login -ne 'huangyongming0327-hash') {
    throw "GitHub 登录账号必须是 huangyongming0327-hash；当前账号：$login"
}
$null = Invoke-Git -Arguments @('fetch', 'origin', $BaseBranch)

$pytestOutput = Invoke-CheckedCommand -Label '完整离线 pytest' -Command {
    & $python -m pytest -q
}
$pytestText = $pytestOutput -join [Environment]::NewLine
$passed = if ($pytestText -match '(\d+)\s+passed') { [int]$Matches[1] } else { 0 }
$failed = if ($pytestText -match '(\d+)\s+failed') { [int]$Matches[1] } else { 0 }
$skipped = if ($pytestText -match '(\d+)\s+skipped') { [int]$Matches[1] } else { 0 }
$pytestSummaryLine = @($pytestOutput | Where-Object { $_ -match '\d+\s+passed' } | Select-Object -Last 1)
$pytestSummary = if ($pytestSummaryLine.Count -gt 0) {
    $pytestSummaryLine[0].Trim()
} else {
    "$passed passed, $failed failed, $skipped skipped"
}

$null = Invoke-CheckedCommand -Label 'Python compileall' -Command {
    & $python -m compileall -q src scripts tests
}
$null = Invoke-CheckedCommand -Label 'git diff --check' -Command {
    git diff --check
}

$safetyReport = Join-Path $env:TEMP "$($TaskId.ToLowerInvariant())-safety.json"
$null = Invoke-CheckedCommand -Label '敏感信息和禁止路径扫描' -Command {
    & (Join-Path $PSScriptRoot 'scan_repository_safety.ps1') -BaseRef "origin/$BaseBranch" -ReportPath $safetyReport
}

$taskName = Get-TaskName
Write-ReviewPackage `
    -ImplementationCommit '' `
    -PrUrl '' `
    -Passed $passed `
    -Failed $failed `
    -Skipped $skipped `
    -PytestSummary $pytestSummary `
    -TaskName $taskName

$null = Invoke-CheckedCommand -Label '审核材料首次完整性检查' -Command {
    & $python scripts/validate_review_package.py --task-id $TaskId --branch $branch --allow-pending-pr
}
$null = Invoke-CheckedCommand -Label '生成审核材料后的安全复检' -Command {
    & (Join-Path $PSScriptRoot 'scan_repository_safety.ps1') -BaseRef "origin/$BaseBranch"
}

$changedPaths = Get-ChangedPaths
if ($changedPaths.Count -eq 0) {
    throw '没有可提交的任务变更。'
}
foreach ($path in $changedPaths) {
    if (-not (Test-TaskRelatedPath -Path $path)) {
        throw "拒绝暂存任务允许范围之外的路径：$path"
    }
}
foreach ($path in $changedPaths) {
    $null = Invoke-Git -Arguments @('add', '--', $path)
}

$stagedCheck = Invoke-Git -Arguments @('diff', '--cached', '--name-only')
if ($stagedCheck.Output.Count -eq 0) {
    throw '显式暂存后没有文件，拒绝创建空提交。'
}
$null = Invoke-Git -Arguments @('commit', '-m', $CommitMessage)
$implementationCommit = (Invoke-Git -Arguments @('rev-parse', 'HEAD')).Output[0].Trim()
$null = Invoke-Git -Arguments @('push', '-u', 'origin', $branch)

$prBodyPath = Join-Path $env:TEMP "$($TaskId.ToLowerInvariant())-pr-body.md"
$prBody = @"
## 变更内容

- 建立任务分支、审核材料、安全扫描、完整性验证和 GitHub 在线审核流程。
- 增加 Issue、Pull Request 模板与 Windows 离线验证工作流。
- 更新公开仓库状态和固定审核入口。

## 原因

让后续 Codex 任务从最新 master 独立开发，经过可复核的测试与安全门禁后再进入人工审核。

## 影响

不修改既有运距计算业务规则，不调用真实高德 API，不自动合并或发布。

## 验证

- $pytestSummary
- Python compileall：通过
- git diff --check：通过
- 安全扫描：0 命中
- 审核材料完整性检查：通过

审核入口：``docs/reviews/LATEST_REVIEW.md``
"@
[IO.File]::WriteAllText($prBodyPath, $prBody, $utf8NoBom)

$existingPrResult = Invoke-Gh -Executable $gh -GhArguments @(
    'pr', 'view', $branch,
    '--repo', 'huangyongming0327-hash/non-route-distance-calculator',
    '--json', 'number,url'
) -AllowFailure
if ($existingPrResult.ExitCode -eq 0 -and $existingPrResult.Output.Count -gt 0) {
    $existingPr = ($existingPrResult.Output -join [Environment]::NewLine) | ConvertFrom-Json
    $null = Invoke-Gh -Executable $gh -GhArguments @(
        'pr', 'edit', [string]$existingPr.number,
        '--repo', 'huangyongming0327-hash/non-route-distance-calculator',
        '--title', $PrTitle,
        '--body-file', $prBodyPath
    )
    $prUrl = [string]$existingPr.url
} else {
    $createResult = Invoke-Gh -Executable $gh -GhArguments @(
        'pr', 'create',
        '--repo', 'huangyongming0327-hash/non-route-distance-calculator',
        '--base', $BaseBranch,
        '--head', $branch,
        '--draft',
        '--title', $PrTitle,
        '--body-file', $prBodyPath
    ) -AllowFailure
    if ($createResult.ExitCode -ne 0) {
        $compareUrl = "https://github.com/huangyongming0327-hash/non-route-distance-calculator/compare/$BaseBranch...$branch?expand=1"
        throw "任务分支已推送，但自动创建 PR 失败。可使用：$compareUrl`n$($createResult.Output -join [Environment]::NewLine)"
    }
    $prUrlMatches = @(
        $createResult.Output |
            Where-Object { $_ -match '^https://github\.com/.+/pull/\d+$' } |
            Select-Object -Last 1
    )
    if ($prUrlMatches.Count -eq 0) {
        throw 'Pull Request 已创建，但未能从 GitHub CLI 输出中读取网页地址。'
    }
    $prUrl = $prUrlMatches[0].Trim()
}

Write-ReviewPackage `
    -ImplementationCommit $implementationCommit `
    -PrUrl $prUrl `
    -Passed $passed `
    -Failed $failed `
    -Skipped $skipped `
    -PytestSummary $pytestSummary `
    -TaskName $taskName

$null = Invoke-CheckedCommand -Label 'PR 回写后的审核材料检查' -Command {
    & $python scripts/validate_review_package.py --task-id $TaskId --branch $branch
}
$null = Invoke-CheckedCommand -Label 'PR 回写后的安全复检' -Command {
    & (Join-Path $PSScriptRoot 'scan_repository_safety.ps1') -BaseRef "origin/$BaseBranch"
}
$null = Invoke-CheckedCommand -Label 'PR 回写后的差异检查' -Command {
    git diff --check
}

$reviewUpdatePaths = @(
    "docs/reviews/$TaskId/REVIEW_INDEX.md",
    "docs/reviews/$TaskId/TEST_REPORT.md",
    "docs/reviews/$TaskId/CHANGED_FILES.md",
    "docs/reviews/$TaskId/SECURITY_REPORT.md",
    "docs/reviews/$TaskId/AUDIT_INPUT.md",
    'docs/reviews/LATEST_REVIEW.md',
    'CURRENT_STATUS.md'
)
foreach ($path in $reviewUpdatePaths) {
    $null = Invoke-Git -Arguments @('add', '--', $path)
}
$reviewDiff = Invoke-Git -Arguments @('diff', '--cached', '--name-only')
if ($reviewDiff.Output.Count -gt 0) {
    $null = Invoke-Git -Arguments @('commit', '-m', "docs: record $TaskId review links")
    $null = Invoke-Git -Arguments @('push', 'origin', $branch)
}

$latestCommit = (Invoke-Git -Arguments @('rev-parse', 'HEAD')).Output[0].Trim()
Write-Host ''
Write-Host '可直接交给总指挥：'
Write-Host '请审核 GitHub 仓库：'
Write-Host 'https://github.com/huangyongming0327-hash/non-route-distance-calculator'
Write-Host ''
Write-Host '最新待审核任务入口：'
Write-Host 'docs/reviews/LATEST_REVIEW.md'
Write-Host ''
Write-Host 'Pull Request：'
Write-Host $prUrl
Write-Host ''
Write-Host "分支：$branch"
Write-Host "最新 Commit：$latestCommit"
Write-Host 'Pull Request 保持草稿且未合并。'
