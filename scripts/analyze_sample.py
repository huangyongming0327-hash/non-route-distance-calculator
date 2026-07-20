"""Read-only structural and business-data audit for the fixed sample workbook."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, range_boundaries


INVISIBLE_EDGE = " \t\r\n\u00a0\u1680\u180e\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u200c\u200d\u2028\u2029\u202f\u205f\u2060\u3000\ufeff"
SPACE_RE = re.compile(r"[\s\u00a0\u3000\u200b-\u200d\u2060\ufeff]+")
MULTI_SEP_RE = re.compile(r"[\r\n;；/／、|｜]+")
CITY_SUFFIX_RE = re.compile(r"([\u4e00-\u9fff]{2,8}(?:市|自治州|地区|盟))")


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def scalar_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        try:
            dec = Decimal(str(value))
            return format(dec.normalize(), "f")
        except InvalidOperation:
            return str(value)
    return str(value)


def edge_normalize(value: Any) -> str:
    return scalar_text(value).strip(INVISIBLE_EDGE)


def key_normalize(value: Any) -> str:
    return SPACE_RE.sub("", unicodedata.normalize("NFKC", edge_normalize(value))).lower()


def vehicle_normalize(value: Any) -> str:
    raw = unicodedata.normalize("NFKC", edge_normalize(value)).lower()
    raw = SPACE_RE.sub("", raw)
    if not raw:
        return "(空白)"
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        try:
            return format(Decimal(raw).normalize(), "f")
        except InvalidOperation:
            return raw
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(米|m)", raw)
    if match:
        try:
            return f"{format(Decimal(match.group(1)).normalize(), 'f')}米"
        except InvalidOperation:
            return raw
    return raw


def vehicle_class(value: Any) -> str:
    norm = vehicle_normalize(value)
    numeric = norm[:-1] if norm.endswith("米") else norm
    mapping = {
        "4.2": "轻型货车",
        "6.8": "中型货车",
        "7.6": "中型货车",
        "9.6": "重型货车",
        "13": "重型货车",
    }
    return mapping.get(numeric, f"未识别:{norm}")


def compact_ranges(numbers: Iterable[int]) -> list[str]:
    values = sorted(set(numbers))
    if not values:
        return []
    output: list[str] = []
    start = previous = values[0]
    for current in values[1:]:
        if current == previous + 1:
            previous = current
            continue
        output.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = current
    output.append(str(start) if start == previous else f"{start}-{previous}")
    return output


def actual_value_bounds(ws: Any) -> dict[str, Any]:
    rows: list[int] = []
    cols: list[int] = []
    nonempty = 0
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                rows.append(cell.row)
                cols.append(cell.column)
                nonempty += 1
    if not rows:
        return {"range": None, "nonempty_cells": 0}
    return {
        "range": f"{get_column_letter(min(cols))}{min(rows)}:{get_column_letter(max(cols))}{max(rows)}",
        "min_row": min(rows),
        "max_row": max(rows),
        "min_col": min(cols),
        "max_col": max(cols),
        "nonempty_cells": nonempty,
    }


def header_score(ws: Any, row_num: int) -> int:
    keywords = (
        "报价类型", "始发仓", "发货地", "发货城市", "始发详细地址", "发货详细地址",
        "到达仓", "目的地", "目的城市", "目的详细地址", "车型",
    )
    texts = [edge_normalize(ws.cell(row_num, c).value) for c in range(1, ws.max_column + 1)]
    return sum(3 for text in texts if text in keywords) + sum(
        1 for text in texts for keyword in keywords if text and keyword in text and text != keyword
    )


def formula_details(ws: Any) -> dict[str, Any]:
    formulas: list[dict[str, Any]] = []
    functions: Counter[str] = Counter()
    for row in ws.iter_rows():
        for cell in row:
            value = cell.value
            if cell.data_type == "f" or (isinstance(value, str) and value.startswith("=")):
                formula = str(value)
                formulas.append({"cell": cell.coordinate, "formula": formula})
                match = re.match(r"=_xlfn\.([A-Z0-9_.]+)|=([A-Z0-9_.]+)", formula, flags=re.I)
                if match:
                    functions[(match.group(1) or match.group(2)).upper()] += 1
    return {"count": len(formulas), "functions": dict(functions), "examples": formulas[:20]}


def data_validation_details(ws: Any) -> dict[str, Any]:
    validations = list(ws.data_validations.dataValidation) if ws.data_validations else []
    return {
        "rule_count": len(validations),
        "ranges": [str(item.sqref) for item in validations],
        "types": dict(Counter(item.type or "unknown" for item in validations)),
    }


def conditional_format_details(ws: Any) -> dict[str, Any]:
    ranges: list[dict[str, Any]] = []
    total_rules = 0
    for item in ws.conditional_formatting:
        rules = list(ws.conditional_formatting[item])
        total_rules += len(rules)
        ranges.append({
            "range": str(item.sqref),
            "rule_count": len(rules),
            "types": [rule.type for rule in rules],
        })
    return {"range_count": len(ranges), "rule_count": total_rules, "ranges": ranges}


def sheet_details(ws: Any) -> dict[str, Any]:
    hidden_rows = [idx for idx, dim in ws.row_dimensions.items() if dim.hidden]
    hidden_cols: list[str] = []
    for key, dim in ws.column_dimensions.items():
        if dim.hidden:
            hidden_cols.append(key)
    header_scores = {row: header_score(ws, row) for row in range(1, min(ws.max_row, 20) + 1)}
    header_row = max(header_scores, key=lambda row: (header_scores[row], -row)) if header_scores else None
    if header_row and header_scores[header_row] == 0:
        header_row = None
    first_data_row = None
    if header_row:
        for row in range(header_row + 1, ws.max_row + 1):
            if any(ws.cell(row, col).value is not None for col in range(1, ws.max_column + 1)):
                first_data_row = row
                break
    return {
        "title": ws.title,
        "state": ws.sheet_state,
        "openpyxl_dimension": ws.calculate_dimension(),
        "max_row": ws.max_row,
        "max_column": ws.max_column,
        "actual_values": actual_value_bounds(ws),
        "detected_header_row": header_row,
        "header_score": header_scores.get(header_row) if header_row else 0,
        "first_data_row": first_data_row,
        "headers": {get_column_letter(c): ws.cell(header_row, c).value for c in range(1, ws.max_column + 1)} if header_row else {},
        "merged_ranges": [str(item) for item in ws.merged_cells.ranges],
        "freeze_panes": str(ws.freeze_panes) if ws.freeze_panes else None,
        "auto_filter": ws.auto_filter.ref,
        "filter_columns": len(ws.auto_filter.filterColumn),
        "hidden_rows": {"count": len(hidden_rows), "ranges": compact_ranges(hidden_rows)},
        "hidden_columns": {"count": len(hidden_cols), "columns": hidden_cols},
        "conditional_formatting": conditional_format_details(ws),
        "data_validations": data_validation_details(ws),
        "tables": [{"name": table.name, "display_name": table.displayName, "ref": table.ref} for table in ws.tables.values()],
        "images_openpyxl": len(ws._images),
        "charts_openpyxl": len(ws._charts),
        "formula_details": formula_details(ws),
        "comments": sum(1 for row in ws.iter_rows() for cell in row if cell.comment is not None),
        "hyperlinks": sum(1 for row in ws.iter_rows() for cell in row if cell.hyperlink is not None),
        "print_area": str(ws.print_area) if ws.print_area else None,
        "print_titles": str(ws.print_titles) if ws.print_titles else None,
    }


def xml_package_details(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        lower_names = {name.lower() for name in names}

        def parts(prefix: str, suffix: str | None = None) -> list[str]:
            result = [name for name in names if name.lower().startswith(prefix.lower())]
            if suffix:
                result = [name for name in result if name.lower().endswith(suffix.lower())]
            return sorted(result)

        external_targets: list[str] = []
        for name in names:
            if not name.lower().endswith(".rels"):
                continue
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                continue
            for rel in root:
                if rel.attrib.get("TargetMode") == "External":
                    external_targets.append(rel.attrib.get("Target", ""))

        drawing_counts: Counter[str] = Counter()
        ns = {"xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"}
        for name in parts("xl/drawings/", ".xml"):
            if "/_rels/" in name:
                continue
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                continue
            for tag in ("pic", "sp", "graphicFrame", "cxnSp", "twoCellAnchor", "oneCellAnchor", "absoluteAnchor"):
                drawing_counts[tag] += len(root.findall(f".//xdr:{tag}", ns))

        content_types = archive.read("[Content_Types].xml").decode("utf-8", errors="replace")
        compatibility_parts = {
            "drawings": parts("xl/drawings/", ".xml"),
            "media": [name for name in parts("xl/media/") if not name.endswith("/")],
            "charts": parts("xl/charts/", ".xml"),
            "cell_images": [name for name in names if "cellimage" in name.lower()],
            "vml_drawings": [name for name in names if name.lower().endswith(".vml")],
            "comments": parts("xl/comments", ".xml"),
            "threaded_comments": parts("xl/threadedcomments/", ".xml"),
            "tables": parts("xl/tables/", ".xml"),
            "pivot_tables": parts("xl/pivottables/", ".xml"),
            "pivot_cache": parts("xl/pivotcache/", ".xml"),
            "slicers": [name for name in names if "slicer" in name.lower()],
            "active_x": parts("xl/activex/"),
            "controls": [name for name in names if "control" in name.lower()],
            "embeddings": parts("xl/embeddings/"),
            "external_links": parts("xl/externallinks/"),
            "connections": [name for name in names if name.lower() == "xl/connections.xml"],
            "custom_xml": parts("customxml/"),
            "rich_data": parts("xl/richdata/"),
            "person_metadata": parts("xl/persons/"),
            "calc_chain": [name for name in names if name.lower() == "xl/calcchain.xml"],
        }
        return {
            "part_count": len(names),
            "content_type_has_macro": "macroEnabled" in content_types,
            "has_vba_project": "xl/vbaproject.bin" in lower_names,
            "has_vba_signature": any("vbasignature" in name for name in lower_names),
            "external_relationship_count": len(external_targets),
            "external_targets": external_targets,
            "drawing_element_counts": dict(drawing_counts),
            "compatibility_parts": compatibility_parts,
        }


def detect_known_cities(values: Iterable[Any]) -> list[str]:
    cities: set[str] = set()
    for value in values:
        text = edge_normalize(value)
        if len(text) >= 2:
            cities.add(text)
            if text.endswith("市") and len(text) > 2:
                cities.add(text[:-1])
    return sorted(cities, key=lambda item: (-len(item), item))


def city_conflict_examples(rows: list[dict[str, Any]], known_cities: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in rows:
        for side, city_key, address_key in (
            ("发货", "origin_city", "origin_address"),
            ("目的", "destination_city", "destination_address"),
        ):
            city = edge_normalize(item[city_key])
            address = edge_normalize(item[address_key])
            if not city or not address:
                continue
            city_forms = {city, city[:-1] if city.endswith("市") else city}
            if any(form and form in address for form in city_forms):
                # A prefecture/county hierarchy can legitimately contain other city names.
                continue
            other_hits = [candidate for candidate in known_cities if candidate not in city_forms and candidate in address]
            suffix_hits = [match.group(1) for match in CITY_SUFFIX_RE.finditer(address)]
            suffix_conflicts = [hit for hit in suffix_hits if all(form not in hit and hit not in form for form in city_forms)]
            hits = sorted(set(other_hits + suffix_conflicts), key=lambda text: (-len(text), text))
            if hits:
                results.append({
                    "row": item["row"], "side": side, "city": city, "address": address,
                    "other_city_hits": hits[:5], "basis": "文本启发式，需地理编码复核",
                })
    return results[:20]


def multi_destination_examples(rows: list[dict[str, Any]], known_cities: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in rows:
        city = edge_normalize(item["destination_city"])
        address = edge_normalize(item["destination_address"])
        segments = [segment.strip() for segment in MULTI_SEP_RE.split(address) if segment.strip()]
        segment_hits: list[tuple[str, list[str]]] = []
        address_distinct: set[str] = set()
        for segment in segments:
            hits = [candidate for candidate in known_cities if candidate in segment]
            if hits:
                canonical = {hit[:-1] if hit.endswith("市") else hit for hit in hits}
                address_distinct.update(canonical)
                segment_hits.append((segment, hits[:5]))
        city_hits = {
            candidate[:-1] if candidate.endswith("市") else candidate
            for candidate in known_cities
            if candidate != city and len(candidate) >= 2 and candidate in city
        }
        separated_address_cities = len(address_distinct) >= 2 and len(segment_hits) >= 2
        combined_city_field = len(city_hits) >= 2
        if separated_address_cities or combined_city_field:
            results.append({
                "row": item["row"], "destination_city": city, "destination_address": address,
                "city_field_hits": sorted(city_hits), "address_city_hits": sorted(address_distinct),
                "segments": segment_hits[:5],
                "basis": "保守文本启发式，需人工复核",
            })
    return results[:20]


def business_details(ws: Any, header_row: int = 1) -> dict[str, Any]:
    # The sample has grouped headers: E/G identify city columns; adjacent F/H headers are blank.
    # These positions are validated against the workbook's own headers and content before use.
    expected_headers = {5: "始发仓", 7: "到达仓", 11: "车型", 13: "报价类型"}
    header_validation = {
        get_column_letter(col): {"expected": expected, "actual": ws.cell(header_row, col).value, "matches": edge_normalize(ws.cell(header_row, col).value) == expected}
        for col, expected in expected_headers.items()
    }
    if not all(item["matches"] for item in header_validation.values()):
        raise ValueError(f"Sample header layout changed: {header_validation}")

    data_rows: list[dict[str, Any]] = []
    first_data_row = None
    for row in range(header_row + 1, ws.max_row + 1):
        values = [ws.cell(row, col).value for col in range(1, 17)]
        if not any(value is not None for value in values):
            continue
        if first_data_row is None:
            first_data_row = row
        data_rows.append({
            "row": row,
            "origin_city": ws.cell(row, 5).value,
            "origin_address": ws.cell(row, 6).value,
            "destination_city": ws.cell(row, 7).value,
            "destination_address": ws.cell(row, 8).value,
            "vehicle": ws.cell(row, 11).value,
            "quote_type": ws.cell(row, 13).value,
        })

    selected = [item for item in data_rows if edge_normalize(item["quote_type"]) == "非线路报价"]
    quote_counts = Counter(edge_normalize(item["quote_type"]) or "(空白)" for item in data_rows)
    vehicle_counts = Counter(vehicle_normalize(item["vehicle"]) for item in selected)

    def route_key(item: dict[str, Any]) -> tuple[str, ...]:
        return tuple(key_normalize(item[key]) for key in ("origin_city", "origin_address", "destination_city", "destination_address"))

    route_groups: defaultdict[tuple[str, ...], list[int]] = defaultdict(list)
    for item in selected:
        route_groups[route_key(item)].append(item["row"])
    duplicate_groups = [rows for rows in route_groups.values() if len(rows) > 1]

    query_raw = {
        (*route_key(item), vehicle_normalize(item["vehicle"]))
        for item in selected
    }
    query_class = {
        (*route_key(item), vehicle_class(item["vehicle"]))
        for item in selected
    }

    known_cities = detect_known_cities(
        [item["origin_city"] for item in data_rows] + [item["destination_city"] for item in data_rows]
    )
    multi_candidates = multi_destination_examples(selected, known_cities)
    multi_rows = {item["row"] for item in multi_candidates}
    conflict_candidates = [
        item for item in city_conflict_examples(selected, known_cities)
        if item["row"] not in multi_rows
    ]
    return {
        "header_validation": header_validation,
        "field_mapping": {
            "origin_city": "E",
            "origin_address": "F（表头为空；由“始发仓”相邻列和内容识别）",
            "destination_city": "G",
            "destination_address": "H（表头为空；由“到达仓”相邻列和内容识别）",
            "vehicle": "K",
            "quote_type": "M",
        },
        "first_data_row": first_data_row,
        "last_data_row": max((item["row"] for item in data_rows), default=None),
        "nonempty_data_rows": len(data_rows),
        "quote_type_counts": dict(quote_counts),
        "non_route_quote_count": len(selected),
        "vehicle_distribution_selected": dict(vehicle_counts),
        "origin_address_blank_count": sum(not edge_normalize(item["origin_address"]) for item in selected),
        "destination_address_blank_count": sum(not edge_normalize(item["destination_address"]) for item in selected),
        "origin_city_blank_count": sum(not edge_normalize(item["origin_city"]) for item in selected),
        "destination_city_blank_count": sum(not edge_normalize(item["destination_city"]) for item in selected),
        "unique_origin_destination_count": len(route_groups),
        "duplicate_route_group_count": len(duplicate_groups),
        "duplicate_route_extra_row_count": sum(len(rows) - 1 for rows in duplicate_groups),
        "duplicate_route_row_count": sum(len(rows) for rows in duplicate_groups),
        "duplicate_route_examples": duplicate_groups[:20],
        "query_combination_count_by_raw_vehicle": len(query_raw),
        "query_combination_count_by_mapped_vehicle_class": len(query_class),
        "vehicle_class_distribution": dict(Counter(vehicle_class(item["vehicle"]) for item in selected)),
        "city_conflict_candidates": conflict_candidates,
        "multi_destination_candidates": multi_candidates,
        "heuristic_known_cities_count": len(known_cities),
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: analyze_sample.py <sample.xlsx> <output.json>")
    sample_path = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()

    before_hash = hashlib.sha256(sample_path.read_bytes()).hexdigest().upper()
    workbook = load_workbook(sample_path, read_only=False, data_only=False, keep_links=True)
    report = {
        "analysis_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "file": {
            "name": sample_path.name,
            "path": str(sample_path),
            "size_bytes": sample_path.stat().st_size,
            "sha256_before": before_hash,
            "suffix": sample_path.suffix.lower(),
        },
        "workbook": {
            "sheet_count": len(workbook.worksheets),
            "active_sheet": workbook.active.title,
            "sheets": [sheet_details(ws) for ws in workbook.worksheets],
            "defined_names": [name.name for name in workbook.defined_names.values()],
            "external_links_openpyxl": len(workbook._external_links),
            "calculation": {
                "calc_mode": workbook.calculation.calcMode,
                "full_calc_on_load": workbook.calculation.fullCalcOnLoad,
                "force_full_calc": workbook.calculation.forceFullCalc,
            },
        },
        "business": business_details(workbook.active),
        "ooxml": xml_package_details(sample_path),
    }
    workbook.close()
    report["file"]["sha256_after"] = hashlib.sha256(sample_path.read_bytes()).hexdigest().upper()
    report["file"]["unchanged"] = report["file"]["sha256_before"] == report["file"]["sha256_after"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
