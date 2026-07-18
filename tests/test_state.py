from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gamedev_agent.state import ManifestStore, SessionStore
from gamedev_agent.storage import JsonStore, StateError
from gamedev_agent.telemetry import AuditLogger, UsageTracker


class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_json_store_rejects_corrupt_state_without_overwriting_it(self) -> None:
        path = self.root / "state.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(StateError, "invalid JSON"):
            JsonStore(path).read()
        self.assertEqual("{broken", path.read_text(encoding="utf-8"))

    def test_manifest_records_provenance_paths_and_checksum(self) -> None:
        manifest = ManifestStore(self.root)
        manifest.initialize("Demo")
        source = self.root / "Assets" / "crate.glb"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"crate")

        asset = manifest.register_asset(
            asset_id="forest-crate-a",
            name="Forest Crate A",
            kind="prop",
            source_type="hand-modeled",
            source_uri=None,
            license_spdx="LicenseRef-Proprietary",
            license_url=None,
            license_verified=True,
            actor="blender-modeler",
            blender_file="Blender/crate.blend",
            export_file="Assets/crate.glb",
            unity_path="Unity/Assets/crate.glb",
        )

        self.assertEqual("blender-modeler", asset["source"]["agent"])
        self.assertEqual("blender-modeler", asset["last_modified_by"])
        self.assertTrue(asset["checksum"].startswith("sha256:"))
        self.assertEqual("Assets/crate.glb", asset["files"]["export"])
        self.assertTrue(manifest.all_licenses_verified())

        updated = manifest.update_asset(
            asset_id="forest-crate-a",
            actor="unity-scene-builder",
            unity_path="Unity/Assets/Game/Art/Imported/SM_Crate_A.glb",
        )
        self.assertEqual("unity-scene-builder", updated["last_modified_by"])
        self.assertEqual(
            "Unity/Assets/Game/Art/Imported/SM_Crate_A.glb",
            updated["files"]["unity"],
        )
        self.assertEqual("updated", updated["history"][-1]["action"])
        self.assertIn("files.unity", updated["history"][-1]["fields"])

        previous_checksum = updated["checksum"]
        revised_export = self.root / "Assets" / "crate-v2.glb"
        revised_export.write_bytes(b"crate-v2")
        exported = manifest.update_asset(
            asset_id="forest-crate-a",
            actor="blender-exporter",
            export_file="Assets/crate-v2.glb",
        )
        self.assertNotEqual(previous_checksum, exported["checksum"])
        self.assertIn("checksum", exported["history"][-1]["fields"])

        with self.assertRaisesRegex(StateError, "changed field"):
            manifest.update_asset(asset_id="forest-crate-a", actor="project-manager")

        with self.assertRaisesRegex(StateError, "already exists"):
            manifest.register_asset(
                asset_id="forest-crate-a",
                name="Duplicate",
                kind="prop",
                source_type="generated",
                source_uri=None,
                license_spdx="MIT",
                license_url=None,
                license_verified=True,
                actor="blender-modeler",
            )

    def test_manifest_rejects_paths_outside_project(self) -> None:
        manifest = ManifestStore(self.root)
        manifest.initialize()
        with self.assertRaisesRegex(StateError, "within project root"):
            manifest.register_asset(
                asset_id="escaped",
                name="Escaped",
                kind="prop",
                source_type="researched",
                source_uri="https://example.invalid/asset",
                license_spdx="MIT",
                license_url="https://example.invalid/license",
                license_verified=True,
                actor="asset-researcher",
                export_file="../escaped.glb",
            )

    def test_session_resumes_and_advances_persistently(self) -> None:
        sessions = SessionStore(self.root)
        session = sessions.start(
            "pipeline-test",
            [
                {"id": "model", "agent": "blender-modeler"},
                {"id": "qa", "agent": "unity-qa-tester"},
            ],
        )
        resumed = SessionStore(self.root).latest_active()
        self.assertEqual(session["id"], resumed["id"])
        advanced = sessions.advance(session["id"], "project-manager")
        self.assertEqual("qa", advanced["stages"][advanced["current_stage"]]["id"])
        completed = sessions.advance(session["id"], "unity-qa-tester")
        self.assertEqual("completed", completed["status"])
        with self.assertRaisesRegex(StateError, "cannot advance"):
            sessions.advance(session["id"], "project-manager")

    def test_jsonl_audit_and_usage_are_machine_readable(self) -> None:
        audit = AuditLogger(self.root)
        audit.record(event="tool-call", actor="blender-modeler", tool="@blender/create")
        line = (self.root / "logs" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual("tool-call", json.loads(line[0])["event"])

        usage = UsageTracker(self.root)
        usage.record(agent="blender-modeler", turns=2, cost_usd=0.25, session_id="s")
        usage.record(agent="blender-modeler", turns=1, cost_usd=0.10, session_id="s")
        summary = usage.summary()
        self.assertEqual(3, summary["by_agent"]["blender-modeler"]["turns"])
        self.assertEqual(0.35, summary["by_agent"]["blender-modeler"]["cost_usd"])


if __name__ == "__main__":
    unittest.main()
