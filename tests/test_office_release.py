from __future__ import annotations

import hashlib
import os

import pytest

from src.application.processor import DRIVING_NOTICE
from src.domain.models import FieldMapping, OfficeEngine, ResultColumns, RowOutcome
from src.office.backend import OfficeBackend, engine_installed


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _macro_sources(path) -> dict[str, str]:
    from oletools.olevba import VBA_Parser

    parser = VBA_Parser(str(path))
    try:
        return {
            filename: source.replace("\r\n", "\n")
            for _container, _stream, filename, source in parser.extract_macros()
        }
    finally:
        parser.close()


@pytest.mark.office
@pytest.mark.parametrize("engine", [OfficeEngine.EXCEL, OfficeEngine.WPS])
def test_xlsm_macro_fixture_is_saved_without_running_vba(
    engine, project_root, tmp_path
):
    if os.environ.get("RUN_OFFICE_TESTS") != "1":
        pytest.skip("设置 RUN_OFFICE_TESTS=1 后执行真实 Office 发布测试。")
    if not engine_installed(engine):
        pytest.skip(f"本机未安装 {engine.value}")
    source = project_root / "tests" / "fixtures" / "office_spike_macro_fixture.xlsm"
    output = tmp_path / f"{engine.value}_macro_output.xlsm"
    source_hash = _sha256(source)
    source_macros = _macro_sources(source)
    backend = OfficeBackend(engine, tmp_path / "runtime", tmp_path / "logs")
    write_response = backend.write_checkpoint(
        source_path=source,
        output_path=output,
        first_save=True,
        sheet_name="MacroFixture",
        header_row=1,
        field_mapping=FieldMapping(1, 2, 3, 4, 5, 6),
        result_columns=ResultColumns(27, 28, 29),
        outcomes=[
            RowOutcome(
                2,
                12.3,
                "缓存复用—普通驾车参考",
                DRIVING_NOTICE,
                "release-office-test",
                cache_reused=True,
            )
        ],
        last_data_row=2,
    )
    verification = backend.verify(
        path=output,
        sheet_name="MacroFixture",
        header_row=1,
        result_columns=ResultColumns(27, 28, 29),
        target_rows=[2],
        last_data_row=2,
    )
    assert _sha256(source) == source_hash
    assert output.exists()
    assert _macro_sources(output) == source_macros
    assert write_response["session"]["security_settings"]["AutomationSecurity"]["readback"] == 3
    assert write_response["session"]["security_settings"]["EnableEvents"]["readback"] is False
    assert write_response["session"]["own_pid_residual"] is False
    assert write_response["session"]["preexisting_processes_unchanged"] is True
    if engine == OfficeEngine.WPS:
        assert write_response["session"]["preexisting_visible_windows_unchanged"] is True
    assert verification["result"]["file_format"] == 52
    assert verification["result"]["status_count"] == 1
    assert verification["result"]["distance_count"] == 1
