#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path, PurePosixPath

from phytobench import __version__

ROOT = Path(__file__).resolve().parents[1]
VERSION = __version__
WHEEL = f"phytobench-{VERSION}-py3-none-any.whl"
SDIST = f"phytobench-{VERSION}.tar.gz"
FLAT_MANIFEST = "RELEASE_SHA256SUMS.txt"
SOURCE_ASSETS = (
    (f"dist/{WHEEL}", WHEEL),
    (f"dist/{SDIST}", SDIST),
    ("dist/SHA256SUMS.txt", "SHA256SUMS.txt"),
    ("release/AVO_RECEIPT.json", "AVO_RECEIPT.json"),
    ("release/CLAIM_BOUNDARY.json", "CLAIM_BOUNDARY.json"),
    ("uv.lock", "uv.lock"),
    ("validate_release.py", "validate_release.py"),
)


class StageError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        parsed = PurePosixPath(relative)
        if (
            separator != "  "
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not relative
            or parsed.is_absolute()
            or ".." in parsed.parts
            or relative in entries
        ):
            raise StageError("manifest is malformed or contains duplicate paths")
        entries[relative] = digest
    return entries


def verify_flat_manifest(directory: Path) -> list[str]:
    try:
        entries = _parse_manifest(directory / FLAT_MANIFEST)
    except (OSError, StageError, UnicodeError):
        return ["flat release manifest is unreadable"]
    expected = {destination for _, destination in SOURCE_ASSETS}
    issues: list[str] = []
    if set(entries) != expected:
        issues.append("flat release manifest inventory differs")
    for name, expected_digest in entries.items():
        asset = directory / name
        if asset.is_symlink() or not asset.is_file():
            issues.append("flat release asset is missing or unsafe")
        elif _sha256(asset) != expected_digest:
            issues.append("flat release asset digest differs")
    return issues


def stage_release_assets(root: Path, destination: Path) -> None:
    root = root.resolve()
    source_manifest = _parse_manifest(root / "release" / "SHA256SUMS.txt")
    expected_sources = {source for source, _ in SOURCE_ASSETS}
    if set(source_manifest) != expected_sources:
        raise StageError("committed release manifest inventory differs")
    for relative, expected_digest in source_manifest.items():
        source = root / relative
        if source.is_symlink() or not source.is_file() or _sha256(source) != expected_digest:
            raise StageError("committed release asset is missing, unsafe, or changed")

    if destination.exists():
        raise StageError("release staging destination already exists")
    destination.mkdir(parents=True)
    for source_name, destination_name in SOURCE_ASSETS:
        shutil.copyfile(root / source_name, destination / destination_name)
        if _sha256(destination / destination_name) != source_manifest[source_name]:
            raise StageError("staged release asset no longer matches the committed manifest")
    flat_manifest = "".join(
        f"{source_manifest[source]}  {name}\n" for source, name in SOURCE_ASSETS
    )
    (destination / FLAT_MANIFEST).write_text(flat_manifest, encoding="utf-8")
    if verify_flat_manifest(destination):
        raise StageError("staged release assets failed flat-manifest replay")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    try:
        stage_release_assets(ROOT, arguments.destination)
    except (OSError, StageError, UnicodeError, ValueError):
        print("FAIL release staging", file=sys.stderr)
        return 2
    print(f"PASS release staging: {len(SOURCE_ASSETS)} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
