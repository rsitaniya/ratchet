"""Checksum-pinned downloader for the real MaDI-Bench Companies data (Stage 1).

The benchmark data is licensed CC BY-NC-ND 4.0, so it is NEVER committed to this
repo (NoDerivatives forbids redistributing a reshaped copy). Reproducibility comes
from this downloader: it fetches the pinned files from the official MaDI-Bench
repository and verifies each against its git blob SHA-1. Downloaded files land in
the gitignored `data/` directory.

This is optional — the loop, its tests, and CI all run on synthetic fixtures. Use
this only to run the loop against the real benchmark. See DATA_LICENSE_NOTICE.md.

Usage:
    python engagements/madi_onboarding/download_data.py
"""
from __future__ import annotations

import hashlib
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "wbsg-uni-mannheim/MaDI-Bench"
REF = "main"
BASE = "use cases/companies/base/input"
DEST = Path(__file__).resolve().parent / "data"

# (repo_path, git_blob_sha1, dest_filename). Stage 1 = schema matching + values.
MANIFEST = [
    (f"{BASE}/data/dbpedia.csv", "1fdf8788c41c0cc9a09f2c3e300b554285b0f6d9", "dbpedia.csv"),
    (f"{BASE}/data/forbes.csv", "5196a702c750f57ce1b7d3dd4eced01fcdd653ee", "forbes.csv"),
    (f"{BASE}/data/fullcontact.csv", "4b9b198b66be29b90f65e367bdb3c9b08371f97f", "fullcontact.csv"),
    (f"{BASE}/schemamatching/target_schema.json", "c4665a362aee80e211783821b8d740be3096ff6c", "target_schema.json"),
    (f"{BASE}/schemamatching/sm_mapping_gold.json", "81437e01a54185d0d2c9def0a4b454cf584e90ee", "sm_mapping_gold.json"),
]


def git_blob_sha1(content: bytes) -> str:
    """Git's object id for a blob: sha1(b'blob <len>\\0' + content)."""
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def _raw_url(repo_path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{REF}/{urllib.parse.quote(repo_path)}"


def download(dest: Path = DEST, manifest=MANIFEST) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for repo_path, expected_sha, filename in manifest:
        url = _raw_url(repo_path)
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (https only)
            content = resp.read()
        actual = git_blob_sha1(content)
        if actual != expected_sha:
            raise SystemExit(f"checksum mismatch for {filename}: expected {expected_sha}, got {actual}")
        out = dest / filename
        out.write_bytes(content)
        written.append(out)
        print(f"  ✓ {filename}  ({len(content)} bytes, blob {actual[:10]})")
    return written


def main() -> None:
    print("MaDI-Bench is licensed CC BY-NC-ND 4.0. Data is downloaded here for")
    print("non-commercial use and is never committed. See DATA_LICENSE_NOTICE.md.\n")
    print(f"Downloading {len(MANIFEST)} files to {DEST} ...")
    download()
    print("\nDone. These files are gitignored and must not be committed.")


if __name__ == "__main__":
    sys.exit(main())
