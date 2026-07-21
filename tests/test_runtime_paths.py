from __future__ import annotations

import sys
from pathlib import Path

from src.runtime_paths import application_root, ensure_runtime_directories, resource_root


def test_source_application_root_is_project_root(project_root):
    assert application_root() == project_root
    assert resource_root() == project_root


def test_frozen_application_root_uses_executable_directory(monkeypatch, tmp_path):
    executable = tmp_path / "中文 路径" / "非线路运距计算工具.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    assert application_root() == executable.parent.resolve()
    assert resource_root() == (tmp_path / "bundle").resolve()


def test_runtime_directories_are_portable_and_local(tmp_path):
    root = tmp_path / "便携版 路径"
    directories = ensure_runtime_directories(root)
    assert set(directories) == {"config", "cache", "logs", "outputs", "temp"}
    assert all(path.is_dir() and path.parent == root for path in directories.values())
