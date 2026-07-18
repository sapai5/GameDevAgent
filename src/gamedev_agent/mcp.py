"""Minimal JSON-RPC MCP adapters for real HTTP and mocked transports."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

JsonValue = dict[str, Any]


class McpError(RuntimeError):
    """Base MCP failure."""


class McpUnavailable(McpError):
    """Transient connectivity or server-availability failure."""


class McpResponseError(McpError):
    """A valid JSON-RPC error response that should not be blindly retried."""


class JsonRpcTransport(Protocol):
    def request(self, method: str, params: Mapping[str, Any]) -> JsonValue: ...


class HttpJsonRpcTransport:
    def __init__(self, endpoint: str, timeout_seconds: float = 5.0) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def request(self, method: str, params: Mapping[str, Any]) -> JsonValue:
        request_id = str(uuid.uuid4())
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": dict(params)}
        ).encode()
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise McpUnavailable(f"MCP endpoint unavailable at {self.endpoint}: {error}") from error
        try:
            value = json.loads(body)
        except json.JSONDecodeError as error:
            raise McpResponseError("MCP returned invalid JSON") from error
        if not isinstance(value, dict) or value.get("id") != request_id:
            raise McpResponseError("MCP returned an invalid JSON-RPC response")
        if "error" in value:
            raise McpResponseError(f"MCP error: {value['error']}")
        result = value.get("result", {})
        if not isinstance(result, dict):
            return {"value": result}
        return result


@dataclass
class MockTransport:
    """A deterministic transport for unit tests and orchestration simulations."""

    responses: dict[str, list[JsonValue | Exception]]
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def request(self, method: str, params: Mapping[str, Any]) -> JsonValue:
        self.calls.append((method, dict(params)))
        queue = self.responses.get(method)
        if not queue:
            raise McpResponseError(f"no canned response for {method}")
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class McpAdapter:
    def __init__(
        self,
        name: str,
        transport: JsonRpcTransport,
        *,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.1,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.name = name
        self.transport = transport
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    def health(self) -> JsonValue:
        return self._request("tools/list", {})

    def invoke(self, tool_name: str, arguments: Mapping[str, Any]) -> JsonValue:
        if not tool_name:
            raise ValueError("tool_name is required")
        return self._request("tools/call", {"name": tool_name, "arguments": dict(arguments)})

    def _request(self, method: str, params: Mapping[str, Any]) -> JsonValue:
        last_error: McpUnavailable | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.transport.request(method, params)
            except McpUnavailable as error:
                last_error = error
                if attempt == self.max_attempts:
                    break
                time.sleep(self.base_delay_seconds * (2 ** (attempt - 1)))
        assert last_error is not None
        raise McpUnavailable(
            f"{self.name} MCP unavailable after {self.max_attempts} attempts: {last_error}"
        ) from last_error
