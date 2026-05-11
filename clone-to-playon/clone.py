#!/usr/bin/env python3
"""
Mirror a Shine `backend-<service>-service` repo into its
`playon-backend-<service>-service` counterpart and apply the infra/project/NuGet
transformations needed to publish under a separate NuGet identity and CI repo
name. Business-logic edits are out of scope.

Steps (each step is idempotent):
  1. Validate OLD/NEW paths and NEW git remote
  2. Mirror OLD -> NEW via rsync (excluding .git, bin, obj)
  3. Patch .github/workflows/ci.yml: prefix `repository_name` value with `playon-`
  4. Rename `Shine.<rest>.sln` -> `Shine.Playon.<rest>.sln` and rewrite any
     references to the old solution filename in text files (e.g. Dockerfile)
  5. Inject `<PackageId>Shine.Playon.<rest></PackageId>` into every packable .csproj
  6. Remove top-level README.md (the playon repo gets its own later, if any)
  7. Print `git status` of NEW for review

Does NOT stage, commit, or push - that is up to the caller.

Usage:
    clone.py <service-name> [--workdir PATH]

Example:
    clone.py games
        OLD: ~/Documents/WORK/backend-games-service
        NEW: ~/Documents/WORK/playon-backend-games-service
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_WORKDIR = Path.home() / "Documents" / "WORK"
EXPECTED_REMOTE_PREFIX = "git@github.com:papaya-shine/playon-"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(msg)


def validate(old: Path, new: Path) -> None:
    if not old.is_dir():
        fail(f"OLD project does not exist: {old}")
    if not new.is_dir():
        fail(f"NEW project does not exist: {new}")
    if not (new / ".git").exists():
        fail(f"NEW project is not a git repo: {new}")

    result = subprocess.run(
        ["git", "-C", str(new), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    remote = result.stdout.strip()
    if remote and not remote.startswith(EXPECTED_REMOTE_PREFIX):
        info(
            f"  WARNING: NEW remote does not start with '{EXPECTED_REMOTE_PREFIX}': {remote}"
        )

    dirty = subprocess.run(
        ["git", "-C", str(new), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        info(
            "  WARNING: NEW has uncommitted changes; mirror will overwrite/delete files."
        )


def mirror(old: Path, new: Path) -> None:
    cmd = [
        "rsync",
        "-a",
        "--delete",
        "--exclude=.git",
        "--exclude=bin",
        "--exclude=obj",
        f"{old}/",
        f"{new}/",
    ]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        fail(f"rsync failed (exit {rc})")


def patch_ci(new: Path) -> None:
    ci = new / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        info("  ci.yml not found, skipping")
        return
    text = ci.read_text()
    new_text, n = re.subn(
        r"^(\s*repository_name:\s*)(?!playon-)(\S+)\s*$",
        r"\1playon-\2",
        text,
        flags=re.MULTILINE,
    )
    if n > 0:
        ci.write_text(new_text)
        info(f"  patched: {ci.relative_to(new)}")
    else:
        info("  ci.yml: no change needed (already prefixed or no match)")


SLN_REF_SKIP_DIRS = {".git", "bin", "obj", "node_modules"}


def rename_solution(new: Path) -> None:
    sln_files = sorted(new.glob("*.sln"))
    shine_sln = [
        p for p in sln_files
        if p.stem.startswith("Shine.") and not p.stem.startswith("Shine.Playon.")
    ]
    playon_sln = [p for p in sln_files if p.stem.startswith("Shine.Playon.")]

    if not shine_sln and playon_sln:
        info(f"  already renamed: {playon_sln[0].name}")
        return
    if not shine_sln:
        info("  no Shine.*.sln found at repo root, skipping")
        return
    if len(shine_sln) > 1:
        info(
            f"  WARNING: multiple Shine.*.sln files at repo root, skipping rename: "
            f"{[p.name for p in shine_sln]}"
        )
        return
    if playon_sln:
        info(
            f"  WARNING: both Shine.* and Shine.Playon.* sln files exist, skipping: "
            f"{[p.name for p in sln_files]}"
        )
        return

    old_sln = shine_sln[0]
    m = re.match(r"^Shine\.(.+)$", old_sln.stem)
    if not m:
        info(f"  WARNING: cannot parse {old_sln.name}, skipping")
        return
    new_sln = old_sln.with_name(f"Shine.Playon.{m.group(1)}.sln")
    old_sln.rename(new_sln)
    info(f"  renamed: {old_sln.name} -> {new_sln.name}")

    old_name = old_sln.name
    new_name = new_sln.name
    updated = 0
    for path in new.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SLN_REF_SKIP_DIRS for part in path.relative_to(new).parts):
            continue
        if path.suffix == ".sln":
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if old_name not in text:
            continue
        path.write_text(text.replace(old_name, new_name))
        info(f"  updated reference in: {path.relative_to(new)}")
        updated += 1
    if updated == 0:
        info(f"  no references to {old_name} found in repo")


def patch_csprojs(new: Path) -> None:
    patched = 0
    for csproj in sorted(new.rglob("*.csproj")):
        text = csproj.read_text()
        if "<GeneratePackageOnBuild>true</GeneratePackageOnBuild>" not in text:
            continue
        if "<PackageId>" in text:
            continue

        m = re.match(r"^Shine\.(.+)$", csproj.stem)
        if not m:
            info(f"  skipping (filename does not match 'Shine.*'): {csproj.name}")
            continue
        package_id = f"Shine.Playon.{m.group(1)}"

        new_text, n = re.subn(
            r"^(\s*)(<GeneratePackageOnBuild>true</GeneratePackageOnBuild>)\s*$",
            lambda mm: (
                f"{mm.group(1)}{mm.group(2)}\n"
                f"{mm.group(1)}<PackageId>{package_id}</PackageId>"
            ),
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if n > 0:
            csproj.write_text(new_text)
            info(f"  patched: {csproj.relative_to(new)} -> {package_id}")
            patched += 1

    if patched == 0:
        info("  no packable .csproj needed patching")


def remove_readme(new: Path) -> None:
    readme = new / "README.md"
    if readme.exists():
        readme.unlink()
        info("  removed: README.md")
    else:
        info("  no README.md to remove")


def print_status(new: Path) -> None:
    subprocess.run(["git", "-C", str(new), "status", "--short"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clone a Shine backend service into its playon-* counterpart.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("service", help="lowercase service name, e.g. 'games'")
    parser.add_argument(
        "--workdir",
        default=str(DEFAULT_WORKDIR),
        help=f"work directory containing both repos (default: {DEFAULT_WORKDIR})",
    )
    args = parser.parse_args()

    service = args.service.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9-]*", service):
        fail(f"invalid service name: {args.service!r}")

    workdir = Path(args.workdir).expanduser()
    old = workdir / f"backend-{service}-service"
    new = workdir / f"playon-backend-{service}-service"

    info(f"OLD: {old}")
    info(f"NEW: {new}")

    info("\n[1/6] Validating...")
    validate(old, new)

    info("\n[2/6] Mirroring files (rsync)...")
    mirror(old, new)

    info("\n[3/6] Patching .github/workflows/ci.yml...")
    patch_ci(new)

    info("\n[4/6] Renaming solution to Shine.Playon.*.sln and updating references...")
    rename_solution(new)

    info("\n[5/6] Patching packable .csproj files...")
    patch_csprojs(new)

    info("\n[6/6] Removing README.md if present...")
    remove_readme(new)

    info("\nGit status of NEW (review before committing):")
    print_status(new)

    info(
        "\nDone. The skill does NOT stage, commit, or push - that is up to you."
    )


if __name__ == "__main__":
    main()
