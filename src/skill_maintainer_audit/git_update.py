from __future__ import annotations

import subprocess
from pathlib import Path

from .models import SkillRecord, UpdateAction


def run_git(path: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def git_stdout(path: Path, args: list[str]) -> str | None:
    result = run_git(path, args)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def inspect_or_update(record: SkillRecord, policy: str) -> UpdateAction:
    path = Path(record.path)
    if not record.is_git:
        reason = "not a Git-backed skill; add source metadata or reinstall as Git clone before auto-update"
        return UpdateAction(record.name, record.path, "needs_manual_review", reason)

    remote = git_stdout(path, ["remote", "get-url", "origin"])
    if not remote:
        return UpdateAction(record.name, record.path, "needs_manual_review", "missing origin remote")

    status = git_stdout(path, ["status", "--porcelain"])
    if status is None:
        return UpdateAction(record.name, record.path, "needs_manual_review", "cannot inspect Git status", remote=remote)
    if status.strip():
        return UpdateAction(record.name, record.path, "needs_manual_review", "working tree has local changes", remote=remote)

    before = git_stdout(path, ["rev-parse", "--short", "HEAD"])
    if policy in {"report-only", "dry-run"}:
        return UpdateAction(record.name, record.path, "eligible", "clean Git skill; update skipped by policy", before=before, remote=remote)
    if policy != "safe":
        return UpdateAction(record.name, record.path, "skipped", f"unsupported update policy: {policy}", before=before, remote=remote)

    fetch = run_git(path, ["fetch", "--ff-only", "origin"], timeout=120)
    if fetch.returncode != 0:
        return UpdateAction(record.name, record.path, "failed", clean_error(fetch), before=before, remote=remote)

    branch = git_stdout(path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if not branch or branch == "HEAD":
        return UpdateAction(record.name, record.path, "needs_manual_review", "detached HEAD cannot be safely pulled", before=before, remote=remote)

    pull = run_git(path, ["pull", "--ff-only", "origin", branch], timeout=120)
    after = git_stdout(path, ["rev-parse", "--short", "HEAD"])
    if pull.returncode != 0:
        return UpdateAction(record.name, record.path, "failed", clean_error(pull), before=before, after=after, remote=remote)
    if before == after:
        return UpdateAction(record.name, record.path, "up_to_date", "already at latest fetched commit", before=before, after=after, remote=remote)
    return UpdateAction(record.name, record.path, "updated", "fast-forward update applied", before=before, after=after, remote=remote)


def clean_error(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "").strip()
    return text.splitlines()[0][:240] if text else f"git exited with {result.returncode}"


def update_skills(records: list[SkillRecord], policy: str) -> list[UpdateAction]:
    return [inspect_or_update(record, policy) for record in records]

