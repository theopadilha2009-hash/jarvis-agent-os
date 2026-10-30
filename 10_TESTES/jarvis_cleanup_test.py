#!/usr/bin/env python3
"""Regra de limpeza e compactação: o que sai, o que nunca sai."""

from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import jarvis_cleanup  # noqa: E402


class HumanSizeTest(unittest.TestCase):
    def test_unidades(self):
        self.assertEqual(jarvis_cleanup.human_size(0), "0 B")
        self.assertEqual(jarvis_cleanup.human_size(900), "900 B")
        self.assertEqual(jarvis_cleanup.human_size(2048), "2.0 KB")
        self.assertEqual(jarvis_cleanup.human_size(5 * 1024 * 1024), "5.0 MB")


class CutoffTest(unittest.TestCase):
    def test_janela_e_no_passado_e_com_timezone(self):
        limit = jarvis_cleanup.cutoff(30)
        self.assertIsNotNone(limit.tzinfo)
        self.assertLess(limit, datetime.now(timezone.utc))

    def test_janela_zero_vira_um_dia(self):
        self.assertLess(jarvis_cleanup.cutoff(0), jarvis_cleanup.cutoff(1))


class PlanLocalTest(unittest.TestCase):
    def _make(self, root: Path, area: str, name: str, age_days: int) -> Path:
        target = root / area / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
        stamp = datetime.now(timezone.utc).timestamp() - age_days * 86400
        os.utime(target, (stamp, stamp))
        return target

    def test_fora_do_git_nao_entra_no_plano(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make(root, "09_LOGS", "velho.log", 90)
            self.assertEqual(jarvis_cleanup.plan_local(30, root=root), [])

    def test_gitkeep_nunca_sai(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make(root, "09_LOGS", ".gitkeep", 90)
            self.assertEqual(jarvis_cleanup.plan_local(30, root=root), [])

    def test_arquivo_recente_nao_entra(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make(root, "09_LOGS", "novo.log", 1)
            self.assertEqual(jarvis_cleanup.plan_local(30, root=root), [])


if __name__ == "__main__":
    unittest.main()
