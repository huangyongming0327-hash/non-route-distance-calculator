from __future__ import annotations

import os

import pytest

from src.domain.models import OfficeEngine
from src.office.backend import engine_installed


@pytest.mark.office
@pytest.mark.parametrize("engine", [OfficeEngine.EXCEL, OfficeEngine.WPS])
def test_office_engines_registered(engine):
    if os.environ.get("RUN_OFFICE_TESTS") != "1":
        pytest.skip("设置 RUN_OFFICE_TESTS=1 后执行真实 Office 端到端；常规单测不启动桌面应用。")
    assert engine_installed(engine)
