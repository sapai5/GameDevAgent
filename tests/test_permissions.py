from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gamedev_agent.permissions import ApprovalStore, classify_event, evaluate_event
from gamedev_agent.storage import JsonStore


class PermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_read_operation_is_allowed_without_approval(self) -> None:
        allowed, _ = evaluate_event(
            self.root, {"tool_name": "read", "tool_input": {"path": "scene.blend"}}
        )
        self.assertTrue(allowed)

    def test_blender_delete_is_blocked_then_one_time_approval_is_consumed(self) -> None:
        event = {"tool_name": "@blender/delete_object", "tool_input": {"object_name": "Cube"}}
        operation = classify_event(event)
        self.assertIsNotNone(operation)
        assert operation is not None
        self.assertEqual("blender.delete", operation.operation)

        allowed, message = evaluate_event(self.root, event)
        self.assertFalse(allowed)
        self.assertIn("gamedev approve", message)

        ApprovalStore(self.root).issue(
            operation="blender.delete", resource="Cube", actor="developer", ttl_minutes=15
        )
        allowed, _ = evaluate_event(self.root, event)
        self.assertTrue(allowed)
        allowed, _ = evaluate_event(self.root, event)
        self.assertFalse(allowed)

    def test_force_push_and_export_overwrite_are_classified(self) -> None:
        force = classify_event(
            {"tool_name": "shell", "tool_input": {"command": "git push --force origin feature"}}
        )
        overwrite = classify_event(
            {
                "tool_name": "@blender/export_gltf",
                "tool_input": {"path": "crate.glb", "overwrite": True},
            }
        )
        self.assertEqual("git.force-push", force.operation if force else None)
        self.assertEqual("export.overwrite", overwrite.operation if overwrite else None)

    def test_expired_approval_is_not_consumed(self) -> None:
        store = ApprovalStore(self.root)
        approval = store.issue(
            operation="unity.delete", resource="Assets/Test.prefab", actor="developer"
        )
        state = store.store.read()
        state["approvals"][0]["expires_at"] = "2000-01-01T00:00:00+00:00"
        JsonStore(store.store.path).write(state)
        self.assertIsNone(store.consume("unity.delete", "Assets/Test.prefab"))
        self.assertIsNone(approval["consumed_at"])


if __name__ == "__main__":
    unittest.main()
