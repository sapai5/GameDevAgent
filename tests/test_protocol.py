from __future__ import annotations

import json
import unittest
from pathlib import Path

from gamedev_agent.protocol import Envelope, ProtocolError

REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURE = REPOSITORY / "src" / "gamedev_agent" / "contracts" / "fixtures" / "worker-request.json"


class ProtocolTests(unittest.TestCase):
    def test_shared_fixture_round_trips_canonically(self) -> None:
        value = Envelope.from_json(FIXTURE.read_bytes())
        self.assertEqual("resource.estimate", value.kind)
        self.assertEqual("fixture-request-1", value.request_id)
        self.assertEqual(1000, value.payload["vertex_count"])
        self.assertEqual(value.to_mapping(), json.loads(value.to_json()))

    def test_create_and_response_preserve_request_identity(self) -> None:
        request = Envelope.create(kind="worker.capabilities", payload={}, request_id="request-1")
        response = request.response({"logical_cpus": 8})
        error = request.response({"code": "failed"}, error=True)
        self.assertEqual("worker.response", response.kind)
        self.assertEqual("worker.error", error.kind)
        self.assertEqual(request.request_id, response.request_id)
        self.assertEqual(request.request_id, error.request_id)

    def test_rejects_unknown_missing_and_unsupported_fields(self) -> None:
        fixture = json.loads(FIXTURE.read_text())
        with self.assertRaisesRegex(ProtocolError, "unknown envelope fields"):
            Envelope.from_mapping({**fixture, "unexpected": True})
        fixture.pop("payload")
        with self.assertRaisesRegex(ProtocolError, "missing envelope fields"):
            Envelope.from_mapping(fixture)
        fixture["payload"] = {}
        fixture["schema_version"] = 2
        with self.assertRaisesRegex(ProtocolError, "unsupported protocol schema version"):
            Envelope.from_mapping(fixture)

    def test_rejects_invalid_json_values_and_kinds(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "non-finite JSON number"):
            Envelope.from_json(
                '{"schema_version":1,"kind":"worker.request","request_id":"r","payload":{"x":NaN}}'
            )
        with self.assertRaisesRegex(ProtocolError, "invalid envelope kind"):
            Envelope.create(kind="Worker Request", payload={})
        with self.assertRaisesRegex(ProtocolError, "payload must contain a JSON object"):
            Envelope.from_mapping(
                {
                    "schema_version": 1,
                    "kind": "worker.request",
                    "request_id": "r",
                    "payload": [],
                }
            )

    def test_enforces_input_and_output_byte_limits(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "exceeds 8 bytes"):
            Envelope.from_json(b'{"large":true}', max_bytes=8)
        value = Envelope.create(kind="worker.request", payload={"value": "x" * 100})
        with self.assertRaisesRegex(ProtocolError, "exceeds 64 bytes"):
            value.to_json(max_bytes=64)


if __name__ == "__main__":
    unittest.main()
