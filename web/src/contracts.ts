export const PROTOCOL_SCHEMA_VERSION = 1 as const;
export const MAX_ENVELOPE_BYTES = 1_048_576;

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type JsonObject = { [key: string]: JsonValue };

export interface Envelope<TPayload extends JsonObject = JsonObject> {
  schema_version: typeof PROTOCOL_SCHEMA_VERSION;
  kind: string;
  request_id: string;
  payload: TPayload;
}

const kindPattern = /^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/;
const envelopeFields = new Set(["schema_version", "kind", "request_id", "payload"]);

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || ["string", "boolean"].includes(typeof value)) {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).every(isJsonValue);
  }
  return false;
}

function isJsonObject(value: unknown): value is JsonObject {
  return value !== null && !Array.isArray(value) && typeof value === "object" && isJsonValue(value);
}

export function parseEnvelope(input: unknown): Envelope {
  if (!isJsonObject(input)) {
    throw new Error("envelope must contain a JSON object");
  }
  const keys = Object.keys(input);
  const unknown = keys.filter((key) => !envelopeFields.has(key));
  const missing = [...envelopeFields].filter((key) => !keys.includes(key));
  if (unknown.length > 0) {
    throw new Error(`unknown envelope fields: ${unknown.sort().join(", ")}`);
  }
  if (missing.length > 0) {
    throw new Error(`missing envelope fields: ${missing.sort().join(", ")}`);
  }
  if (input.schema_version !== PROTOCOL_SCHEMA_VERSION) {
    throw new Error(`unsupported protocol schema version: ${String(input.schema_version)}`);
  }
  if (typeof input.kind !== "string" || !kindPattern.test(input.kind)) {
    throw new Error(`invalid envelope kind: ${String(input.kind)}`);
  }
  if (
    typeof input.request_id !== "string" ||
    input.request_id.length === 0 ||
    input.request_id.length > 128
  ) {
    throw new Error("request_id must contain 1-128 characters");
  }
  if (!isJsonObject(input.payload)) {
    throw new Error("payload must contain a JSON object");
  }
  return {
    schema_version: PROTOCOL_SCHEMA_VERSION,
    kind: input.kind,
    request_id: input.request_id,
    payload: input.payload,
  };
}

export function encodeEnvelope(envelope: Envelope): string {
  const validated = parseEnvelope(envelope);
  const encoded = JSON.stringify(validated);
  if (new TextEncoder().encode(encoded).byteLength > MAX_ENVELOPE_BYTES) {
    throw new Error(`envelope exceeds ${MAX_ENVELOPE_BYTES} bytes`);
  }
  return encoded;
}
