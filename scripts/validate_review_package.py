from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


REQUIRED_FILES = (
    "REVIEW_INDEX.md",
    "TASK_RESULT.md",
    "TEST_REPORT.md",
    "CHANGED_FILES.md",
    "SECURITY_REPORT.md",
    "KNOWN_ISSUES.md",
    "AUDIT_INPUT.md",
)
PLACEHOLDER_PATTERNS = (
    re.compile(r"\{\{[^{}]+\}\}"),
    re.compile(r"TODO\s*待补充", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"待补充"),
)
COMMIT_PATTERN = re.compile(r"\b[0-9a-f]{40}\b", re.IGNORECASE)
PR_PATTERN = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+")


def repository_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return Path(completed.stdout.strip())


def current_branch() -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证任务审核材料是否完整且可交付。")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--branch", default="")
    parser.add_argument(
        "--allow-pending-pr",
        action="store_true",
        help="首次提交前允许 PR 地址尚未生成；CI 和最终交付不得使用。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repository_root()
    branch = args.branch or current_branch()
    review_dir = root / "docs" / "reviews" / args.task_id
    latest = root / "docs" / "reviews" / "LATEST_REVIEW.md"
    errors: list[str] = []
    contents: dict[str, str] = {}

    if not review_dir.is_dir():
        errors.append(f"审核目录不存在：docs/reviews/{args.task_id}/")
    else:
        for name in REQUIRED_FILES:
            path = review_dir / name
            if not path.is_file():
                errors.append(f"缺少审核文件：{path.relative_to(root).as_posix()}")
                continue
            text = path.read_text(encoding="utf-8").strip()
            contents[name] = text
            if not text:
                errors.append(f"审核文件为空：{path.relative_to(root).as_posix()}")
                continue
            if args.task_id not in text:
                errors.append(f"TaskId 不一致：{path.relative_to(root).as_posix()}")
            if branch and branch not in text:
                errors.append(f"分支不一致：{path.relative_to(root).as_posix()}")
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern.search(text):
                    errors.append(f"存在模板占位：{path.relative_to(root).as_posix()}")
                    break

    if not latest.is_file():
        errors.append("固定审核入口不存在：docs/reviews/LATEST_REVIEW.md")
        latest_text = ""
    else:
        latest_text = latest.read_text(encoding="utf-8").strip()
        expected_entry = f"{args.task_id}/REVIEW_INDEX.md"
        if args.task_id not in latest_text:
            errors.append("LATEST_REVIEW.md 的 TaskId 不一致。")
        if branch and branch not in latest_text:
            errors.append("LATEST_REVIEW.md 的分支不一致。")
        if expected_entry not in latest_text:
            errors.append("LATEST_REVIEW.md 未链接到正确的任务审核首页。")
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(latest_text):
                errors.append("LATEST_REVIEW.md 仍含模板占位。")
                break

    commit_evidence = "\n".join(
        (
            contents.get("REVIEW_INDEX.md", ""),
            contents.get("AUDIT_INPUT.md", ""),
            latest_text,
        )
    )
    if not COMMIT_PATTERN.search(commit_evidence):
        errors.append("审核材料中没有非空的 40 位 Commit Hash。")

    test_report = contents.get("TEST_REPORT.md", "")
    if not re.search(r"通过[：:]\s*\d+", test_report):
        errors.append("TEST_REPORT.md 缺少通过数量。")
    if not re.search(r"失败[：:]\s*\d+", test_report):
        errors.append("TEST_REPORT.md 缺少失败数量。")
    if "真实 API 调用次数" not in test_report:
        errors.append("TEST_REPORT.md 缺少真实 API 调用次数。")

    security_report = contents.get("SECURITY_REPORT.md", "")
    if not re.search(r"是否允许推送[：:]\s*(?:是|否)", security_report):
        errors.append("SECURITY_REPORT.md 缺少明确的推送结论。")
    if "0 命中" not in security_report and "命中" not in security_report:
        errors.append("SECURITY_REPORT.md 缺少安全扫描结果。")

    known_issues = contents.get("KNOWN_ISSUES.md", "")
    if len(known_issues) < 80:
        errors.append("KNOWN_ISSUES.md 内容不足。")

    if not args.allow_pending_pr:
        pr_evidence = "\n".join(
            (
                contents.get("REVIEW_INDEX.md", ""),
                contents.get("AUDIT_INPUT.md", ""),
                latest_text,
            )
        )
        if len(PR_PATTERN.findall(pr_evidence)) < 3:
            errors.append("PR 创建后必须在 REVIEW_INDEX、AUDIT_INPUT 和 LATEST_REVIEW 中回写地址。")

    if errors:
        print("审核材料检查失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"审核材料检查通过：{args.task_id}，分支 {branch}，"
        f"{len(REQUIRED_FILES)} 个任务文件完整。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
