#!/usr/bin/env python3
"""Kiro preToolUse hook: block destructive operations without one-time approval."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"GameDev safety hook received invalid JSON: {error}", file=sys.stderr)
        return 2
    root = Path(str(event.get("cwd", Path.cwd()))).resolve()
    for candidate in (root, *root.parents):
        if (candidate / "src" / "gamedev_agent").is_dir():
            root = candidate
            break
    sys.path.insert(0, str(root / "src"))
    try:
        from gamedev_agent.permissions import evaluate_event

        allowed, reason = evaluate_event(root, event)
    except Exception as error:  # A safety hook must fail closed.
        print(f"GameDev safety hook failed closed: {error}", file=sys.stderr)
        return 2
    if allowed:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
