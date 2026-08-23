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
    assert "SECRET_GITHUB_TOKEN" in issues
    assert "PRIVATE_ABSOLUTE_PATH" in issues
    assert "RAW_BIOLOGICAL_PAYLOAD" in issues


def test_privacy_scanner_cli_never_logs_tainted_paths_or_matches(tmp_path, capsys):
    module = _scanner_module()
    secret = "gh" + "o_" + "B" * 24
    sensitive_name = "private-subject-path.txt"
    (tmp_path / sensitive_name).write_text(secret, encoding="utf-8")

    assert module.main([str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert output == "FAIL privacy scan: forbidden public-release material detected\n"
    assert sensitive_name not in output
    assert secret not in output


def test_privacy_scanner_cli_suppresses_filesystem_exception_details(tmp_path, capsys, monkeypatch):
    module = _scanner_module()
    sensitive_path = "/" + "Users/private-subject/controlled-study"

    def fail_scan(_root):
        raise OSError(f"cannot read {sensitive_path}")

    monkeypatch.setattr(module, "scan", fail_scan)
    assert module.main([str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert output == "FAIL privacy scan: unable to complete safe scan\n"
    assert sensitive_path not in output
