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
    assert "Wait-CurrentHeadActions" in finalize
    assert "New-CommanderReviewNotice" in finalize
    assert "headRefOid" in finalize
    assert "建立 Codex 自动上传与 GitHub 在线审核流程" not in finalize
    assert "本任务只建立开发与审核流程" not in finalize

    for path in (
        ROOT / "AGENTS.md",
        ROOT / "docs" / "CODEX_TASK_TEMPLATE.md",
        ROOT / "docs" / "reviews" / "README.md",
    ):
        text = path.read_text(encoding="utf-8-sig")
        assert "【可直接复制给总指挥审核】" in text
        assert "最终回复" in text
        assert "最末尾" in text

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


def test_safety_scanner_blocks_named_excel_fixture(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    workbook = tmp_path / "tests" / "fixtures" / "测试样表.xlsm"
    workbook.parent.mkdir(parents=True)
    workbook.write_bytes(b"synthetic workbook fixture")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "未经授权的 Excel 工作簿" in blocked.stdout
    assert "tests/fixtures/测试样表.xlsm" in blocked.stdout


def test_safety_scanner_blocks_synthetic_excel_fixture(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    (tmp_path / "synthetic_fixture.xlsm").write_bytes(b"synthetic workbook fixture")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "未经授权的 Excel 工作簿" in blocked.stdout
    assert "synthetic_fixture.xlsm" in blocked.stdout


def test_safety_scanner_ignores_unchanged_excel_fixture_from_master(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    fixture = tmp_path / "tests" / "fixtures" / "synthetic_fixture.xlsm"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"audited master workbook fixture")
    run("git", "add", "--", "tests/fixtures/synthetic_fixture.xlsm", cwd=tmp_path)
    run("git", "commit", "-m", "add audited master workbook", cwd=tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "switch", "-c", "task/TASK-TEST-003-excel", cwd=tmp_path)
    (tmp_path / "safe-note.txt").write_text("safe task change\n", encoding="utf-8")

    completed = run_safety_scanner(tmp_path, scanner, base_commit)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "安全扫描通过：0 命中" in completed.stdout


def test_safety_scanner_blocks_modified_excel_fixture_from_master(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    fixture = tmp_path / "tests" / "fixtures" / "synthetic_fixture.xlsm"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"audited master workbook fixture")
    run("git", "add", "--", "tests/fixtures/synthetic_fixture.xlsm", cwd=tmp_path)
    run("git", "commit", "-m", "add audited master workbook", cwd=tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "switch", "-c", "task/TASK-TEST-004-excel", cwd=tmp_path)
    fixture.write_bytes(b"modified workbook fixture")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "未经授权的 Excel 工作簿" in blocked.stdout
    assert "tests/fixtures/synthetic_fixture.xlsm" in blocked.stdout


def test_safety_scanner_detects_excel_removed_from_history(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "switch", "-c", "task/TASK-TEST-005-excel", cwd=tmp_path)
    workbook = tmp_path / "synthetic_fixture.xlsm"
    workbook.write_bytes(b"temporary workbook fixture")
    run("git", "add", "--", workbook.name, cwd=tmp_path)
    run("git", "commit", "-m", "add workbook history fixture", cwd=tmp_path)
    workbook_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "rm", "--", workbook.name, cwd=tmp_path)
    run("git", "commit", "-m", "remove workbook history fixture", cwd=tmp_path)

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "未经授权的 Excel 工作簿（提交历史）" in blocked.stdout
    assert "synthetic_fixture.xlsm" in blocked.stdout
    assert f"Commit={workbook_commit[:12]}" in blocked.stdout


def test_safety_scanner_does_not_print_excel_content(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    phone = "139" + "0013" + "8000"
    marker = "PRIVATE_WORKBOOK_PAYLOAD_MARKER"
    (tmp_path / "test_workbook.xlsm").write_bytes(f"{marker}:{phone}".encode())

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)
    output = blocked.stdout + blocked.stderr

    assert blocked.returncode != 0
    assert "test_workbook.xlsm" in output
    assert marker not in output
    assert phone not in output


def test_safety_scanner_blocks_province_city_county_address(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    address = "".join(
        (
            "河北",
            "省",
            "保定",
            "市",
            "望都",
            "县",
            "高岭",
            "镇",
            "某",
            "工业园",
        )
    )
    (tmp_path / "address.txt").write_text(address + "\n", encoding="utf-8")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "行政区划连续地址形态" in blocked.stdout
    assert address not in blocked.stdout


def test_safety_scanner_blocks_labeled_municipality_address(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    label = "".join(
        (
            "原始",
            "详细",
            "地址",
            "：",
        )
    )
    address = "".join(
        (
            "北京",
            "市",
            "海淀",
            "区",
            "上庄",
            "镇",
            "某村",
        )
    )
    value = label + address
    (tmp_path / "labeled-address.txt").write_text(value + "\n", encoding="utf-8")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "地址字段形态" in blocked.stdout
    assert value not in blocked.stdout


def test_safety_scanner_blocks_province_city_district_street_address(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    address = "".join(
        (
            "江苏",
            "省",
            "南京",
            "市",
            "江宁",
            "区",
            "麒麟",
            "街道",
            "西村",
        )
    )
    (tmp_path / "street-address.txt").write_text(address + "\n", encoding="utf-8")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "行政区划连续地址形态" in blocked.stdout
    assert address not in blocked.stdout


def test_safety_scanner_does_not_exempt_synthetic_test_address(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    address = "".join(
        (
            "广东",
            "省",
            "深圳",
            "市",
            "南山",
            "区",
            "粤海",
            "街道",
        )
    )
    note = tmp_path / "tests" / "synthetic_test_address.txt"
    note.parent.mkdir()
    note.write_text(
        f"ordinary synthetic test text\n{address}\n",
        encoding="utf-8",
    )

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "行政区划连续地址形态" in blocked.stdout
    assert "tests/synthetic_test_address.txt" in blocked.stdout
    assert address not in blocked.stdout


def test_safety_scanner_detects_address_removed_from_history(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "switch", "-c", "task/TASK-TEST-006-address", cwd=tmp_path)
    address = "".join(
        (
            "河北",
            "省",
            "保定",
            "市",
            "望都",
            "县",
            "高岭",
            "镇",
        )
    )
    note = tmp_path / "address-history.txt"
    note.write_text(address + "\n", encoding="utf-8")
    run("git", "add", "--", note.name, cwd=tmp_path)
    run("git", "commit", "-m", "add address history fixture", cwd=tmp_path)
    address_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    run("git", "rm", "--", note.name, cwd=tmp_path)
    run("git", "commit", "-m", "remove address history fixture", cwd=tmp_path)

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)

    assert blocked.returncode != 0
    assert "行政区划连续地址形态（提交历史）" in blocked.stdout
    assert "address-history.txt" in blocked.stdout
    assert f"Commit={address_commit[:12]}" in blocked.stdout
    assert address not in blocked.stdout


def test_safety_scanner_ignores_address_rule_explanations(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    (tmp_path / "safe-address-rules.txt").write_text(
        "地址字段不能为空\n测试地址匹配规则\n",
        encoding="utf-8",
    )

    completed = run_safety_scanner(tmp_path, scanner, base_commit)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "安全扫描通过：0 命中" in completed.stdout


def test_safety_scanner_does_not_print_labeled_address_content(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    scanner = install_safety_scanner(tmp_path)
    base_commit = run("git", "rev-parse", "HEAD", cwd=tmp_path).stdout.strip()
    label = "".join(
        (
            "标准",
            "地址",
            "：",
        )
    )
    address = "".join(
        (
            "上海",
            "市",
            "浦东",
            "区",
            "某",
            "街道",
            "某村",
        )
    )
    value = label + address
    (tmp_path / "private-address.txt").write_text(value + "\n", encoding="utf-8")

    blocked = run_safety_scanner(tmp_path, scanner, base_commit)
    output = blocked.stdout + blocked.stderr

    assert blocked.returncode != 0
    assert "private-address.txt" in output
    assert value not in output
    assert address not in output


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


def render_commander_notice(
    tmp_path: Path,
    *,
    actions_status: str,
    actions_conclusion: str,
) -> subprocess.CompletedProcess[str]:
    initialize_repository(tmp_path)
    task_id = "TASK-NOTICE-001"
    branch = f"task/{task_id}-review"
    run("git", "switch", "-c", branch, cwd=tmp_path)

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    finalizer = scripts / "finalize_task.ps1"
    shutil.copy2(ROOT / "scripts" / "finalize_task.ps1", finalizer)

    review_dir = tmp_path / "docs" / "reviews" / task_id
    review_dir.mkdir(parents=True)
    for name in REQUIRED_REVIEW_FILES:
        (review_dir / name).write_text("合成审核通知测试\n", encoding="utf-8")

    context = {
        "task_name": "固定总指挥通知",
        "task_goal": ["验证自动审核通知。"],
        "unfinished_scope": ["不连接 GitHub。"],
        "key_risks": ["不得输出占位符。"],
        "test_evidence_notes": ["仅使用离线合成证据。"],
        "in_scope": "是。",
        "core_business_changed": "否。",
        "request_summary": "生成完整总指挥通知。",
        "acceptance_criteria": ["所有字段完整。"],
        "known_risks": ["无线上操作。"],
        "uncertainties": ["无。"],
        "actions_status": "以Pull Request当前HEAD对应的Checks页面为准。",
        "task_result": {
            "user_request": "生成通知。",
            "implementation": ["增加通知渲染。"],
            "not_implemented": ["不执行网络请求。"],
            "design_tradeoffs": ["使用离线证据模式测试。"],
            "business_rules_changed": "否。",
            "merge_recommendation": "由审核者决定。",
        },
        "known_issues": {
            "known": ["无。"],
            "deferred": ["无。"],
            "user_impact": "只影响审核通知。",
            "blocks_merge": "否。",
            "follow_up": ["复核通知。"],
        },
    }
    (review_dir / "REVIEW_CONTEXT.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    evidence = {
        "project_name": "synthetic-project",
        "repository_url": "https://github.com/example/example",
        "pr_url": "https://github.com/example/example/pull/7",
        "pr_number": 7,
        "pr_head": "2" * 40,
        "actions_status": actions_status,
        "actions_conclusion": actions_conclusion,
        "actions_run_id": "99887766",
        "actions_url": "https://github.com/example/example/actions/runs/99887766",
        "pytest_passed": 9,
        "pytest_failed": 0,
        "pytest_skipped": 2,
        "safety_scanned": 12,
        "safety_changed": 4,
        "safety_findings": 0,
        "pr_draft": True,
        "pr_merged": False,
        "master_modified": False,
        "release_created": False,
        "formal_tag_moved": False,
    }
    evidence_path = tmp_path / "notice-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return run(
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(finalizer),
        "-TaskId",
        task_id,
        "-CommitMessage",
        "test notice",
        "-PrTitle",
        "test notice",
        "-RenderCommanderNoticeOnly",
        "-CommanderNoticeEvidencePath",
        str(evidence_path),
        cwd=tmp_path,
        check=False,
    )


def test_commander_notice_uses_complete_actual_evidence(tmp_path: Path) -> None:
    completed = render_commander_notice(
        tmp_path,
        actions_status="completed",
        actions_conclusion="success",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    notice = completed.stdout
    assert "【可直接复制给总指挥审核】" in notice
    assert "项目：synthetic-project" in notice
    assert "任务：TASK-NOTICE-001｜固定总指挥通知" in notice
    assert "https://github.com/example/example/pull/7" in notice
    assert "PR编号：#7" in notice
    assert "2" * 40 in notice
    assert "task/TASK-NOTICE-001-review" in notice
    assert "docs/reviews/LATEST_REVIEW.md" in notice
    assert "docs/reviews/TASK-NOTICE-001/" in notice
    assert "成功；运行 99887766" in notice
    assert "https://github.com/example/example/actions/runs/99887766" in notice
    assert "9 passed，0 failed，2 skipped" in notice
    assert "12 个文件，4 个差异文件，0 个命中" in notice
    assert "- PR是否Draft：是" in notice
    assert "- PR是否已合并：否" in notice
    assert not re.search(r"<[^>]+>", notice)


def test_commander_notice_is_blocked_while_actions_are_running(
    tmp_path: Path,
) -> None:
    completed = render_commander_notice(
        tmp_path,
        actions_status="in_progress",
        actions_conclusion="",
    )

    assert completed.returncode != 0
    assert "【可直接复制给总指挥审核】" not in completed.stdout
    assert "GitHub Actions 尚未完成" in completed.stderr


def test_commander_notice_reports_failed_actions_as_failure(
    tmp_path: Path,
) -> None:
    completed = render_commander_notice(
        tmp_path,
        actions_status="completed",
        actions_conclusion="failure",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "GitHub Actions：\n失败（failure）；运行 99887766" in completed.stdout
    assert "GitHub Actions：\n成功" not in completed.stdout
