from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class FileFingerprint:
    path: str
    size: int
    mtime_ns: int
    sha256: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fingerprint(path: str | Path) -> FileFingerprint:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    return FileFingerprint(str(resolved), stat.st_size, stat.st_mtime_ns, sha256_file(resolved))


def assert_unchanged(before: FileFingerprint, path: str | Path) -> None:
    after = fingerprint(path)
    if before != after:
        raise RuntimeError(f"输入文件在处理期间发生变化，任务已停止：{after.path}")


def reject_xlm_macro_sheets(path: str | Path) -> None:
    candidate = Path(path)
    if candidate.suffix.lower() not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        raise ValueError("阶段 3B 原型仅支持 OOXML 工作簿（.xlsx/.xlsm）。")
    with zipfile.ZipFile(candidate) as archive:
        relationship_names = [name for name in archive.namelist() if name.lower().endswith(".rels")]
        for name in relationship_names:
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                continue
            for relation in root:
                rel_type = relation.attrib.get("Type", "").lower()
                if "xlmacrosheet" in rel_type or rel_type.endswith("/macrosheet"):
                    raise RuntimeError("检测到 Excel 4.0/XLM 宏工作表；阶段 3B 为安全起见拒绝自动打开。")


def is_within(path: str | Path, parent: str | Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def atomic_promote(partial: str | Path, final: str | Path) -> None:
    partial_path = Path(partial).resolve()
    final_path = Path(final).resolve()
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(partial_path, final_path)

