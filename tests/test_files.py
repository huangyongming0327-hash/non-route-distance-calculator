from __future__ import annotations

import zipfile

import pytest

from src.utils.files import assert_unchanged, fingerprint, reject_xlm_macro_sheets


def test_sample_fingerprint_is_expected(sample_path):
    result = fingerprint(sample_path)
    assert result.size == 828799
    assert result.sha256 == "52011587F8F12A87749087ABEA0ADCE2557874D1B268A55F348E86F8DFA7A951"


def test_assert_unchanged(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"A")
    before = fingerprint(path)
    assert_unchanged(before, path)
    path.write_bytes(b"B")
    with pytest.raises(RuntimeError):
        assert_unchanged(before, path)


def test_reject_non_ooxml(tmp_path):
    path = tmp_path / "old.xls"
    path.write_bytes(b"fake")
    with pytest.raises(ValueError):
        reject_xlm_macro_sheets(path)


def test_reject_xlm_relationship(tmp_path):
    path = tmp_path / "xlm.xlsx"
    rels = '<?xml version="1.0"?><Relationships><Relationship Type="http://schemas/test/xlMacrosheet"/></Relationships>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
    with pytest.raises(RuntimeError):
        reject_xlm_macro_sheets(path)
