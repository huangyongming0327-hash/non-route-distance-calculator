[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$')]
    [string]$TaskId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$BranchSlug,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$TaskName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& git @Arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw "Git 命令失败：git $($Arguments -join ' ')`n$($output -join [Environment]::NewLine)"
    }
    return $output
}

function Stop-ForDirtyWorktree {
    param([string[]]$StatusLines)

    Write-Host '1. 发现了什么问题：当前 Git 工作区不是干净状态。'
    Write-Host '2. 会造成什么影响：继续创建任务分支可能把上一个任务或本地文件混入新任务。'
    Write-Host '3. 推荐方案：先确认、提交或安全保存现有改动，再重新运行本脚本。'
    Write-Host '4. 会删除或改变什么：本脚本没有删除或修改任何现有文件。'
    Write-Host '5. 是否影响程序正常使用：不会，只是停止了任务初始化。'
    Write-Host '6. 用户只需要回复：请帮我检查当前未提交改动。'
    Write-Host ''
    Write-Host '当前状态：'
    $StatusLines | ForEach-Object { Write-Host "  $_" }
    exit 2
}

$status = @(& git status --porcelain=v1)
if ($LASTEXITCODE -ne 0) {
    throw '无法读取 Git 工作区状态。'
}
if ($status.Count -gt 0) {
    Stop-ForDirtyWorktree -StatusLines $status
}

$null = Invoke-Git -Arguments @('rev-parse', '--show-toplevel')
$null = Invoke-Git -Arguments @('ls-remote', '--exit-code', 'origin', 'HEAD')
$null = Invoke-Git -Arguments @('fetch', 'origin', 'master')
$null = Invoke-Git -Arguments @('switch', 'master')
$null = Invoke-Git -Arguments @('merge', '--ff-only', 'origin/master')

$baseCommit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $baseCommit) {
    throw '无法确定最新 master Commit。'
}

$branch = "task/$TaskId-$BranchSlug"
& git show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) {
    throw "本地分支已存在：$branch"
}
& git ls-remote --exit-code --heads origin $branch *> $null
if ($LASTEXITCODE -eq 0) {
    throw "远程分支已存在：$branch"
}

$templateDir = Join-Path $repoRoot 'docs\reviews\TASK_TEMPLATE'
$reviewDir = Join-Path $repoRoot "docs\reviews\$TaskId"
$requiredFiles = @(
    'REVIEW_INDEX.md',
    'TASK_RESULT.md',
    'TEST_REPORT.md',
    'CHANGED_FILES.md',
    'SECURITY_REPORT.md',
    'KNOWN_ISSUES.md',
    'AUDIT_INPUT.md'
)

foreach ($name in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $templateDir $name) -PathType Leaf)) {
        throw "审核模板缺失：docs/reviews/TASK_TEMPLATE/$name"
    }
}
if (Test-Path -LiteralPath $reviewDir) {
    throw "任务审核目录已存在：docs/reviews/$TaskId"
}

$null = Invoke-Git -Arguments @('switch', '-c', $branch)
New-Item -ItemType Directory -Path $reviewDir | Out-Null

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
foreach ($name in $requiredFiles) {
    $source = Join-Path $templateDir $name
    $destination = Join-Path $reviewDir $name
    $content = [IO.File]::ReadAllText($source, [Text.Encoding]::UTF8)
    $content = $content.Replace('{{TASK_ID}}', $TaskId)
    $content = $content.Replace('{{TASK_NAME}}', $TaskName)
    $content = $content.Replace('{{BRANCH}}', $branch)
    $content = $content.Replace('{{BASE_COMMIT}}', $baseCommit)
    [IO.File]::WriteAllText($destination, $content, $utf8NoBom)
}

Write-Host "任务分支已创建：$branch"
Write-Host "基础 Commit：$baseCommit"
Write-Host "审核目录已创建：docs/reviews/$TaskId/"
Write-Host '未提交、未推送空分支，也未修改任何业务代码。'
