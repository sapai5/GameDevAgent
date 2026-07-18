from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gamedev_agent.cli import build_parser
from gamedev_agent.runtime import install_agents, install_claude_plugin, run_agent

REPOSITORY = Path(__file__).resolve().parents[1]


class RuntimeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for directory in ("agents", "skills", "agent-sops", "hooks"):
            shutil.copytree(REPOSITORY / directory, self.root / directory)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_claude_plugin_contains_shared_agents_skills_sops_hooks_and_mcp(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "GAMEDEV_BLENDER_MCP_COMMAND": "/usr/bin/true",
                "GAMEDEV_UNITY_MCP_COMMAND": "/usr/bin/true",
            },
        ):
            installed = install_claude_plugin(self.root)

        plugin = (self.root / ".claude" / "skills" / "gamedev-agent").resolve()
        self.assertEqual(13, len(list((plugin / "agents").glob("*.md"))))
        self.assertEqual(32, len(list((plugin / "skills").glob("*/SKILL.md"))))
        self.assertIn(plugin / ".claude-plugin" / "plugin.json", installed)
        manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual("gamedev-agent", manifest["name"])
        self.assertEqual("0.1.0", manifest["version"])
        self.assertTrue(manifest["description"])
        self.assertEqual(
            (REPOSITORY / "skills" / "naming-and-conventions" / "SKILL.md").read_text(),
            (plugin / "skills" / "naming-and-conventions" / "SKILL.md").read_text(),
        )

        manager = (plugin / "agents" / "project-manager.md").read_text()
        modeler = (plugin / "agents" / "blender-modeler.md").read_text()
        self.assertIn('"Agent"', manager)
        self.assertIn('"pipeline-scene-to-unity"', manager)
        self.assertIn("mcp__plugin_gamedev-agent_blender__*", modeler)

        mcp = json.loads((plugin / ".mcp.json").read_text())
        self.assertEqual({"blender", "unity"}, set(mcp["mcpServers"]))
        hooks = json.loads((plugin / "hooks" / "hooks.json").read_text())
        self.assertIn("PreToolUse", hooks["hooks"])
        self.assertTrue((plugin / "hooks" / "pre_tool_use.py").is_file())

    def test_install_agents_keeps_kiro_adapter_backward_compatible(self) -> None:
        installed = install_agents(self.root, "kiro")
        self.assertEqual(13, len(installed))
        manager = json.loads((self.root / ".kiro" / "agents" / "project-manager.json").read_text())
        self.assertEqual("project-manager", manager["name"])
        self.assertIn("subagent", manager["tools"])

    def test_generators_replace_stale_outputs_deterministically(self) -> None:
        def contents(directory: Path) -> dict[str, bytes]:
            return {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in sorted(directory.rglob("*"))
                if path.is_file()
            }

        environment = {
            "GAMEDEV_BLENDER_MCP_COMMAND": "/usr/bin/true",
            "GAMEDEV_UNITY_MCP_COMMAND": "/usr/bin/true",
        }
        with mock.patch.dict(os.environ, environment):
            install_agents(self.root, "kiro")
            install_agents(self.root, "claude")
            kiro = (self.root / ".kiro" / "agents").resolve()
            claude = (self.root / ".claude" / "skills" / "gamedev-agent").resolve()
            expected_kiro = contents(kiro)
            expected_claude = contents(claude)
            (kiro / "stale.json").write_text("{}\n")
            (claude / "agents" / "stale.md").write_text("stale\n")

            install_agents(self.root, "kiro")
            install_agents(self.root, "claude")

        self.assertEqual(expected_kiro, contents(kiro))
        self.assertEqual(expected_claude, contents(claude))
        self.assertFalse((kiro / "stale.json").exists())
        self.assertFalse((claude / "agents" / "stale.md").exists())

    def test_claude_runner_uses_scoped_agent_and_explicit_headless_trust(self) -> None:
        plugin = (self.root / ".claude" / "skills" / "gamedev-agent").resolve()
        plugin.mkdir(parents=True)
        completed = subprocess.CompletedProcess([], 0, "done\n", "")
        with (
            mock.patch("gamedev_agent.runtime.shutil.which", return_value="/bin/claude"),
            mock.patch("gamedev_agent.runtime.subprocess.run", return_value=completed) as invoked,
        ):
            result = run_agent(
                self.root,
                prompt="Build a prop",
                client="claude",
                headless=True,
                trusted_tools=["read", "subagent"],
            )

        self.assertEqual(0, result.returncode)
        command = invoked.call_args.args[0]
        self.assertEqual("/bin/claude", command[0])
        self.assertIn("--plugin-dir", command)
        self.assertEqual("gamedev-agent:project-manager", command[command.index("--agent") + 1])
        self.assertIn("--print", command)
        self.assertEqual("Read,Agent", command[command.index("--allowedTools") + 1])
        self.assertNotIn("--dangerously-skip-permissions", command)

    def test_cli_parser_selects_each_supported_client(self) -> None:
        parser = build_parser()
        self.assertEqual("all", parser.parse_args(["agents", "install", "--client", "all"]).client)
        self.assertEqual(
            "claude",
            parser.parse_args(["run", "Build a scene", "--client", "claude"]).client,
        )


if __name__ == "__main__":
    unittest.main()
