#!/usr/bin/env python3
"""Selo do criador: o nome não fica em claro; reconstrói com XOR + HMAC.

Isto não impede um atacante determinado de recompilar o produto. Impede
remoção casual: se o texto visível some, o runtime restaura o nome a
partir do ciphertext. Se o ciphertext for adulterado, o HMAC recusa.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac


LOCK_ID = "ai.theopadilha.jarvis.lock/1"
KEY_MATERIAL = b"ai.theopadilha.jarvis.cockpit|creator-lock-v1"
# XOR(nome, sha256(KEY_MATERIAL)) — não é o nome em claro.
CIPHER_B64 = "ggCZbZFBcds2X3zL5N5jloFWuxA="
SHORT_CIPHER_B64 = "ggCZbZFdf806XWDQ"
MAC_HEX = "fd104b309b652386d59db44c056d7a93749557e8888b7e52eb8e658de0d30eb3"
SHORT_MAC_HEX = "55e05c82e1b5706d895eb848c390c8a0465fc441515269acc74bc6a9956d0bb8"
# Último recurso, já usado no cockpit antigo.
MARK_B64 = "VGhlbyBMb3JlbnR6IFBhZGlsaGE="


def seal_key() -> bytes:
    return hashlib.sha256(KEY_MATERIAL).digest()


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))


def _unlock(cipher_b64: str, mac_hex: str) -> str:
    key = seal_key()
    name = _xor(base64.b64decode(cipher_b64), key).decode("utf-8")
    digest = hmac.new(key, name.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, mac_hex):
        raise ValueError("creator seal broken")
    if not name.strip():
        raise ValueError("creator seal empty")
    return name


def creator_name() -> str:
    try:
        return _unlock(CIPHER_B64, MAC_HEX)
    except (ValueError, UnicodeError, binascii.Error):
        return base64.b64decode(MARK_B64).decode("utf-8")


def creator_short_name() -> str:
    try:
        return _unlock(SHORT_CIPHER_B64, SHORT_MAC_HEX)
    except (ValueError, UnicodeError, binascii.Error):
        name = creator_name()
        parts = name.split()
        return f"{parts[0]} {parts[-1]}" if len(parts) >= 2 else name


def fingerprint() -> str:
    return hmac.new(seal_key(), LOCK_ID.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def copyright_line() -> str:
    return f"Copyright (c) 2026 {creator_name()}. All rights reserved."


def verify() -> bool:
    return hmac.compare_digest(creator_name(), base64.b64decode(MARK_B64).decode("utf-8"))
