from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import islice
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from src.addressing.service import AddressBookService, TRUSTED_STATUSES
from src.domain.models import AddressConfirmationStatus, ConfirmedAddress
from src.utils.text import normalized_text


PENDING_HEADERS = (
    "地址ID",
    "原始城市",
    "原始详细地址",
    "高德标准地址",
    "定位层级",
    "修正查询地址",
    "是否确认",
    "确认备注",
)
HEADER_SCAN_LIMIT = 20


@dataclass(frozen=True)
class ImportSummary:
    success: int
    skipped: int
    failed: int
    errors: tuple[str, ...] = ()


def _exact_header_text(value: object) -> str:
    """只忽略单元格值两端空白，字段名本身不做模糊或同义匹配。"""
    return "" if value is None else str(value).strip()


def _summarize_scan_row(row_number: int, values: tuple[object, ...]) -> str:
    cells: list[str] = []
    nonempty_total = 0
    for column, value in enumerate(values, start=1):
        text = _exact_header_text(value).replace("\r", " ").replace("\n", " ")
        if not text:
            continue
        nonempty_total += 1
        if len(cells) >= 8:
            continue
        if len(text) > 40:
            text = text[:37] + "..."
        cells.append(f"{get_column_letter(column)}={text!r}")
    if not cells:
        return f"第 {row_number} 行：(空白)"
    suffix = f"；其他 {nonempty_total - len(cells)} 个非空单元格" if nonempty_total > len(cells) else ""
    return f"第 {row_number} 行：" + "，".join(cells) + suffix


def _detect_pending_header(
    sheet,
) -> tuple[int | None, dict[str, int], tuple[tuple[object, ...], ...], str]:
    scanned_rows = tuple(
        tuple(row) for row in islice(sheet.iter_rows(values_only=True), HEADER_SCAN_LIMIT)
    )
    required = set(PENDING_HEADERS)
    candidates: list[tuple[int, tuple[str, ...], tuple[str, ...]]] = []
    for row_number, values in enumerate(scanned_rows, start=1):
        positions: dict[str, int] = {}
        for column, value in enumerate(values, start=1):
            header = _exact_header_text(value)
            if header in required and header not in positions:
                positions[header] = column
        missing = tuple(header for header in PENDING_HEADERS if header not in positions)
        if not missing:
            return row_number, positions, scanned_rows, ""
        matched = tuple(header for header in PENDING_HEADERS if header in positions)
        if matched:
            candidates.append((row_number, matched, missing))

    summaries = [
        _summarize_scan_row(row_number, values)
        for row_number, values in enumerate(scanned_rows, start=1)
    ]
    if not summaries:
        summaries = ["(工作表为空)"]
    if candidates:
        row_number, matched, missing = max(candidates, key=lambda item: (len(item[1]), -item[0]))
        candidate = (
            f"可能的表头行：第 {row_number} 行（匹配 {len(matched)}/{len(PENDING_HEADERS)}；"
            f"缺少：{'、'.join(missing)}）"
        )
    else:
        candidate = "可能的表头行：未发现包含必需字段名称的候选行"
    diagnostic = (
        f"前 {HEADER_SCAN_LIMIT} 行中未找到同时包含全部必需字段的表头。\n"
        f"实际扫描 {len(scanned_rows)} 行内容摘要：\n"
        + "\n".join(summaries)
        + "\n"
        + candidate
    )
    return None, {}, scanned_rows, diagnostic


def export_pending_addresses(path: str | Path, addresses: list[ConfirmedAddress]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "待确认地址"
    sheet.append(PENDING_HEADERS)
    pending = [item for item in addresses if item.confirmation_status not in TRUSTED_STATUSES]
    for item in pending:
        sheet.append((
            item.address_id,
            item.original_city,
            item.original_address,
            item.formatted_address,
            item.level,
            item.query_address,
            "",
            item.confirmation_note,
        ))
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    widths = (22, 12, 42, 42, 12, 42, 12, 30)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:H{max(1, sheet.max_row)}"
    if sheet.max_row >= 2:
        validation = DataValidation(type="list", formula1='"是,否,地址无效,待进一步核实"')
        sheet.add_data_validation(validation)
        validation.add(f"G2:G{sheet.max_row}")
        for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    workbook.save(target)
    workbook.close()
    return target


def import_confirmation_results(
    path: str | Path,
    service: AddressBookService,
    *,
    confirmed_by: str = "Excel 导入",
) -> ImportSummary:
    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    errors: list[str] = []
    success = skipped = failed = 0
    try:
        sheet = workbook[workbook.sheetnames[0]]
        header_row, positions, _, diagnostic = _detect_pending_header(sheet)
        if header_row is None:
            return ImportSummary(0, 0, 1, (diagnostic,))

        def value_at(values: tuple[object, ...], header: str) -> object:
            index = positions[header] - 1
            return values[index] if index < len(values) else None

        seen: dict[str, tuple[str, str, str]] = {}
        rows = sheet.iter_rows(min_row=header_row + 1, values_only=True)
        for row_number, values in enumerate(rows, start=header_row + 1):
            values = tuple(values)
            address_id = normalized_text(value_at(values, "地址ID"))
            if not address_id:
                skipped += 1
                continue
            query = normalized_text(value_at(values, "修正查询地址"))
            decision = normalized_text(value_at(values, "是否确认"), remove_all_space=True)
            note = normalized_text(value_at(values, "确认备注"))
            signature = (query, decision, note)
            if address_id in seen:
                if seen[address_id] != signature:
                    failed += 1
                    errors.append(f"第 {row_number} 行：地址ID重复且内容冲突")
                else:
                    skipped += 1
                continue
            seen[address_id] = signature
            current = service.repository.get_address(address_id)
            if current is None:
                failed += 1
                errors.append(f"第 {row_number} 行：地址ID不存在")
                continue
            try:
                if decision in {"", "否"}:
                    if note != current.confirmation_note:
                        service.repository.put_address(replace(current, confirmation_note=note))
                        success += 1
                    else:
                        skipped += 1
                    continue
                if decision == "地址无效":
                    service.mark_invalid(address_id, note=note)
                    success += 1
                    continue
                if decision == "待进一步核实":
                    service.repository.put_address(replace(
                        current,
                        confirmation_status=AddressConfirmationStatus.NEEDS_FURTHER_REVIEW.value,
                        confirmation_note=note,
                    ))
                    success += 1
                    continue
                if decision != "是":
                    failed += 1
                    errors.append(f"第 {row_number} 行：是否确认值无效“{decision}”")
                    continue
                if query and query != current.query_address:
                    service.save_query_address(address_id, query)
                    if service.geocoder is None:
                        failed += 1
                        errors.append(f"第 {row_number} 行：修正地址已保存，但缺少地理编码客户端，尚未确认")
                        continue
                    service.reparse(address_id, confirm_corrected=True)
                    reparsed = service.repository.get_address(address_id)
                    if reparsed and note:
                        service.repository.put_address(replace(
                            reparsed, confirmed_by=confirmed_by, confirmation_note=note
                        ))
                else:
                    service.confirm(address_id, confirmed_by=confirmed_by, note=note)
                success += 1
            except Exception as exc:
                failed += 1
                errors.append(f"第 {row_number} 行：{exc}")
    finally:
        workbook.close()
    return ImportSummary(success, skipped, failed, tuple(errors))
