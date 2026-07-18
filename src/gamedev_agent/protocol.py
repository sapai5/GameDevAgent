"""Versioned JSON envelopes for language-neutral process boundaries."""

from __future__ import annotations

import json
import math
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from .storage import StateError

PROTOCOL_SCHEMA_VERSION = 1
MAX_ENVELOPE_BYTES = 1_048_576
_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_ALLOWED_FIELDS = frozenset({"schema_version", "kind", "request_id", "payload"})


class ProtocolError(StateError):
    """Raised when a cross-language envelope violates the protocol contract."""


def _reject_constant(value: str) -> None:
    raise ProtocolError(f"non-finite JSON number is not allowed: {value}")


def _validate_json(value: Any, path: str = "payload") -> None:
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError(f"{path} contains a non-string key")
            _validate_json(item, f"{path}.{key}")
        return
    raise ProtocolError(f"{path} contains unsupported JSON value: {type(value).__name__}")


@dataclass(frozen=True)
class Envelope:
    """One request or response crossing a process or language boundary."""

    schema_version: int
    kind: str
    request_id: str
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        kind: str,
        payload: Mapping[str, Any],
        request_id: str | None = None,
    ) -> Self:
        return cls.from_mapping(
            {
                "schema_version": PROTOCOL_SCHEMA_VERSION,
                "kind": kind,
                "request_id": request_id or str(uuid.uuid4()),
                "payload": dict(payload),
            }
        )

    @classmethod
    def from_json(cls, serialized: str | bytes, *, max_bytes: int = MAX_ENVELOPE_BYTES) -> Self:
        raw = serialized.encode("utf-8") if isinstance(serialized, str) else serialized
        if len(raw) > max_bytes:
            raise ProtocolError(f"envelope exceeds {max_bytes} bytes")
        try:
            value = json.loads(raw, parse_constant=_reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProtocolError(f"invalid envelope JSON: {error}") from error
        if not isinstance(value, dict):
            raise ProtocolError("envelope must contain a JSON object")
        return cls.from_mapping(value)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Self:
        unknown = set(value) - _ALLOWED_FIELDS
        missing = _ALLOWED_FIELDS - set(value)
        if unknown:
            raise ProtocolError(f"unknown envelope fields: {', '.join(sorted(unknown))}")
        if missing:
            raise ProtocolError(f"missing envelope fields: {', '.join(sorted(missing))}")

        schema_version = value["schema_version"]
        if schema_version != PROTOCOL_SCHEMA_VERSION:
            raise ProtocolError(f"unsupported protocol schema version: {schema_version}")
        kind = value["kind"]
        if not isinstance(kind, str) or not _KIND_PATTERN.fullmatch(kind):
            raise ProtocolError(f"invalid envelope kind: {kind!r}")
        request_id = value["request_id"]
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            raise ProtocolError("request_id must be a non-empty string of at most 128 characters")
        payload = value["payload"]
        if not isinstance(payload, dict):
            raise ProtocolError("payload must contain a JSON object")
        _validate_json(payload)
        return cls(schema_version, kind, request_id, dict(payload))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "request_id": self.request_id,
            "payload": self.payload,
        }

    def to_json(self, *, max_bytes: int = MAX_ENVELOPE_BYTES) -> str:
        serialized = json.dumps(
            self.to_mapping(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        if len(serialized.encode("utf-8")) > max_bytes:
            raise ProtocolError(f"envelope exceeds {max_bytes} bytes")
        return serialized

    def response(self, payload: Mapping[str, Any], *, error: bool = False) -> Self:
        return type(self).create(
            kind="worker.error" if error else "worker.response",
            request_id=self.request_id,
            payload=payload,
        )
