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

    [string]$BaseBranch = 'master',

    [string]$ReviewContextPath = '',

    [switch]$RenderReviewOnly,

    [string]$EvidenceCommit = '',

    [string]$EvidencePrUrl = '',

    [ValidateRange(0, 1000000)]
    [int]$EvidencePassed = 0,

    [ValidateRange(0, 1000000)]
    [int]$EvidenceFailed = 0,

    [ValidateRange(0, 1000000)]
    [int]$EvidenceSkipped = 0,

    [string]$EvidencePytestSummary = '',

    [ValidateRange(0, 1000000)]
    [int]$EvidenceSafetyFindingCount = 0
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
$reviewContextFile = if ($ReviewContextPath) {
    if ([IO.Path]::IsPathRooted($ReviewContextPath)) {
        $ReviewContextPath
    } else {
        Join-Path $repoRoot $ReviewContextPath
    }
} else {
    Join-Path $reviewDir 'REVIEW_CONTEXT.json'
}

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

function Get-RequiredContextValue {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Location
    )
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) {
        throw "审核上下文缺少字段：$Location.$Name"
    }
    $value = $property.Value
    if ($value -is [string]) {
        if (-not $value.Trim()) {
            throw "审核上下文字段为空：$Location.$Name"
        }
        if ($value -match '\{\{[^{}]+\}\}') {
            throw "审核上下文仍含模板占位：$Location.$Name"
        }
    } else {
        $items = @($value)
        if ($items.Count -eq 0) {
            throw "审核上下文字段为空：$Location.$Name"
        }
        foreach ($item in $items) {
            if ($item -is [string] -and (
                -not $item.Trim() -or
                $item -match '\{\{[^{}]+\}\}'
            )) {
                throw "审核上下文列表含空值或模板占位：$Location.$Name"
            }
        }
    }
    return $value
}

function ConvertTo-Markdown {
    param([Parameter(Mandatory = $true)]$Value)
    if ($Value -is [string]) {
        return $Value.Trim()
    }
    $items = @(
        $Value |
            ForEach-Object { [string]$_ } |
            Where-Object { $_.Trim() } |
            ForEach-Object { $_.Trim() }
    )
    if ($items.Count -eq 0) {
        throw '审核上下文列表不得为空。'
    }
    return (($items | ForEach-Object { "- $_" }) -join [Environment]::NewLine)
}

function Read-ReviewContext {
    if (-not (Test-Path -LiteralPath $reviewContextFile -PathType Leaf)) {
        throw "审核上下文缺失：$reviewContextFile"
    }
    try {
        $context = [IO.File]::ReadAllText(
            $reviewContextFile,
            [Text.Encoding]::UTF8
        ) | ConvertFrom-Json
    } catch {
        throw "审核上下文不是有效 JSON：$reviewContextFile"
    }

    foreach ($name in @(
        'task_name',
        'task_goal',
        'unfinished_scope',
        'key_risks',
        'test_evidence_notes',
        'in_scope',
        'core_business_changed',
        'request_summary',
        'acceptance_criteria',
        'known_risks',
        'uncertainties',
        'task_result',
        'known_issues'
    )) {
        $null = Get-RequiredContextValue -Object $context -Name $name -Location 'root'
    }
    foreach ($name in @(
        'user_request',
        'implementation',
        'not_implemented',
        'design_tradeoffs',
        'business_rules_changed',
        'merge_recommendation'
    )) {
        $null = Get-RequiredContextValue `
            -Object $context.task_result `
            -Name $name `
            -Location 'task_result'
    }
    foreach ($name in @(
        'known',
        'deferred',
        'user_impact',
        'blocks_merge',
        'follow_up'
    )) {
        $null = Get-RequiredContextValue `
            -Object $context.known_issues `
            -Name $name `
            -Location 'known_issues'
    }
    return $context
}

