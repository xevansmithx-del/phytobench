from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


def _staging_module():
    script = Path(__file__).parents[1] / "scripts" / "stage_release_assets.py"
    spec = importlib.util.spec_from_file_location("stage_release_assets", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_tree(tmp_path, module):
    root = tmp_path / "source"
    for relative, _ in module.SOURCE_ASSETS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"synthetic bytes for {relative}\n", encoding="utf-8")
    manifest = "".join(
        f"{_sha256(root / relative)}  {relative}\n" for relative, _ in module.SOURCE_ASSETS
    )
    (root / "release" / "SHA256SUMS.txt").write_text(manifest, encoding="utf-8")
    return root


def test_release_staging_produces_a_self_verifying_flat_asset_set(tmp_path):
    module = _staging_module()
    root = _source_tree(tmp_path, module)
    destination = tmp_path / "published"

    module.stage_release_assets(root, destination)

    expected = {name for _, name in module.SOURCE_ASSETS} | {module.FLAT_MANIFEST}
    assert {path.name for path in destination.iterdir()} == expected
    assert module.verify_flat_manifest(destination) == []


def test_flat_release_manifest_detects_downloaded_asset_drift(tmp_path):
    module = _staging_module()
    root = _source_tree(tmp_path, module)
    destination = tmp_path / "published"
    module.stage_release_assets(root, destination)
    (destination / module.WHEEL).write_bytes(b"changed")

    assert "flat release asset digest differs" in module.verify_flat_manifest(destination)
