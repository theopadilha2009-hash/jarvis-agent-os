#!/usr/bin/env python3
"""Contas JARVIS: hash, signup pendente, aprovação e reserva de login."""

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_accounts",
    ROOT / "11_SCRIPTS" / "jarvis_accounts.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class JarvisAccountsTest(unittest.TestCase):
    def test_signup_stays_pending_until_owner_approves(self):
        store = MODULE.empty_store()
        store, user = MODULE.signup(store, "amigo02", "segredo123", "amigo@example.com", accepted_terms=True)
        self.assertEqual(user["role"], "pending")
        self.assertEqual(user["access"], ["jarvis"])
        self.assertNotIn("password_hash", user)
        with self.assertRaises(ValueError):
            MODULE.authenticate(store, "amigo02", "segredo123")
        approved = MODULE.manage(store, "approve", "amigo02")
        self.assertEqual(approved["role"], "member")
        self.assertIn("code", approved["access"])
        row = MODULE.authenticate(store, "amigo02", "segredo123")
        self.assertEqual(row["username"], "amigo02")
        listed = MODULE.list_public(store)
        self.assertEqual(listed[0]["username"], "amigo02")
        self.assertTrue(all("password_hash" not in item for item in listed))

    def test_reserved_usernames_and_roundtrip_file(self):
        with self.assertRaises(ValueError):
            MODULE.signup(MODULE.empty_store(), "theo", "segredo123", accepted_terms=True)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "accounts.json"
            store = MODULE.empty_store()
            MODULE.signup(store, "amigo03", "segredo123", accepted_terms=True)
            with self.assertRaises(ValueError):
                MODULE.signup(MODULE.empty_store(), "amigo04", "segredo123", accepted_terms=False)
            MODULE.save_local(store, path)
            loaded = MODULE.load_local(path)
            self.assertTrue(MODULE.password_matches("segredo123", loaded["users"][0]["password_hash"]))
            self.assertFalse(MODULE.password_matches("errado", loaded["users"][0]["password_hash"]))


if __name__ == "__main__":
    unittest.main()
