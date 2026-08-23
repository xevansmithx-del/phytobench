from __future__ import annotations

import json

from phytobench.cli import main


def _example(root, name):
    return root / "examples" / "empty" / name


def test_cli_audits_empty_contract_and_require_ready_refuses(capsys):
    root = __import__("pathlib").Path(__file__).parents[1]
    arguments = [
        "audit",
        "--sources",
        str(_example(root, "source_registry.json")),
        "--rows",
        str(_example(root, "benchmark_rows.json")),
        "--contract",
        str(_example(root, "freeze_contract.json")),
    ]
    assert main(arguments) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS_WITH_EMPIRICAL_BLOCKER"
    assert main(arguments + ["--require-ready"]) == 2


def test_cli_freeze_and_verify(capsys, tmp_path):
    root = __import__("pathlib").Path(__file__).parents[1]
    output = tmp_path / "bundle"
    arguments = [
        "freeze",
        "--sources",
        str(_example(root, "source_registry.json")),
        "--rows",
        str(_example(root, "benchmark_rows.json")),
        "--contract",
        str(_example(root, "freeze_contract.json")),
        "--output",
        str(output),
    ]
    assert main(arguments) == 0
    capsys.readouterr()
    assert main(["verify", str(output)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"


def test_cli_refuses_symlink_inputs(tmp_path, capsys):
    root = __import__("pathlib").Path(__file__).parents[1]
    target = _example(root, "source_registry.json")
    link = tmp_path / "sources.json"
    link.symlink_to(target)
    result = main(
        [
            "audit",
            "--sources",
            str(link),
            "--rows",
            str(_example(root, "benchmark_rows.json")),
            "--contract",
            str(_example(root, "freeze_contract.json")),
        ]
    )
    assert result == 2
    assert "non-symlink" in capsys.readouterr().err
