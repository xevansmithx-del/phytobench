#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

EXCLUDED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "temp_docs_and_tests",
}
FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "secrets.json",
}
GENERATED_FILE_NAMES = {".coverage", "coverage.xml"}
FORBIDDEN_SUFFIXES = {
    ".bam",
    ".bcf",
    ".cram",
    ".fa",
    ".fasta",
    ".fastq",
    ".fq",
    ".sam",
    ".vcf",
    ".vcf.gz",
    ".fastq.gz",
    ".fq.gz",
}
MAX_PUBLIC_FILE_BYTES = 2 * 1024 * 1024

SECRET_PATTERNS = {
    "GitHub token": re.compile("gh" + r"[opsu]_[A-Za-z0-9]{20,}"),
    "OpenAI-style token": re.compile("s" + r"k-[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile("AK" + r"IA[0-9A-Z]{16}"),
    "private key": re.compile("BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"),
}
LOCAL_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9.:])/(?:Users|home)/[^/\s]+/")


def _walk_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_DIRECTORIES for part in path.parts)
    ]


def scan(root: Path) -> list[str]:
    root = root.resolve()
    files = _walk_files(root)
    issues: list[str] = []
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        if path.name in GENERATED_FILE_NAMES:
            continue
        if path.is_symlink():
            issues.append(f"symlink is forbidden: {relative}")
            continue
        if not path.exists():
            continue
        if path.name in FORBIDDEN_NAMES:
            issues.append(f"credential-like filename is forbidden: {relative}")
        lower = relative.lower()
        if any(lower.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            issues.append(f"raw biological payload is forbidden: {relative}")
        size = path.stat().st_size
        if size > MAX_PUBLIC_FILE_BYTES:
            issues.append(f"public file exceeds {MAX_PUBLIC_FILE_BYTES} bytes: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(f"unexpected binary file: {relative}")
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                issues.append(f"{label} pattern found: {relative}")
        if LOCAL_PATH_PATTERN.search(text):
            issues.append(f"private absolute path found: {relative}")
    return issues


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    root = Path(arguments[0]) if arguments else Path.cwd()
    issues = scan(root)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 2
    files = _walk_files(root.resolve())
    print(f"PASS privacy scan: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
