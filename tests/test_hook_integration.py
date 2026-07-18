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
APPLE_PYTHON_39 = Path(
    "/Library/Developer/CommandLineTools/Library/Frameworks/"
    "Python3.framework/Versions/3.9/bin/python3"
)


class HookIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(APPLE_PYTHON_39.is_file(), "Apple Python 3.9 is not installed")
    def test_hook_allows_read_with_apple_python_3_9(self) -> None:
        event = {
            "hook_event_name": "preToolUse",
            "cwd": str(REPOSITORY),
            "tool_name": "read",
            "tool_input": {"path": "state"},
        }
        result = subprocess.run(
            [str(APPLE_PYTHON_39), str(HOOK)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

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
