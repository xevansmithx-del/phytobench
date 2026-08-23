from __future__ import annotations

import pytest

from phytobench.canonical import DuplicateKeyError, canonical_bytes, load_json, sha256_receipt


def test_canonical_receipt_is_order_independent():
    assert sha256_receipt({"b": 2, "a": 1}) == sha256_receipt({"a": 1, "b": 2})


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(DuplicateKeyError):
        load_json(path)


def test_nonfinite_json_is_not_emitted():
    with pytest.raises(ValueError):
        canonical_bytes(float("nan"))


def test_nonfinite_json_is_not_loaded(tmp_path):
    path = tmp_path / "nan.json"
    path.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        load_json(path)
