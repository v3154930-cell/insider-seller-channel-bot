#!/usr/bin/env python3
"""NEWSBOT v3 backup planning tool (dry-run by default)."""

from __future__ import annotations

import argparse
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_targets(root: Path) -> dict[str, Path]:
    return {
        "config_files": root / "newsbot_v3" / "config",
        "future_v3_db_path": root / "newsbot_v3" / "runtime" / "newsbot_v3.db",
        "source_registry": root / "newsbot_v3" / "runtime" / "source_registry.jsonl",
        "digest_history": root / "newsbot_v3" / "runtime" / "digest_history.jsonl",
        "published_history": root / "newsbot_v3" / "runtime" / "published_history.jsonl",
        "admin_actions": root / "newsbot_v3" / "runtime" / "admin_actions.jsonl",
        "logs_reports": root / "newsbot_v3" / "runtime" / "reports",
    }


def evaluate_target(path: Path) -> str:
    if path.exists():
        return "present"
    if path.suffix:
        parent = path.parent
        return "planned_missing_parent_present" if parent.exists() else "planned_missing_parent_absent"
    return "planned_missing"


def run_dry_run() -> int:
    root = repo_root()
    targets = build_targets(root)

    known: list[str] = []
    missing: list[str] = []
    for name, path in targets.items():
        state = evaluate_target(path)
        known.append(f"{name}:{state}:{path.relative_to(root)}")
        if "missing" in state:
            missing.append(f"{name}:{path.relative_to(root)}")

    status = "OK" if not missing else "WARN"

    print(f"V3_BACKUP_DRY_RUN_STATUS={status}")
    print("backup_mode=dry_run")
    print("production_mutation=false")
    print(f"backup_targets_known={' | '.join(known)}")
    print(f"missing_targets={'; '.join(missing) if missing else 'none'}")
    print(
        "recommended_next_steps="
        "create runtime target dirs/files for v3 when rollout starts; "
        "keep dry-run in CI; enable real backup only with explicit operator command"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan v3 backup targets without mutating production")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Reserved for future explicit backup execution. Not implemented in foundation PR.",
    )
    args = parser.parse_args()

    if args.execute:
        print("V3_BACKUP_DRY_RUN_STATUS=FAIL")
        print("backup_mode=execute_requested")
        print("production_mutation=false")
        print("backup_targets_known=not_evaluated")
        print("missing_targets=not_evaluated")
        print("recommended_next_steps=execution mode intentionally disabled in foundation PR; use dry-run only")
        return 2

    return run_dry_run()


if __name__ == "__main__":
    raise SystemExit(main())
