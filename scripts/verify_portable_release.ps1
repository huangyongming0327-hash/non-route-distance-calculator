param(
    [string]$ReleaseRoot = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ReleaseRoot) {
    $ReleaseRoot = Join-Path $ProjectRoot "release\非线路运距计算工具_V1.0_RC2"
}
$ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
$ProductName = "非线路运距计算工具"
$VerificationRoot = Join-Path $ProjectRoot "temp\portable_verification"
$EvidenceRoot = Join-Path $ProjectRoot "docs\evidence\task007a"

$expectedRelease = [System.IO.Path]::GetFullPath(
    (Join-Path $ProjectRoot "release\非线路运距计算工具_V1.0_RC2")
)
if ($ReleaseRoot -ne $expectedRelease) {
    throw "仅允许验证当前项目的 V1.0 RC2 发布目录：$expectedRelease"
}
if (-not (Test-Path -LiteralPath (Join-Path $ReleaseRoot "$ProductName.exe"))) {
    throw "发布 EXE 不存在：$ReleaseRoot"
}

if (Test-Path -LiteralPath $VerificationRoot) {
    $resolved = [System.IO.Path]::GetFullPath($VerificationRoot)
    $expected = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "temp\portable_verification"))
    if ($resolved -ne $expected) {
        throw "验证临时目录不符合预期：$resolved"
    }
    Remove-Item -LiteralPath $VerificationRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $VerificationRoot, $EvidenceRoot -Force | Out-Null

$Targets = @(
    @{ Name = "开发目录发布包"; Path = $ReleaseRoot; Copy = $false },
    @{ Name = "中文路径"; Path = (Join-Path $VerificationRoot "中文验证路径\非线路工具"); Copy = $true },
    @{ Name = "带空格路径"; Path = (Join-Path $VerificationRoot "带 空格 路径\非线路工具"); Copy = $true }
)
$Results = @()
foreach ($target in $Targets) {
    $targetPath = [string]$target.Path
    if ([bool]$target.Copy) {
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        Copy-Item -Path (Join-Path $ReleaseRoot "*") -Destination $targetPath -Recurse -Force
    }
    $exe = Join-Path $targetPath "$ProductName.exe"
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -WorkingDirectory $targetPath -WindowStyle Hidden -Wait -PassThru
    $watch.Stop()
    $startupLog = Join-Path $targetPath "logs\startup.log"
    $startupRecorded = Test-Path -LiteralPath $startupLog
    if ($process.ExitCode -ne 0 -or -not $startupRecorded) {
        throw "便携版启动验证失败：$($target.Name)，退出码 $($process.ExitCode)"
    }
    $windowLine = Get-Content -LiteralPath $startupLog -Encoding UTF8 |
        Where-Object { $_ -match '\| 主窗口已显示 \|' } |
        Select-Object -Last 1
    if ($windowLine -notmatch '\| 主窗口已显示 \| ([0-9.]+) ms') {
        throw "启动日志缺少主窗口出现耗时：$startupLog"
    }
    $mainWindowSeconds = [Math]::Round(([double]$Matches[1] / 1000), 3)
    $Results += [pscustomobject][ordered]@{
        name = $target.Name
        path = $targetPath
        exit_code = $process.ExitCode
        elapsed_seconds = [Math]::Round($watch.Elapsed.TotalSeconds, 3)
        main_window_seconds = $mainWindowSeconds
        startup_log = $startupLog
        source_directory_absent = -not (Test-Path -LiteralPath (Join-Path $targetPath "src"))
        venv_absent = -not (Test-Path -LiteralPath (Join-Path $targetPath ".venv"))
    }
}

$Evidence = [ordered]@{
    tested_at = (Get-Date).ToString("o")
    release_root = $ReleaseRoot
    maximum_main_window_seconds = ($Results | Measure-Object -Property main_window_seconds -Maximum).Maximum
    maximum_process_elapsed_seconds = ($Results | Measure-Object -Property elapsed_seconds -Maximum).Maximum
    results = $Results
}
$EvidencePath = Join-Path $EvidenceRoot "portable_verification_rc2.json"
[System.IO.File]::WriteAllText(
    $EvidencePath,
    ($Evidence | ConvertTo-Json -Depth 8),
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output "EVIDENCE=$EvidencePath"
$Results | ForEach-Object {
    Write-Output ("{0}: main_window={1}s, process={2}s, exit={3}" -f $_.name, $_.main_window_seconds, $_.elapsed_seconds, $_.exit_code)
}
