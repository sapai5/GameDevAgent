"""Deterministic change-impact reconciliation and validation routing."""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

IMPACT_SCHEMA_VERSION = 1
MAX_REQUEST_BYTES = 4 * 1024 * 1024
_CHECKSUM_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")

SAFETY_GATES = (
    "license-integrity",
    "provenance-integrity",
    "spatial-integrity",
    "required-approvals",
    "authoritative-state-integrity",
)


class ChangeImpactError(ValueError):
    """Raised when an impact request or graph is malformed."""


class ChangeDomain(StrEnum):
    GEOMETRY_TOPOLOGY = "geometry-topology"
    OBJECT_TRANSFORMS = "object-transforms"
    CAMERA = "camera"
    LIGHTING_WORLD = "lighting-world"
    MATERIALS_TEXTURES = "materials-textures"
    ANIMATION = "animation"
    RENDER_SETTINGS = "render-settings"
    EXPORT_IMPORT = "export-import"
    PROVENANCE_LICENSE = "provenance-license"
    AUTHORITATIVE_STATE = "authoritative-state"
    UNKNOWN = "unknown"


TRACKED_DOMAINS = tuple(domain for domain in ChangeDomain if domain is not ChangeDomain.UNKNOWN)


class ImpactStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ImpactNodeKind(StrEnum):
    STAGE = "stage"
    VALIDATOR = "validator"
    APPROVAL = "approval"
    STATE = "state"
    ARTIFACT = "artifact"
    CACHE = "cache"


class EvidenceOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    CANCELLED = "cancelled"


def fingerprint_value(value: Any) -> str:
    """Return a stable checksum for a JSON-compatible value."""
    try:
        serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as error:
        raise ChangeImpactError(f"value is not canonical JSON: {error}") from error
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_checksum(value: str, field: str) -> None:
    if not _CHECKSUM_PATTERN.fullmatch(value):
        raise ChangeImpactError(f"{field} must be a lowercase sha256 fingerprint")


def _validate_id(value: str, field: str) -> None:
    if not _ID_PATTERN.fullmatch(value):
        raise ChangeImpactError(f"{field} must be a lowercase stable identifier")


def _unique(values: Sequence[Any], field: str) -> None:
    if len(values) != len(set(values)):
        raise ChangeImpactError(f"{field} must contain unique values")


@dataclass(frozen=True, slots=True)
class DomainFingerprint:
    domain: ChangeDomain
    before: str
    after: str

    def __post_init__(self) -> None:
        if self.domain is ChangeDomain.UNKNOWN:
            raise ChangeImpactError("unknown cannot have a domain fingerprint")
        _validate_checksum(self.before, "before")
        _validate_checksum(self.after, "after")

    @property
    def changed(self) -> bool:
        return self.before != self.after

    def to_dict(self) -> dict[str, str]:
        return {"domain": self.domain.value, "before": self.before, "after": self.after}


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    node_id: str
    input_fingerprint: str
    outcome: EvidenceOutcome = EvidenceOutcome.PASS

    def __post_init__(self) -> None:
        _validate_id(self.node_id, "node_id")
        _validate_checksum(self.input_fingerprint, "input_fingerprint")

    def to_dict(self) -> dict[str, str]:
        return {
            "node_id": self.node_id,
            "input_fingerprint": self.input_fingerprint,
            "outcome": self.outcome.value,
        }


@dataclass(frozen=True, slots=True)
class DependencyNode:
    node_id: str
    kind: ImpactNodeKind
    domains: tuple[ChangeDomain, ...]
    input_fingerprint: str

    def __post_init__(self) -> None:
        _validate_id(self.node_id, "dependency node_id")
        if not self.domains:
            raise ChangeImpactError("dependency node domains must not be empty")
        _unique(self.domains, "dependency node domains")
        if ChangeDomain.UNKNOWN in self.domains:
            raise ChangeImpactError("dependency nodes cannot use the unknown domain")
        _validate_checksum(self.input_fingerprint, "dependency input_fingerprint")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "domains": [domain.value for domain in self.domains],
            "input_fingerprint": self.input_fingerprint,
        }


