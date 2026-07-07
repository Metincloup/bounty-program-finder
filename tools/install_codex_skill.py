#!/usr/bin/env python3
"""Install or update the skill in the local Codex skills directory."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Sequence


DEFAULT_SKILL_DIR = Path("skills/bounty-program-finder")
EXCLUDED_DIRS = {".git", ".cache", "__pycache__", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}
EXCLUDED_NAMES = {".env"}


def default_dest_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "skills"
    return Path.home() / ".codex" / "skills"


def should_ignore(path: Path) -> bool:
    if set(path.parts).intersection(EXCLUDED_DIRS):
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def copy_skill(skill_dir: Path, dest_root: Path, force: bool = False) -> Path:
    if not skill_dir.exists():
        raise FileNotFoundError(f"skill directory not found: {skill_dir}")
    dest = dest_root / skill_dir.name
    if dest.exists():
        if not force:
            raise FileExistsError(f"{dest} already exists; pass --force to update it")
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    for source in skill_dir.rglob("*"):
        rel = source.relative_to(skill_dir)
        if should_ignore(rel):
            continue
        target = dest / rel
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return dest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install bounty-program-finder as a local Codex skill.")
    parser.add_argument("--skill-dir", default=str(DEFAULT_SKILL_DIR), help="Skill source directory.")
    parser.add_argument("--dest-root", default=str(default_dest_root()), help="Codex skills directory.")
    parser.add_argument("--force", action="store_true", help="Replace an existing installed skill.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    installed = copy_skill(Path(args.skill_dir), Path(args.dest_root), force=args.force)
    print(installed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
