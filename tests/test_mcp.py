from __future__ import annotations

import unittest

from gamedev_agent.mcp import (
    McpAdapter,
    McpResponseError,
    McpUnavailable,
    MockTransport,
)


class McpTests(unittest.TestCase):
    def test_mock_blender_health_and_tool_call(self) -> None:
        transport = MockTransport(
            {
                "tools/list": [{"tools": [{"name": "create_cube"}]}],
                "tools/call": [{"content": [{"type": "text", "text": "created"}]}],
            }
        )
        adapter = McpAdapter("blender", transport, base_delay_seconds=0)
        self.assertEqual("create_cube", adapter.health()["tools"][0]["name"])
        adapter.invoke("create_cube", {"size": 1})
        self.assertEqual(
            ("tools/call", {"name": "create_cube", "arguments": {"size": 1}}),
            transport.calls[1],
        )

    def test_transient_unity_failure_is_retried_with_bound(self) -> None:
        transport = MockTransport(
            {"tools/list": [McpUnavailable("starting"), {"tools": [{"name": "play_mode"}]}]}
        )
        adapter = McpAdapter("unity", transport, max_attempts=2, base_delay_seconds=0)
        self.assertEqual("play_mode", adapter.health()["tools"][0]["name"])
        self.assertEqual(2, len(transport.calls))

    def test_response_error_is_not_retried(self) -> None:
        transport = MockTransport(
            {"tools/call": [McpResponseError("invalid scene"), {"content": []}]}
        )
        adapter = McpAdapter("unity", transport, max_attempts=3, base_delay_seconds=0)
        with self.assertRaisesRegex(McpResponseError, "invalid scene"):
            adapter.invoke("open_scene", {"path": "missing"})
        self.assertEqual(1, len(transport.calls))

    def test_transient_failure_exhaustion_reports_attempt_count(self) -> None:
        transport = MockTransport(
            {"tools/list": [McpUnavailable("down"), McpUnavailable("still down")]}
        )
        adapter = McpAdapter("blender", transport, max_attempts=2, base_delay_seconds=0)
        with self.assertRaisesRegex(McpUnavailable, "after 2 attempts"):
            adapter.health()


if __name__ == "__main__":
    unittest.main()
