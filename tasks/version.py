"""Version management tasks."""

import re
from pathlib import Path

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import task

VERSION_FILE = Path("crypto_dot_com/__init__.py")
VERSION_PATTERN = re.compile(r'^__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)


def _read_version() -> tuple[int, int, int]:
    content = VERSION_FILE.read_text()
    match = VERSION_PATTERN.search(content)
    if not match:
        raise RuntimeError(f"Could not find __version__ in {VERSION_FILE}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _write_version(major: int, minor: int, patch: int) -> None:
    content = VERSION_FILE.read_text()
    new_content = VERSION_PATTERN.sub(
        f'__version__ = "{major}.{minor}.{patch}"', content
    )
    VERSION_FILE.write_text(new_content)


@task(
    help={
        "part": "Part to bump: major, minor, or patch (default: patch)",
        "dry_run": "Print the new version without writing it (default: False)",
    }
)
def bump(c: Context, part: str = "patch", dry_run: bool = False) -> None:
    """Bump the project version (major, minor, or patch)."""
    major, minor, patch = _read_version()
    current = f"{major}.{minor}.{patch}"

    part = part.lower()
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid part '{part}'. Must be major, minor, or patch.")

    new_version = f"{major}.{minor}.{patch}"
    print(f"Bumping {part}: {current} → {new_version}")

    if dry_run:
        print("Dry run — no changes written.")
        return

    _write_version(major, minor, patch)
    print(f"Updated {VERSION_FILE} to {new_version}")


@task(
    help={
        "push": "Push the tag to remote after creating it (default: True)",
        "push_commit": "Also push the current commit before tagging (default: True)",
    }
)
def tag(c: Context, push: bool = True, push_commit: bool = True) -> None:
    """Create a git tag for the current version and optionally push it."""
    major, minor, patch = _read_version()
    version = f"{major}.{minor}.{patch}"
    tag_name = f"v{version}"

    print(f"Creating tag {tag_name}...")
    c.run(f"git tag {tag_name}", pty=True)
    print(f"✅ Tag {tag_name} created.")

    if push_commit:
        print("Pushing commit...")
        c.run("git push", pty=True)

    if push:
        print(f"Pushing tag {tag_name}...")
        c.run("git push --tags", pty=True)
        print(f"✅ Tag {tag_name} pushed.")


@task(
    help={
        "part": "Part to bump: major, minor, or patch (default: patch)",
        "message": "Commit message (default: 'Bump version to X.Y.Z')",
    }
)
def release(c: Context, part: str = "patch", message: str = "") -> None:
    """Bump version, commit, tag, and push in one step."""
    bump(c, part=part)

    major, minor, patch = _read_version()
    version = f"{major}.{minor}.{patch}"
    commit_message = message or f"Bump version to {version}"

    print(f"Committing version bump to {version}...")
    c.run(f'git add {VERSION_FILE}', pty=True)
    c.run(f'git commit -m "{commit_message}"', pty=True)

    tag(c, push=True, push_commit=True)
    print(f"\n✅ Released version {version}!")


ns_version = Collection("version")
ns_version.add_task(bump)
ns_version.add_task(tag)
ns_version.add_task(release)

__all__ = ["ns_version"]
