import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { encodeEnvelope, parseEnvelope } from "../dist/contracts.js";

const fixtureUrl = new URL(
  "../../src/gamedev_agent/contracts/fixtures/worker-request.json",
  import.meta.url,
);

async function fixture() {
  return JSON.parse(await readFile(fixtureUrl, "utf8"));
}

test("parses and encodes the shared worker fixture", async () => {
  const value = parseEnvelope(await fixture());
  assert.equal(value.kind, "resource.estimate");
  assert.equal(value.request_id, "fixture-request-1");
  assert.deepEqual(JSON.parse(encodeEnvelope(value)), value);
});

test("rejects unknown fields and non-finite values", async () => {
  const value = await fixture();
  assert.throws(() => parseEnvelope({ ...value, unexpected: true }), /unknown envelope fields/);
  assert.throws(
    () => parseEnvelope({ ...value, payload: { invalid: Number.POSITIVE_INFINITY } }),
    /envelope must contain a JSON object/,
  );
});
