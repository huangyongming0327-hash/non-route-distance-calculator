from __future__ import annotations

import json
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


def install_safety_scanner(path: Path) -> Path:
    scripts = path / "scripts"
    scripts.mkdir(exist_ok=True)
    scanner = scripts / "scan_repository_safety.ps1"
    shutil.copy2(ROOT / "scripts" / "scan_repository_safety.ps1", scanner)
    run("git", "add", "--", "scripts/scan_repository_safety.ps1", cwd=path)
    run("git", "commit", "-m", "add scanner", cwd=path)
    return scanner


def run_safety_scanner(
    path: Path,
    scanner: Path,
    base_ref: str,
) -> subprocess.CompletedProcess[str]:
    return run(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scanner),
        "-BaseRef",
        base_ref,
        cwd=path,
        check=False,
    )


def create_valid_review_package(path: Path) -> None:
    review_dir = path / "docs" / "reviews" / TASK_ID
    review_dir.mkdir(parents=True)
    common = f"# {TASK_ID}\n\n- 任务分支：`{BRANCH}`\n"
    for name in REQUIRED_REVIEW_FILES:
        text = common + "\n本文件使用合成测试数据，不含真实业务信息。\n"
        if name == "REVIEW_INDEX.md":
            text += f"\n- 实现 Commit：`{COMMIT}`\n- Pull Request：{PR_URL}\n"
        elif name == "TEST_REPORT.md":
            text += (
                "\n- 通过：3\n- 失败：0\n- 跳过：1\n"
                "- 完整离线 pytest：3 passed, 1 skipped\n"
            )
        elif name == "CHANGED_FILES.md":
            expected_paths = [
                "docs/reviews/LATEST_REVIEW.md",
                *(f"docs/reviews/{TASK_ID}/{item}" for item in REQUIRED_REVIEW_FILES),
                f"docs/reviews/{TASK_ID}/REVIEW_CONTEXT.json",
            ]
            text += "\n" + "\n".join(f"- `{item}`" for item in expected_paths) + "\n"
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

    (review_dir / "REVIEW_CONTEXT.json").write_text(
        json.dumps(
            {
                "task_name": "合成审核任务",
                "task_goal": ["验证审核材料。"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    latest = (
        f"# 最新待审核任务\n\n- 任务编号：{TASK_ID}\n"
        f"- 任务分支：`{BRANCH}`\n"
        f"- 最新 Commit：`{COMMIT}`\n"
        "- 审核目标：Pull Request 当前 HEAD\n"
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
    assert (template / "REVIEW_CONTEXT.json").is_file()
    assert (task_review / "REVIEW_CONTEXT.json").is_file()

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
    assert "REVIEW_CONTEXT.json" in finalize
    assert "建立 Codex 自动上传与 GitHub 在线审核流程" not in finalize
    assert "本任务只建立开发与审核流程" not in finalize

    workflow = (ROOT / ".github" / "workflows" / "pr-validation.yml").read_text(
        encoding="utf-8"
    )
    assert "python -m venv .venv" in workflow
    assert r".\.venv\Scripts\python.exe -m pytest -q" in workflow
    assert 'PYTHONIOENCODING: "utf-8"' in workflow
    assert "ls-files --cached --others --exclude-standard" in workflow


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


def test_review_validator_rejects_changed_file_list_mismatch(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    run("git", "switch", "-c", BRANCH, cwd=tmp_path)
    create_valid_review_package(tmp_path)
    changed_file = (
        tmp_path / "docs" / "reviews" / TASK_ID / "CHANGED_FILES.md"
    )
    changed_file.write_text(
        changed_file.read_text(encoding="utf-8").replace(
            "- `docs/reviews/LATEST_REVIEW.md`\n",
            "",
        ),
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
    assert "CHANGED_FILES.md 缺少真实变更" in completed.stdout
    assert "docs/reviews/LATEST_REVIEW.md" in completed.stdout


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


def test_safety_scanner_does_not_exempt_test_text_with_personal_data(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts" / "scan_repository_safety.ps1", scripts)
    run("git", "add", "--", "scripts/scan_repository_safety.ps1", cwd=tmp_path)
    run("git", "commit", "-m", "add scanner", cwd=tmp_path)

    phone = "138" + "0013" + "8000"
    coordinates = "116." + "481008, 39." + "989625"
    address = "".join(
        chr(code)
        for code in (
            23458,
            25143,
            20179,
            24211,
            65306,
            26576,
            24066,
            26576,
            21306,
            27979,
            35797,
            36335,
            56,
            56,
            21495,
        )
    )
    note = tmp_path / "tests" / "synthetic_mock_note.txt"
    note.parent.mkdir()
    note.write_text(
        f"ordinary test synthetic mock text\n{phone}\n{address}\n{coordinates}\n",
        encoding="utf-8",
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
    assert "手机号形态" in blocked.stdout
    assert "完整业务地址形态" in blocked.stdout
    assert "经纬度业务证据形态" in blocked.stdout
    assert phone not in blocked.stdout
    assert address not in blocked.stdout
    assert coordinates not in blocked.stdout


def test_safety_scanner_detects_sensitive_data_removed_from_history(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts" / "scan_repository_safety.ps1", scripts)
    run("git", "add", "--", "scripts/scan_repository_safety.ps1", cwd=tmp_path)
    run("git", "commit", "-m", "add scanner", cwd=tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()

    phone = "139" + "0013" + "8000"
    history_note = tmp_path / "notes" / "synthetic_mock_history.txt"
    history_note.parent.mkdir()
    history_note.write_text(
        f"ordinary synthetic test text\nphone={phone}\n",
        encoding="utf-8",
    )
    run("git", "add", "--", "notes/synthetic_mock_history.txt", cwd=tmp_path)
    run("git", "commit", "-m", "add unsafe history fixture", cwd=tmp_path)
    run("git", "rm", "--", "notes/synthetic_mock_history.txt", cwd=tmp_path)
    run("git", "commit", "-m", "remove unsafe history fixture", cwd=tmp_path)

    blocked = run(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scripts / "scan_repository_safety.ps1"),
        "-BaseRef",
        base_commit,
        cwd=tmp_path,
        check=False,
    )
    assert blocked.returncode != 0
    assert "手机号形态（提交历史）" in blocked.stdout
    assert "synthetic_mock_history.txt" in blocked.stdout
    assert re.search(r"Commit=[0-9a-f]{12}", blocked.stdout)
    assert phone not in blocked.stdout


def test_safety_scanner_blocks_new_png(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    (tmp_path / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "未经授权的二进制图片或 PDF" in blocked.stdout
    assert "screenshot.png" in blocked.stdout
    assert "二进制图片或PDF无法自动确认是否已脱敏" in blocked.stdout
    assert "普通开发任务禁止提交" in blocked.stdout


def test_safety_scanner_blocks_new_pdf(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    (tmp_path / "audit.pdf").write_bytes(b"%PDF-1.4\nsynthetic\n%%EOF\n")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "未经授权的二进制图片或 PDF" in blocked.stdout
    assert "audit.pdf" in blocked.stdout


def test_safety_scanner_does_not_exempt_binary_test_names(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    names = ("test-map.png", "测试截图.jpg", "synthetic-report.pdf")
    for name in names:
        (tmp_path / name).write_bytes(b"synthetic binary fixture")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    for name in names:
        assert name in blocked.stdout


def test_safety_scanner_detects_png_removed_from_history(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    image = tmp_path / "test-history.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic history fixture")
    run("git", "add", "--", image.name, cwd=tmp_path)
    run("git", "commit", "-m", "add binary history fixture", cwd=tmp_path)
    image_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "rm", "--", image.name, cwd=tmp_path)
    run("git", "commit", "-m", "remove binary history fixture", cwd=tmp_path)

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "未经授权的二进制图片或 PDF（提交历史）" in blocked.stdout
    assert "test-history.png" in blocked.stdout
    assert f"Commit={image_commit[:12]}" in blocked.stdout


def test_safety_scanner_ignores_unchanged_pdf_from_master(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    evidence = tmp_path / "docs" / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "audited.pdf").write_bytes(b"%PDF-1.4\nmaster fixture\n%%EOF\n")
    run("git", "add", "--", "docs/evidence/audited.pdf", cwd=tmp_path)
    run("git", "commit", "-m", "add audited master document", cwd=tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "switch", "-c", "task/TASK-TEST-002-binary", cwd=tmp_path)
    (tmp_path / "safe-note.txt").write_text("safe task change\n", encoding="utf-8")

    completed = run_safety_scanner(tmp_path, scanner, base_commit)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "安全扫描通过：0 命中" in completed.stdout


def test_safety_scanner_does_not_print_binary_content(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    phone = "138" + "0013" + "8000"
    marker = "PRIVATE_BINARY_PAYLOAD_MARKER"
    (tmp_path / "private.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + f"{marker}:{phone}".encode()
    )

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)
    output = blocked.stdout + blocked.stderr

    assert blocked.returncode != 0
    assert "private.png" in output
    assert marker not in output
    assert phone not in output


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


def test_finalize_review_renderer_supports_non_github_flow_task(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    task_id = "TASK-OFFLINE-001"
    branch = f"task/{task_id}-cleanup"
    run("git", "switch", "-c", branch, cwd=tmp_path)

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts" / "finalize_task.ps1", scripts)
    review_dir = tmp_path / "docs" / "reviews" / task_id
    review_dir.mkdir(parents=True)
    for name in REQUIRED_REVIEW_FILES:
        (review_dir / name).write_text("待渲染\n", encoding="utf-8")

    context = {
        "task_name": "离线术语表清理",
        "task_goal": ["统一本地术语文档中的标题格式。"],
        "unfinished_scope": ["不修改任何网络或 GitHub 流程。"],
        "key_risks": ["不得把文档清理描述成业务逻辑变更。"],
        "test_evidence_notes": ["专项验证只检查离线文档渲染结果。"],
        "in_scope": "是；只包含模拟仓库中的文档与审核材料。",
        "core_business_changed": "否；模拟任务没有业务代码。",
        "request_summary": "只整理本地术语文档，不建立或修改 GitHub 流程。",
        "acceptance_criteria": ["审核材料准确描述离线文档任务。"],
        "known_risks": ["模拟任务不验证任何线上服务。"],
        "uncertainties": ["无。"],
        "actions_status": "以Pull Request当前HEAD对应的Checks页面为准。",
        "task_result": {
            "user_request": "统一离线术语表标题。",
            "implementation": ["新增离线术语说明文件。"],
            "not_implemented": ["未执行网络操作。"],
            "design_tradeoffs": ["保留原有术语含义，只调整标题。"],
            "business_rules_changed": "否。",
            "merge_recommendation": "由模拟审核者决定。",
        },
        "known_issues": {
            "known": ["无已知阻塞问题。"],
            "deferred": ["无。"],
            "user_impact": "只影响离线文档阅读。",
            "blocks_merge": "否。",
            "follow_up": ["复核标题格式。"],
        },
    }
    (review_dir / "REVIEW_CONTEXT.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    offline_note = tmp_path / "docs" / "offline_notes.md"
    offline_note.write_text("# 离线术语说明\n", encoding="utf-8")
    commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()

    completed = run(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scripts / "finalize_task.ps1"),
        "-TaskId",
        task_id,
        "-CommitMessage",
        "docs: render offline review",
        "-PrTitle",
        "offline review",
        "-RenderReviewOnly",
        "-EvidenceCommit",
        commit,
        "-EvidencePrUrl",
        "https://example.invalid/review/7",
        "-EvidencePassed",
        "3",
        "-EvidenceFailed",
        "0",
        "-EvidenceSkipped",
        "1",
        "-EvidencePytestSummary",
        "3 passed, 1 skipped",
        cwd=tmp_path,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    review_index = (review_dir / "REVIEW_INDEX.md").read_text(encoding="utf-8")
    audit_input = (review_dir / "AUDIT_INPUT.md").read_text(encoding="utf-8")
    changed_files = (review_dir / "CHANGED_FILES.md").read_text(encoding="utf-8")
    task_result = (review_dir / "TASK_RESULT.md").read_text(encoding="utf-8")
    test_report = (review_dir / "TEST_REPORT.md").read_text(encoding="utf-8")
    assert "离线术语表清理" in review_index
    assert "只整理本地术语文档" in audit_input
    assert "docs/offline_notes.md" in changed_files
    assert "统一离线术语表标题" in task_result
    assert "建立 Codex 自动上传与 GitHub 在线审核流程" not in audit_input
    assert "建立任务分支、审核材料、安全扫描" not in task_result
    assert (
        "GitHub Actions结果：以Pull Request当前HEAD对应的Checks页面为准。"
        in test_report
    )


def test_versioned_actions_status_does_not_pin_run_number() -> None:
    expected = "以Pull Request当前HEAD对应的Checks页面为准。"
    paths = (
        ROOT / "CURRENT_STATUS.md",
        ROOT / "docs" / "reviews" / "LATEST_REVIEW.md",
        ROOT / "docs" / "reviews" / "TASK-GITHUB-002" / "REVIEW_CONTEXT.json",
        ROOT / "docs" / "reviews" / "TASK-GITHUB-002" / "KNOWN_ISSUES.md",
        ROOT / "docs" / "reviews" / "TASK-GITHUB-002" / "TEST_REPORT.md",
        ROOT / "docs" / "reviews" / "TASK_TEMPLATE" / "TEST_REPORT.md",
        ROOT / "scripts" / "finalize_task.ps1",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8-sig")
        assert expected in text, path
        assert not re.search(r"GitHub Actions[^\n]*运行\s*\d+", text), path