@dataclass(frozen=True, slots=True, order=True)
class DependencyEdge:
    source: str
    target: str

    def __post_init__(self) -> None:
        _validate_id(self.source, "edge source")
        _validate_id(self.target, "edge target")
        if self.source == self.target:
            raise ChangeImpactError(f"dependency graph contains self-cycle at {self.source}")

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target}


@dataclass(frozen=True, slots=True)
class ImpactRequest:
    declared_domains: tuple[ChangeDomain, ...]
    observed_domains: tuple[ChangeDomain, ...]
    fingerprints: tuple[DomainFingerprint, ...]
    prior_evidence: tuple[EvidenceRecord, ...] = ()
    dependency_nodes: tuple[DependencyNode, ...] = ()
    dependency_edges: tuple[DependencyEdge, ...] = ()
    cancelled: bool = False

    def __post_init__(self) -> None:
        _unique(self.declared_domains, "declared_domains")
        _unique(self.observed_domains, "observed_domains")
        _unique(tuple(item.domain for item in self.fingerprints), "fingerprint domains")
        _unique(tuple(item.node_id for item in self.prior_evidence), "prior evidence node_ids")
        _unique(tuple(item.node_id for item in self.dependency_nodes), "dependency node_ids")
        _unique(self.dependency_edges, "dependency_edges")

    @classmethod
    def from_json(cls, serialized: str | bytes, *, max_bytes: int = MAX_REQUEST_BYTES) -> Self:
        raw = serialized.encode("utf-8") if isinstance(serialized, str) else serialized
        if len(raw) > max_bytes:
            raise ChangeImpactError(f"impact request exceeds {max_bytes} bytes")
        try:
            value = json.loads(raw, parse_constant=_reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ChangeImpactError(f"invalid impact request JSON: {error}") from error
        if not isinstance(value, dict):
            raise ChangeImpactError("impact request must contain a JSON object")
        return cls.from_mapping(value)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Self:
        required = {"schema_version", "declared_domains", "observed_domains", "fingerprints"}
        optional = {"prior_evidence", "dependency_nodes", "dependency_edges", "cancelled"}
        unknown = set(value) - required - optional
        missing = required - set(value)
        if unknown:
            raise ChangeImpactError(f"unknown impact request fields: {', '.join(sorted(unknown))}")
        if missing:
            raise ChangeImpactError(f"missing impact request fields: {', '.join(sorted(missing))}")
        if value["schema_version"] != IMPACT_SCHEMA_VERSION:
            raise ChangeImpactError(f"unsupported impact schema version: {value['schema_version']}")
        declared = _parse_domains(value["declared_domains"], "declared_domains")
        observed = _parse_domains(value["observed_domains"], "observed_domains")
        fingerprints = tuple(
            DomainFingerprint(
                _parse_domain(item.get("domain"), "fingerprint domain"),
                _require_string(item.get("before"), "fingerprint before"),
                _require_string(item.get("after"), "fingerprint after"),
            )
            for item in _require_mappings(value["fingerprints"], "fingerprints")
        )
        prior_evidence = tuple(
            EvidenceRecord(
                _require_string(item.get("node_id"), "evidence node_id"),
                _require_string(item.get("input_fingerprint"), "evidence input_fingerprint"),
                _parse_outcome(item.get("outcome", EvidenceOutcome.PASS.value)),
            )
            for item in _require_mappings(value.get("prior_evidence", []), "prior_evidence")
        )
        dependency_nodes = tuple(
            DependencyNode(
                _require_string(item.get("node_id"), "dependency node_id"),
                _parse_kind(item.get("kind")),
                _parse_domains(item.get("domains"), "dependency domains"),
                _require_string(item.get("input_fingerprint"), "dependency input_fingerprint"),
            )
            for item in _require_mappings(value.get("dependency_nodes", []), "dependency_nodes")
        )
        dependency_edges = tuple(
            DependencyEdge(
                _require_string(item.get("source"), "edge source"),
                _require_string(item.get("target"), "edge target"),
            )
            for item in _require_mappings(value.get("dependency_edges", []), "dependency_edges")
        )
        cancelled = value.get("cancelled", False)
        if not isinstance(cancelled, bool):
            raise ChangeImpactError("cancelled must be a boolean")
        return cls(
            declared,
            observed,
            fingerprints,
            prior_evidence,
            dependency_nodes,
            dependency_edges,
            cancelled,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": IMPACT_SCHEMA_VERSION,
            "declared_domains": [domain.value for domain in self.declared_domains],
            "observed_domains": [domain.value for domain in self.observed_domains],
            "fingerprints": [item.to_dict() for item in self.fingerprints],
            "prior_evidence": [item.to_dict() for item in self.prior_evidence],
            "dependency_nodes": [item.to_dict() for item in self.dependency_nodes],
            "dependency_edges": [item.to_dict() for item in self.dependency_edges],
            "cancelled": self.cancelled,
        }


@dataclass(frozen=True, slots=True)
class ImpactNodeSpec:
    node_id: str
    kind: ImpactNodeKind
    trigger_domains: tuple[ChangeDomain, ...] = ()
    depends_on: tuple[str, ...] = ()
    always: bool = False
    conservative_only: bool = False
    reusable: bool = True

    def __post_init__(self) -> None:
        _validate_id(self.node_id, "impact node_id")
        _unique(self.trigger_domains, "impact node trigger_domains")
        _unique(self.depends_on, "impact node depends_on")
        if ChangeDomain.UNKNOWN in self.trigger_domains:
            raise ChangeImpactError("impact nodes cannot use the unknown domain")
        if self.always and self.conservative_only:
            raise ChangeImpactError("impact node cannot be always and conservative-only")


@dataclass(frozen=True, slots=True)
class ImpactDecision:
    node_id: str
    kind: ImpactNodeKind
    reason_code: str
    domains: tuple[ChangeDomain, ...]
    depends_on: tuple[str, ...]
    input_fingerprint: str
    supporting_fingerprints: tuple[DomainFingerprint, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "reason_code": self.reason_code,
            "domains": [domain.value for domain in self.domains],
            "depends_on": list(self.depends_on),
            "input_fingerprint": self.input_fingerprint,
            "supporting_fingerprints": [item.to_dict() for item in self.supporting_fingerprints],
        }


@dataclass(frozen=True, slots=True)
class InvalidationRecord:
    node_id: str
    kind: ImpactNodeKind
    reason_code: str
    input_fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "reason_code": self.reason_code,
            "input_fingerprint": self.input_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class ImpactPlan:
    status: ImpactStatus
    changed_domains: tuple[ChangeDomain, ...]
    selected_nodes: tuple[ImpactDecision, ...]
    skipped_nodes: tuple[ImpactDecision, ...]
    dirty_nodes: tuple[str, ...]
    reusable_evidence: tuple[EvidenceRecord, ...]
    dependency_edges: tuple[DependencyEdge, ...]
    invalidated_evidence: tuple[InvalidationRecord, ...]
    required_safety_gates: tuple[str, ...]
    reason_codes: tuple[str, ...]
    plan_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": IMPACT_SCHEMA_VERSION,
            "status": self.status.value,
            "changed_domains": [domain.value for domain in self.changed_domains],
            "selected_nodes": [item.to_dict() for item in self.selected_nodes],
            "skipped_nodes": [item.to_dict() for item in self.skipped_nodes],
            "dirty_nodes": list(self.dirty_nodes),
            "reusable_evidence": [item.to_dict() for item in self.reusable_evidence],
            "dependency_edges": [item.to_dict() for item in self.dependency_edges],
            "invalidated_evidence": [item.to_dict() for item in self.invalidated_evidence],
            "required_safety_gates": list(self.required_safety_gates),
            "reason_codes": list(self.reason_codes),
            "plan_fingerprint": self.plan_fingerprint,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


_ALL = TRACKED_DOMAINS
_DEFAULT_NODES = (
    ImpactNodeSpec("stage.inspect-target", ImpactNodeKind.STAGE, always=True, reusable=False),
    ImpactNodeSpec(
        "stage.evaluate-safety-gates",
        ImpactNodeKind.STAGE,
        depends_on=("stage.inspect-target",),
        always=True,
        reusable=False,
    ),
    ImpactNodeSpec(
        "stage.apply-change",
        ImpactNodeKind.STAGE,
        _ALL,
        ("stage.evaluate-safety-gates",),
        reusable=False,
    ),
    ImpactNodeSpec("stage.generation", ImpactNodeKind.STAGE, depends_on=("stage.apply-change",)),
    ImpactNodeSpec("stage.render", ImpactNodeKind.STAGE, depends_on=("stage.apply-change",)),
    ImpactNodeSpec(
        "stage.export",
        ImpactNodeKind.STAGE,
        (ChangeDomain.EXPORT_IMPORT,),
        ("stage.apply-change",),
        reusable=False,
    ),
    ImpactNodeSpec(
        "stage.spatial-validation",
        ImpactNodeKind.STAGE,
        (ChangeDomain.GEOMETRY_TOPOLOGY, ChangeDomain.OBJECT_TRANSFORMS),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.render-settings",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.RENDER_SETTINGS,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.color-exposure-clipping-render-state",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.LIGHTING_WORLD,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.configured-visual",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.LIGHTING_WORLD, ChangeDomain.MATERIALS_TEXTURES),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.camera-composition",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.CAMERA,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.terrain-relative-clearance",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.CAMERA,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.grounding-penetration-bounds",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.GEOMETRY_TOPOLOGY, ChangeDomain.OBJECT_TRANSFORMS),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.topology",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.GEOMETRY_TOPOLOGY,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.material-texture",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.MATERIALS_TEXTURES,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.animation-channels-frame-continuity",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.ANIMATION,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.export-import",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.EXPORT_IMPORT,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.provenance-license",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.PROVENANCE_LICENSE,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.authoritative-state",
        ImpactNodeKind.VALIDATOR,
        (ChangeDomain.AUTHORITATIVE_STATE,),
        ("stage.apply-change",),
    ),
    ImpactNodeSpec(
        "validator.conservative-full",
        ImpactNodeKind.VALIDATOR,
        depends_on=("stage.evaluate-safety-gates",),
        conservative_only=True,
        reusable=False,
    ),
    ImpactNodeSpec(
        "approval.required",
        ImpactNodeKind.APPROVAL,
        _ALL,
        ("stage.evaluate-safety-gates",),
        reusable=False,
    ),
    ImpactNodeSpec(
        "state.persist-authoritative",
        ImpactNodeKind.STATE,
        _ALL,
        ("stage.apply-change",),
        reusable=False,
    ),
)

