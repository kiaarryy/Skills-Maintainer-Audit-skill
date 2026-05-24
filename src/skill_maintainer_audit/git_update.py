from __future__ import annotations

import subprocess
from pathlib import Path

from .install_info import generate_reinstall_command
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
        return inspect_non_git(record)

    remote = git_stdout(path, ["remote", "get-url", "origin"])
    if not remote:
        return UpdateAction(record.name, record.path, "unknown_source", "Git folder has no origin remote")

    status = git_stdout(path, ["status", "--porcelain"])
    if status is None:
        return UpdateAction(record.name, record.path, "unknown_source", "cannot inspect Git status", remote=remote)
    if status.strip():
        return UpdateAction(record.name, record.path, "dirty_git", "working tree has local changes", remote=remote)

    before = git_stdout(path, ["rev-parse", "--short", "HEAD"])
    if policy in {"report-only", "dry-run"}:
        return UpdateAction(record.name, record.path, "up_to_date", "clean Git skill; update skipped by report-only policy", before=before, remote=remote)
    if policy != "safe":
        return UpdateAction(record.name, record.path, "skipped", f"unsupported update policy: {policy}", before=before, remote=remote)

    fetch = run_git(path, ["fetch", "origin"], timeout=120)
    if fetch.returncode != 0:
        return UpdateAction(record.name, record.path, "failed", clean_error(fetch), before=before, remote=remote)

    branch = git_stdout(path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if not branch or branch == "HEAD":
        return UpdateAction(record.name, record.path, "dirty_git", "detached HEAD cannot be safely pulled", before=before, remote=remote)

    pull = run_git(path, ["pull", "--ff-only", "origin", branch], timeout=120)
    after = git_stdout(path, ["rev-parse", "--short", "HEAD"])
    if pull.returncode != 0:
        return UpdateAction(record.name, record.path, "failed", clean_error(pull), before=before, after=after, remote=remote)
    if before == after:
        return UpdateAction(record.name, record.path, "up_to_date", "already at latest fetched commit", before=before, after=after, remote=remote)
    return UpdateAction(record.name, record.path, "updated", "fast-forward update applied", before=before, after=after, remote=remote)


def inspect_non_git(record: SkillRecord) -> UpdateAction:
    source = record.source_url
    skill_dir = Path(record.path)
    # Prefer the skills.sh registry command when available
    registry_cmd = record.registry_add_command

    if not source and not registry_cmd:
        return UpdateAction(
            record.name,
            record.path,
            "unknown_source",
            "not Git-backed and no source URL was discovered",
            source_type=record.source_type,
            source_confidence=record.source_confidence,
        )

    # Skills found in skills.sh registry: use `npx skills add` as the preferred update path
    if registry_cmd:
        return UpdateAction(
            record.name,
            record.path,
            "registry_updateable",
            f"Found in skills.sh registry (source={record.registry_source}, installs={record.registry_installs:,})",
            remote=record.registry_source,
            source_type="skillssh_registry",
            source_confidence="high",
            registry_command=registry_cmd,
            manual_command=registry_cmd,  # keep manual_command populated for backward compat
        )

    # Fallback: non-registry git-clone approach
    reinstall_cmd = generate_reinstall_command(skill_dir, source) if source else None

    if not record.source_commit:
        upstream = remote_head(source) if source else None
        if not upstream:
            return UpdateAction(
                record.name,
                record.path,
                "non_git_no_baseline",
                "source URL found but upstream HEAD could not be fetched; manual check needed",
                remote=source,
                source_type=record.source_type,
                source_confidence=record.source_confidence,
                manual_command=reinstall_cmd,
            )
        return UpdateAction(
            record.name,
            record.path,
            "non_git_updateable",
            f"source URL confirmed; upstream HEAD={upstream[:12]}; no local baseline to compare",
            after=upstream[:12],
            remote=source,
            source_type=record.source_type,
            source_confidence=record.source_confidence,
            manual_command=reinstall_cmd,
        )

    upstream = remote_head(source) if source else None
    if not upstream:
        return UpdateAction(
            record.name,
            record.path,
            "non_git_no_baseline",
            "source commit exists, but upstream HEAD could not be checked",
            before=record.source_commit[:12],
            remote=source,
            source_type=record.source_type,
            source_confidence=record.source_confidence,
            manual_command=reinstall_cmd,
        )

    is_current = upstream.startswith(record.source_commit) or record.source_commit.startswith(upstream)
    status = "up_to_date" if is_current else "outdated_source_detected"
    reason = "vendored source commit matches upstream HEAD" if is_current else "vendored source commit differs from upstream HEAD"
    return UpdateAction(
        record.name,
        record.path,
        status,
        reason,
        before=record.source_commit[:12],
        after=upstream[:12],
        remote=source,
        source_type=record.source_type,
        source_confidence=record.source_confidence,
        manual_command=None if is_current else reinstall_cmd,
    )


def remote_head(remote: str) -> str | None:
    result = subprocess.run(
        ["git", "ls-remote", remote, "HEAD"],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return None
    first = result.stdout.strip().splitlines()
    if not first:
        return None
    return first[0].split()[0]


def clean_error(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "").strip()
    return text.splitlines()[0][:240] if text else f"git exited with {result.returncode}"


def update_skills(records: list[SkillRecord], policy: str) -> list[UpdateAction]:
    return [inspect_or_update(record, policy) for record in records]
