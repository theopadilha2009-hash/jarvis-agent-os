#!/usr/bin/env python3
"""Contas locais do JARVIS: signup, login e gestão do dono.

Sem API externa. Persistência: JSON em HOME (ou JARVIS_ACCOUNTS_PATH).
O gateway pode gravar a mesma estrutura no Supabase (jarvis_settings.accounts).
Senhas só em pbkdf2; a listagem pública nunca devolve hash.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import threading


USERNAME_RE = re.compile(r"^[a-z][a-z0-9._-]{2,31}$")
ROLES = {"owner", "member", "pending"}
HASH_PREFIX = "pbkdf2_sha256"
ITERATIONS = 120_000
_LOCK = threading.Lock()


def accounts_path(home=None) -> Path:
    override = (os.environ.get("JARVIS_ACCOUNTS_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    root = Path(home) if home else Path.home()
    return root / "Library" / "Application Support" / "JARVIS" / "accounts.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def empty_store() -> dict:
    return {
        "schema": 1,
        "signing_secret": secrets.token_hex(32),
        "users": [],
    }


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{HASH_PREFIX}${iterations}${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_raw, salt_hex, digest_hex = str(encoded or "").split("$", 3)
        if algorithm != HASH_PREFIX:
            return False
        iterations = int(iterations_raw)
        if not 100_000 <= iterations <= 2_000_000:
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            str(password or "")[:512].encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def normalize_username(value: str) -> str:
    return str(value or "").strip().casefold()


def normalize_email(value: str) -> str:
    email = str(value or "").strip().casefold()
    if not email:
        return ""
    if "@" not in email or len(email) > 160:
        raise ValueError("e-mail inválido")
    return email


def public_user(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "email": row.get("email") or "",
        "role": row.get("role"),
        "access": list(row.get("access") or []),
        "disabled": bool(row.get("disabled")),
        "created_at": row.get("created_at") or "",
        "last_seen_at": row.get("last_seen_at") or "",
    }


def load_local(path=None) -> dict:
    target = Path(path) if path else accounts_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_store()
    if not isinstance(payload, dict):
        return empty_store()
    users = payload.get("users")
    if not isinstance(users, list):
        payload["users"] = []
    if not payload.get("signing_secret"):
        payload["signing_secret"] = secrets.token_hex(32)
    payload["schema"] = 1
    return payload


def save_local(store: dict, path=None) -> Path:
    target = Path(path) if path else accounts_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return target


def find_user(store: dict, username: str):
    wanted = normalize_username(username)
    for row in store.get("users") or []:
        if isinstance(row, dict) and row.get("username") == wanted:
            return row
    return None


def signing_secret(store: dict) -> str:
    return str(store.get("signing_secret") or "")


def signup(store: dict, username: str, password: str, email: str = "") -> tuple[dict, dict]:
    name = normalize_username(username)
    if not USERNAME_RE.fullmatch(name):
        raise ValueError("use um login de 3 a 32 caracteres (letra inicial, sem espaço)")
    if name in {"admin", "root", "theo", "ultron", "jarvis"}:
        raise ValueError("esse login é reservado")
    secret = str(password or "")
    if len(secret) < 8 or len(secret) > 128:
        raise ValueError("a senha precisa ter pelo menos 8 caracteres")
    if find_user(store, name):
        raise ValueError("esse login já existe")
    row = {
        "id": f"u-{secrets.token_hex(6)}",
        "username": name,
        "email": normalize_email(email),
        "password_hash": hash_password(secret),
        "role": "pending",
        "access": ["jarvis"],
        "disabled": False,
        "created_at": now_iso(),
        "last_seen_at": "",
    }
    store.setdefault("users", []).append(row)
    return store, public_user(row)


def authenticate(store: dict, username: str, password: str):
    row = find_user(store, username)
    if not row or not password_matches(password, row.get("password_hash") or ""):
        return None
    if row.get("disabled"):
        raise ValueError("essa conta está desativada")
    if row.get("role") == "pending":
        raise ValueError("sua conta ainda espera a aprovação do Theo")
    row["last_seen_at"] = now_iso()
    return row


def manage(store: dict, action: str, username: str) -> dict:
    row = find_user(store, username)
    if not row:
        raise ValueError("conta não encontrada")
    if row.get("role") == "owner" and action in {"delete", "disable"}:
        raise ValueError("a conta dono não pode ser apagada por aqui")
    if action == "approve":
        row["role"] = "member"
        row["access"] = ["jarvis", "code"]
        row["disabled"] = False
    elif action == "disable":
        row["disabled"] = True
    elif action == "enable":
        row["disabled"] = False
    elif action == "delete":
        store["users"] = [item for item in store.get("users") or [] if item is not row]
        return {"deleted": True, "username": normalize_username(username)}
    elif action == "promote":
        row["role"] = "owner"
        row["access"] = ["jarvis", "ultron", "code"]
        row["disabled"] = False
    else:
        raise ValueError("ação inválida")
    return public_user(row)


def list_public(store: dict) -> list:
    rows = [public_user(row) for row in store.get("users") or [] if isinstance(row, dict)]
    rows.sort(key=lambda item: (item.get("role") != "owner", item.get("username") or ""))
    return rows


def ensure_owner_from_env(store: dict, username: str, password_hash: str) -> dict:
    """Espelha o admin do ambiente como dono, sem inventar senha."""
    name = normalize_username(username) or "theo"
    if not USERNAME_RE.fullmatch(name):
        name = "theo"
    if find_user(store, name) or not password_hash:
        return store
    store.setdefault("users", []).append({
        "id": "u-owner",
        "username": name,
        "email": "theopadilha2009@gmail.com",
        "password_hash": password_hash,
        "role": "owner",
        "access": ["jarvis", "ultron", "code"],
        "disabled": False,
        "created_at": now_iso(),
        "last_seen_at": "",
    })
    return store


def locked(fn):
    def wrapped(*args, **kwargs):
        with _LOCK:
            return fn(*args, **kwargs)
    return wrapped
