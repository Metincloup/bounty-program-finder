#!/usr/bin/env python3
"""Package the canonical Codex skill source as a Claude upload zip."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_SKILL_DIR = Path("skills/bounty-program-finder")
DEFAULT_DIST_DIR = Path("dist")

EXCLUDED_DIRS = {".git", ".cache", "__pycache__", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}
EXCLUDED_NAMES = {".env"}


def should_exclude(path: Path) -> bool:
    parts = set(path.parts)
    if parts.intersection(EXCLUDED_DIRS):
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def copy_skill(skill_dir: Path, staging_root: Path) -> Path:
    if not skill_dir.exists():
        raise FileNotFoundError(f"skill directory not found: {skill_dir}")
    target_dir = staging_root / skill_dir.name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    for source in skill_dir.rglob("*"):
        rel = source.relative_to(skill_dir)
        if should_exclude(rel):
            continue
        dest = target_dir / rel
        if source.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        if source.name == "SKILL.md":
            dest = target_dir / "skill.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    return target_dir


def make_zip(folder: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, path.relative_to(folder.parent))
    return zip_path


def package(skill_dir: Path = DEFAULT_SKILL_DIR, dist_dir: Path = DEFAULT_DIST_DIR) -> Path:
    staging_root = dist_dir / "claude"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)
    staged_skill = copy_skill(skill_dir, staging_root)
    return make_zip(staged_skill, dist_dir / f"{skill_dir.name}.zip")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package bounty-program-finder for Claude skill upload.")
    parser.add_argument("--skill-dir", default=str(DEFAULT_SKILL_DIR), help="Canonical skill source directory.")
    parser.add_argument("--dist-dir", default=str(DEFAULT_DIST_DIR), help="Output directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    zip_path = package(Path(args.skill_dir), Path(args.dist_dir))
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
