use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::io::{self, BufRead};

const SCHEMA_VERSION: u32 = 1;
const VERTEX_BYTES: u64 = 32;
const INDEX_BYTES: u64 = 4;
const INDICES_PER_TRIANGLE: u64 = 3;
const INSTANCE_BYTES: u64 = 64;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Envelope {
    schema_version: u32,
    kind: String,
    request_id: String,
    payload: Value,
}

#[derive(Debug, Serialize)]
struct ResponseEnvelope {
    schema_version: u32,
    kind: &'static str,
    request_id: String,
    payload: Value,
}

fn response(request_id: String, payload: Value) -> ResponseEnvelope {
    ResponseEnvelope {
        schema_version: SCHEMA_VERSION,
        kind: "worker.response",
        request_id,
        payload,
    }
}

fn error(request_id: String, code: &str, message: String) -> ResponseEnvelope {
    ResponseEnvelope {
        schema_version: SCHEMA_VERSION,
        kind: "worker.error",
        request_id,
        payload: json!({"code": code, "message": message}),
    }
}

fn required_u64(payload: &Value, field: &str) -> Result<u64, String> {
    payload
        .get(field)
        .and_then(Value::as_u64)
        .ok_or_else(|| format!("payload.{field} must be a non-negative integer"))
}

fn checked_product(left: u64, right: u64, name: &str) -> Result<u64, String> {
    left.checked_mul(right)
        .ok_or_else(|| format!("{name} exceeds the supported u64 range"))
}

fn estimate_resources(payload: &Value) -> Result<Value, String> {
    let vertices = required_u64(payload, "vertex_count")?;
    let triangles = required_u64(payload, "triangle_count")?;
    let texture_bytes = required_u64(payload, "texture_bytes")?;
    let instances = required_u64(payload, "instance_count")?;

    let vertex_bytes = checked_product(vertices, VERTEX_BYTES, "vertex bytes")?;
    let index_count = checked_product(triangles, INDICES_PER_TRIANGLE, "index count")?;
    let index_bytes = checked_product(index_count, INDEX_BYTES, "index bytes")?;
    let instance_bytes = checked_product(instances, INSTANCE_BYTES, "instance bytes")?;
    let estimated_bytes = vertex_bytes
        .checked_add(index_bytes)
        .and_then(|value| value.checked_add(texture_bytes))
        .and_then(|value| value.checked_add(instance_bytes))
        .ok_or_else(|| "estimated bytes exceed the supported u64 range".to_string())?;

    Ok(json!({
        "vertex_bytes": vertex_bytes,
        "index_bytes": index_bytes,
        "texture_bytes": texture_bytes,
        "instance_bytes": instance_bytes,
        "estimated_bytes": estimated_bytes
    }))
}

fn handle_line(line: &str) -> ResponseEnvelope {
    let request: Envelope = match serde_json::from_str(line) {
        Ok(value) => value,
        Err(parse_error) => {
            return error(
                "unknown".to_string(),
                "invalid_request",
                parse_error.to_string(),
            );
        }
    };
    if request.schema_version != SCHEMA_VERSION {
        return error(
            request.request_id,
            "unsupported_schema",
            format!("unsupported schema version: {}", request.schema_version),
        );
    }
    if request.request_id.is_empty() || request.request_id.len() > 128 {
        return error(
            request.request_id,
            "invalid_request_id",
            "request_id must contain 1-128 characters".to_string(),
        );
    }

    match request.kind.as_str() {
        "worker.capabilities" => response(
            request.request_id,
            json!({
                "worker": "gamedev-worker",
                "schema_versions": [SCHEMA_VERSION],
                "operations": ["resource.estimate"],
                "logical_cpus": std::thread::available_parallelism()
                    .map(|value| value.get())
                    .unwrap_or(1)
            }),
        ),
        "resource.estimate" => match estimate_resources(&request.payload) {
            Ok(payload) => response(request.request_id, payload),
            Err(message) => error(request.request_id, "invalid_payload", message),
        },
        _ => error(
            request.request_id,
            "unknown_operation",
            format!("unsupported worker operation: {}", request.kind),
        ),
    }
}

fn main() {
    for line in io::stdin().lock().lines() {
        match line {
            Ok(value) if !value.trim().is_empty() => {
                let response = handle_line(&value);
                println!(
                    "{}",
                    serde_json::to_string(&response).expect("response must serialize")
                );
            }
            Ok(_) => {}
            Err(read_error) => {
                eprintln!("failed to read worker request: {read_error}");
                std::process::exit(1);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixture_estimates_resources() {
        let fixture =
            include_str!("../../../src/gamedev_agent/contracts/fixtures/worker-request.json");
        let output = handle_line(fixture);
        assert_eq!(output.kind, "worker.response");
        assert_eq!(output.request_id, "fixture-request-1");
        assert_eq!(output.payload["estimated_bytes"], 42_864);
    }

    #[test]
    fn overflow_returns_error() {
        let request = json!({
            "schema_version": 1,
            "kind": "resource.estimate",
            "request_id": "overflow",
            "payload": {
                "vertex_count": u64::MAX,
                "triangle_count": 0,
                "texture_bytes": 0,
                "instance_count": 0
            }
        });
        let output = handle_line(&request.to_string());
        assert_eq!(output.kind, "worker.error");
        assert_eq!(output.payload["code"], "invalid_payload");
    }

    #[test]
    fn unknown_operation_returns_error() {
        let request = json!({
            "schema_version": 1,
            "kind": "unknown.operation",
            "request_id": "unknown",
            "payload": {}
        });
        let output = handle_line(&request.to_string());
        assert_eq!(output.kind, "worker.error");
        assert_eq!(output.payload["code"], "unknown_operation");
    }
}
