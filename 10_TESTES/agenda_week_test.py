#!/usr/bin/env python3
"""Agenda local (data+hora), relatório semanal e estado canônico de tasks."""

from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import task_queue  # noqa: E402
import week_report  # noqa: E402
from local_capture import (  # noqa: E402
    _infer_when,
    _strip_note_verb,
    read_agenda_items,
    read_inbox_items,
)

MONDAY = date(2026, 10, 26)


class InferWhenTest(unittest.TestCase):
    def test_data_e_hora(self):
        self.assertEqual(_infer_when("sexta às 14h", "", today=MONDAY), "2026-10-30 14:00")
        self.assertEqual(_infer_when("hoje às 14h30", "", today=MONDAY), "2026-10-26 14:30")
        self.assertEqual(_infer_when("amanhã 9:00", "", today=MONDAY), "2026-10-27 09:00")
        self.assertEqual(
            _infer_when("2026-11-06 14:00", "", today=MONDAY), "2026-11-06 14:00"
        )

    def test_sem_hora_fica_so_data(self):
        self.assertEqual(_infer_when("sexta", "", today=MONDAY), "2026-10-30")

    def test_sem_data_retorna_none(self):
        self.assertIsNone(_infer_when("qualquer coisa", "", today=MONDAY))

    def test_strip_verbo(self):
        self.assertEqual(
            _strip_note_verb("anota que sexta às 14h eu preciso postar um vídeo"),
            "sexta às 14h eu preciso postar um vídeo",
        )
        self.assertEqual(_strip_note_verb("me lembra de comprar pão"), "comprar pão")


class ReadItemsTest(unittest.TestCase):
    def test_le_agenda_e_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            agenda = Path(tmp) / "AGENDA.md"
            agenda.write_text(
                "- [2026-10-30 14:00] (criado 2026-10-29T10:00:00) postar um vídeo\n",
                encoding="utf-8",
            )
            inbox = Path(tmp) / "INBOX.md"
            inbox.write_text("- [2026-10-29T09:00:00] ideia solta\n", encoding="utf-8")

            agenda_items = read_agenda_items(agenda)
            self.assertEqual(len(agenda_items), 1)
            self.assertEqual(agenda_items[0]["when"], "2026-10-30 14:00")
            self.assertEqual(agenda_items[0]["text"], "postar um vídeo")

            inbox_items = read_inbox_items(inbox)
            self.assertEqual(len(inbox_items), 1)
            self.assertEqual(inbox_items[0]["text"], "ideia solta")


class WeekReportTest(unittest.TestCase):
    def _report(self, agenda_text="", inbox_text="", tasks=None):
        tasks = tasks or []
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        agenda = base / "AGENDA.md"
        agenda.write_text(agenda_text, encoding="utf-8")
        inbox = base / "INBOX.md"
        inbox.write_text(inbox_text, encoding="utf-8")
        tasks_file = base / "tasks.jsonl"
        tasks_file.write_text(
            "\n".join(json.dumps(ev) for ev in tasks), encoding="utf-8"
        )
        with mock.patch.object(week_report, "read_agenda_items", lambda: read_agenda_items(agenda)), \
             mock.patch.object(week_report, "read_inbox_items", lambda: read_inbox_items(inbox)), \
             mock.patch.object(task_queue, "TASKS_FILE", tasks_file):
            return week_report.build_report(days=7, today=MONDAY)

    def test_item_da_janela_aparece_em_upcoming(self):
        data = self._report(agenda_text="- [2026-10-30 14:00] (criado x) postar vídeo\n")
        self.assertEqual(len(data["agenda"]["upcoming"]), 1)
        self.assertEqual(data["agenda"]["upcoming"][0]["text"], "postar vídeo")
        self.assertFalse(data["notes"]["used_as_fallback"])

    def test_item_passado_vira_atrasado(self):
        data = self._report(agenda_text="- [2026-10-20] (criado x) coisa velha\n")
        self.assertEqual(len(data["agenda"]["overdue"]), 1)

    def test_agenda_vazia_usa_anotacoes(self):
        data = self._report(inbox_text="- [2026-10-28T09:00:00] ideia do inbox\n")
        self.assertTrue(data["notes"]["used_as_fallback"])
        rendered = "\n".join(week_report.render_report(data))
        self.assertIn("usando no lugar da agenda", rendered)
        self.assertIn("ideia do inbox", rendered)

    def test_task_concluida_nao_aparece_como_pendente(self):
        data = self._report(
            tasks=[
                {"id": "t-1", "ts": "2026-10-20T10:00:00", "type": "created", "text": "feita", "status": "pending"},
                {"id": "t-1", "ts": "2026-10-21T10:00:00", "type": "done"},
                {"id": "t-2", "ts": "2026-10-22T10:00:00", "type": "created", "text": "aberta", "status": "pending"},
            ]
        )
        pending_ids = [t["id"] for t in data["tasks"]["pending"]]
        self.assertEqual(pending_ids, ["t-2"])
        self.assertEqual(len(data["tasks"]["done_in_window"]), 1)


class TaskStateConsistencyTest(unittest.TestCase):
    def test_leitores_concordam_com_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = Path(tmp) / "tasks.jsonl"
            tasks_file.write_text(
                "\n".join(
                    json.dumps(ev)
                    for ev in [
                        {"id": "t-1", "ts": "2026-10-20T10:00:00", "type": "created", "text": "feita", "status": "pending"},
                        {"id": "t-1", "ts": "2026-10-21T10:00:00", "type": "done"},
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch.object(task_queue, "TASKS_FILE", tasks_file):
                self.assertEqual(task_queue.task_state()["t-1"]["status"], "done")
                self.assertEqual(task_queue._rebuild_state()["t-1"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
