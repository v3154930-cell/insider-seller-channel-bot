from __future__ import annotations

import os
from pathlib import Path


def resolve_runtime_root() -> Path:
    """Resolve NEWSBOT v3 runtime root for both repo and stripped deployments.

    Priority:
    1) NEWSBOT_V3_ROOT env var
    2) stripped runtime detected from this tool path: <root>/tools/*.py
    3) repository layout detected from this tool path: <repo>/newsbot_v3/tools/*.py
    4) current working directory
    """
    env_root = os.getenv("NEWSBOT_V3_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    this_file = Path(__file__).resolve()
    parent = this_file.parent

    # stripped runtime layout: /opt/newsbot_v3/tools/<tool>.py
    if parent.name == "tools" and parent.parent.joinpath("app").exists():
        return parent.parent

    # repository layout: <repo>/newsbot_v3/tools/<tool>.py
    if parent.name == "tools" and parent.parent.name == "newsbot_v3":
        return parent.parent

    return Path.cwd().resolve()


def tool_exists(tool_name: str) -> bool:
    return resolve_runtime_root().joinpath("tools", tool_name).exists()
