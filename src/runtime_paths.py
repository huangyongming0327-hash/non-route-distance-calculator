from __future__ import annotations

import sys
from pathlib import Path


RUNTIME_DIRECTORY_NAMES = ("config", "cache", "logs", "outputs", "temp")


def application_root() -> Path:
    """Return the writable application root in source and frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    """Return the read-only root containing bundled resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return application_root()


def ensure_runtime_directories(root: str | Path) -> dict[str, Path]:
    base = Path(root).resolve()
    directories = {name: base / name for name in RUNTIME_DIRECTORY_NAMES}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    return directories
