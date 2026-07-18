"""Project manifest and resumable pipeline session state."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from .storage import JsonObject, JsonStore, StateError

MANIFEST_SCHEMA_VERSION = 1
SESSION_SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def project_path(root: Path, value: str | None) -> str | None:
    """Return a normalized project-relative path and reject path traversal."""
    if value is None:
        return None
    candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        return candidate.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise StateError(f"path must remain within project root: {value}") from error


def sha256_file(root: Path, relative_path: str | None) -> str | None:
    if relative_path is None:
        return None
    path = root / relative_path
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


class ManifestStore:
    """Own the versioned, auditable asset manifest."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.store = JsonStore(self.root / "state" / "manifest.json")

    def initialize(self, project_name: str | None = None) -> JsonObject:
        if self.store.path.exists():
            existing = self.read()
            if existing["project"].get("id") != "uninitialized":
                return existing
        now = utc_now()
        manifest: JsonObject = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "project": {
                "id": str(uuid.uuid4()),
                "name": project_name or self.root.name,
                "created_at": now,
                "updated_at": now,
            },
            "assets": [],
        }
        self.store.write(manifest)
        return manifest

    def read(self) -> JsonObject:
        manifest = self.store.read()
        self._validate(manifest)
        return manifest

    def register_asset(
        self,
        *,
        asset_id: str,
        name: str,
        kind: str,
        source_type: str,
        source_uri: str | None,
        license_spdx: str,
        license_url: str | None,
        license_verified: bool,
        actor: str,
        blender_file: str | None = None,
        export_file: str | None = None,
        unity_path: str | None = None,
    ) -> JsonObject:
        if not asset_id or any(character.isspace() for character in asset_id):
            raise StateError("asset id must be non-empty and contain no whitespace")
        now = utc_now()
        normalized_blender = project_path(self.root, blender_file)
        normalized_export = project_path(self.root, export_file)
        normalized_unity = project_path(self.root, unity_path)
        asset: JsonObject = {
            "id": asset_id,
            "name": name,
            "kind": kind,
            "source": {"type": source_type, "uri": source_uri, "agent": actor},
            "license": {
                "spdx": license_spdx,
                "url": license_url,
                "verified": license_verified,
                "verified_by": actor if license_verified else None,
                "verified_at": now if license_verified else None,
            },
            "files": {
                "blender": normalized_blender,
                "export": normalized_export,
                "unity": normalized_unity,
            },
            "checksum": sha256_file(self.root, normalized_export or normalized_blender),
            "created_at": now,
            "updated_at": now,
            "last_modified_by": actor,
            "history": [{"at": now, "agent": actor, "action": "registered"}],
        }

        def add(manifest: JsonObject) -> None:
            self._validate(manifest)
            assets = manifest["assets"]
            if any(existing.get("id") == asset_id for existing in assets):
                raise StateError(f"asset already exists: {asset_id}")
            assets.append(asset)
            manifest["project"]["updated_at"] = now

        self.store.update(add)
        return asset

    def update_asset(
        self,
        *,
        asset_id: str,
        actor: str,
        blender_file: str | None = None,
        export_file: str | None = None,
        unity_path: str | None = None,
        license_spdx: str | None = None,
        license_url: str | None = None,
        license_verified: bool | None = None,
    ) -> JsonObject:
        now = utc_now()

        def update(manifest: JsonObject) -> JsonObject:
            asset = self._find_asset(manifest, asset_id)
            changed: list[str] = []
            path_updates = {
                "blender": blender_file,
                "export": export_file,
                "unity": unity_path,
            }
            for key, value in path_updates.items():
                if value is not None:
                    asset["files"][key] = project_path(self.root, value)
                    changed.append(f"files.{key}")
            if license_spdx is not None:
                asset["license"]["spdx"] = license_spdx
                changed.append("license.spdx")
            if license_url is not None:
                asset["license"]["url"] = license_url
                changed.append("license.url")
            if license_verified is not None:
                asset["license"]["verified"] = license_verified
                asset["license"]["verified_by"] = actor if license_verified else None
                asset["license"]["verified_at"] = now if license_verified else None
                changed.append("license.verified")
            if not changed:
                raise StateError("asset update requires at least one changed field")
            if blender_file is not None or export_file is not None:
                files = asset["files"]
                checksum_path = files.get("export") or files.get("blender")
                asset["checksum"] = sha256_file(self.root, checksum_path)
                changed.append("checksum")
            asset["updated_at"] = now
            asset["last_modified_by"] = actor
            asset["history"].append(
                {"at": now, "agent": actor, "action": "updated", "fields": changed}
            )
            manifest["project"]["updated_at"] = now
            return asset

        return self.store.update(update)

    def refresh_checksum(self, asset_id: str, actor: str) -> JsonObject:
        now = utc_now()

        def refresh(manifest: JsonObject) -> JsonObject:
            asset = self._find_asset(manifest, asset_id)
            files = asset["files"]
            path = files.get("export") or files.get("blender")
            asset["checksum"] = sha256_file(self.root, path)
            asset["updated_at"] = now
            asset["last_modified_by"] = actor
            asset["history"].append({"at": now, "agent": actor, "action": "checksum-refreshed"})
            manifest["project"]["updated_at"] = now
            return asset

        return self.store.update(refresh)

    def all_licenses_verified(self) -> bool:
        assets = self.read()["assets"]
        return all(asset["license"]["verified"] for asset in assets)

    @staticmethod
    def _find_asset(manifest: JsonObject, asset_id: str) -> JsonObject:
        for asset in manifest["assets"]:
            if asset.get("id") == asset_id:
                return cast(JsonObject, asset)
        raise StateError(f"unknown asset: {asset_id}")

    @staticmethod
    def _validate(manifest: JsonObject) -> None:
        if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            raise StateError("unsupported manifest schema version")
        if not isinstance(manifest.get("project"), dict):
            raise StateError("manifest is missing project metadata")
        if not isinstance(manifest.get("assets"), list):
            raise StateError("manifest assets must be a list")
        seen: set[str] = set()
        for asset in manifest["assets"]:
            required = {"id", "source", "license", "files", "checksum", "last_modified_by"}
            if not isinstance(asset, dict) or not required.issubset(asset):
                raise StateError("manifest contains an incomplete asset")
            if asset["id"] in seen:
                raise StateError(f"manifest contains duplicate asset id: {asset['id']}")
            seen.add(asset["id"])


