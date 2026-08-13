#!/usr/bin/env python3
"""Focused contracts for the JARVIS V4 registry, runs and memory index."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))

from action_registry import ACTION_REGISTRY, RunStore, action_for_intent, run_public_payload
from memory_index import MemoryIndex


class ActionRegistryTest(unittest.TestCase):
    def test_registry_covers_high_risk_and_core_intents(self):
        self.assertEqual(action_for_intent("message_send").confirmation, "interactive")
        self.assertEqual(action_for_intent("self_edit").risk, "code_write")
        self.assertEqual(action_for_intent("research_plan").name, "web_research")
        self.assertIn("memory_search", ACTION_REGISTRY)

    def test_run_lifecycle_is_durable_and_terminal(self):
        with TemporaryDirectory() as temp:
            store = RunStore(Path(temp))
            created = store.create(
                "enviar algo",
                action="message_send",
                state="waiting_confirmation",
                plan=[{"id": "step-1", "action": "message_send"}],
            )
            self.assertEqual(store.get(created["id"])["state"], "waiting_confirmation")
            running = store.update(created["id"], state="running", event_type="RUN_CONFIRMED")
            self.assertEqual(running["state"], "running")
            completed = store.update(
                created["id"],
                state="completed",
                result={"ok": True},
                evidence=[{"type": "worker_job", "value": 12}],
                event_type="RUN_COMPLETED",
            )
            public = run_public_payload(completed)
            self.assertEqual(public["run_id"], created["id"])
            self.assertEqual(public["state"], "completed")
            self.assertFalse(public["needs_confirmation"])
            with self.assertRaises(ValueError):
                store.update(created["id"], state="running")


class MemoryIndexTest(unittest.TestCase):
    def test_index_sync_search_and_remove(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            memories = base / "memories" / "PREFERENCIAS"
            memories.mkdir(parents=True)
            note = memories / "interface.md"
            note.write_text("# Preferência\n\nO busto mecânico deve ficar frontal.\n", encoding="utf-8")
            index = MemoryIndex(base / "runtime" / "memory.sqlite3", base / "memories")
            result = index.search("busto mecânico")
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["results"][0]["kind"], "preference")
            self.assertIn("busto mecânico", result["results"][0]["snippet"])
            note.unlink()
            empty = index.search("busto")
            self.assertEqual(empty["count"], 0)
            self.assertEqual(empty["index"]["removed"], 1)


if __name__ == "__main__":
    unittest.main()
