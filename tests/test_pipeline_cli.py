from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from gamedev_agent.cli import main
from gamedev_agent.permissions import ApprovalStore
from gamedev_agent.pipelines import PipelineCoordinator
from gamedev_agent.state import ManifestStore
from gamedev_agent.storage import StateError

REPOSITORY = Path(__file__).resolve().parents[1]


class PipelineAndCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        shutil.copytree(REPOSITORY / "pipelines", self.root / "pipelines")
        ManifestStore(self.root).initialize("Test")
        (self.root / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
        (self.root / "gamedev.json").write_text(
            '{"schema_version":1,"mcp":{"blender":{"url":null},"unity":{"url":null}}}\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_pipeline_blocks_unverified_license_before_export(self) -> None:
        manifest = ManifestStore(self.root)
        manifest.register_asset(
            asset_id="crate",
            name="Crate",
            kind="prop",
            source_type="researched",
            source_uri="https://example.invalid/crate",
            license_spdx="LicenseRef-Unknown",
            license_url=None,
            license_verified=False,
            actor="asset-researcher",
        )
        coordinator = PipelineCoordinator(self.root)
        session = coordinator.start("pipeline-scene-to-unity")
        for _ in range(5):
            coordinator.advance(session["id"], "project-manager")
        with self.assertRaisesRegex(StateError, "license gate failed"):
            coordinator.advance(session["id"], "blender-exporter")
        self.assertEqual("blocked", coordinator.resume(session["id"])["status"])

    def test_final_stage_requires_one_time_human_approval(self) -> None:
        coordinator = PipelineCoordinator(self.root)
        session = coordinator.start("pipeline-scene-to-unity")
        for _ in range(8):
            session = coordinator.advance(session["id"], "project-manager")
        resource = f"{session['id']}:release"
        with self.assertRaisesRegex(StateError, "approval gate failed"):
            coordinator.advance(session["id"], "release-engineer")
        ApprovalStore(self.root).issue(
            operation="pipeline.stage", resource=resource, actor="developer"
        )
        completed = coordinator.advance(session["id"], "release-engineer")
        self.assertEqual("completed", completed["status"])

    def test_cli_status_and_resume_emit_structured_json(self) -> None:
        session = PipelineCoordinator(self.root).start("pipeline-prop-kit")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--project", str(self.root), "status"])
        self.assertEqual(0, code)
        self.assertEqual(session["id"], json.loads(stdout.getvalue())["pipeline"]["session_id"])

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--project", str(self.root), "resume"])
        self.assertEqual(0, code)
        self.assertEqual("plan-kit", json.loads(stdout.getvalue())["next_stage"])

    def test_asset_update_command_records_later_unity_handoff(self) -> None:
        ManifestStore(self.root).register_asset(
            asset_id="crate",
            name="Crate",
            kind="prop",
            source_type="hand-modeled",
            source_uri=None,
            license_spdx="LicenseRef-Proprietary",
            license_url=None,
            license_verified=True,
            actor="blender-modeler",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "--project",
                    str(self.root),
                    "asset",
                    "update",
                    "--id",
                    "crate",
                    "--actor",
                    "unity-scene-builder",
                    "--unity-path",
                    "Unity/Assets/Crate.glb",
                ]
            )
        updated = json.loads(stdout.getvalue())
        self.assertEqual(0, code)
        self.assertEqual("Unity/Assets/Crate.glb", updated["files"]["unity"])
        self.assertEqual("unity-scene-builder", updated["last_modified_by"])

    def test_doctor_fails_fast_when_endpoints_are_unconfigured(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--project", str(self.root), "doctor"])
        report = json.loads(stdout.getvalue())
        self.assertEqual(1, code)
        self.assertFalse(report["ok"])
        self.assertEqual({"blender", "unity"}, {check["server"] for check in report["checks"]})


if __name__ == "__main__":
    unittest.main()
