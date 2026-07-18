from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gamedev_agent.permissions import ApprovalStore

REPOSITORY = Path(__file__).resolve().parents[1]
HOOK = REPOSITORY / "hooks" / "pre_tool_use.py"


class HookIntegrationTests(unittest.TestCase):
    def test_hook_blocks_then_allows_one_approved_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").symlink_to(REPOSITORY / "src", target_is_directory=True)
            event = {
                "hook_event_name": "preToolUse",
                "cwd": str(root),
                "tool_name": "@blender/delete_object",
                "tool_input": {"object_name": "Cube"},
            }
            blocked = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(event),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, blocked.returncode)
            self.assertIn("Blocked blender.delete", blocked.stderr)

            ApprovalStore(root).issue(
                operation="blender.delete", resource="Cube", actor="developer"
            )
            allowed = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(event),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, allowed.returncode, allowed.stderr)


if __name__ == "__main__":
    unittest.main()
