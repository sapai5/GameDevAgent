from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gamedev_agent.cli import build_parser, main
from gamedev_agent.runtime import AgentRunResult
from gamedev_agent.task_difficulty import (
    SAFETY_GATES,
    DifficultyLevel,
    ExecutionRoute,
    ExecutionTiming,
    ResponseDetail,
    TaskOverrides,
    TaskState,
    classify_task,
    compare_budget,
)


class TaskDifficultyTests(unittest.TestCase):
    def test_classification_is_stable_for_normalized_request_and_state(self) -> None:
        first = classify_task(
            "  SHOW   the Current Manifest status  ",
            state=TaskState(connected_applications=("unity", "blender", "unity")),
        )
        second = classify_task(
            "show the current manifest STATUS",
            state=TaskState(connected_applications=("blender", "unity")),
        )

        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual("show the current manifest status", first.normalized_request)
        self.assertTrue(first.state_fingerprint.startswith("sha256:"))

    def test_initial_difficulty_levels_and_routes(self) -> None:
        cases = (
            (
                "Show the current manifest status",
                TaskState(),
                DifficultyLevel.TRIVIAL,
                ExecutionRoute.QUERY,
            ),
            (
                "Change the existing Blender resolution from 4K to 2K",
                TaskState(target_exists=True, connected_applications=("blender",)),
                DifficultyLevel.TRIVIAL,
                ExecutionRoute.PROPERTY_EDIT,
            ),
            (
                "Update the existing crate color and roughness",
                TaskState(target_exists=True),
                DifficultyLevel.SMALL,
                ExecutionRoute.STAGED_EDIT,
            ),
            (
                "Update multiple objects then export them",
                TaskState(target_exists=True),
                DifficultyLevel.STANDARD,
                ExecutionRoute.STAGED_EDIT,
            ),
            (
                "Generate a high-density forest and produce a final render",
                TaskState(),
                DifficultyLevel.COMPLEX,
                ExecutionRoute.REBUILD,
            ),
        )

        for request, state, difficulty, route in cases:
            with self.subTest(request=request):
                assessment = classify_task(request, state=state)
                self.assertEqual(difficulty, assessment.difficulty)
                self.assertEqual(route, assessment.route)

    def test_high_density_generation_ranks_above_property_edit(self) -> None:
        edit = classify_task(
            "Set the existing Blender render resolution to 2K",
            state=TaskState(target_exists=True),
        )
        generation = classify_task("Generate a high-density forest")

        self.assertGreater(generation.score, edit.score)
        self.assertEqual(DifficultyLevel.COMPLEX, generation.difficulty)
        self.assertEqual(DifficultyLevel.TRIVIAL, edit.difficulty)

    def test_explicit_overrides_win_without_removing_safety_gates(self) -> None:
        inferred = classify_task(
            "Inspect the scene in detail, do not render, within 45 seconds",
            state=TaskState(target_exists=True),
        )
        supplied = classify_task(
            "Inspect the scene in detail, do not render, within 45 seconds",
            state=TaskState(target_exists=True),
            overrides=TaskOverrides(
                detail=ResponseDetail.BRIEF,
                render_allowed=True,
                deadline_seconds=90,
            ),
        )

        self.assertEqual(ResponseDetail.DETAILED, inferred.response_detail)
        self.assertFalse(inferred.render_allowed)
        self.assertEqual(45, inferred.budget.active_limit_seconds)
        self.assertEqual(ResponseDetail.BRIEF, supplied.response_detail)
        self.assertTrue(supplied.render_allowed)
        self.assertEqual(90, supplied.budget.active_limit_seconds)
        self.assertEqual(SAFETY_GATES, supplied.required_safety_gates)

    def test_deadline_constrains_active_work_not_safety(self) -> None:
        assessment = classify_task(
            "Update multiple objects then export them within 30 seconds",
            state=TaskState(target_exists=True),
        )

        self.assertEqual(DifficultyLevel.STANDARD, assessment.difficulty)
        self.assertEqual(30, assessment.budget.active_limit_seconds)
        self.assertEqual(600, assessment.budget.predicted_active_seconds)
        self.assertTrue(assessment.budget.constrained_by_deadline)
        self.assertEqual(SAFETY_GATES, assessment.required_safety_gates)

    def test_warm_4k_to_2k_uses_targeted_property_fast_path(self) -> None:
        assessment = classify_task(
            "Change the existing Blender scene from 4K to 2K without regenerating trees, "
            "rendering, or rerunning broad validation",
            state=TaskState(target_exists=True, connected_applications=("blender",)),
        )

        self.assertEqual(DifficultyLevel.TRIVIAL, assessment.difficulty)
        self.assertEqual(ExecutionRoute.PROPERTY_EDIT, assessment.route)
        self.assertTrue(assessment.fast_path)
        self.assertEqual(
            (
                "blender.scene.render.resolution_x",
                "blender.scene.render.resolution_y",
            ),
            assessment.target_properties,
        )
        self.assertIn("mutate-properties", assessment.allowed_stages)
        self.assertIn("verify-targeted-properties", assessment.allowed_stages)
        self.assertEqual(60, assessment.budget.active_limit_seconds)
        self.assertEqual(0, assessment.budget.predicted_startup_seconds)
        self.assertFalse(assessment.render_allowed)
        for stage in (
            "generation",
            "simulation",
            "preview-render",
            "final-render",
            "export",
            "broad-validation",
        ):
            self.assertNotIn(stage, assessment.allowed_stages)
            self.assertIn(stage, assessment.skipped_stages)

    def test_budget_overrun_reports_predicted_and_actual_active_time(self) -> None:
        assessment = classify_task(
            "Set the existing Blender resolution to 2K",
            state=TaskState(target_exists=True, connected_applications=("blender",)),
        )
        outcome = compare_budget(
            assessment,
            ExecutionTiming(
                active_seconds=75,
                startup_seconds=120,
                queue_seconds=30,
                stages=(("mutate-properties", 30),),
            ),
        )
        evidence = outcome.to_dict()

        self.assertTrue(outcome.overrun)
        self.assertEqual(60, evidence["predicted_active_seconds"])
        self.assertEqual(60, evidence["active_limit_seconds"])
        self.assertEqual(75, evidence["actual_active_seconds"])
        self.assertEqual(15, evidence["active_overrun_seconds"])
        self.assertEqual(225, evidence["actual_wall_seconds"])
        self.assertEqual(120, evidence["actual_startup_seconds"])
        self.assertEqual(30, evidence["actual_queue_seconds"])
        self.assertEqual("task-budget-evaluated", evidence["event"])

    def test_cold_start_and_queue_do_not_cause_active_overrun(self) -> None:
        assessment = classify_task(
            "Set the existing Blender resolution to 2K",
            state=TaskState(target_exists=True),
        )
        outcome = compare_budget(
            assessment,
            ExecutionTiming(active_seconds=55, startup_seconds=120, queue_seconds=90),
        )

        self.assertFalse(outcome.overrun)
        self.assertEqual(0, outcome.active_overrun_seconds)
        self.assertEqual(265, outcome.actual_wall_seconds)

    def test_all_routes_retain_safety_gates(self) -> None:
        requests = (
            "Show current status",
            "Change the existing resolution to 2K",
            "Update the existing color and scale",
            "Generate a full scene and render the result",
        )
        for request in requests:
            with self.subTest(request=request):
                assessment = classify_task(request, state=TaskState(target_exists=True))
                self.assertEqual(SAFETY_GATES, assessment.required_safety_gates)

    def test_invalid_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            classify_task("   ")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            TaskState(predicted_queue_seconds=-1)
        with self.assertRaisesRegex(ValueError, "finite"):
            TaskState(predicted_startup_seconds=float("nan"))
        with self.assertRaisesRegex(ValueError, "positive"):
            TaskOverrides(deadline_seconds=0)
        with self.assertRaisesRegex(ValueError, "finite"):
            TaskOverrides(deadline_seconds=float("inf"))
        with self.assertRaisesRegex(ValueError, "non-negative"):
            ExecutionTiming(active_seconds=-1)
        with self.assertRaisesRegex(ValueError, "finite"):
            ExecutionTiming(active_seconds=float("nan"))
        with self.assertRaisesRegex(ValueError, "unique"):
            ExecutionTiming(active_seconds=1, stages=(("edit", 1), ("edit", 2)))
        for invalid_deadline in ("0", "nan", "inf"):
            with self.subTest(invalid_deadline=invalid_deadline), self.assertRaises(SystemExit):
                build_parser().parse_args(
                    ["run", "request", "--deadline-seconds", invalid_deadline]
                )

    def test_serialized_contract_is_schema_versioned_and_prompt_safe(self) -> None:
        assessment = classify_task("Show current status")
        serialized = assessment.to_dict()
        directive = assessment.prompt_directive()

        self.assertEqual(1, serialized["schema_version"])
        self.assertIn('"schema_version":1', directive)
        self.assertIn("never execute skipped_stages", directive)
        self.assertIn("may not be bypassed", directive)


class TaskDifficultyCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "pipelines").mkdir()
        (self.root / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_run_audits_and_routes_property_edit_without_starting_pipeline(self) -> None:
        result = AgentRunResult(0, "done\n", "", 0.5)
        with (
            mock.patch("gamedev_agent.cli.install_agents"),
            mock.patch("gamedev_agent.cli.PipelineCoordinator.start") as start,
            mock.patch("gamedev_agent.cli.run_agent", return_value=result) as runner,
        ):
            code = main(
                [
                    "--project",
                    str(self.root),
                    "run",
                    "Change the existing Blender scene resolution from 4K to 2K",
                    "--no-render",
                    "--detail",
                    "brief",
                    "--deadline-seconds",
                    "60",
                ]
            )

        self.assertEqual(0, code)
        start.assert_not_called()
        prompt = runner.call_args.kwargs["prompt"]
        self.assertIn("without starting or advancing a broad pipeline", prompt)
        self.assertIn('"route":"property-edit"', prompt)
        self.assertIn('"allowed_stages":["inspect-target"', prompt)
        self.assertIn('"render_allowed":false', prompt)
        self.assertNotIn("Select the narrowest matching pipeline", prompt)

        records = [
            json.loads(line)
            for line in (self.root / "logs" / "audit.jsonl").read_text().splitlines()
        ]
        self.assertEqual("task-preflight-classified", records[0]["event"])
        self.assertEqual("property-edit", records[0]["details"]["route"])
        self.assertEqual(60, records[0]["details"]["budget"]["active_limit_seconds"])


if __name__ == "__main__":
    unittest.main()