_INVALIDATIONS: dict[ChangeDomain, tuple[tuple[str, ImpactNodeKind], ...]] = {
    ChangeDomain.GEOMETRY_TOPOLOGY: (
        ("validator.grounding-penetration-bounds", ImpactNodeKind.VALIDATOR),
        ("validator.topology", ImpactNodeKind.VALIDATOR),
        ("artifact.export", ImpactNodeKind.ARTIFACT),
        ("cache.render", ImpactNodeKind.CACHE),
    ),
    ChangeDomain.OBJECT_TRANSFORMS: (
        ("validator.grounding-penetration-bounds", ImpactNodeKind.VALIDATOR),
        ("artifact.export", ImpactNodeKind.ARTIFACT),
        ("cache.render", ImpactNodeKind.CACHE),
    ),
    ChangeDomain.CAMERA: (
        ("validator.camera-composition", ImpactNodeKind.VALIDATOR),
        ("validator.terrain-relative-clearance", ImpactNodeKind.VALIDATOR),
        ("cache.render", ImpactNodeKind.CACHE),
    ),
    ChangeDomain.LIGHTING_WORLD: (
        ("validator.color-exposure-clipping-render-state", ImpactNodeKind.VALIDATOR),
        ("validator.configured-visual", ImpactNodeKind.VALIDATOR),
        ("cache.render", ImpactNodeKind.CACHE),
    ),
    ChangeDomain.MATERIALS_TEXTURES: (
        ("validator.material-texture", ImpactNodeKind.VALIDATOR),
        ("validator.configured-visual", ImpactNodeKind.VALIDATOR),
        ("artifact.export", ImpactNodeKind.ARTIFACT),
        ("cache.render", ImpactNodeKind.CACHE),
    ),
    ChangeDomain.ANIMATION: (
        ("validator.animation-channels-frame-continuity", ImpactNodeKind.VALIDATOR),
        ("artifact.export", ImpactNodeKind.ARTIFACT),
        ("cache.render", ImpactNodeKind.CACHE),
    ),
    ChangeDomain.RENDER_SETTINGS: (
        ("validator.render-settings", ImpactNodeKind.VALIDATOR),
        ("cache.render", ImpactNodeKind.CACHE),
    ),
    ChangeDomain.EXPORT_IMPORT: (
        ("validator.export-import", ImpactNodeKind.VALIDATOR),
        ("artifact.export", ImpactNodeKind.ARTIFACT),
    ),
    ChangeDomain.PROVENANCE_LICENSE: (("validator.provenance-license", ImpactNodeKind.VALIDATOR),),
    ChangeDomain.AUTHORITATIVE_STATE: (
        ("validator.authoritative-state", ImpactNodeKind.VALIDATOR),
    ),
}


