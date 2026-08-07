#!/usr/bin/env python3
"""Contract tests for the isolated JARVIS self-edit command."""

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_self_edit",
    ROOT / "11_SCRIPTS" / "self_edit.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SelfEditTest(unittest.TestCase):
    def run_preview(self, codex_path):
        output = StringIO()
        with patch.object(MODULE.shutil, "which", return_value=codex_path), redirect_stdout(output):
            result = MODULE.execute("melhorar os próprios scripts com evidência", dry_run=True)
        return result, output.getvalue()

    def test_dry_run_reports_codex_cli_available(self):
        result, output = self.run_preview("/usr/local/bin/codex")
        self.assertEqual(result, 0)
        self.assertIn("Codex CLI: disponível.", output)
        self.assertIn("Modo preview: nenhum worktree, diff ou commit criado.", output)
        self.assertRegex(output, r"Duração total: \d+\.\d{3}s\.")
        self.assertTrue(output.rstrip().endswith("Produção: nada alterado."))

    def test_dry_run_reports_codex_cli_unavailable_without_failing(self):
        result, output = self.run_preview(None)
        self.assertEqual(result, 0)
        self.assertIn("Codex CLI: indisponível.", output)
        self.assertIn("Status real: preview de autoedição; Codex local indisponível.", output)
        self.assertIn("Produção: nada alterado.", output)

    def test_publish_dry_run_records_fixed_real_targets_without_side_effects(self):
        output = StringIO()
        with patch.object(MODULE.shutil, "which", return_value="/usr/local/bin/codex"), redirect_stdout(output):
            result = MODULE.execute(
                "adicione um diagnóstico ao jarvis e faça deploy",
                dry_run=True,
                publish=True,
            )
        self.assertEqual(result, 0)
        self.assertIn("GitHub main + Vercel production autorizados", output.getvalue())
        self.assertIn(MODULE.PUBLISH_REPOSITORY, output.getvalue())
        self.assertIn(MODULE.PRODUCTION_URL, output.getvalue())
        self.assertTrue(output.getvalue().rstrip().endswith("Produção: nada alterado."))

    def test_live_run_still_requires_codex_cli(self):
        with patch.object(MODULE.shutil, "which", return_value=None):
            with self.assertRaisesRegex(MODULE.SelfEditError, "Codex CLI não está instalado"):
                MODULE.execute("melhorar os próprios scripts com evidência")

    def test_safety_gate_is_post_commit_not_a_dirty_tree_validation(self):
        commands = MODULE.validation_commands(["11_SCRIPTS/self_edit.py"])
        self.assertIn(["./jarvis", "command-audit"], commands)
        self.assertNotIn(["./jarvis", "safety-gate"], commands)

    def test_format_duration_keeps_long_runs_readable(self):
        self.assertEqual(MODULE.format_duration(3_661.25), "1h 01m 01.250s")

    def test_publish_parser_requires_explicit_flag(self):
        parser = MODULE.build_parser()
        local = parser.parse_args(["melhore", "seus", "scripts"])
        published = parser.parse_args(["melhore", "seus", "scripts", "--publish"])
        self.assertFalse(local.publish)
        self.assertTrue(published.publish)

    def test_only_the_jarvis_remote_is_normalized_as_publish_target(self):
        self.assertEqual(
            MODULE.normalized_remote_url("git@github.com:theopadilha2009-hash/jarvis-agent-os.git"),
            MODULE.PUBLISH_REMOTE_URL,
        )
        self.assertNotEqual(
            MODULE.normalized_remote_url("https://github.com/theopadilha2009-hash/copytrade.git"),
            MODULE.PUBLISH_REMOTE_URL,
        )

    def test_publish_release_pushes_correct_remote_merges_and_deploys_exact_merge(self):
        merge_commit = "a" * 40

        def fake_run(argv, cwd, timeout=180, env=None):
            stdout = ""
            if argv[:3] == ["gh", "pr", "create"]:
                stdout = "https://github.com/theopadilha2009-hash/jarvis-agent-os/pull/99\n"
            elif argv[:3] == ["gh", "pr", "view"]:
                stdout = '{"state":"MERGED","mergeCommit":{"oid":"' + merge_commit + '"}}'
            elif argv[:4] == ["git", "worktree", "add", "--detach"]:
                Path(argv[4]).mkdir(parents=True, exist_ok=True)
            elif argv == ["vercel", "--prod", "--yes"]:
                stdout = "Production https://jarvis-agent-test.vercel.app\n"
            return MODULE.subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "runs"
            report = Path(tmp) / "agent.md"
            report.write_text("agent report\n", encoding="utf-8")
            with patch.object(MODULE, "RUN_ROOT", run_root), patch.object(
                MODULE, "run", side_effect=fake_run
            ) as runner, patch.object(
                MODULE, "production_healthcheck", return_value={"status_real": "web_cockpit_ready"}
            ), patch.object(
                MODULE, "activate_local_runtime", return_value="fast_forwarded_restart_requested"
            ):
                result = MODULE.publish_release(
                    Path(tmp),
                    "jarvis/self-edit-test",
                    "melhorar scripts e publicar",
                    {"gh": "gh", "vercel": "vercel"},
                    report,
                )

        self.assertEqual(result["merge_commit"], merge_commit)
        self.assertEqual(result["deployment_url"], "https://jarvis-agent-test.vercel.app")
        commands = [call.args[0] for call in runner.call_args_list]
        self.assertIn(
            ["git", "push", "--set-upstream", MODULE.PUBLISH_REMOTE, "jarvis/self-edit-test"],
            commands,
        )
        self.assertIn(["vercel", "--prod", "--yes"], commands)

    def test_handled_error_also_reports_total_duration(self):
        output = StringIO()
        argv = ["self_edit.py", "curto", "--dry-run"]
        with patch.object(sys, "argv", argv):
            with patch.object(MODULE.time, "monotonic", side_effect=[10.0, 10.75]):
                with redirect_stdout(output):
                    result = MODULE.main()
        self.assertEqual(result, 1)
        self.assertIn("Duração total: 0.750s.", output.getvalue())
        self.assertTrue(output.getvalue().rstrip().endswith("Produção: nada alterado."))


if __name__ == "__main__":
    unittest.main()
