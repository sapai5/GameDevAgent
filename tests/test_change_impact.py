from __future__ import annotations

import json
import math
import time
import unittest

from gamedev_agent.change_impact import (
    IMPACT_SCHEMA_VERSION,
    SAFETY_GATES,
    TRACKED_DOMAINS,
    ChangeDomain,
    ChangeImpactError,
    ChangeImpactPlanner,
    DependencyEdge,
    DependencyNode,
    DomainFingerprint,
    EvidenceRecord,
    ImpactNodeKind,
    ImpactNodeSpec,
    ImpactRequest,
    ImpactStatus,
    fingerprint_value,
    infer_change_domains,
)


def _request(
    *changed: ChangeDomain,
    declared: tuple[ChangeDomain, ...] | None = None,
    observed: tuple[ChangeDomain, ...] | None = None,
    prior_evidence: tuple[EvidenceRecord, ...] = (),
    dependency_nodes: tuple[DependencyNode, ...] = (),
    dependency_edges: tuple[DependencyEdge, ...] = (),
    cancelled: bool = False,
    omit: ChangeDomain | None = None,
) -> ImpactRequest:
    changed_set = set(changed)
    fingerprints = tuple(
        DomainFingerprint(
            domain,
            fingerprint_value({"domain": domain.value, "revision": 1}),
            fingerprint_value(
                {"domain": domain.value, "revision": 2 if domain in changed_set else 1}
            ),
        )
        for domain in TRACKED_DOMAINS
        if domain is not omit
    )
    normalized = tuple(sorted(changed_set, key=lambda item: item.value))
    return ImpactRequest(
        normalized if declared is None else declared,
        normalized if observed is None else observed,
        fingerprints,
        prior_evidence,
        dependency_nodes,
        dependency_edges,
        cancelled,
    )


def _selected(plan: object) -> set[str]:
    return {item.node_id for item in plan.selected_nodes}  # type: ignore[attr-defined]


def _skipped(plan: object) -> set[str]:
    return {item.node_id for item in plan.skipped_nodes}  # type: ignore[attr-defined]


def _invalidated(plan: object) -> set[str]:
    return {item.node_id for item in plan.invalidated_evidence}  # type: ignore[attr-defined]


class ChangeImpactRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = ChangeImpactPlanner()

    def test_identical_normalized_evidence_produces_byte_stable_plan(self) -> None:
        request = _request(ChangeDomain.RENDER_SETTINGS)
        first = self.planner.plan(request)
        second = self.planner.plan(ImpactRequest.from_json(json.dumps(request.to_dict())))

        self.assertEqual(first, second)
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(
            first.plan_fingerprint,
            fingerprint_value(
                {key: value for key, value in first.to_dict().items() if key != "plan_fingerprint"}
            ),
        )
        self.assertEqual(IMPACT_SCHEMA_VERSION, json.loads(first.to_json())["schema_version"])

    def test_render_settings_only_selects_targeted_verification(self) -> None:
        plan = self.planner.plan(_request(ChangeDomain.RENDER_SETTINGS))

        self.assertEqual(ImpactStatus.READY, plan.status)
        self.assertIn("validator.render-settings", _selected(plan))
        self.assertTrue(
            {
                "stage.generation",
                "stage.render",
                "stage.export",
                "stage.spatial-validation",
                "validator.grounding-penetration-bounds",
            }.issubset(_skipped(plan))
        )
        self.assertEqual({"validator.render-settings", "cache.render"}, _invalidated(plan))

    def test_lighting_only_skips_spatial_and_geometry_validation(self) -> None:
        plan = self.planner.plan(_request(ChangeDomain.LIGHTING_WORLD))

        self.assertTrue(
            {
                "validator.color-exposure-clipping-render-state",
                "validator.configured-visual",
            }.issubset(_selected(plan))
        )
        self.assertTrue(
            {
                "stage.spatial-validation",
                "validator.grounding-penetration-bounds",
                "validator.topology",
            }.issubset(_skipped(plan))
        )
        self.assertEqual(
            {
                "validator.color-exposure-clipping-render-state",
                "validator.configured-visual",
                "cache.render",
            },
            _invalidated(plan),
        )

    def test_camera_only_selects_composition_and_local_clearance(self) -> None:
        plan = self.planner.plan(_request(ChangeDomain.CAMERA))

        self.assertTrue(
            {
                "validator.camera-composition",
                "validator.terrain-relative-clearance",
            }.issubset(_selected(plan))
        )
        self.assertTrue(
            {
                "stage.generation",
                "stage.spatial-validation",
                "validator.topology",
                "validator.material-texture",
            }.issubset(_skipped(plan))
        )
        self.assertEqual(
            {
                "validator.camera-composition",
                "validator.terrain-relative-clearance",
                "cache.render",
            },
            _invalidated(plan),
        )

    def test_exact_geometry_transform_material_animation_and_export_invalidations(self) -> None:
        cases = {
            ChangeDomain.GEOMETRY_TOPOLOGY: {
                "validator.grounding-penetration-bounds",
                "validator.topology",
                "artifact.export",
                "cache.render",
            },
            ChangeDomain.OBJECT_TRANSFORMS: {
                "validator.grounding-penetration-bounds",
                "artifact.export",
                "cache.render",
            },
            ChangeDomain.MATERIALS_TEXTURES: {
                "validator.material-texture",
                "validator.configured-visual",
                "artifact.export",
                "cache.render",
            },
            ChangeDomain.ANIMATION: {
                "validator.animation-channels-frame-continuity",
                "artifact.export",
                "cache.render",
            },
            ChangeDomain.EXPORT_IMPORT: {
                "validator.export-import",
                "artifact.export",
            },
        }
        for domain, expected in cases.items():
            with self.subTest(domain=domain):
                plan = self.planner.plan(_request(domain))
                self.assertEqual(expected, _invalidated(plan))

    def test_provenance_and_state_domains_keep_safety_and_state_gates(self) -> None:
        plan = self.planner.plan(
            _request(ChangeDomain.PROVENANCE_LICENSE, ChangeDomain.AUTHORITATIVE_STATE)
        )

        self.assertEqual(SAFETY_GATES, plan.required_safety_gates)
        self.assertTrue(
            {
                "validator.provenance-license",
                "validator.authoritative-state",
                "approval.required",
                "state.persist-authoritative",
            }.issubset(_selected(plan))
        )

    def test_multi_domain_change_is_the_union_of_targeted_routes(self) -> None:
        plan = self.planner.plan(_request(ChangeDomain.CAMERA, ChangeDomain.MATERIALS_TEXTURES))

        self.assertTrue(
            {
                "validator.camera-composition",
                "validator.terrain-relative-clearance",
                "validator.material-texture",
                "validator.configured-visual",
            }.issubset(_selected(plan))
        )
        self.assertNotIn("validator.topology", _selected(plan))

    def test_declared_observed_conflict_blocks_and_invalidates_prior_evidence(self) -> None:
        prior = EvidenceRecord("validator.render-settings", fingerprint_value("prior"))
        request = _request(
            ChangeDomain.LIGHTING_WORLD,
            declared=(ChangeDomain.RENDER_SETTINGS,),
            observed=(ChangeDomain.LIGHTING_WORLD,),
            prior_evidence=(prior,),
        )
        plan = self.planner.plan(request)

        self.assertEqual(ImpactStatus.BLOCKED, plan.status)
        self.assertIn("declared-observed-mismatch", plan.reason_codes)
        self.assertIn("validator.conservative-full", _selected(plan))
        self.assertIn("validator.render-settings", _invalidated(plan))
        self.assertNotIn("stage.apply-change", _selected(plan))

    def test_missing_fingerprint_and_unknown_domain_fail_closed(self) -> None:
        missing = self.planner.plan(
            _request(ChangeDomain.CAMERA, omit=ChangeDomain.GEOMETRY_TOPOLOGY)
        )
        unknown = self.planner.plan(
            _request(
                declared=(ChangeDomain.UNKNOWN,),
                observed=(ChangeDomain.UNKNOWN,),
            )
        )

        self.assertEqual(ImpactStatus.BLOCKED, missing.status)
        self.assertIn("missing-domain-fingerprints", missing.reason_codes)
        self.assertEqual(ImpactStatus.BLOCKED, unknown.status)
        self.assertIn("unknown-change-domain", unknown.reason_codes)

    def test_observed_domain_must_match_before_after_changes(self) -> None:
        plan = self.planner.plan(
            _request(
                ChangeDomain.RENDER_SETTINGS,
                declared=(ChangeDomain.RENDER_SETTINGS,),
                observed=(),
            )
        )

        self.assertEqual(ImpactStatus.BLOCKED, plan.status)
        self.assertIn("observed-fingerprint-mismatch", plan.reason_codes)

    def test_resume_reuses_only_checksum_matched_pass_evidence(self) -> None:
        first = self.planner.plan(_request(ChangeDomain.CAMERA))
        decision = next(
            item for item in first.selected_nodes if item.node_id == "validator.camera-composition"
        )
        reusable = EvidenceRecord(decision.node_id, decision.input_fingerprint)
        resumed = self.planner.plan(_request(ChangeDomain.CAMERA, prior_evidence=(reusable,)))
        stale = EvidenceRecord(decision.node_id, fingerprint_value("stale"))
        rerun = self.planner.plan(_request(ChangeDomain.CAMERA, prior_evidence=(stale,)))

        self.assertIn(reusable, resumed.reusable_evidence)
        self.assertNotIn(decision.node_id, resumed.dirty_nodes)
        self.assertNotIn(decision.node_id, _invalidated(resumed))
        self.assertIn(decision.node_id, rerun.dirty_nodes)
        self.assertIn(decision.node_id, _invalidated(rerun))

    def test_cancelled_plan_is_auditable_and_schedules_no_dirty_nodes(self) -> None:
        plan = self.planner.plan(_request(ChangeDomain.ANIMATION, cancelled=True))

        self.assertEqual(ImpactStatus.CANCELLED, plan.status)
        self.assertEqual(("execution-cancelled",), plan.reason_codes)
        self.assertEqual((), plan.dirty_nodes)
        self.assertIn("validator.animation-channels-frame-continuity", _selected(plan))

    def test_every_skipped_node_has_reason_and_supporting_fingerprints(self) -> None:
        plan = self.planner.plan(_request(ChangeDomain.LIGHTING_WORLD))

        for decision in plan.skipped_nodes:
            self.assertTrue(decision.reason_code, decision.node_id)
            self.assertTrue(decision.supporting_fingerprints, decision.node_id)
            self.assertTrue(decision.input_fingerprint.startswith("sha256:"))


