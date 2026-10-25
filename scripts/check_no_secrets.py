#!/usr/bin/env python3
"""Refuse a commit (or a push) that would publish a secret. This repository is public.

Scans file contents for an API-key shape, a database URI, a private IPv4 address, a home-directory
path, and a filled-in ZAI_API_KEY; and refuses any file that must never be tracked (.env, data/,
*.local.md, lock files), whatever .gitignore says.

    python3 scripts/check_no_secrets.py              # every tracked file (run before a push)
    python3 scripts/check_no_secrets.py --staged     # the pre-commit hook
    python3 scripts/check_no_secrets.py --install    # write .git/hooks/pre-commit
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PATTERNS = {
    "Z.ai API key": re.compile(r"\b[0-9a-f]{32}\.[A-Za-z0-9]{16}\b"),
    "sk- style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._-]{24,}"),
    "database URI": re.compile("mongodb" + r"(\+srv)?://"),
    "private IPv4 address": re.compile(r"\b(10\.\d{1,3}|172\.(1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b"),
    "home-directory path": re.compile("/" + r"home/[A-Za-z0-9_.-]+/"),
    "filled-in ZAI_API_KEY": re.compile(r"ZAI_API_KEY\s*=\s*['\"]?(?!\s*$)(?!<)[^\s'\"#]{8,}", re.MULTILINE),
}
NEVER_TRACKED = [re.compile(p) for p in (r"(^|/)\.env$", r"(^|/)\.env\.(?!example$)", r"^data/(?!\.gitkeep$)",
                                         r"\.local\.md$", r"\.lock$", r"\.tmp$")]


def git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def staged_text(path: str) -> str:
    return subprocess.run(["git", "show", f":{path}"], cwd=REPO, capture_output=True, check=True).stdout.decode("utf-8", "replace")


def scan(name: str, text: str) -> list[str]:
    found = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                found.append(f"{name}:{line_no}: {label}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    if args.install:
        hook = REPO / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text('#!/bin/sh\nexec python3 scripts/check_no_secrets.py --staged\n', encoding="utf-8")
        hook.chmod(0o755)
        print(f"installed {hook.relative_to(REPO)}")
        return 0

    files = git("diff", "--cached", "--name-only", "--diff-filter=ACMR") if args.staged else git("ls-files")
    problems = []
    for name in files:
        if any(p.search(name) for p in NEVER_TRACKED):
            problems.append(f"{name}: must never be committed")
            continue
        try:
            text = staged_text(name) if args.staged else (REPO / name).read_text(encoding="utf-8", errors="replace")
        except (OSError, subprocess.CalledProcessError):
            continue
        problems += scan(name, text)
    if problems:
        print("REFUSING -- this would publish something it must not:")
        for p in problems:
            print(f"  {p}")
        print("Fix the file (or unstage it). Never bypass with --no-verify on this public repository.")
        return 1
    print(f"no secrets in {len(files)} {'staged' if args.staged else 'tracked'} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
