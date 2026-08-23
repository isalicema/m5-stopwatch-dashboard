#!/usr/bin/env python3
"""Export the reviewed public subset into a dedicated GitHub worktree.

The development checkout intentionally contains device journals and design
iterations. This exporter copies only an explicit allowlist and removes only
already-tracked public files that fall outside that allowlist. It never touches
the target's .git directory or untracked files.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


SOURCE = Path(__file__).resolve().parent.parent
EXPECTED_ORIGIN = "https://github.com/isalicema/m5-stopwatch-dashboard.git"
ROOT_FILES = {
    ".gitignore",
    "LICENSE",
    "README.md",
    "scripts/check_ready.py",
    "scripts/export_public.py",
    "design/stopwatch-ui-preview.png",
    "design/stopwatch-ui-preview.svg",
}
PUBLIC_TREES = (
    "m5-dashboard/",
    "m5-dashboard-home/",
    "design/assets/",
)


def git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, encoding="utf-8"
    ).strip()


def is_public(path: str) -> bool:
    return path in ROOT_FILES or path.startswith(PUBLIC_TREES)


def tracked_files(root: Path) -> set[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    return {
        item.decode("utf-8")
        for item in raw.split(b"\0")
        if item
    }


def validate_target(target: Path, allow_dirty: bool) -> None:
    if target.resolve() == SOURCE.resolve():
        raise SystemExit("Refusing to export over the development checkout")
    if not (target / ".git").is_dir():
        raise SystemExit(f"Target is not a Git worktree: {target}")
    origin = git_output(target, "remote", "get-url", "origin")
    if origin.rstrip("/") != EXPECTED_ORIGIN.rstrip("/"):
        raise SystemExit(f"Unexpected public origin: {origin}")
    if not allow_dirty and git_output(target, "status", "--porcelain"):
        raise SystemExit(
            "Public target has uncommitted changes; review them or rerun with --allow-dirty"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy the reviewed M5 StopWatch public subset"
    )
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="continue after intentionally reviewing existing target changes",
    )
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    validate_target(target, args.allow_dirty)

    source_tracked = tracked_files(SOURCE)
    # The exporter can publish its own first uncommitted revision safely.
    source_tracked.add("scripts/export_public.py")
    manifest = {path for path in source_tracked if is_public(path)}

    removed = []
    for relative in sorted(tracked_files(target) - manifest):
        destination = target / relative
        if destination.is_file() or destination.is_symlink():
            destination.unlink()
            removed.append(relative)

    copied = []
    for relative in sorted(manifest):
        source = SOURCE / relative
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f"Public source is missing or unsafe: {relative}")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative)

    print(f"Public export ready: {target}")
    print(f"Copied {len(copied)} allowlisted files; removed {len(removed)} old tracked files")
    for relative in removed:
        print(f"  removed: {relative}")


if __name__ == "__main__":
    main()
