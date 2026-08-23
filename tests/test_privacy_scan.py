from __future__ import annotations

import importlib.util
from pathlib import Path


def _scanner_module():
    script = Path(__file__).parents[1] / "scripts" / "privacy_scan.py"
    spec = importlib.util.spec_from_file_location("privacy_scan", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_privacy_scanner_accepts_safe_text(tmp_path):
    module = _scanner_module()
    (tmp_path / "README.md").write_text("synthetic metadata only\n", encoding="utf-8")
    (tmp_path / ".coverage").write_bytes(b"\x00generated coverage database")
    assert module.scan(tmp_path) == []


def test_privacy_scanner_rejects_secrets_paths_and_raw_payloads(tmp_path):
    module = _scanner_module()
    (tmp_path / "token.txt").write_text("gh" + "o_" + "A" * 24, encoding="utf-8")
    (tmp_path / "local.txt").write_text("/" + "Users/private/research/data", encoding="utf-8")
    (tmp_path / "sample.vcf").write_text("synthetic", encoding="utf-8")
    issues = module.scan(tmp_path)
    assert any("GitHub token" in issue for issue in issues)
    assert any("private absolute path" in issue for issue in issues)
    assert any("raw biological payload" in issue for issue in issues)