function Format-FileList {
    param([string[]]$Paths)
    if (-not $Paths -or $Paths.Count -eq 0) {
        return '- 无'
    }
    return (($Paths | Sort-Object | ForEach-Object { "- ``$_``" }) -join [Environment]::NewLine)
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
        [Parameter(Mandatory = $true)]$TaskContext,
        [Parameter(Mandatory = $true)]$SafetySummary,
        [Parameter(Mandatory = $true)][string]$BaseRef
    )

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
    $commitDisplay = if ($ImplementationCommit) {
        $ImplementationCommit
    } else {
        '待首次实现提交后回写'
    }
    $taskName = [string]$TaskContext.task_name
    $taskGoal = ConvertTo-Markdown -Value $TaskContext.task_goal
    $unfinishedScope = ConvertTo-Markdown -Value $TaskContext.unfinished_scope
    $keyRisks = ConvertTo-Markdown -Value $TaskContext.key_risks
    $testEvidenceNotes = ConvertTo-Markdown -Value $TaskContext.test_evidence_notes
    $requestSummary = ConvertTo-Markdown -Value $TaskContext.request_summary
    $acceptanceCriteria = ConvertTo-Markdown -Value $TaskContext.acceptance_criteria
    $knownRisks = ConvertTo-Markdown -Value $TaskContext.known_risks
    $uncertainties = ConvertTo-Markdown -Value $TaskContext.uncertainties
    $taskImplementation = ConvertTo-Markdown -Value $TaskContext.task_result.implementation
    $safetyFindings = [int]$SafetySummary.finding_count
    $safetyAllowed = [bool]$SafetySummary.allowed_to_push
    $safetyDecision = if ($safetyAllowed -and $safetyFindings -eq 0) { '是' } else { '否' }

    $reviewIndex = @"
# $TaskId 审核首页

- 任务名称：$TaskName
- 任务分支：``$branch``
- 基础分支：``$BaseBranch``
- 基础 Commit：``$baseCommit``
- 审核目标：Pull Request 当前 HEAD
- 生成证据 Commit：``$commitDisplay``
- Pull Request：$prDisplay

## 任务目标

$taskGoal

## 实际完成范围

$changedList

## 未完成范围

$unfinishedScope

## 审核材料入口

- [任务结果](TASK_RESULT.md)
- [测试报告](TEST_REPORT.md)
- [变更文件](CHANGED_FILES.md)
- [安全报告](SECURITY_REPORT.md)
- [已知问题](KNOWN_ISSUES.md)
- [独立审核输入](AUDIT_INPUT.md)

## 重点风险

$keyRisks

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

## 任务提供的验证说明

$testEvidenceNotes

## 失败或警告

- 本地自动化失败数：$Failed
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

- 所有变更是否属于任务范围：$($TaskContext.in_scope)
- 是否修改核心业务文件：$($TaskContext.core_business_changed)
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'CHANGED_FILES.md') -Content $changedFiles

    $securityReport = @"
# $TaskId 安全报告

- 任务名称：$TaskName
- 任务分支：``$branch``

## 扫描结果

- 扫描文件数：$($SafetySummary.scanned_file_count)
- 当前差异文件数：$($SafetySummary.changed_file_count)
- 当前内容及分支提交历史命中数：$safetyFindings
- 扫描基线：``$($SafetySummary.base_ref)``

## 推送结论

是否允许推送：$safetyDecision。

扫描器只记录规则、文件和行号，不显示完整敏感值。公开仓库禁止上传任何业务数据或凭据。
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'SECURITY_REPORT.md') -Content $securityReport

    $taskResult = @"
# $TaskId 任务结果

- 任务名称：$TaskName
- 任务分支：``$branch``

## 用户原始需求

$($TaskContext.task_result.user_request)

## 实际实现

$taskImplementation

## 未实现内容

$(
    ConvertTo-Markdown -Value $TaskContext.task_result.not_implemented
)

## 设计取舍

$(
    ConvertTo-Markdown -Value $TaskContext.task_result.design_tradeoffs
)

## 业务口径

是否修改既有业务口径：$($TaskContext.task_result.business_rules_changed)

## 合并建议

$($TaskContext.task_result.merge_recommendation)
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'TASK_RESULT.md') -Content $taskResult

    $knownIssues = @"
# $TaskId 已知问题

- 任务名称：$TaskName
- 任务分支：``$branch``

## 已知问题

$(
    ConvertTo-Markdown -Value $TaskContext.known_issues.known
)

## 暂缓问题

$(
    ConvertTo-Markdown -Value $TaskContext.known_issues.deferred
)

## 用户影响

$($TaskContext.known_issues.user_impact)

## 是否阻止合并

$($TaskContext.known_issues.blocks_merge)

## 后续建议

$(
    ConvertTo-Markdown -Value $TaskContext.known_issues.follow_up
)
"@
    Write-Utf8File -Path (Join-Path $reviewDir 'KNOWN_ISSUES.md') -Content $knownIssues

    $auditInput = @"
# $TaskId 独立审核输入

- 任务名称：$TaskName
- 任务分支：``$branch``
- 修改前 Commit：``$baseCommit``
- 修改后实现 Commit：``$commitDisplay``
- 审核目标：Pull Request 当前 HEAD
- Pull Request：$prDisplay

## 用户需求原文摘要

$requestSummary

## 验收标准

$acceptanceCriteria

## git diff 统计

$diffStat

## 核心改动位置

$changedList

## 测试命令和原始结果摘要