class ChangeImpactGraphTests(unittest.TestCase):
    def test_dependency_graph_propagates_dirty_nodes(self) -> None:
        nodes = (
            DependencyNode(
                "artifact.source",
                ImpactNodeKind.ARTIFACT,
                (ChangeDomain.GEOMETRY_TOPOLOGY,),
                fingerprint_value("source"),
            ),
            DependencyNode(
                "artifact.exported",
                ImpactNodeKind.ARTIFACT,
                (ChangeDomain.EXPORT_IMPORT,),
                fingerprint_value("exported"),
            ),
            DependencyNode(
                "cache.preview",
                ImpactNodeKind.CACHE,
                (ChangeDomain.RENDER_SETTINGS,),
                fingerprint_value("preview"),
            ),
        )
        edges = (
            DependencyEdge("artifact.source", "artifact.exported"),
            DependencyEdge("artifact.exported", "cache.preview"),
        )
        plan = ChangeImpactPlanner().plan(
            _request(
                ChangeDomain.GEOMETRY_TOPOLOGY,
                dependency_nodes=nodes,
                dependency_edges=edges,
            )
        )

        self.assertTrue({node.node_id for node in nodes}.issubset(_invalidated(plan)))

    def test_rejects_cycles_and_missing_dependency_nodes(self) -> None:
        node_a = DependencyNode(
            "artifact.a",
            ImpactNodeKind.ARTIFACT,
            (ChangeDomain.GEOMETRY_TOPOLOGY,),
            fingerprint_value("a"),
        )
        node_b = DependencyNode(
            "artifact.b",
            ImpactNodeKind.ARTIFACT,
            (ChangeDomain.EXPORT_IMPORT,),
            fingerprint_value("b"),
        )
        with self.assertRaisesRegex(ChangeImpactError, "cycle"):
            ChangeImpactPlanner().plan(
                _request(
                    ChangeDomain.GEOMETRY_TOPOLOGY,
                    dependency_nodes=(node_a, node_b),
                    dependency_edges=(
                        DependencyEdge("artifact.a", "artifact.b"),
                        DependencyEdge("artifact.b", "artifact.a"),
                    ),
                )
            )
        with self.assertRaisesRegex(ChangeImpactError, "missing node"):
            ChangeImpactPlanner().plan(
                _request(
                    ChangeDomain.GEOMETRY_TOPOLOGY,
                    dependency_nodes=(node_a,),
                    dependency_edges=(DependencyEdge("artifact.a", "artifact.missing"),),
                )
            )

    def test_rejects_cycles_in_validation_policy(self) -> None:
        with self.assertRaisesRegex(ChangeImpactError, "cycle"):
            ChangeImpactPlanner(
                (
                    ImpactNodeSpec(
                        "validator.a", ImpactNodeKind.VALIDATOR, depends_on=("validator.b",)
                    ),
                    ImpactNodeSpec(
                        "validator.b", ImpactNodeKind.VALIDATOR, depends_on=("validator.a",)
                    ),
                )
            )

    def test_one_thousand_nodes_and_ten_thousand_edges_stay_under_p95_ceiling(self) -> None:
        nodes = tuple(
            DependencyNode(
                f"artifact.node-{index:04d}",
                ImpactNodeKind.ARTIFACT,
                (ChangeDomain.GEOMETRY_TOPOLOGY if index == 0 else ChangeDomain.EXPORT_IMPORT,),
                fingerprint_value(index),
            )
            for index in range(1_000)
        )
        edge_pairs = {(index, index + 1) for index in range(999)}
        gap = 2
        while len(edge_pairs) < 10_000:
            for source in range(1_000 - gap):
                edge_pairs.add((source, source + gap))
                if len(edge_pairs) == 10_000:
                    break
            gap += 1
        edges = tuple(
            DependencyEdge(f"artifact.node-{source:04d}", f"artifact.node-{target:04d}")
            for source, target in sorted(edge_pairs)
        )
        request = _request(
            ChangeDomain.GEOMETRY_TOPOLOGY,
            dependency_nodes=nodes,
            dependency_edges=edges,
        )
        planner = ChangeImpactPlanner()
        planner.plan(request)
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            plan = planner.plan(request)
            samples.append(time.perf_counter() - started)

        p95 = sorted(samples)[math.ceil(len(samples) * 0.95) - 1]
        self.assertEqual(1_000, len(nodes))
        self.assertEqual(10_000, len(edges))
        self.assertEqual(
            1_000,
            len(
                [
                    item
                    for item in plan.invalidated_evidence
                    if item.node_id.startswith("artifact.node-")
                ]
            ),
        )
        self.assertLess(p95, 0.100, f"p95 was {p95:.6f}s")


class ChangeImpactContractTests(unittest.TestCase):
    def test_infers_initial_bounded_write_sets(self) -> None:
        self.assertEqual(
            (ChangeDomain.RENDER_SETTINGS,),
            infer_change_domains("Change the existing resolution from 4K to 2K"),
        )
        self.assertEqual(
            (ChangeDomain.CAMERA,),
            infer_change_domains("Adjust the camera composition"),
        )
        self.assertEqual(
            (ChangeDomain.UNKNOWN,),
            infer_change_domains("Update the existing thing"),
        )

    def test_request_rejects_unknown_fields_versions_and_bad_fingerprints(self) -> None:
        value = _request(ChangeDomain.CAMERA).to_dict()
        with self.assertRaisesRegex(ChangeImpactError, "unknown impact request fields"):
            ImpactRequest.from_mapping({**value, "unexpected": True})
        with self.assertRaisesRegex(ChangeImpactError, "unsupported impact schema version"):
            ImpactRequest.from_mapping({**value, "schema_version": 2})
        value["fingerprints"][0]["before"] = "not-a-checksum"
        with self.assertRaisesRegex(ChangeImpactError, "sha256"):
            ImpactRequest.from_mapping(value)


if __name__ == "__main__":
    unittest.main()
