#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from phytobench import __version__
from phytobench.audit import audit_documents
from phytobench.canonical import file_sha256, load_json
from phytobench.freeze import freeze_bundle, verify_bundle

ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0a3"
WHEEL = f"phytobench-{VERSION}-py3-none-any.whl"
SDIST = f"phytobench-{VERSION}.tar.gz"
SOURCE_DATE_EPOCH = "1787443200"


class ValidationError(RuntimeError):
    pass


class Checks:
    def __init__(self) -> None:
        self.count = 0

    def require(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            raise ValidationError(message)


def _run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    environment: dict[str, str] | None = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if environment:
        merged.update(environment)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=merged,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != expected:
        raise ValidationError(
            f"command returned {result.returncode}, expected {expected}: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _safe_archive_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def _audit_wheel(path: Path, checks: Checks) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        checks.require(len(names) == len(set(names)), "wheel contains duplicate paths")
        checks.require(all(_safe_archive_name(name) for name in names), "wheel path is unsafe")
        checks.require(
            "phytobench/schema/source_registry.schema.json" in names,
            "wheel is missing packaged source schema",
        )
        checks.require(
            "phytobench/schema/benchmark_rows.schema.json" in names,
            "wheel is missing packaged row schema",
        )
        checks.require(
            "phytobench/schema/freeze_contract.schema.json" in names,
            "wheel is missing packaged contract schema",
        )
        records = [name for name in names if name.endswith(".dist-info/RECORD")]
        checks.require(len(records) == 1, "wheel must contain exactly one RECORD")
        rows = list(csv.reader(archive.read(records[0]).decode("utf-8").splitlines()))
        checks.require(len(rows) == len(names), "wheel RECORD inventory is incomplete")
        record_by_name = {row[0]: row for row in rows}
        checks.require(set(record_by_name) == set(names), "wheel RECORD path set differs")
        for name in names:
            digest_field, size_field = record_by_name[name][1:]
            if name == records[0]:
                checks.require(
                    digest_field == "" and size_field == "",
                    "wheel RECORD must leave its own digest and size empty",
                )
                continue
            data = archive.read(name)
            import base64

            encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            checks.require(digest_field == f"sha256={encoded}", f"wheel hash mismatch: {name}")
            checks.require(size_field == str(len(data)), f"wheel size mismatch: {name}")


def _audit_sdist(path: Path, checks: Checks) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        checks.require(len(names) == len(set(names)), "sdist contains duplicate paths")
        checks.require(all(_safe_archive_name(name) for name in names), "sdist path is unsafe")
        checks.require(
            all(not member.issym() and not member.islnk() for member in members),
            "sdist contains a link",
        )
        required = {
            f"phytobench-{VERSION}/uv.lock",
            f"phytobench-{VERSION}/validate_release.py",
            f"phytobench-{VERSION}/registry/LOCKED_SOURCE_REGISTRY.json",
            f"phytobench-{VERSION}/registry/LOCKED_BENCHMARK_ROWS.json",
            f"phytobench-{VERSION}/registry/LOCKED_FREEZE_CONTRACT.json",
        }
        checks.require(required <= set(names), "sdist is missing replay assets")


def _normalize_sdist(path: Path) -> None:
    epoch = int(SOURCE_DATE_EPOCH)
    entries: list[tuple[str, bool, bytes]] = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if not _safe_archive_name(member.name) or member.issym() or member.islnk():
                raise ValidationError(f"cannot normalize unsafe sdist member: {member.name}")
            if member.isdir():
                entries.append((member.name.rstrip("/") + "/", True, b""))
            elif member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValidationError(f"cannot read sdist member: {member.name}")
                entries.append((member.name, False, extracted.read()))
            else:
                raise ValidationError(f"unsupported sdist member type: {member.name}")
    temporary = path.with_name(f".{path.name}.normalized")
    with (
        temporary.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as output,
    ):
        for name, is_directory, data in sorted(entries):
            info = tarfile.TarInfo(name)
            info.mtime = epoch
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.pax_headers = {}
            if is_directory:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.size = 0
                output.addfile(info)
            else:
                info.mode = 0o644
                info.size = len(data)
                output.addfile(info, io.BytesIO(data))
    os.replace(temporary, path)


def _locked_documents() -> tuple[dict, dict, dict]:
    return (
        load_json(ROOT / "registry" / "LOCKED_SOURCE_REGISTRY.json"),
        load_json(ROOT / "registry" / "LOCKED_BENCHMARK_ROWS.json"),
        load_json(ROOT / "registry" / "LOCKED_FREEZE_CONTRACT.json"),
    )


def _build_twice(temporary: Path, checks: Checks) -> tuple[Path, Path]:
    first = temporary / "dist-one"
    second = temporary / "dist-two"
    environment = {"SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH, "PYTHONHASHSEED": "0"}
    for destination in (first, second):
        _run(
            [
                "uv",
                "run",
                "--frozen",
                "--no-sync",
                "python",
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(destination),
            ],
            environment=environment,
        )
        _normalize_sdist(destination / SDIST)
    first_wheel, second_wheel = first / WHEEL, second / WHEEL
    first_sdist, second_sdist = first / SDIST, second / SDIST
    checks.require(
        first_wheel.read_bytes() == second_wheel.read_bytes(), "wheel is not reproducible"
    )
    checks.require(
        first_sdist.read_bytes() == second_sdist.read_bytes(), "sdist is not reproducible"
    )
    _run(
        [
            "uv",
            "run",
            "--frozen",
            "--no-sync",
            "python",
            "-m",
            "twine",
            "check",
            str(first_wheel),
            str(first_sdist),
        ]
    )
    return first_wheel, first_sdist


def _installed_replay(
    wheel: Path, sdist: Path, temporary: Path, checks: Checks, python_version: str
) -> None:
    environment = temporary / f"wheel-{python_version}"
    requirements = temporary / "artifact-runtime.txt"
    if not requirements.exists():
        _run(
            [
                "uv",
                "export",
                "--frozen",
                "--extra",
                "dev",
                "--no-emit-project",
                "--output-file",
                str(requirements),
            ]
        )
    _run(["uv", "venv", str(environment), "--python", python_version])
    python = environment / "bin" / "python"
    executable = environment / "bin" / "phytobench"
    _run(
        [
            "uv",
            "pip",
            "sync",
            "--python",
            str(python),
            "--require-hashes",
            str(requirements),
        ]
    )
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            str(wheel),
        ]
    )
    arbitrary = temporary / f"cwd-{python_version}"
    arbitrary.mkdir()
    result = _run([str(executable), "--version"], cwd=arbitrary)
    checks.require(
        result.stdout.strip() == VERSION, f"installed version mismatch on {python_version}"
    )
    sources, rows, contract = _locked_documents()
    inputs = temporary / f"inputs-{python_version}"
    inputs.mkdir()
    for name, value in (
        ("sources.json", sources),
        ("rows.json", rows),
        ("contract.json", contract),
    ):
        (inputs / name).write_text(json.dumps(value), encoding="utf-8")
    result = _run(
        [
            str(executable),
            "audit",
            "--sources",
            str(inputs / "sources.json"),
            "--rows",
            str(inputs / "rows.json"),
            "--contract",
            str(inputs / "contract.json"),
        ],
        cwd=arbitrary,
    )
    payload = json.loads(result.stdout)
    checks.require(payload["empirical_n"] == 0, "installed wheel changed empirical N")
    checks.require(payload["evaluation_ready"] is False, "installed wheel opened readiness gate")
    with tarfile.open(sdist, "r:gz") as archive:
        archive.extractall(temporary / f"sdist-{python_version}", filter="data")
    sdist_root = temporary / f"sdist-{python_version}" / f"phytobench-{VERSION}"
    _run([str(python), "-I", "-m", "pytest", "-q", str(sdist_root / "tests")], cwd=arbitrary)


def _publish_dist(wheel: Path, sdist: Path) -> tuple[str, str, str]:
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    expected = {WHEEL, SDIST, "SHA256SUMS.txt"}
    unexpected = {path.name for path in destination.iterdir()} - expected
    if unexpected:
        raise ValidationError(
            f"refusing to replace dist with unexpected files: {sorted(unexpected)}"
        )
    shutil.copy2(wheel, destination / WHEEL)
    shutil.copy2(sdist, destination / SDIST)
    wheel_hash = file_sha256(destination / WHEEL)
    sdist_hash = file_sha256(destination / SDIST)
    manifest = f"{wheel_hash}  {WHEEL}\n{sdist_hash}  {SDIST}\n"
    (destination / "SHA256SUMS.txt").write_text(manifest, encoding="utf-8")
    return wheel_hash, sdist_hash, file_sha256(destination / "SHA256SUMS.txt")


def _load_release_manifest() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in (ROOT / "release" / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if (
            separator != "  "
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not _safe_archive_name(relative)
            or relative in entries
        ):
            raise ValidationError("release manifest is malformed or contains duplicate paths")
        entries[relative] = digest
    return entries


def _verify_release_receipts(
    wheel_hash: str,
    sdist_hash: str,
    dist_manifest_hash: str,
    test_count: int,
    checks: Checks,
) -> None:
    avo = load_json(ROOT / "release" / "AVO_RECEIPT.json")
    claim = load_json(ROOT / "release" / "CLAIM_BOUNDARY.json")
    checks.require(avo["schema_version"] == "avo-supervisor-receipt-v1", "AVO schema changed")
    checks.require(avo["version"] == VERSION, "AVO version is not release-bound")
    checks.require(
        avo["status"] == "SOFTWARE_ONLY_PASS_WITH_EMPIRICAL_BLOCKER", "AVO status changed"
    )
    checks.require(avo["software_release_gate"] == "PASS", "AVO software gate is not PASS")
    checks.require(avo["unit_and_adversarial_tests"] == test_count, "AVO test count drifted")
    checks.require(avo["wheel_sha256"] == wheel_hash, "AVO wheel hash drifted")
    checks.require(avo["sdist_sha256"] == sdist_hash, "AVO sdist hash drifted")
    checks.require(
        avo["dist_manifest_sha256"] == dist_manifest_hash, "AVO dist manifest hash drifted"
    )
    checks.require(avo["locked_causal_rows"] == 0, "AVO causal row count changed")
    checks.require(avo["locked_causal_independent_n"] == 0, "AVO causal N changed")
    checks.require(avo["locked_null_rows"] == 0, "AVO null row count changed")
    checks.require(avo["locked_null_independent_n"] == 0, "AVO null N changed")
    checks.require(avo["empirical_n"] == 0, "AVO empirical N changed")
    checks.require(avo["benchmark_ready"] is False, "AVO opened benchmark readiness")
    checks.require(avo["breakthrough_validated"] is False, "AVO claims a breakthrough")
    checks.require(avo["execution_authorized"] is False, "AVO grants execution authority")

    checks.require(
        claim["schema_version"] == "phytobench-claim-boundary-v1",
        "claim-boundary schema changed",
    )
    checks.require(claim["version"] == VERSION, "claim boundary is not release-bound")
    checks.require(claim["locked_causal_rows"] == 0, "claim boundary causal rows changed")
    checks.require(claim["locked_null_rows"] == 0, "claim boundary null rows changed")
    checks.require(claim["empirical_n"] == 0, "claim boundary empirical N changed")
    checks.require(claim["benchmark_ready"] is False, "claim boundary opened readiness")
    checks.require(claim["breakthrough_validated"] is False, "claim boundary claims a breakthrough")
    checks.require(
        claim["causal_discovery_validated"] is False,
        "claim boundary claims causal discovery",
    )
    checks.require(claim["execution_authorized"] is False, "claim boundary grants authority")

    release_manifest = _load_release_manifest()
    expected_paths = {
        f"dist/{WHEEL}",
        f"dist/{SDIST}",
        "dist/SHA256SUMS.txt",
        "release/AVO_RECEIPT.json",
        "release/CLAIM_BOUNDARY.json",
        "uv.lock",
        "validate_release.py",
    }
    checks.require(set(release_manifest) == expected_paths, "release manifest inventory drifted")
    checks.require(
        all(file_sha256(ROOT / path) == digest for path, digest in release_manifest.items()),
        "release manifest hash verification failed",
    )
    checks.require(
        avo["validator_checks"] == checks.count + 1,
        f"AVO validator count drifted; expected {checks.count + 1}",
    )


def validate(full: bool) -> tuple[int, int, str, str, str]:
    checks = Checks()
    checks.require(__version__ == VERSION, "imported version mismatch")
    sources, rows, contract = _locked_documents()
    report = audit_documents(sources, rows, contract)
    checks.require(report.structurally_valid, "locked empty documents are structurally invalid")
    checks.require(not report.evaluation_ready, "empty benchmark cannot be evaluation-ready")
    checks.require(report.status == "PASS_WITH_EMPIRICAL_BLOCKER", "empty status changed")
    checks.require(report.empirical_n == 0, "empirical N must remain zero")
    checks.require(report.causal_rows == 0, "locked causal rows must remain zero")
    checks.require(report.null_rows == 0, "locked null rows must remain zero")

    pytest = _run(["uv", "run", "--frozen", "--no-sync", "pytest", "-q"])
    final_line = pytest.stdout.strip().splitlines()[-1]
    test_count = int(final_line.split()[0])
    checks.require(test_count >= 1, "pytest did not report tests")
    _run(["uv", "run", "--frozen", "--no-sync", "ruff", "check", "."])
    _run(["uv", "run", "--frozen", "--no-sync", "ruff", "format", "--check", "."])
    _run(["uv", "run", "--frozen", "--no-sync", "python", "scripts/privacy_scan.py", "."])
    _run(["uv", "lock", "--check", "--offline"])

    with tempfile.TemporaryDirectory(prefix="phytobench-validate-") as directory:
        temporary = Path(directory)
        bundle = temporary / "empty-bundle"
        freeze_bundle(sources, rows, contract, bundle)
        checks.require(verify_bundle(bundle) == [], "empty freeze does not replay")
        receipt = load_json(bundle / "FREEZE_RECEIPT.json")
        checks.require(receipt["breakthrough_validated"] is False, "freeze claims breakthrough")
        checks.require(receipt["empirical_n"] == 0, "freeze empirical N changed")

        if full:
            wheel, sdist = _build_twice(temporary, checks)
            _audit_wheel(wheel, checks)
            _audit_sdist(sdist, checks)
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(temporary / "wheel-tree")
            with tarfile.open(sdist, "r:gz") as archive:
                archive.extractall(temporary / "sdist-tree", filter="data")
            _run(
                [
                    "uv",
                    "run",
                    "--frozen",
                    "--no-sync",
                    "python",
                    "scripts/privacy_scan.py",
                    str(temporary / "wheel-tree"),
                ]
            )
            _run(
                [
                    "uv",
                    "run",
                    "--frozen",
                    "--no-sync",
                    "python",
                    "scripts/privacy_scan.py",
                    str(temporary / "sdist-tree"),
                ]
            )
            for version in ("3.10", "3.11", "3.12", "3.13"):
                _installed_replay(wheel, sdist, temporary, checks, version)
            wheel_hash, sdist_hash, manifest_hash = _publish_dist(wheel, sdist)
            _verify_release_receipts(wheel_hash, sdist_hash, manifest_hash, test_count, checks)
            staged_release = temporary / "flat-release-assets"
            _run(
                [
                    "uv",
                    "run",
                    "--frozen",
                    "--no-sync",
                    "python",
                    "scripts/stage_release_assets.py",
                    str(staged_release),
                ]
            )
            _run(
                ["sha256sum", "--check", "RELEASE_SHA256SUMS.txt"],
                cwd=staged_release,
            )
        else:
            wheel_hash = sdist_hash = manifest_hash = "not-built"
    return checks.count, test_count, wheel_hash, sdist_hash, manifest_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    arguments = parser.parse_args()
    try:
        checks, tests, wheel_hash, sdist_hash, manifest_hash = validate(arguments.full)
    except (OSError, ValidationError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    print(
        f"PASS: {checks} checks; full_replay={arguments.full}; tests={tests}; "
        "locked_causal_rows=0; locked_null_rows=0; empirical_n=0; "
        "breakthrough_validated=false; "
        f"wheel_sha256={wheel_hash}; sdist_sha256={sdist_hash}; "
        f"dist_manifest_sha256={manifest_hash}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
