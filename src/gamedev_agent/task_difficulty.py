"""Deterministic task classification and adaptive execution budgets."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .change_impact import (
    IMPACT_SCHEMA_VERSION,
    SAFETY_GATES,
    ChangeDomain,
    infer_change_domains,
)

SCHEMA_VERSION = 1


class DifficultyLevel(StrEnum):
    TRIVIAL = "trivial"
    SMALL = "small"
    STANDARD = "standard"
    COMPLEX = "complex"


class ExecutionRoute(StrEnum):
    QUERY = "query"
    PROPERTY_EDIT = "property-edit"
    STAGED_EDIT = "staged-edit"
    REBUILD = "rebuild"


class ResponseDetail(StrEnum):
    BRIEF = "brief"
    NORMAL = "normal"
    DETAILED = "detailed"


_PROPERTY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "render-resolution",
        (
            "blender.scene.render.resolution_x",
            "blender.scene.render.resolution_y",
        ),
    ),
    ("frame-rate", ("scene.render.fps",)),
    ("exposure", ("scene.view_settings.look", "scene.view_settings.exposure")),
    ("render-engine", ("scene.render.engine",)),
    ("output-format", ("scene.render.image_settings.file_format",)),
    ("sample-count", ("scene.render.samples",)),
    ("scale", ("object.scale",)),
    ("location", ("object.location",)),
    ("rotation", ("object.rotation_euler",)),
    ("roughness", ("material.roughness",)),
    ("color", ("material.base_color",)),
)
_PROPERTY_TERMS: dict[str, tuple[str, ...]] = {
    "render-resolution": ("resolution", "4k", "2k", "1080p", "720p"),
    "frame-rate": ("frame rate", "framerate", "fps"),
    "exposure": ("exposure",),
    "render-engine": ("render engine", "cycles", "eevee"),
    "output-format": ("output format", "file format"),
    "sample-count": ("samples", "sample count"),
    "scale": ("scale", "size"),
    "location": ("location", "position"),
    "rotation": ("rotation", "rotate"),
    "roughness": ("roughness",),
    "color": ("color", "colour"),
}
_MUTATION_TERMS = (
    "change",
    "set",
    "update",
    "edit",
    "reduce",
    "increase",
    "decrease",
    "switch",
    "adjust",
    "make",
)
_QUERY_TERMS = (
    "read",
    "show",
    "list",
    "inspect",
    "report",
    "what",
    "which",
    "where",
    "summarize",
    "summarise",
    "check status",
)
_GENERATION_TERMS = (
    "create",
    "generate",
    "build",
    "regenerate",
    "rebuild",
    "procedural",
    "synthesize",
)
_SIMULATION_TERMS = ("simulate", "simulation", "bake physics", "fluid", "cloth simulation")
_HIGH_DENSITY_TERMS = (
    "high-density",
    "high density",
    "dense forest",
    "thousands of",
    "millions of",
    "large crowd",
)
_BROAD_COMPOSITION_TERMS = (
    "full scene",
    "whole scene",
    "entire scene",
    "environment composition",
    "level composition",
)
_MULTI_OBJECT_TERMS = ("multiple objects", "multi-object", "several objects", "object set")
_BROAD_VALIDATION_TERMS = (
    "broad validation",
    "validate everything",
    "full qa",
    "complete qa",
    "all tests",
)
_MULTI_STAGE_TERMS = (
    " then ",
    "pipeline",
    "export",
    "import",
    "unity",
    "multiple stages",
    "multi-stage",
)
_NO_RENDER_TERMS = ("do not render", "don't render", "without rendering", "no render")
_DEADLINE_PATTERN = re.compile(
    r"(?:within|deadline(?:\s+of|\s*:)?|in)\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>seconds?|secs?|minutes?|mins?)\b"
)


@dataclass(frozen=True)
class TaskState:
    """Normalized state inputs that can affect routing, never authoritative state itself."""

    target_exists: bool = False
    connected_applications: tuple[str, ...] = ()
    active_pipeline: str | None = None
    predicted_startup_seconds: float = 0.0
    predicted_queue_seconds: float = 0.0

    def __post_init__(self) -> None:
        estimates = (self.predicted_startup_seconds, self.predicted_queue_seconds)
        if any(not math.isfinite(value) or value < 0 for value in estimates):
            raise ValueError("startup and queue estimates must be finite and non-negative")
        normalized = tuple(
            sorted({application.strip().casefold() for application in self.connected_applications})
        )
        object.__setattr__(self, "connected_applications", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_exists": self.target_exists,
            "connected_applications": list(self.connected_applications),
            "active_pipeline": self.active_pipeline,
            "predicted_startup_seconds": self.predicted_startup_seconds,
            "predicted_queue_seconds": self.predicted_queue_seconds,
        }


@dataclass(frozen=True)
class TaskOverrides:
    detail: ResponseDetail | None = None
    render_allowed: bool | None = None
    deadline_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.deadline_seconds is not None and (
            not math.isfinite(self.deadline_seconds) or self.deadline_seconds <= 0
        ):
            raise ValueError("deadline_seconds must be finite and positive")


@dataclass(frozen=True)
class ClassificationFactor:
    name: str
    points: int
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "points": self.points, "explanation": self.explanation}


@dataclass(frozen=True)
class StageBudget:
    stage: str
    active_seconds: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.active_seconds) or self.active_seconds < 0:
            raise ValueError("stage active time must be finite and non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "active_seconds": self.active_seconds}


@dataclass(frozen=True)
class ExecutionBudget:
    active_limit_seconds: float | None
    predicted_startup_seconds: float
    predicted_queue_seconds: float
    stages: tuple[StageBudget, ...]
    deadline_seconds: float | None = None
    constrained_by_deadline: bool = False

    def __post_init__(self) -> None:
        estimates = (self.predicted_startup_seconds, self.predicted_queue_seconds)
        if any(not math.isfinite(value) or value < 0 for value in estimates):
            raise ValueError("budget startup and queue values must be finite and non-negative")
        if self.active_limit_seconds is not None and (
            not math.isfinite(self.active_limit_seconds) or self.active_limit_seconds <= 0
        ):
            raise ValueError("active limit must be finite and positive")
        if self.deadline_seconds is not None and (
            not math.isfinite(self.deadline_seconds) or self.deadline_seconds <= 0
        ):
            raise ValueError("budget deadline must be finite and positive")
        names = [stage.stage for stage in self.stages]
        if not names or len(names) != len(set(names)):
            raise ValueError("budget stage names must be present and unique")

    @property
    def predicted_active_seconds(self) -> float:
        return sum(stage.active_seconds for stage in self.stages)

    @property
    def predicted_wall_seconds(self) -> float:
        return (
            self.predicted_queue_seconds
            + self.predicted_startup_seconds
            + self.predicted_active_seconds
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_limit_seconds": self.active_limit_seconds,
            "predicted_active_seconds": self.predicted_active_seconds,
            "predicted_startup_seconds": self.predicted_startup_seconds,
            "predicted_queue_seconds": self.predicted_queue_seconds,
            "predicted_wall_seconds": self.predicted_wall_seconds,
            "deadline_seconds": self.deadline_seconds,
            "constrained_by_deadline": self.constrained_by_deadline,
            "stages": [stage.to_dict() for stage in self.stages],
        }


@dataclass(frozen=True)
class TaskAssessment:
    normalized_request: str
    state_fingerprint: str
    difficulty: DifficultyLevel
    score: int
    factors: tuple[ClassificationFactor, ...]
    route: ExecutionRoute
    response_detail: ResponseDetail
    render_allowed: bool
    target_properties: tuple[str, ...]
    declared_change_domains: tuple[ChangeDomain, ...]
    allowed_stages: tuple[str, ...]
    skipped_stages: tuple[str, ...]
    required_safety_gates: tuple[str, ...]
    budget: ExecutionBudget

    @property
    def fast_path(self) -> bool:
        return self.route in {ExecutionRoute.QUERY, ExecutionRoute.PROPERTY_EDIT}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "normalized_request": self.normalized_request,
            "state_fingerprint": self.state_fingerprint,
            "difficulty": self.difficulty.value,
            "score": self.score,
            "factors": [factor.to_dict() for factor in self.factors],
            "route": self.route.value,
            "fast_path": self.fast_path,
            "response_detail": self.response_detail.value,
            "render_allowed": self.render_allowed,
            "target_properties": list(self.target_properties),
            "change_impact": {
                "schema_version": IMPACT_SCHEMA_VERSION,
                "declared_domains": [domain.value for domain in self.declared_change_domains],
                "observation_required": bool(self.declared_change_domains),
            },
            "allowed_stages": list(self.allowed_stages),
            "skipped_stages": list(self.skipped_stages),
            "required_safety_gates": list(self.required_safety_gates),
            "budget": self.budget.to_dict(),
        }

    def prompt_directive(self) -> str:
        serialized = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return (
            "Python preflight execution contract (authoritative routing policy):\n"
            f"{serialized}\n"
            "Execute only allowed_stages; never execute skipped_stages. Before validating a "
            "mutation, reconcile declared change domains with observed before/after fingerprints "
            "through the Python impact planner; blocked plans cannot pass on stale evidence. "
            "Required safety gates remain mandatory when applicable and may not be bypassed to "
            "meet a deadline."
        )


@dataclass(frozen=True)
class ExecutionTiming:
    active_seconds: float
    startup_seconds: float = 0.0
    queue_seconds: float = 0.0
    stages: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        values = (self.active_seconds, self.startup_seconds, self.queue_seconds)
        stage_values = tuple(value for _, value in self.stages)
        if any(not math.isfinite(value) or value < 0 for value in (*values, *stage_values)):
            raise ValueError("execution timing values must be finite and non-negative")
        names = [name for name, _ in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("execution stage timing names must be unique")


@dataclass(frozen=True)
class BudgetOutcome:
    predicted_active_seconds: float
    active_limit_seconds: float
    actual_active_seconds: float
    actual_startup_seconds: float
    actual_queue_seconds: float
    actual_wall_seconds: float
    active_overrun_seconds: float
    stage_overruns: tuple[tuple[str, float], ...]

    @property
    def overrun(self) -> bool:
        return self.active_overrun_seconds > 0 or bool(self.stage_overruns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "task-budget-evaluated",
            "predicted_active_seconds": self.predicted_active_seconds,
            "active_limit_seconds": self.active_limit_seconds,
            "actual_active_seconds": self.actual_active_seconds,
            "actual_startup_seconds": self.actual_startup_seconds,
            "actual_queue_seconds": self.actual_queue_seconds,
            "actual_wall_seconds": self.actual_wall_seconds,
            "active_overrun_seconds": self.active_overrun_seconds,
            "stage_overruns": [
                {"stage": stage, "overrun_seconds": seconds}
                for stage, seconds in self.stage_overruns
            ],
            "overrun": self.overrun,
        }


def normalize_request(request: str) -> str:
    normalized = " ".join(request.split()).casefold()
    if not normalized:
        raise ValueError("request must not be empty")
    return normalized


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _contains_property_term(text: str, name: str) -> bool:
    return any(
        re.search(rf"(?<!\\w){re.escape(term)}(?!\\w)", text) is not None
        for term in _PROPERTY_TERMS[name]
    )


def _resolve_overrides(text: str, supplied: TaskOverrides | None) -> TaskOverrides:
    detail: ResponseDetail | None = None
    markers = [
        (text.rfind("brief"), ResponseDetail.BRIEF),
        (text.rfind("detailed"), ResponseDetail.DETAILED),
        (text.rfind("in detail"), ResponseDetail.DETAILED),
    ]
    position, inferred_detail = max(markers, key=lambda marker: marker[0])
    if position >= 0:
        detail = inferred_detail

    without_clause = text.split(" without ", 1)[1] if " without " in text else ""
    render_allowed = (
        False if _contains_any(text, _NO_RENDER_TERMS) or "render" in without_clause else None
    )
    deadline_seconds: float | None = None
    deadline = _DEADLINE_PATTERN.search(text)
    if deadline:
        deadline_seconds = float(deadline.group("value"))
        if deadline.group("unit").startswith(("m", "min")):
            deadline_seconds *= 60

    if supplied is not None:
        detail = supplied.detail if supplied.detail is not None else detail
        render_allowed = (
            supplied.render_allowed if supplied.render_allowed is not None else render_allowed
        )
        deadline_seconds = (
            supplied.deadline_seconds if supplied.deadline_seconds is not None else deadline_seconds
        )
    return TaskOverrides(detail, render_allowed, deadline_seconds)


def _property_targets(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    for name, properties in _PROPERTY_PATTERNS:
        if _contains_property_term(text, name):
            targets.extend(properties)
    return tuple(dict.fromkeys(targets))


def _state_fingerprint(normalized_request: str, state: TaskState) -> str:
    payload = json.dumps(
        {"request": normalized_request, "state": state.to_dict()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _difficulty(score: int) -> DifficultyLevel:
    if score <= 1:
        return DifficultyLevel.TRIVIAL
    if score <= 4:
        return DifficultyLevel.SMALL
    if score <= 12:
        return DifficultyLevel.STANDARD
    return DifficultyLevel.COMPLEX


def _stage_plan(
    route: ExecutionRoute,
    difficulty: DifficultyLevel,
    *,
    render_allowed: bool,
    generation: bool,
    simulation: bool,
    final_render: bool,
    broad_validation: bool,
    export_requested: bool,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    expensive = (
        "generation",
        "simulation",
        "preview-render",
        "final-render",
        "export",
        "broad-validation",
    )
    if route is ExecutionRoute.QUERY:
        return ("inspect-authoritative-state", "report"), expensive
    if route is ExecutionRoute.PROPERTY_EDIT:
        return (
            "inspect-target",
            "evaluate-safety-gates",
            "mutate-properties",
            "verify-targeted-properties",
            "persist-authoritative-state",
        ), expensive
    if difficulty is not DifficultyLevel.COMPLEX:
        stages = [
            "plan-local-work",
            "evaluate-safety-gates",
            "apply-staged-edits",
        ]
        if export_requested:
            stages.append("export")
        stages.extend(
            (
                "broad-validation" if broad_validation else "targeted-validation",
                "persist-authoritative-state",
            )
        )
        staged_skipped = ["generation", "simulation", "preview-render", "final-render"]
        if not export_requested:
            staged_skipped.append("export")
        if not broad_validation:
            staged_skipped.append("broad-validation")
        return tuple(stages), tuple(staged_skipped)

    stages = [
        "plan-with-estimates",
        "evaluate-safety-gates",
        "preview-checkpoint",
    ]
    if generation:
        stages.append("generation")
    if simulation:
        stages.append("simulation")
    if final_render and render_allowed:
        stages.append("final-render")
    if export_requested:
        stages.append("export")
    stages.extend(("broad-validation", "persist-authoritative-state"))

    skipped: list[str] = []
    if not generation:
        skipped.append("generation")
    if not simulation:
        skipped.append("simulation")
    if not final_render or not render_allowed:
        skipped.extend(("preview-render", "final-render"))
    if not export_requested:
        skipped.append("export")
    return tuple(stages), tuple(dict.fromkeys(skipped))


def _stage_budgets(
    difficulty: DifficultyLevel, allowed_stages: tuple[str, ...]
) -> tuple[StageBudget, ...]:
    total = {
        DifficultyLevel.TRIVIAL: 60.0,
        DifficultyLevel.SMALL: 180.0,
        DifficultyLevel.STANDARD: 600.0,
    }.get(difficulty)
    if total is not None:
        per_stage = total / len(allowed_stages)
        return tuple(StageBudget(stage, per_stage) for stage in allowed_stages)
    estimates = {
        "plan-with-estimates": 60.0,
        "evaluate-safety-gates": 30.0,
        "preview-checkpoint": 180.0,
        "generation": 600.0,
        "simulation": 600.0,
        "final-render": 900.0,
        "export": 120.0,
        "broad-validation": 300.0,
        "persist-authoritative-state": 30.0,
    }
    return tuple(StageBudget(stage, estimates[stage]) for stage in allowed_stages)


def classify_task(
    request: str,
    *,
    state: TaskState | None = None,
    overrides: TaskOverrides | None = None,
) -> TaskAssessment:
    """Classify normalized request and state using stable, explainable rules."""
    text = normalize_request(request)
    task_state = state or TaskState()
    resolved = _resolve_overrides(text, overrides)
    render_allowed = resolved.render_allowed is not False
    positive_text = text.split(" without ", 1)[0]
    text_without_no_render = positive_text
    for term in _NO_RENDER_TERMS:
        text_without_no_render = text_without_no_render.replace(term, "")

    matched_property_groups = tuple(
        name for name, _ in _PROPERTY_PATTERNS if _contains_property_term(positive_text, name)
    )
    targets = _property_targets(positive_text)
    mutation = _contains_any(positive_text, _MUTATION_TERMS)
    generation = _contains_any(positive_text, _GENERATION_TERMS)
    simulation = _contains_any(positive_text, _SIMULATION_TERMS)
    high_density = _contains_any(positive_text, _HIGH_DENSITY_TERMS)
    broad_composition = _contains_any(positive_text, _BROAD_COMPOSITION_TERMS)
    multi_object = _contains_any(positive_text, _MULTI_OBJECT_TERMS)
    broad_validation = _contains_any(positive_text, _BROAD_VALIDATION_TERMS)
    export_requested = "export" in positive_text
    multi_stage = _contains_any(f" {positive_text} ", _MULTI_STAGE_TERMS)
    final_render = (
        "final render" in text_without_no_render
        or "render animation" in text_without_no_render
        or "render the" in text_without_no_render
    )
    existing_target = task_state.target_exists or _contains_any(
        positive_text, ("existing", "current", "already")
    )
    several_properties = (
        len(matched_property_groups) > 1
        or "several" in positive_text
        or "multiple" in positive_text
    )
    bounded_property = (
        mutation
        and bool(targets)
        and existing_target
        and len(matched_property_groups) == 1
        and not several_properties
        and not generation
        and not simulation
        and not high_density
        and not broad_composition
        and not multi_object
        and not broad_validation
        and not multi_stage
        and not final_render
    )
    read_only = (
        _contains_any(text, _QUERY_TERMS)
        and not mutation
        and not generation
        and not simulation
        and not final_render
    )
    declared_change_domains = () if read_only else infer_change_domains(positive_text)

    factors: list[ClassificationFactor] = []
    if read_only:
        factors.append(ClassificationFactor("read-only-query", 0, "No mutation was requested."))
    elif bounded_property:
        factors.append(
            ClassificationFactor(
                "bounded-property-edit",
                1,
                "One existing target and at most two related properties can be verified directly.",
            )
        )
    else:
        if mutation and (targets or several_properties) and not multi_stage:
            factors.append(
                ClassificationFactor("local-edits", 3, "Several local mutations require checks.")
            )
        if multi_stage:
            factors.append(
                ClassificationFactor("multi-stage", 7, "The request crosses execution stages.")
            )
        if multi_object:
            factors.append(
                ClassificationFactor("multi-object", 4, "Several objects require coordinated work.")
            )
        if broad_composition:
            factors.append(
                ClassificationFactor(
                    "broad-composition", 13, "Broad composition requires preview checkpoints."
                )
            )
        if generation:
            factors.append(
                ClassificationFactor("generation", 13, "Generation requires preview checkpoints.")
            )
        if simulation:
            factors.append(
                ClassificationFactor("simulation", 14, "Simulation requires estimated stage work.")
            )
        if final_render:
            factors.append(
                ClassificationFactor("final-render", 14, "Final rendering is an expensive stage.")
            )
        if high_density:
            factors.append(
                ClassificationFactor(
                    "high-density", 6, "High-density content increases execution cost."
                )
            )
        if broad_validation:
            factors.append(
                ClassificationFactor(
                    "broad-validation", 6, "Broad validation exceeds targeted checks."
                )
            )
        if not factors:
            factors.append(
                ClassificationFactor(
                    "unspecified-work", 5, "The request is not bounded enough for a fast path."
                )
            )

    score = sum(factor.points for factor in factors)
    difficulty = _difficulty(score)
    if read_only:
        route = ExecutionRoute.QUERY
    elif bounded_property:
        route = ExecutionRoute.PROPERTY_EDIT
    elif generation or simulation:
        route = ExecutionRoute.REBUILD
    else:
        route = ExecutionRoute.STAGED_EDIT

    allowed_stages, skipped_stages = _stage_plan(
        route,
        difficulty,
        render_allowed=render_allowed,
        generation=generation,
        simulation=simulation,
        final_render=final_render,
        broad_validation=broad_validation,
        export_requested=export_requested,
    )
    stage_budgets = _stage_budgets(difficulty, allowed_stages)
    default_active_limit = {
        DifficultyLevel.TRIVIAL: 60.0,
        DifficultyLevel.SMALL: 180.0,
        DifficultyLevel.STANDARD: 600.0,
        DifficultyLevel.COMPLEX: None,
    }[difficulty]
    estimated_active = sum(stage.active_seconds for stage in stage_budgets)
    active_limit = default_active_limit
    constrained = False
    if resolved.deadline_seconds is not None:
        active_limit = resolved.deadline_seconds
        constrained = resolved.deadline_seconds < estimated_active

    required_applications: set[str] = set()
    if "blender" in text or targets or generation or final_render:
        required_applications.add("blender")
    if "unity" in text:
        required_applications.add("unity")
    disconnected = required_applications - set(task_state.connected_applications)
    inferred_startup = 30.0 * len(disconnected)
    startup_seconds = max(task_state.predicted_startup_seconds, inferred_startup)
    budget = ExecutionBudget(
        active_limit,
        startup_seconds,
        task_state.predicted_queue_seconds,
        stage_budgets,
        resolved.deadline_seconds,
        constrained,
    )
    return TaskAssessment(
        normalized_request=text,
        state_fingerprint=_state_fingerprint(text, task_state),
        difficulty=difficulty,
        score=score,
        factors=tuple(factors),
        route=route,
        response_detail=resolved.detail or ResponseDetail.NORMAL,
        render_allowed=render_allowed,
        target_properties=targets if bounded_property else (),
        declared_change_domains=declared_change_domains,
        allowed_stages=allowed_stages,
        skipped_stages=skipped_stages,
        required_safety_gates=SAFETY_GATES,
        budget=budget,
    )


def compare_budget(assessment: TaskAssessment, timing: ExecutionTiming) -> BudgetOutcome:
    """Compare active work only; preserve startup and queue as separate evidence."""
    predicted = assessment.budget.predicted_active_seconds
    active_limit = assessment.budget.active_limit_seconds or predicted
    estimates = {stage.stage: stage.active_seconds for stage in assessment.budget.stages}
    stage_overruns = tuple(
        (name, round(actual - estimates[name], 3))
        for name, actual in timing.stages
        if name in estimates and actual > estimates[name]
    )
    return BudgetOutcome(
        predicted_active_seconds=predicted,
        active_limit_seconds=active_limit,
        actual_active_seconds=timing.active_seconds,
        actual_startup_seconds=timing.startup_seconds,
        actual_queue_seconds=timing.queue_seconds,
        actual_wall_seconds=timing.queue_seconds + timing.startup_seconds + timing.active_seconds,
        active_overrun_seconds=round(max(0.0, timing.active_seconds - active_limit), 3),
        stage_overruns=stage_overruns,
    )