class ChangeImpactPlanner:
    """Build byte-stable plans from reconciled change evidence."""

    def __init__(self, nodes: Sequence[ImpactNodeSpec] = _DEFAULT_NODES) -> None:
        self.nodes = tuple(sorted(nodes, key=lambda item: item.node_id))
        _validate_impact_graph(self.nodes)

    def plan(self, request: ImpactRequest) -> ImpactPlan:
        fingerprint_by_domain = {item.domain: item for item in request.fingerprints}
        reasons = _reconciliation_reasons(request, fingerprint_by_domain)
        changed_domains = tuple(
            sorted(
                (item.domain for item in request.fingerprints if item.changed),
                key=lambda domain: domain.value,
            )
        )
        status = ImpactStatus.BLOCKED if reasons else ImpactStatus.READY
        if request.cancelled and status is ImpactStatus.READY:
            status = ImpactStatus.CANCELLED
            reasons = ("execution-cancelled",)

        selected, skipped = self._decisions(status, changed_domains, fingerprint_by_domain)
        selected_ids = {item.node_id for item in selected}
        edges = tuple(
            DependencyEdge(source, decision.node_id)
            for decision in selected
            for source in decision.depends_on
            if source in selected_ids
        )
        prior_by_node = {item.node_id: item for item in request.prior_evidence}
        reusable: list[EvidenceRecord] = []
        dirty: list[str] = []
        invalidations = self._invalidations(
            status, changed_domains, selected, request, fingerprint_by_domain
        )
        reusable_ids = {node.node_id for node in self.nodes if node.reusable}
        if status is ImpactStatus.READY:
            for decision in selected:
                prior = prior_by_node.get(decision.node_id)
                if (
                    decision.node_id in reusable_ids
                    and prior is not None
                    and prior.outcome is EvidenceOutcome.PASS
                    and prior.input_fingerprint == decision.input_fingerprint
                ):
                    reusable.append(prior)
                    invalidations.pop(prior.node_id, None)
                else:
                    dirty.append(decision.node_id)
                    if prior is not None:
                        invalidations[prior.node_id] = InvalidationRecord(
                            prior.node_id,
                            decision.kind,
                            "stale-or-failed-evidence",
                            decision.input_fingerprint,
                        )
        elif status is ImpactStatus.BLOCKED:
            dirty.extend(item.node_id for item in selected)
        # A cancelled plan records logical selection but schedules no work.

        dependency_dirty = _dependency_dirty_nodes(
            request.dependency_nodes, request.dependency_edges, changed_domains, status
        )
        for node in dependency_dirty:
            invalidations[node.node_id] = InvalidationRecord(
                node.node_id,
                node.kind,
                "upstream-domain-changed"
                if status is ImpactStatus.READY
                else "reconciliation-blocked",
                node.input_fingerprint,
            )

        body = {
            "schema_version": IMPACT_SCHEMA_VERSION,
            "status": status.value,
            "changed_domains": [domain.value for domain in changed_domains],
            "selected_nodes": [item.to_dict() for item in selected],
            "skipped_nodes": [item.to_dict() for item in skipped],
            "dirty_nodes": sorted(dirty),
            "reusable_evidence": [
                item.to_dict() for item in sorted(reusable, key=lambda x: x.node_id)
            ],
            "dependency_edges": [item.to_dict() for item in sorted(edges)],
            "invalidated_evidence": [
                item.to_dict() for item in sorted(invalidations.values(), key=lambda x: x.node_id)
            ],
            "required_safety_gates": list(SAFETY_GATES),
            "reason_codes": list(reasons),
        }
        plan_fingerprint = fingerprint_value(body)
        return ImpactPlan(
            status,
            changed_domains,
            selected,
            skipped,
            tuple(sorted(dirty)),
            tuple(sorted(reusable, key=lambda item: item.node_id)),
            tuple(sorted(edges)),
            tuple(sorted(invalidations.values(), key=lambda item: item.node_id)),
            SAFETY_GATES,
            reasons,
            plan_fingerprint,
        )

    def _decisions(
        self,
        status: ImpactStatus,
        changed_domains: tuple[ChangeDomain, ...],
        fingerprints: Mapping[ChangeDomain, DomainFingerprint],
    ) -> tuple[tuple[ImpactDecision, ...], tuple[ImpactDecision, ...]]:
        selected_specs: list[ImpactNodeSpec] = []
        skipped_specs: list[ImpactNodeSpec] = []
        changed = set(changed_domains)
        for node in self.nodes:
            if status is ImpactStatus.BLOCKED:
                is_selected = node.always or node.conservative_only
            else:
                is_selected = not node.conservative_only and (
                    node.always or bool(changed.intersection(node.trigger_domains))
                )
            (selected_specs if is_selected else skipped_specs).append(node)
        selected_ids = {node.node_id for node in selected_specs}
        selected = tuple(
            self._decision(
                node,
                "reconciliation-blocked"
                if status is ImpactStatus.BLOCKED and node.conservative_only
                else ("required-control-plane-stage" if node.always else "domain-changed"),
                changed_domains,
                fingerprints,
                selected_ids,
            )
            for node in selected_specs
        )
        skipped = tuple(
            self._decision(
                node,
                "blocked-pending-reconciliation"
                if status is ImpactStatus.BLOCKED
                else (
                    "conservative-route-not-required"
                    if node.conservative_only
                    else "no-relevant-domain-change"
                ),
                changed_domains,
                fingerprints,
                selected_ids,
            )
            for node in skipped_specs
        )
        return selected, skipped

    @staticmethod
    def _decision(
        node: ImpactNodeSpec,
        reason: str,
        changed_domains: tuple[ChangeDomain, ...],
        fingerprints: Mapping[ChangeDomain, DomainFingerprint],
        selected_ids: set[str],
    ) -> ImpactDecision:
        relevant = node.trigger_domains or TRACKED_DOMAINS
        supporting = tuple(
            fingerprints[domain]
            for domain in sorted(relevant, key=lambda item: item.value)
            if domain in fingerprints
        )
        domains = tuple(domain for domain in changed_domains if domain in node.trigger_domains)
        input_fingerprint = fingerprint_value(
            {
                "node_id": node.node_id,
                "fingerprints": [item.to_dict() for item in supporting],
            }
        )
        return ImpactDecision(
            node.node_id,
            node.kind,
            reason,
            domains,
            tuple(dep for dep in node.depends_on if dep in selected_ids),
            input_fingerprint,
            supporting,
        )

    @staticmethod
    def _invalidations(
        status: ImpactStatus,
        changed_domains: tuple[ChangeDomain, ...],
        selected: tuple[ImpactDecision, ...],
        request: ImpactRequest,
        fingerprints: Mapping[ChangeDomain, DomainFingerprint],
    ) -> dict[str, InvalidationRecord]:
        invalidations: dict[str, InvalidationRecord] = {}
        if status is ImpactStatus.BLOCKED:
            for prior in request.prior_evidence:
                invalidations[prior.node_id] = InvalidationRecord(
                    prior.node_id,
                    ImpactNodeKind.VALIDATOR,
                    "reconciliation-blocked",
                    prior.input_fingerprint,
                )
            return invalidations
        selected_by_id = {item.node_id: item for item in selected}
        for domain in changed_domains:
            domain_fingerprint = fingerprints[domain].after
            for node_id, kind in _INVALIDATIONS[domain]:
                expected = selected_by_id.get(node_id)
                invalidations[node_id] = InvalidationRecord(
                    node_id,
                    kind,
                    "domain-changed",
                    expected.input_fingerprint if expected is not None else domain_fingerprint,
                )
        return invalidations


