"""Repository hygiene guard for Folio.

Scans git-tracked files to prevent accidental commits of API keys, cloud
credentials, local machine paths, private IP addresses, or external project
research artifacts.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai_or_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("huggingface_token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("azure_conn_string", re.compile(r"DefaultEndpointsProtocol[=]https;AccountName[=]")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("local_home_path", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")),
    (
        "private_ipv4",
        re.compile(
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        ),
    ),
)

FORBIDDEN_EXTENSIONS: tuple[str, ...] = (
    ".pt",
    ".pth",
    ".safetensors",
    ".ckpt",
    ".npz",
    ".npy",
    ".parquet",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
)

FORBIDDEN_FILENAME_SUBSTRINGS: tuple[str, ...] = (
    "funnel_results.json",
    "optimize_results.json",
    "loop_compact_results.json",
    "inequity_results.json",
    "valuation_results.json",
    "substack_paste_ready.html",
)

MAX_TRACKED_FILE_BYTES = 2 * 1024 * 1024  # 2 MB ceiling for framework repo files


def audit_repo(repo_root: Path) -> list[str]:
    """Scan tracked files for secrets, local paths, IPs, or research data leaks."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    findings: list[str] = []
    for raw_rel in proc.stdout.decode("utf-8", errors="replace").split("\0"):
        if not raw_rel:
            continue
        file_path = repo_root / raw_rel
        if not file_path.is_file():
            continue

        lower_rel = raw_rel.lower()
        for ext in FORBIDDEN_EXTENSIONS:
            if lower_rel.endswith(ext):
                findings.append(f"{raw_rel}: blocked binary/credential extension '{ext}'")
        for sub in FORBIDDEN_FILENAME_SUBSTRINGS:
            if sub in lower_rel:
                findings.append(f"{raw_rel}: blocked external project artifact '{sub}'")

        size = file_path.stat().st_size
        if size > MAX_TRACKED_FILE_BYTES:
            findings.append(
                f"{raw_rel}: file size {size:,} bytes exceeds {MAX_TRACKED_FILE_BYTES:,} byte limit"
            )

        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                findings.append(f"{raw_rel}:{line_no}: blocked pattern '{label}'")
    return findings
