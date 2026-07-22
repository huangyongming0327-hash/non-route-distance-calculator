param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProductName = "非线路运距计算工具"
$ReleaseName = "非线路运距计算工具_V1.0_RC2"
$ReleaseParent = Join-Path $ProjectRoot "release"
$ReleaseRoot = Join-Path $ReleaseParent $ReleaseName
$BuildRoot = Join-Path $ProjectRoot "build\v1.0_rc2"
$DistRoot = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$SpecRoot = Join-Path $BuildRoot "spec"

function Assert-ProjectChild([string]$PathToCheck) {
    $full = [System.IO.Path]::GetFullPath($PathToCheck)
    $root = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\') + '\'
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝操作项目目录之外的路径：$full"
    }
    if ($full -eq [System.IO.Path]::GetFullPath($ProjectRoot)) {
        throw "拒绝把项目根目录作为清理目标。"
    }
}

Assert-ProjectChild $ReleaseRoot
Assert-ProjectChild $BuildRoot

if (-not $Python) {
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "未找到构建 Python：$Python"
}

foreach ($target in @($ReleaseRoot, $BuildRoot)) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
New-Item -ItemType Directory -Path $DistRoot, $WorkRoot, $SpecRoot -Force | Out-Null

$PyInstallerArguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", $ProductName,
    "--distpath", $DistRoot,
    "--workpath", $WorkRoot,
    "--specpath", $SpecRoot,
    "--paths", $ProjectRoot,
    "--add-data", "$ProjectRoot\src\config\vehicle_mappings.json;src\config",
    "--hidden-import", "win32cred",
    "--hidden-import", "win32crypt",
    "--hidden-import", "pythoncom",
    "--hidden-import", "pywintypes",
    "--hidden-import", "win32com.client",
    "$ProjectRoot\src\main.py"
)

& $Python @PyInstallerArguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败，退出码：$LASTEXITCODE"
}

$BuiltRoot = Join-Path $DistRoot $ProductName
if (-not (Test-Path -LiteralPath (Join-Path $BuiltRoot "$ProductName.exe"))) {
    throw "构建结果缺少 EXE：$BuiltRoot"
}
Copy-Item -Path (Join-Path $BuiltRoot "*") -Destination $ReleaseRoot -Recurse -Force

foreach ($name in @("config", "cache", "logs", "outputs", "temp")) {
    New-Item -ItemType Directory -Path (Join-Path $ReleaseRoot $name) -Force | Out-Null
}

$RequiredDocuments = @(
    @{ Source = "docs\USER_GUIDE.md"; Destination = "USER_GUIDE.md" },
    @{ Source = "output\pdf\使用说明.pdf"; Destination = "使用说明.pdf" },
    @{ Source = "CHANGELOG.md"; Destination = "CHANGELOG.md" },
    @{ Source = "KNOWN_ISSUES.md"; Destination = "KNOWN_ISSUES.md" }
)
foreach ($document in $RequiredDocuments) {
    $source = Join-Path $ProjectRoot $document.Source
    if (-not (Test-Path -LiteralPath $source)) {
        throw "发布文档缺失：$source"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $ReleaseRoot $document.Destination) -Force
}

$GitHash = (git -C $ProjectRoot rev-parse HEAD).Trim()
$GitStatus = @(git -C $ProjectRoot status --porcelain)
$WorkingTreeState = if ($GitStatus.Count -eq 0) { "clean" } else { "含未提交的 TASK-007A 候选版修改" }
$BuildDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
$PythonVersion = (& $Python -c "import platform; print(platform.python_version())").Trim()
$PySideVersion = (& $Python -c "import PySide6; print(PySide6.__version__)").Trim()
$VersionLines = @(
    "产品名称：非线路运距计算工具",
    "版本：V1.0 RC2",
    "构建日期：$BuildDate",
    "基线 Git Commit Hash：$GitHash",
    "构建工作区状态：$WorkingTreeState",
    "Python版本：$PythonVersion",
    "PySide6版本：$PySideVersion",
    "高德接口版本：地理编码 v3；普通驾车路径规划 v5",
    "缓存版本：SQLite schema 5；迁移格式 1",
    "可信地址库版本：confirmed-address-v1",
    "工作簿检测算法版本：task-007a-ooxml-v1"
)
[System.IO.File]::WriteAllLines(
    (Join-Path $ReleaseRoot "VERSION.txt"),
    $VersionLines,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output "RELEASE_ROOT=$ReleaseRoot"
Write-Output "EXE_PATH=$(Join-Path $ReleaseRoot "$ProductName.exe")"