def _reconciliation_reasons(
    request: ImpactRequest,
    fingerprints: Mapping[ChangeDomain, DomainFingerprint],
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if (
        ChangeDomain.UNKNOWN in request.declared_domains
        or ChangeDomain.UNKNOWN in request.observed_domains
    ):
        reasons.add("unknown-change-domain")
    tracked: set[ChangeDomain] = set(TRACKED_DOMAINS)
    missing = tracked - set(fingerprints.keys())
    if missing:
        reasons.add("missing-domain-fingerprints")
    changed = {item.domain for item in request.fingerprints if item.changed}
    declared = set(request.declared_domains) - {ChangeDomain.UNKNOWN}
    observed = set(request.observed_domains) - {ChangeDomain.UNKNOWN}
    if declared != observed:
        reasons.add("declared-observed-mismatch")
    if observed != changed:
        reasons.add("observed-fingerprint-mismatch")
    return tuple(sorted(reasons))


def _validate_impact_graph(nodes: Sequence[ImpactNodeSpec]) -> None:
    ids = tuple(node.node_id for node in nodes)
    _unique(ids, "impact node_ids")
    known = set(ids)
    indegree = {node_id: 0 for node_id in ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for node in nodes:
        for dependency in node.depends_on:
            if dependency not in known:
                raise ChangeImpactError(
                    f"impact node {node.node_id} depends on missing node {dependency}"
                )
            outgoing[dependency].append(node.node_id)
            indegree[node.node_id] += 1
    queue = deque(sorted(node_id for node_id, count in indegree.items() if count == 0))
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        raise ChangeImpactError("impact graph contains a dependency cycle")


def _dependency_dirty_nodes(
    nodes: Sequence[DependencyNode],
    edges: Sequence[DependencyEdge],
    changed_domains: Sequence[ChangeDomain],
    status: ImpactStatus,
) -> tuple[DependencyNode, ...]:
    if not nodes:
        if edges:
            raise ChangeImpactError("dependency edges require dependency nodes")
        return ()
    by_id = {node.node_id: node for node in nodes}
    indegree = {node.node_id: 0 for node in nodes}
    outgoing: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    for edge in edges:
        if edge.source not in by_id or edge.target not in by_id:
            raise ChangeImpactError(
                f"dependency edge references missing node: {edge.source}->{edge.target}"
            )
        outgoing[edge.source].append(edge.target)
        indegree[edge.target] += 1
    queue = deque(node_id for node_id, count in indegree.items() if count == 0)
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        raise ChangeImpactError("dependency graph contains a cycle")

    changed = set(changed_domains)
    dirty = (
        set(by_id)
        if status is ImpactStatus.BLOCKED
        else {node.node_id for node in nodes if changed.intersection(node.domains)}
    )
    queue = deque(sorted(dirty))
    while queue:
        source = queue.popleft()
        for target in outgoing[source]:
            if target not in dirty:
                dirty.add(target)
                queue.append(target)
    return tuple(by_id[node_id] for node_id in sorted(dirty))


def infer_change_domains(request: str) -> tuple[ChangeDomain, ...]:
    """Infer a bounded planned write set; unresolved mutations become unknown."""
    text = " ".join(request.casefold().split())
    matches: set[ChangeDomain] = set()
    patterns: tuple[tuple[ChangeDomain, tuple[str, ...]], ...] = (
        (
            ChangeDomain.RENDER_SETTINGS,
            (
                "resolution",
                "4k",
                "2k",
                "frame rate",
                "framerate",
                "fps",
                "render engine",
                "output format",
                "file format",
                "sample count",
            ),
        ),
        (ChangeDomain.CAMERA, ("camera", "composition", "framing", "field of view", "focal")),
        (
            ChangeDomain.LIGHTING_WORLD,
            ("light", "lighting", "world", "sun", "sky", "exposure", "clipping"),
        ),
        (
            ChangeDomain.MATERIALS_TEXTURES,
            ("material", "texture", "roughness", "base color", "colour", "shader"),
        ),
        (
            ChangeDomain.ANIMATION,
            ("animation", "animate", "keyframe", "frame range", "continuity", "simulate"),
        ),
        (
            ChangeDomain.GEOMETRY_TOPOLOGY,
            ("geometry", "topology", "mesh", "model", "generate", "create", "sculpt"),
        ),
        (
            ChangeDomain.OBJECT_TRANSFORMS,
            ("transform", "location", "position", "rotation", "scale", "move", "ground"),
        ),
        (ChangeDomain.EXPORT_IMPORT, ("export", "import")),
        (ChangeDomain.PROVENANCE_LICENSE, ("provenance", "license", "licence", "source uri")),
        (
            ChangeDomain.AUTHORITATIVE_STATE,
            ("manifest", "authoritative state", "session record", "state record"),
        ),
    )
    for domain, terms in patterns:
        if any(_contains_phrase(text, term) for term in terms):
            matches.add(domain)
    mutation_terms = (
        "add",
        "adjust",
        "change",
        "create",
        "delete",
        "generate",
        "import",
        "move",
        "remove",
        "replace",
        "set",
        "update",
    )
    if not matches and any(_contains_phrase(text, term) for term in mutation_terms):
        matches.add(ChangeDomain.UNKNOWN)
    return tuple(sorted(matches, key=lambda domain: domain.value))


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", text) is not None


def _parse_domains(value: Any, field: str) -> tuple[ChangeDomain, ...]:
    if not isinstance(value, list):
        raise ChangeImpactError(f"{field} must be a JSON array")
    return tuple(_parse_domain(item, field) for item in value)


def _parse_domain(value: Any, field: str) -> ChangeDomain:
    if not isinstance(value, str):
        raise ChangeImpactError(f"{field} must contain strings")
    try:
        return ChangeDomain(value)
    except ValueError as error:
        raise ChangeImpactError(f"unsupported change domain: {value}") from error


def _parse_kind(value: Any) -> ImpactNodeKind:
    if not isinstance(value, str):
        raise ChangeImpactError("dependency kind must be a string")
    try:
        return ImpactNodeKind(value)
    except ValueError as error:
        raise ChangeImpactError(f"unsupported dependency kind: {value}") from error


def _parse_outcome(value: Any) -> EvidenceOutcome:
    if not isinstance(value, str):
        raise ChangeImpactError("evidence outcome must be a string")
    try:
        return EvidenceOutcome(value)
    except ValueError as error:
        raise ChangeImpactError(f"unsupported evidence outcome: {value}") from error


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ChangeImpactError(f"{field} must be a string")
    return value


def _require_mappings(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise ChangeImpactError(f"{field} must be a JSON array")
    result: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ChangeImpactError(f"{field} entries must be JSON objects")
        result.append(item)
    return tuple(result)


def _reject_constant(value: str) -> None:
    raise ChangeImpactError(f"non-finite JSON number is not allowed: {value}")
