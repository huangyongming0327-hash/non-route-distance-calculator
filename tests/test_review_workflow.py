from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_REVIEW_FILES = (
    "REVIEW_INDEX.md",
    "TASK_RESULT.md",
    "TEST_REPORT.md",
    "CHANGED_FILES.md",
    "SECURITY_REPORT.md",
    "KNOWN_ISSUES.md",
    "AUDIT_INPUT.md",
)
BRANCH = "task/TASK-TEST-001-review"
TASK_ID = "TASK-TEST-001"
COMMIT = "1" * 40
PR_URL = "https://github.com/example/example/pull/1"


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def initialize_repository(path: Path) -> None:
    run("git", "init", "-b", "master", cwd=path)
    run("git", "config", "user.email", "synthetic@example.invalid", cwd=path)
    run("git", "config", "user.name", "Synthetic Test", cwd=path)
    (path / "README.md").write_text("synthetic fixture\n", encoding="utf-8")
    run("git", "add", "--", "README.md", cwd=path)
    run("git", "commit", "-m", "test baseline", cwd=path)


def create_valid_review_package(path: Path) -> None:
    review_dir = path / "docs" / "reviews" / TASK_ID
    review_dir.mkdir(parents=True)
    common = f"# {TASK_ID}\n\n- 任务分支：`{BRANCH}`\n"
    for name in REQUIRED_REVIEW_FILES:
        text = common + "\n本文件使用合成测试数据，不含真实业务信息。\n"
        if name == "REVIEW_INDEX.md":
            text += f"\n- 实现 Commit：`{COMMIT}`\n- Pull Request：{PR_URL}\n"
        elif name == "TEST_REPORT.md":
            text += "\n- 通过：3\n- 失败：0\n- 跳过：1\n- 真实 API 调用次数：0\n"
        elif name == "SECURITY_REPORT.md":
            text += "\n安全扫描：0 命中。\n\n是否允许推送：是。\n"
        elif name == "KNOWN_ISSUES.md":
            text += (
                "\n未发现已知阻塞问题。此段是合成审核材料，"
                "用于验证文件非空、任务编号一致、分支一致和结论完整。"
            )
        elif name == "AUDIT_INPUT.md":
            text += f"\n- 修改后 Commit：`{COMMIT}`\n- Pull Request：{PR_URL}\n"
        (review_dir / name).write_text(text, encoding="utf-8")

    latest = (
        f"# 最新待审核任务\n\n- 任务编号：{TASK_ID}\n"
        f"- 任务分支：`{BRANCH}`\n"
        f"- 最新 Commit：`{COMMIT}`\n"
        f"- Pull Request：{PR_URL}\n"
        f"- 审核入口：{TASK_ID}/REVIEW_INDEX.md\n"
    )
    (path / "docs" / "reviews" / "LATEST_REVIEW.md").write_text(
        latest, encoding="utf-8"
    )


def test_required_workflow_files_and_safety_guards_exist() -> None:
    template = ROOT / "docs" / "reviews" / "TASK_TEMPLATE"
    task_review = ROOT / "docs" / "reviews" / "TASK-GITHUB-002"
    for name in REQUIRED_REVIEW_FILES:
        assert (template / name).is_file()
        assert (task_review / name).is_file()

    finalize = (ROOT / "scripts" / "finalize_task.ps1").read_text(
        encoding="utf-8-sig"
    )
    lowered = finalize.lower()
    assert not re.search(r"(?im)^\s*(?:&\s*)?git\s+add\s+-a\b", lowered)
    assert "'add', '-a'" not in lowered
    assert "push --force" not in lowered
    assert "pr merge" not in lowered
    assert "release create" not in lowered
    assert "--draft" in finalize
    assert "scan_repository_safety.ps1" in finalize
    assert "validate_review_package.py" in finalize

    workflow = (ROOT / ".github" / "workflows" / "pr-validation.yml").read_text(
        encoding="utf-8"
    )
    assert "python -m venv .venv" in workflow
    assert r".\.venv\Scripts\python.exe -m pytest -q" in workflow