class SessionStore:
    """Persist pipeline progress as one file per session."""

    ACTIVE_STATUSES = {"in-progress", "blocked"}

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.sessions_dir = self.root / "state" / "sessions"

    def start(self, pipeline: str, stages: list[JsonObject]) -> JsonObject:
        if not stages:
            raise StateError("pipeline must contain at least one stage")
        session_id = str(uuid.uuid4())
        now = utc_now()
        session: JsonObject = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "id": session_id,
            "pipeline": pipeline,
            "status": "in-progress",
            "current_stage": 0,
            "stages": [
                {**stage, "status": "pending", "attempts": 0, "started_at": None, "ended_at": None}
                for stage in stages
            ],
            "created_at": now,
            "updated_at": now,
            "events": [{"at": now, "type": "session-started"}],
        }
        session["stages"][0]["status"] = "in-progress"
        session["stages"][0]["started_at"] = now
        session["stages"][0]["attempts"] = 1
        self._store(session_id).write(session)
        return session

    def read(self, session_id: str) -> JsonObject:
        session = self._store(session_id).read()
        self._validate(session)
        return session

    def latest_active(self) -> JsonObject:
        if not self.sessions_dir.exists():
            raise StateError("no pipeline sessions exist")
        active: list[JsonObject] = []
        for path in self.sessions_dir.glob("*.json"):
            session = JsonStore(path).read()
            self._validate(session)
            if session["status"] in self.ACTIVE_STATUSES:
                active.append(session)
        if not active:
            raise StateError("no resumable pipeline session exists")
        return max(active, key=lambda item: str(item["updated_at"]))

    def advance(self, session_id: str, actor: str) -> JsonObject:
        now = utc_now()

        def advance_session(session: JsonObject) -> JsonObject:
            self._validate(session)
            if session["status"] not in self.ACTIVE_STATUSES:
                raise StateError(f"cannot advance session in status {session['status']}")
            index = int(session["current_stage"])
            current = session["stages"][index]
            current["status"] = "completed"
            current["ended_at"] = now
            current["completed_by"] = actor
            next_index = index + 1
            if next_index == len(session["stages"]):
                session["status"] = "completed"
            else:
                session["status"] = "in-progress"
                session["current_stage"] = next_index
                following = session["stages"][next_index]
                following["status"] = "in-progress"
                following["started_at"] = now
                following["attempts"] += 1
            session["updated_at"] = now
            session["events"].append({"at": now, "type": "stage-advanced", "actor": actor})
            return session

        return self._store(session_id).update(advance_session)

    def block(self, session_id: str, reason: str) -> JsonObject:
        now = utc_now()

        def block_session(session: JsonObject) -> JsonObject:
            session["status"] = "blocked"
            session["updated_at"] = now
            session["events"].append({"at": now, "type": "blocked", "reason": reason})
            return session

        return self._store(session_id).update(block_session)

    def fail(self, session_id: str, reason: str) -> JsonObject:
        now = utc_now()

        def fail_session(session: JsonObject) -> JsonObject:
            index = int(session["current_stage"])
            session["stages"][index]["status"] = "failed"
            session["status"] = "failed"
            session["updated_at"] = now
            session["events"].append({"at": now, "type": "failed", "reason": reason})
            return session

        return self._store(session_id).update(fail_session)

    def _store(self, session_id: str) -> JsonStore:
        if not session_id or any(character not in "0123456789abcdef-" for character in session_id):
            raise StateError("invalid session id")
        return JsonStore(self.sessions_dir / f"{session_id}.json")

    @staticmethod
    def _validate(session: JsonObject) -> None:
        if session.get("schema_version") != SESSION_SCHEMA_VERSION:
            raise StateError("unsupported session schema version")
        if not isinstance(session.get("stages"), list) or not session["stages"]:
            raise StateError("session stages are missing")
        index = session.get("current_stage")
        if not isinstance(index, int) or not 0 <= index < len(session["stages"]):
            raise StateError("session current_stage is invalid")
