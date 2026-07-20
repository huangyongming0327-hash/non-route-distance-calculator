from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def sample_path(project_root: Path) -> Path:
    path = project_root / "samples" / "input" / "副本26年6月干线账单 2.1-对账2.0-物流商(2).xlsx"
    assert path.exists()
    return path
