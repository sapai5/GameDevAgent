from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]


class PolyglotLayoutTests(unittest.TestCase):
    def test_python_package_declares_contract_and_sql_resources(self) -> None:
        pyproject = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())
        package_data = pyproject["tool"]["setuptools"]["package-data"]["gamedev_agent"]
        self.assertEqual(
            [
                "contracts/*.json",
                "contracts/fixtures/*.json",
                "sql/migrations/*.sql",
            ],
            package_data,
        )
        for relative in (
            "src/gamedev_agent/contracts/envelope.schema.json",
            "src/gamedev_agent/contracts/hardware-budget.schema.json",
            "src/gamedev_agent/contracts/fixtures/worker-request.json",
            "src/gamedev_agent/sql/migrations/0001_ai_memory.sql",
        ):
            self.assertTrue((REPOSITORY / relative).is_file(), relative)

    def test_contract_schemas_and_fixture_are_version_one_json(self) -> None:
        contracts = REPOSITORY / "src" / "gamedev_agent" / "contracts"
        envelope = json.loads((contracts / "envelope.schema.json").read_text())
        budget = json.loads((contracts / "hardware-budget.schema.json").read_text())
        fixture = json.loads((contracts / "fixtures" / "worker-request.json").read_text())
        self.assertEqual(1, envelope["properties"]["schema_version"]["const"])
        self.assertEqual(1, fixture["schema_version"])
        self.assertEqual("resource.estimate", fixture["kind"])
        self.assertIn("max_vram_bytes", budget["properties"])
        self.assertIn("max_read_bytes", budget["properties"])
        self.assertIn("max_write_bytes", budget["properties"])

    def test_type_script_and_rust_dependencies_are_exactly_pinned(self) -> None:
        web = json.loads((REPOSITORY / "web" / "package.json").read_text())
        self.assertEqual("5.8.3", web["devDependencies"]["typescript"])
        self.assertTrue((REPOSITORY / "web" / "package-lock.json").is_file())

        cargo = tomllib.loads((REPOSITORY / "Cargo.toml").read_text())
        dependencies = cargo["workspace"]["dependencies"]
        self.assertEqual("=1.0.219", dependencies["serde"]["version"])
        self.assertEqual("=1.0.140", dependencies["serde_json"])
        self.assertTrue((REPOSITORY / "Cargo.lock").is_file())

    def test_architecture_document_declares_single_policy_owner(self) -> None:
        architecture = (REPOSITORY / "docs" / "architecture" / "polyglot-boundaries.md").read_text()
        self.assertIn("Python control plane", architecture)
        self.assertIn("SQLite is derived", architecture)
        self.assertIn("MUST NOT duplicate pipeline", architecture)
        self.assertIn("Rust workers", architecture)


if __name__ == "__main__":
    unittest.main()
