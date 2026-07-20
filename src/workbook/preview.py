from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from src.domain.models import FieldMapping, ResultColumns, RowInput
from src.utils.files import reject_xlm_macro_sheets
from src.utils.text import normalized_text


RESULT_HEADERS = (
    "高德普通驾车公路距离（公里）",
    "距离查询状态",
    "距离查询说明",
)

HEADER_KEYWORDS = {
    "quote_type": ("报价类型", "报价"),
    "origin_city": ("始发城市", "发货城市", "始发仓", "发货地"),
    "origin_address": ("始发详细地址", "发货详细地址", "始发地址"),
    "destination_city": ("目的城市", "到达城市", "到达仓", "目的地"),
    "destination_address": ("目的详细地址", "到达详细地址", "目的地址"),
    "vehicle": ("车型", "车长"),
}


@dataclass(frozen=True)
class WorkbookInfo:
    path: str
    sheets: tuple[str, ...]
    selected_sheet: str
    header_row: int
    header_score: int
    max_row: int
    max_column: int
    actual_last_column: int
    descriptors: tuple[str, ...]
    recommended_mapping: FieldMapping
    result_columns: ResultColumns
    city_catalog: tuple[str, ...]
    preview_rows: tuple[tuple[Any, ...], ...]


def _score_header_row(ws: Any, row: int) -> int:
    score = 0
    for col in range(1, min(ws.max_column, 80) + 1):
        text = normalized_text(ws.cell(row, col).value, remove_all_space=True)
        for keywords in HEADER_KEYWORDS.values():
            if any(keyword in text for keyword in keywords):
                score += 3 if text in keywords else 1
    return score


def detect_header_row(ws: Any, limit: int = 20) -> tuple[int, int]:
    candidates = [(row, _score_header_row(ws, row)) for row in range(1, min(limit, ws.max_row) + 1)]
    row, score = max(candidates, key=lambda item: (item[1], -item[0]))
    if score <= 0:
        raise ValueError("前 20 行未检测到可信表头，请手动选择表头行。")
    return row, score


def _sample_values(ws: Any, header_row: int, col: int, limit: int = 3) -> list[str]:
    values: list[str] = []
    for row in range(header_row + 1, min(ws.max_row, header_row + 30) + 1):
        value = normalized_text(ws.cell(row, col).value)
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return values


def _descriptor(ws: Any, header_row: int, col: int) -> str:
    header = normalized_text(ws.cell(header_row, col).value) or "（空表头）"
    samples = " / ".join(_sample_values(ws, header_row, col)) or "（无样例）"
    if len(samples) > 60:
        samples = samples[:57] + "..."
    return f"{get_column_letter(col)}｜{header}｜{samples}"


def _address_score(samples: list[str]) -> int:
    markers = ("省", "市", "区", "县", "路", "街", "道", "号", "园", "仓", "镇")
    return sum(sum(marker in sample for marker in markers) for sample in samples)


def recommend_mapping(ws: Any, header_row: int) -> FieldMapping:
    headers = {col: normalized_text(ws.cell(header_row, col).value, remove_all_space=True) for col in range(1, ws.max_column + 1)}

    def best_header(field: str) -> int | None:
        keywords = HEADER_KEYWORDS[field]
        scored = []
        for col, text in headers.items():
            score = max((100 if text == keyword else 60 if keyword in text else 0) for keyword in keywords)
            if score:
                scored.append((score, -col, col))
        return max(scored)[2] if scored else None

    quote = best_header("quote_type")
    vehicle = best_header("vehicle")
    origin_city = best_header("origin_city")
    destination_city = best_header("destination_city")
    if not all((quote, origin_city, destination_city)):
        raise ValueError("无法完整推荐报价、始发或目的列，请在界面手动确认。")

    def adjacent_address(city_col: int) -> int:
        candidates = [col for col in (city_col + 1, city_col - 1) if 1 <= col <= ws.max_column]
        scored = []
        for col in candidates:
            samples = _sample_values(ws, header_row, col, limit=8)
            explicit = 50 if any(keyword in headers[col] for keyword in HEADER_KEYWORDS["origin_address"] + HEADER_KEYWORDS["destination_address"]) else 0
            scored.append((explicit + _address_score(samples), -abs(col - city_col), col))
        return max(scored)[2]

    origin_address = best_header("origin_address") or adjacent_address(origin_city)
    destination_address = best_header("destination_address") or adjacent_address(destination_city)
    return FieldMapping(quote, origin_city, origin_address, destination_city, destination_address, vehicle)


def actual_last_column(ws: Any) -> int:
    last = 0
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                last = max(last, cell.column)
    return last


def plan_result_columns(ws: Any, header_row: int) -> ResultColumns:
    expected = tuple(normalized_text(header, remove_all_space=True) for header in RESULT_HEADERS)
    for start in range(1, max(1, ws.max_column - 1)):
        actual = tuple(
            normalized_text(ws.cell(header_row, start + offset).value, remove_all_space=True)
            for offset in range(3)
        )
        if actual == expected:
            return ResultColumns(start, start + 1, start + 2)
    start = actual_last_column(ws) + 1
    return ResultColumns(start, start + 1, start + 2)


def inspect_workbook(path: str | Path, sheet_name: str | None = None, header_row: int | None = None) -> WorkbookInfo:
    reject_xlm_macro_sheets(path)
    book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        sheets = tuple(book.sheetnames)
        selected = sheet_name if sheet_name in sheets else sheets[0]
        ws = book[selected]
        detected_row, detected_score = detect_header_row(ws) if header_row is None else (header_row, _score_header_row(ws, header_row))
        mapping = recommend_mapping(ws, detected_row)
        descriptors = tuple(_descriptor(ws, detected_row, col) for col in range(1, ws.max_column + 1))
        result_columns = plan_result_columns(ws, detected_row)
        city_values: set[str] = {"北京", "上海", "天津", "重庆", "广州", "深圳", "杭州", "佛山", "贵阳", "无锡"}
        for col in (mapping.origin_city, mapping.destination_city):
            for row in range(detected_row + 1, ws.max_row + 1):
                value = normalized_text(ws.cell(row, col).value, remove_all_space=True)
                if value and len(value) <= 20:
                    city_values.add(value.removesuffix("市"))
        preview = tuple(tuple(ws.cell(row, col).value for col in range(1, min(ws.max_column, 19) + 1)) for row in range(detected_row, min(ws.max_row, detected_row + 10) + 1))
        return WorkbookInfo(
            str(Path(path).resolve()), sheets, selected, detected_row, detected_score,
            ws.max_row, ws.max_column, actual_last_column(ws), descriptors, mapping,
            result_columns, tuple(sorted(city_values)), preview,
        )
    finally:
        book.close()


def iter_row_inputs(selection: Any):
    book = load_workbook(selection.path, read_only=True, data_only=False, keep_links=False)
    try:
        ws = book[selection.sheet_name]
        fields = selection.fields
        for row in range(selection.header_row + 1, ws.max_row + 1):
            yield RowInput(
                row,
                ws.cell(row, fields.quote_type).value,
                ws.cell(row, fields.origin_city).value,
                ws.cell(row, fields.origin_address).value,
                ws.cell(row, fields.destination_city).value,
                ws.cell(row, fields.destination_address).value,
                ws.cell(row, fields.vehicle).value if fields.vehicle is not None else None,
            )
    finally:
        book.close()