- ``$pythonDisplay -m pytest -q``：$PytestSummary
- ``$pythonDisplay -m compileall -q src scripts tests``：通过。
- ``git diff --check``：通过。
- 安全扫描：$safetyFindings 命中。

## 已知风险

$knownRisks

## 重点检查路径

$changedList

## Codex 最不确定的地方

$uncertainties

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
- 审核目标：Pull Request 当前 HEAD
- 生成证据 Commit Hash：``$commitDisplay``
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
- 敏感扫描结果：$safetyFindings 命中
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
# 当前状态：$TaskId 待审核

更新日期：$((Get-Date).ToString('yyyy-MM-dd'))

## 基础分支与审核范围

- 基础分支：``$BaseBranch``。
- 基础 Commit：``$baseCommit``。
- ``finalize_task.ps1`` 不执行合并、标签移动或 Release 创建。

## 最新待审核任务

- 任务：$TaskId — $TaskName。
- 任务分支：``$branch``。
- Pull Request：$prDisplay
- 审核目标：Pull Request 当前 HEAD。
- 生成证据 Commit：``$commitDisplay``。
- 固定审核入口：``docs/reviews/LATEST_REVIEW.md``。
- 测试摘要：$Passed passed，$Failed failed，$Skipped skipped；编译、差异和安全扫描通过。

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

$reviewContext = Read-ReviewContext
$taskName = [string]$reviewContext.task_name

if ($RenderReviewOnly) {
    $renderCommit = if ($EvidenceCommit) {
        $EvidenceCommit
    } else {
        (Invoke-Git -Arguments @('rev-parse', 'HEAD')).Output[0].Trim()
    }
    $renderPrUrl = if ($EvidencePrUrl) {
        $EvidencePrUrl
    } else {
        '未提供（仅渲染验证）'
    }
    $renderPytestSummary = if ($EvidencePytestSummary) {
        $EvidencePytestSummary
    } else {
        "$EvidencePassed passed, $EvidenceFailed failed, $EvidenceSkipped skipped"
    }
    $renderSafetySummary = [pscustomobject]@{
        base_ref = $BaseBranch
        scanned_file_count = (Invoke-Git -Arguments @('ls-files')).Output.Count
        changed_file_count = (Get-BaseChangedPaths -Ref $BaseBranch).Count
        finding_count = $EvidenceSafetyFindingCount
        allowed_to_push = ($EvidenceSafetyFindingCount -eq 0)
    }
    Write-ReviewPackage `
        -ImplementationCommit $renderCommit `
        -PrUrl $renderPrUrl `
        -Passed $EvidencePassed `
        -Failed $EvidenceFailed `
        -Skipped $EvidenceSkipped `
        -PytestSummary $renderPytestSummary `
        -TaskContext $reviewContext `
        -SafetySummary $renderSafetySummary `
        -BaseRef $BaseBranch
    Write-Host "审核材料渲染完成：docs/reviews/$TaskId/"
    exit 0
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

$safetySummary = [IO.File]::ReadAllText(
    $safetyReport,
    [Text.Encoding]::UTF8
) | ConvertFrom-Json
if (-not [bool]$safetySummary.allowed_to_push -or [int]$safetySummary.finding_count -ne 0) {
    throw '安全报告不允许推送，拒绝生成通过结论。'
}
Write-ReviewPackage `
    -ImplementationCommit '' `
    -PrUrl '' `
    -Passed $passed `
    -Failed $failed `
    -Skipped $skipped `
    -PytestSummary $pytestSummary `
    -TaskContext $reviewContext `
    -SafetySummary $safetySummary `
    -BaseRef "origin/$BaseBranch"

$null = Invoke-CheckedCommand -Label '审核材料首次完整性检查' -Command {
    & $python scripts/validate_review_package.py `
        --task-id $TaskId `
        --branch $branch `
        --base-ref "origin/$BaseBranch" `
        --allow-pending-pr
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
$prChanges = ConvertTo-Markdown -Value $reviewContext.task_result.implementation
$prReason = ConvertTo-Markdown -Value $reviewContext.request_summary
$prImpact = [string]$reviewContext.known_issues.user_impact
$prBody = @"
## 变更内容

$prChanges

## 原因

$prReason

## 影响

$prImpact

## 验证

- $pytestSummary
- Python compileall：通过
- git diff --check：通过
- 安全扫描：$($safetySummary.finding_count) 命中
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
    -TaskContext $reviewContext `
    -SafetySummary $safetySummary `
    -BaseRef "origin/$BaseBranch"

$null = Invoke-CheckedCommand -Label 'PR 回写后的审核材料检查' -Command {
    & $python scripts/validate_review_package.py `
        --task-id $TaskId `
        --branch $branch `
        --base-ref "origin/$BaseBranch"
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