def test_powershell_scripts_parse_in_windows_powershell() -> None:
    command = (
        "$failed=$false;"
        "Get-ChildItem scripts\\start_task.ps1,scripts\\finalize_task.ps1,"
        "scripts\\scan_repository_safety.ps1 | ForEach-Object {"
        "$tokens=$null;$errors=$null;"
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        "$_.FullName,[ref]$tokens,[ref]$errors);"
        "if($errors.Count -gt 0){$failed=$true;$errors | ForEach-Object {"
        "Write-Error $_.Message}}};if($failed){exit 1}"
    )
    completed = run(
        "powershell",
        "-NoProfile",
        "-Command",
        command,
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_review_validator_accepts_complete_package(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    run("git", "switch", "-c", BRANCH, cwd=tmp_path)
    create_valid_review_package(tmp_path)

    completed = run(
        sys.executable,
        str(ROOT / "scripts" / "validate_review_package.py"),
        "--task-id",
        TASK_ID,
        "--branch",
        BRANCH,
        cwd=tmp_path,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "审核材料检查通过" in completed.stdout


def test_review_validator_rejects_placeholder(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    run("git", "switch", "-c", BRANCH, cwd=tmp_path)
    create_valid_review_package(tmp_path)
    result_file = tmp_path / "docs" / "reviews" / TASK_ID / "TASK_RESULT.md"
    result_file.write_text(
        result_file.read_text(encoding="utf-8") + "\nTODO待补充\n",
        encoding="utf-8",
    )

    completed = run(
        sys.executable,
        str(ROOT / "scripts" / "validate_review_package.py"),
        "--task-id",
        TASK_ID,
        "--branch",
        BRANCH,
        cwd=tmp_path,
        check=False,
    )
    assert completed.returncode != 0
    assert "存在模板占位" in completed.stdout


def test_safety_scanner_blocks_synthetic_token_shape(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "中文说明.md").write_text("合成测试说明\n", encoding="utf-8")
    run("git", "add", "--", "中文说明.md", cwd=tmp_path)
    run("git", "commit", "-m", "add non-ascii path", cwd=tmp_path)
    run("git", "config", "core.quotepath", "true", cwd=tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts" / "scan_repository_safety.ps1", scripts)
    run("git", "add", "--", "scripts/scan_repository_safety.ps1", cwd=tmp_path)
    run("git", "commit", "-m", "add scanner", cwd=tmp_path)

    clean = run(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scripts / "scan_repository_safety.ps1"),
        "-BaseRef",
        "HEAD",
        cwd=tmp_path,
        check=False,
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr

    synthetic_token = "gh" + "p_" + ("A" * 24)
    (tmp_path / "unsafe.txt").write_text(
        f"synthetic test credential: {synthetic_token}\n", encoding="utf-8"
    )
    blocked = run(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scripts / "scan_repository_safety.ps1"),
        "-BaseRef",
        "HEAD",
        cwd=tmp_path,
        check=False,
    )
    assert blocked.returncode != 0
    assert "GitHub Token" in blocked.stdout
    assert synthetic_token not in blocked.stdout


def test_start_task_stops_before_network_when_worktree_is_dirty(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts" / "start_task.ps1", scripts)
    (tmp_path / "README.md").write_text(
        "synthetic fixture with local change\n", encoding="utf-8"
    )

    completed = run(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scripts / "start_task.ps1"),
        "-TaskId",
        "TASK-TEST-001",
        "-BranchSlug",
        "review",
        "-TaskName",
        "合成任务",
        cwd=tmp_path,
        check=False,
    )
    assert completed.returncode == 2
    assert "当前 Git 工作区不是干净状态" in completed.stdout
    assert "本脚本没有删除或修改任何现有文件" in completed.stdout
