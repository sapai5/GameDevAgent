"""Command-line interface for persistent GameDevAgent projects."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, cast

from . import __version__
from .evals import EvaluationRunner
from .mcp import HttpJsonRpcTransport, McpAdapter, McpError
from .permissions import ApprovalStore
from .pipelines import PipelineCatalog, PipelineCoordinator, current_stage
from .runtime import Client, install_agents, run_agent
from .state import ManifestStore, SessionStore
from .storage import StateError
from .task_difficulty import ResponseDetail, TaskOverrides, TaskState, classify_task
from .telemetry import AuditLogger, UsageTracker


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "pipelines").is_dir():
            return candidate
    return current


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return seconds


def _load_config(root: Path) -> dict[str, Any]:
    path = root / "gamedev.json"
    if not path.exists():
        return {"mcp": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StateError("gamedev.json must contain a JSON object")
    return value


def command_init(args: argparse.Namespace, root: Path) -> int:
    manifest = ManifestStore(root).initialize(args.name)
    (root / "state" / "sessions").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    AuditLogger(root).record(event="project-initialized", actor=args.actor)
    _json({"project": manifest["project"], "manifest": "state/manifest.json"})
    return 0


def command_status(args: argparse.Namespace, root: Path) -> int:
    manifest = ManifestStore(root).read()
    response: dict[str, Any] = {
        "project": manifest["project"],
        "assets": len(manifest["assets"]),
        "licenses_verified": sum(
            1 for asset in manifest["assets"] if asset["license"].get("verified")
        ),
        "pipeline": None,
    }
    try:
        session = SessionStore(root).latest_active()
        stage = current_stage(session)
        response["pipeline"] = {
            "session_id": session["id"],
            "name": session["pipeline"],
            "status": session["status"],
            "stage": stage["id"],
            "agent": stage["agent"],
        }
    except StateError:
        pass
    _json(response)
    return 0


def command_manifest(args: argparse.Namespace, root: Path) -> int:
    manifest = ManifestStore(root).read()
    rendered = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    else:
        print(rendered, end="")
    return 0


def command_resume(args: argparse.Namespace, root: Path) -> int:
    session = PipelineCoordinator(root).resume(args.session)
    stage = current_stage(session)
    _json(
        {
            "session_id": session["id"],
            "pipeline": session["pipeline"],
            "status": session["status"],
            "next_stage": stage["id"],
            "agent": stage["agent"],
            "instructions": stage.get("instructions"),
            "attempts": stage["attempts"],
        }
    )
    return 0


def command_doctor(args: argparse.Namespace, root: Path) -> int:
    config = _load_config(root)
    configured = config.get("mcp", {})
    results: list[dict[str, Any]] = []
    failed = False
    for name in ("blender", "unity"):
        endpoint = os.environ.get(f"GAMEDEV_{name.upper()}_MCP_URL")
        if endpoint is None and isinstance(configured, dict):
            server = configured.get(name, {})
            if isinstance(server, dict):
                endpoint = server.get("url")
        if not endpoint:
            failed = True
            results.append(
                {
                    "server": name,
                    "status": "unconfigured",
                    "hint": f"set GAMEDEV_{name.upper()}_MCP_URL or gamedev.json mcp.{name}.url",
                }
            )
            continue
        try:
            tools = McpAdapter(
                name,
                HttpJsonRpcTransport(str(endpoint), timeout_seconds=args.timeout),
                max_attempts=1,
            ).health()
            results.append({"server": name, "status": "ok", "endpoint": endpoint, "result": tools})
        except McpError as error:
            failed = True
            results.append(
                {"server": name, "status": "unavailable", "endpoint": endpoint, "error": str(error)}
            )
    _json({"ok": not failed, "checks": results})
    return 1 if failed else 0


def command_asset_add(args: argparse.Namespace, root: Path) -> int:
    asset = ManifestStore(root).register_asset(
        asset_id=args.id,
        name=args.name,
        kind=args.kind,
        source_type=args.source_type,
        source_uri=args.source_uri,
        license_spdx=args.license,
        license_url=args.license_url,
        license_verified=args.license_verified,
        actor=args.actor,
        blender_file=args.blender_file,
        export_file=args.export_file,
        unity_path=args.unity_path,
    )
    AuditLogger(root).record(
        event="asset-registered", actor=args.actor, details={"asset_id": args.id}
    )
    _json(asset)
    return 0


def command_asset_update(args: argparse.Namespace, root: Path) -> int:
    asset = ManifestStore(root).update_asset(
        asset_id=args.id,
        actor=args.actor,
        blender_file=args.blender_file,
        export_file=args.export_file,
        unity_path=args.unity_path,
        license_spdx=args.license,
        license_url=args.license_url,
        license_verified=args.license_verified,
    )
    AuditLogger(root).record(event="asset-updated", actor=args.actor, details={"asset_id": args.id})
    _json(asset)
    return 0


def command_asset_checksum(args: argparse.Namespace, root: Path) -> int:
    asset = ManifestStore(root).refresh_checksum(args.id, args.actor)
    AuditLogger(root).record(
        event="asset-checksum-refreshed", actor=args.actor, details={"asset_id": args.id}
    )
    _json(asset)
    return 0


def command_pipeline_list(args: argparse.Namespace, root: Path) -> int:
    _json({"pipelines": PipelineCatalog(root).names()})
    return 0


def command_pipeline_start(args: argparse.Namespace, root: Path) -> int:
    session = PipelineCoordinator(root).start(args.name)
    AuditLogger(root).record(
        event="pipeline-started",
        actor=args.actor,
        session_id=session["id"],
        details={"pipeline": args.name},
    )
    _json(session)
    return 0


def command_pipeline_advance(args: argparse.Namespace, root: Path) -> int:
    session = PipelineCoordinator(root).advance(args.session, args.actor)
    AuditLogger(root).record(event="pipeline-advanced", actor=args.actor, session_id=args.session)
    _json(session)
    return 0


def command_approve(args: argparse.Namespace, root: Path) -> int:
    approval = ApprovalStore(root).issue(
        operation=args.operation,
        resource=args.resource,
        actor=args.actor,
        ttl_minutes=args.ttl_minutes,
    )
    AuditLogger(root).record(
        event="approval-issued",
        actor=args.actor,
        details={
            "approval_id": approval["id"],
            "operation": args.operation,
            "resource": args.resource,
        },
    )
    _json(approval)
    return 0


def command_usage_record(args: argparse.Namespace, root: Path) -> int:
    result = UsageTracker(root).record(
        agent=args.agent,
        turns=args.turns,
        cost_usd=args.cost_usd,
        session_id=args.session,
        model=args.model,
    )
    _json(result)
    return 0


def command_usage_summary(args: argparse.Namespace, root: Path) -> int:
    _json(UsageTracker(root).summary())
    return 0


def command_eval(args: argparse.Namespace, root: Path) -> int:
    report = EvaluationRunner(root).run(case_id=args.case)
    _json(report)
    return 0 if report["failed"] == 0 else 1


def command_agents_install(args: argparse.Namespace, root: Path) -> int:
    clients = ("kiro", "claude") if args.client == "all" else (args.client,)
    installed = {
        client: [
            path.relative_to(root).as_posix() for path in install_agents(root, cast(Client, client))
        ]
        for client in clients
    }
    _json({"installed": installed})
    return 0


def command_run(args: argparse.Namespace, root: Path) -> int:
    manifest = ManifestStore(root).initialize()
    coordinator = PipelineCoordinator(root)
    active_session: dict[str, Any] | None = None
    try:
        active_session = coordinator.resume()
    except StateError as error:
        if "no resumable pipeline" not in str(error) and "no pipeline sessions" not in str(error):
            raise

    overrides = TaskOverrides(
        detail=ResponseDetail(args.detail) if args.detail else None,
        render_allowed=False if args.no_render else None,
        deadline_seconds=args.deadline_seconds,
    )
    assessment = classify_task(
        args.request,
        state=TaskState(
            target_exists=bool(manifest.get("assets")),
            active_pipeline=(
                str(active_session["pipeline"]) if active_session is not None else None
            ),
        ),
        overrides=overrides,
    )
    AuditLogger(root).record(
        event="task-preflight-classified",
        actor="project-manager",
        session_id=(str(active_session["id"]) if active_session is not None else None),
        details=assessment.to_dict(),
    )

    session: dict[str, Any] | None = None
    if not assessment.fast_path or args.pipeline:
        if active_session is not None:
            if args.pipeline and active_session["pipeline"] != args.pipeline:
                message = (
                    f"active pipeline {active_session['pipeline']} must be completed or failed "
                    f"before {args.pipeline}"
                )
                raise StateError(message)
            session = active_session
        elif args.pipeline:
            session = coordinator.start(args.pipeline)

    install_agents(root, args.client)
    if assessment.fast_path and not args.pipeline:
        session_context = (
            "Use the classified fast path without starting or advancing a broad pipeline. "
            "Inspect authoritative state first and persist any applicable state evidence after "
            "the targeted verification."
        )
    elif session:
        session_context = (
            f"Resume GameDev session {session['id']} for {session['pipeline']}. "
            f"Current stage: {current_stage(session)['id']}."
        )
    else:
        session_context = (
            "Select the narrowest matching pipeline and start it with the gamedev CLI before work."
        )
    execution_instruction = (
        "Execute only the preflight contract's allowed stages and return concise evidence."
        if assessment.fast_path and not args.pipeline
        else (
            "Use the installed narrow agents and relevant pipeline SOP. Keep state/manifest.json "
            "and session progress current. Do not merely describe a plan: execute each available "
            "stage, stopping only for a required human decision or unavailable application."
        )
    )
    request = (
        f"Project root: {root}\n"
        f"{session_context}\n"
        f"User request: {args.request}\n\n"
        f"{assessment.prompt_directive()}\n\n"
        "Act as the project-manager orchestrator. "
        f"{execution_instruction}"
    )
    trusted_tools = (
        [item.strip() for item in args.trust_tools.split(",") if item.strip()]
        if args.trust_tools
        else None
    )
    result = run_agent(
        root,
        prompt=request,
        agent="project-manager",
        client=args.client,
        headless=args.headless,
        trusted_tools=trusted_tools,
    )
    if args.headless:
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gamedev")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--project", type=Path, help="project root; defaults to auto-detection")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="initialize persistent project state")
    init.add_argument("--name")
    init.add_argument("--actor", default="project-manager")
    init.set_defaults(handler=command_init)

    status = commands.add_parser("status", help="show manifest and current pipeline stage")
    status.set_defaults(handler=command_status)

    resume = commands.add_parser("resume", help="show the next step for an interrupted pipeline")
    resume.add_argument("--session")
    resume.set_defaults(handler=command_resume)

    doctor = commands.add_parser("doctor", help="check Blender and Unity MCP reachability")
    doctor.add_argument("--timeout", type=float, default=2.0)
    doctor.set_defaults(handler=command_doctor)

    manifest = commands.add_parser("manifest", help="inspect or export the asset manifest")
    manifest.add_argument("--output")
    manifest.set_defaults(handler=command_manifest)

    evaluate = commands.add_parser("eval", help="run deterministic regression evaluations")
    evaluate.add_argument("--case")
    evaluate.set_defaults(handler=command_eval)

    run = commands.add_parser("run", help="execute a request through the project-manager agent")
    run.add_argument("request", help="the game-development outcome to create")
    run.add_argument(
        "--client",
        choices=["kiro", "claude"],
        default="kiro",
        help="agent client to run; defaults to kiro",
    )
    run.add_argument(
        "--pipeline",
        choices=["pipeline-scene-to-unity", "pipeline-prop-kit", "pipeline-vertical-slice"],
    )
    run.add_argument(
        "--detail",
        choices=["brief", "normal", "detailed"],
        help="override response detail without changing required safety work",
    )
    run.add_argument(
        "--deadline-seconds",
        type=_positive_seconds,
        help="active execution deadline; startup and queue time remain separate",
    )
    run.add_argument(
        "--no-render",
        action="store_true",
        help="forbid preview and final render stages",
    )
    run.add_argument("--headless", action="store_true", help="run without interactive approvals")
    run.add_argument(
        "--trust-tools",
        help="comma-separated tools trusted in headless mode; no trust is added by default",
    )
    run.set_defaults(handler=command_run)

    agents = commands.add_parser("agents", help="install repository specs for supported clients")
    agent_commands = agents.add_subparsers(dest="agents_command", required=True)
    install = agent_commands.add_parser("install")
    install.add_argument(
        "--client",
        choices=["kiro", "claude", "all"],
        default="kiro",
        help="client adapter to generate; defaults to kiro",
    )
    install.set_defaults(handler=command_agents_install)

    asset = commands.add_parser("asset", help="manage traceable assets")
    asset_commands = asset.add_subparsers(dest="asset_command", required=True)
    add = asset_commands.add_parser("add")
    add.add_argument("--id", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--kind", required=True)
    add.add_argument(
        "--source-type",
        choices=["hand-modeled", "researched", "generated"],
        required=True,
    )
    add.add_argument("--source-uri")
    add.add_argument("--license", required=True, help="SPDX identifier or LicenseRef-* value")
    add.add_argument("--license-url")
    add.add_argument("--license-verified", action="store_true")
    add.add_argument("--actor", required=True)
    add.add_argument("--blender-file")
    add.add_argument("--export-file")
    add.add_argument("--unity-path")
    add.set_defaults(handler=command_asset_add)
    update = asset_commands.add_parser("update")
    update.add_argument("--id", required=True)
    update.add_argument("--actor", required=True)
    update.add_argument("--blender-file")
    update.add_argument("--export-file")
    update.add_argument("--unity-path")
    update.add_argument("--license", help="SPDX identifier or LicenseRef-* value")
    update.add_argument("--license-url")
    update.add_argument(
        "--license-verified",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    update.set_defaults(handler=command_asset_update)
    checksum = asset_commands.add_parser("checksum")
    checksum.add_argument("--id", required=True)
    checksum.add_argument("--actor", required=True)
    checksum.set_defaults(handler=command_asset_checksum)

    pipeline = commands.add_parser("pipeline", help="manage persistent pipelines")
    pipeline_commands = pipeline.add_subparsers(dest="pipeline_command", required=True)
    listing = pipeline_commands.add_parser("list")
    listing.set_defaults(handler=command_pipeline_list)
    start = pipeline_commands.add_parser("start")
    start.add_argument("name")
    start.add_argument("--actor", default="project-manager")
    start.set_defaults(handler=command_pipeline_start)
    advance = pipeline_commands.add_parser("advance")
    advance.add_argument("--session", required=True)
    advance.add_argument("--actor", required=True)
    advance.set_defaults(handler=command_pipeline_advance)

    approve = commands.add_parser("approve", help="issue an expiring one-time safety approval")
    approve.add_argument("--operation", required=True)
    approve.add_argument("--resource", required=True)
    approve.add_argument("--actor", required=True)
    approve.add_argument("--ttl-minutes", type=int, default=15)
    approve.set_defaults(handler=command_approve)

    usage = commands.add_parser("usage", help="record and summarize agent ResultMessage usage")
    usage_commands = usage.add_subparsers(dest="usage_command", required=True)
    record = usage_commands.add_parser("record")
    record.add_argument("--agent", required=True)
    record.add_argument("--turns", type=int, required=True)
    record.add_argument("--cost-usd", type=float, required=True)
    record.add_argument("--session")
    record.add_argument("--model")
    record.set_defaults(handler=command_usage_record)
    summary = usage_commands.add_parser("summary")
    summary.set_defaults(handler=command_usage_summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = (args.project or find_project_root(Path.cwd())).resolve()
    try:
        return int(args.handler(args, root))
    except (StateError, McpError, json.JSONDecodeError, OSError) as error:
        print(f"gamedev: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
