from __future__ import annotations

from src.application.processor import BusinessProcessor, MOCK_WARNING
from src.cache.sqlite_cache import CacheRepository
from src.domain.models import RowInput, TaskMode, WorkbookSelection
from src.utils.files import fingerprint
from src.workbook.preview import inspect_workbook, iter_row_inputs


def _sample_process(sample_path, tmp_path, mode=TaskMode.MOCK):
    info = inspect_workbook(sample_path)
    selection = WorkbookSelection(str(sample_path), info.selected_sheet, info.header_row, info.recommended_mapping)
    cache = CacheRepository(tmp_path / f"{mode.value}.db")
    cache.create_task("task", fingerprint(sample_path).sha256, {}, mode.value)
    outcomes = BusinessProcessor(cache).process(
        iter_row_inputs(selection), task_id="task", mode=mode, city_catalog=info.city_catalog, force_all=True
    )
    return info, cache, outcomes


def test_sample_business_acceptance(sample_path, tmp_path):
    _, cache, outcomes = _sample_process(sample_path, tmp_path)
    try:
        assert len(outcomes) == 74
        assert sum(item.distance_km is not None for item in outcomes) == 73
        by_row = {item.excel_row: item for item in outcomes}
        assert by_row[248].status == "多目的地待确认"
        assert by_row[248].distance_km is None
        assert [row for row, item in by_row.items() if item.status == "模拟测试—地址冲突待确认"] == [39, 78, 272]
        assert all(MOCK_WARNING in item.explanation for item in outcomes)
        assert cache.counts()["route_cache"] == 28
        assert sum(item.cache_reused for item in outcomes) == 45
    finally:
        cache.close()


def test_local_validation_does_not_populate_mock_cache(sample_path, tmp_path):
    _, cache, outcomes = _sample_process(sample_path, tmp_path, TaskMode.LOCAL_VALIDATION)
    try:
        assert all(item.distance_km is None for item in outcomes)
        assert cache.counts()["geocode_cache"] == 0
        assert cache.counts()["route_cache"] == 0
        assert any(item.status == "本地校验通过" for item in outcomes)
    finally:
        cache.close()


def test_blank_address_prevents_route(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    try:
        result = BusinessProcessor(cache).process_row(
            RowInput(2, "非线路报价", "广州", "", "深圳", "B路", 4.2), TaskMode.MOCK, ["广州", "深圳"]
        )
        assert result.status == "地址为空"
        assert result.distance_km is None
        assert cache.counts()["route_cache"] == 0
    finally:
        cache.close()


def test_unknown_vehicle_does_not_affect_route(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    try:
        result = BusinessProcessor(cache).process_row(
            RowInput(2, "非线路报价", "广州", "A路", "深圳", "B路", "4.2吨"), TaskMode.MOCK, ["广州", "深圳"]
        )
        assert result.status == "模拟测试"
        assert result.distance_km is not None
        assert "4.2吨" not in result.explanation
        assert cache.counts()["route_cache"] == 1
    finally:
        cache.close()


def test_empty_vehicle_does_not_affect_route(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    try:
        result = BusinessProcessor(cache).process_row(
            RowInput(2, "非线路报价", "广州", "A路", "深圳", "B路", None),
            TaskMode.MOCK,
            ["广州", "深圳"],
        )
        assert result.distance_km is not None
        assert result.status == "模拟测试"
    finally:
        cache.close()


def test_non_target_rows_are_not_processed(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    cache.create_task("task", "SHA", {}, "mock")
    try:
        rows = [
            RowInput(2, "线路报价", "广州", "A路", "深圳", "B路", 4.2),
            RowInput(3, "非线路报价", "广州", "A路", "深圳", "B路", 4.2),
        ]
        outcomes = BusinessProcessor(cache).process(
            rows, task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"]
        )
        assert [item.excel_row for item in outcomes] == [3]
    finally:
        cache.close()


def test_route_cache_reused_across_different_excel_rows(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    cache.create_task("task", "SHA", {}, "mock")
    try:
        rows = [
            RowInput(2, "非线路报价", "广州", "A路", "深圳", "B路", 4.2),
            RowInput(99, "非线路报价", "广州", "A路", "深圳", "B路", "未知车型"),
        ]
        outcomes = BusinessProcessor(cache).process(
            rows, task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"], force_all=True
        )
        assert outcomes[0].cache_reused is False
        assert outcomes[1].cache_reused is True
        assert outcomes[0].distance_km == outcomes[1].distance_km
    finally:
        cache.close()


def test_incremental_mode_reuses_unchanged_row_result(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    cache.create_task("task", "SHA", {}, "mock")
    rows = [RowInput(2, "非线路报价", "广州", "A路", "深圳", "B路", 4.2)]
    try:
        first = BusinessProcessor(cache).process(
            rows, task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"], force_all=True
        )

        class FailingGeocoder:
            mode = "mock"
            cache_contract = "mock-api-v1"

            def cache_key_for(self, cleaned, city):
                from src.amap.mock_clients import MockGeocoder

                return MockGeocoder().cache_key_for(cleaned, city)

            def geocode(self, *_):
                raise AssertionError("未变化行不应再次调用模拟地理编码")

        second = BusinessProcessor(cache, geocoder=FailingGeocoder()).process(
            rows, task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"], force_all=False
        )
        assert second[0].input_digest == first[0].input_digest
        assert second[0].distance_km == first[0].distance_km
        assert second[0].status == first[0].status
        assert second[0].explanation == first[0].explanation
    finally:
        cache.close()


def test_changed_input_is_reprocessed(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    cache.create_task("task", "SHA", {}, "mock")
    try:
        first_row = RowInput(2, "非线路报价", "广州", "A路", "深圳", "B路", 4.2)
        changed_row = RowInput(2, "非线路报价", "广州", "A路已变更", "深圳", "B路", 4.2)
        processor = BusinessProcessor(cache)
        first = processor.process(
            [first_row], task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"], force_all=True
        )[0]
        changed = processor.process(
            [changed_row], task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"], force_all=False
        )[0]
        assert changed.input_digest != first.input_digest
        assert changed.audit["origin_geocode_key"] != first.audit["origin_geocode_key"]
    finally:
        cache.close()


def test_resume_checkpoint_starts_after_saved_watermark(tmp_path):
    cache = CacheRepository(tmp_path / "cache.db")
    cache.create_task("task", "SHA", {}, "mock")
    rows = [
        RowInput(row, "非线路报价", "广州", f"A路{row}", "深圳", "B路", 4.2)
        for row in range(2, 8)
    ]
    try:
        processor = BusinessProcessor(cache)
        processor.process(
            rows[:4], task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"], force_all=True
        )
        checkpoints = []
        processor.process(
            rows, task_id="task", mode=TaskMode.MOCK, city_catalog=["广州", "深圳"], force_all=False,
            resume_after=4, checkpoint_batch=2,
            checkpoint=lambda outcomes, forced: checkpoints.append((len(outcomes), forced)),
        )
        assert checkpoints == [(6, False)]
    finally:
        cache.close()
