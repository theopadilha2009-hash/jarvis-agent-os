#!/usr/bin/env python3
"""Preferências que o Theo ensina falando e o JARVIS aplica depois.

"Quando eu te pedir a música do Homem de Ferro, bota essa: <link>". A regra
não fica no código: ela é gravada na memória (jarvis_memories, kind=preference)
e lida pelo gateway e pelo worker do Mac. O que se guarda é o gatilho falado já
normalizado mais a URI explícita — nada de busca livre.
"""

from __future__ import annotations

import re
import unicodedata

TRACK_URI_PATTERN = re.compile(r"^spotify:track:[A-Za-z0-9]{10,40}$")

_URI = r"spotify:track:[A-Za-z0-9]{10,40}"
_LINK = r"https?://open\.spotify\.com/(?:[A-Za-z-]+/)*track/[A-Za-z0-9]{10,40}[^\s]*"

# "quando eu te pedir a música do homem de ferro, bota essa aqui <link>"
# A vírgula é opcional: o reconhecimento de fala costuma engolir ela.
_WHEN = re.compile(
    r"\bquando\s+eu\s+(?:te\s+)?(?:pedir|pedi|falar|falo|mandar|mando|disser|digo|pe[cç]o)\s+"
    r"(?P<trigger>.{2,80}?)\s*,?\s*(?:voc[eê]\s+)?"
    r"(?:bota|bote|toca|toque|coloca|coloque|p[oõ]e|p[oõ]em|usa|use|faz|fa[cç]a)\s+"
    r"(?:(?:essa|esse|esta|este|aqui|nisso|a[ií])\s*){0,3}"
    rf"(?P<target>{_URI}|{_LINK})",
    re.I,
)

# "a música do homem de ferro é essa aqui: <link>"
_IS = re.compile(
    r"^(?P<trigger>.{2,80}?)\s+(?:[eé]|vai\s+ser|ser[aá])\s+"
    r"(?:essa|esse|esta|este)\s*(?:aqui)?\s*[:\-]?\s*"
    rf"(?P<target>{_URI}|{_LINK})$",
    re.I,
)

# O gatilho é guardado sem o enfeite da frase, para casar com o pedido falado
# ("toca a música do homem de ferro" também chega assim, mas "homem de ferro"
# sozinho precisa casar do mesmo jeito).
_FILLER = re.compile(
    r"^(?:(?:a|o|as|os)\s+)?(?:m[uú]sica|faixa|can[cç][aã]o)\s+(?:do|da|de)\s+|"
    r"^(?:a|o|as|os)\s+|^(?:que\s+eu\s+chamo\s+de)\s+",
    re.I,
)


def folded(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def trigger_key(value: str) -> str:
    """Frase falada → chave de casamento (sem acento, sem artigo, minúscula)."""
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .,!?:;\"'")
    text = _FILLER.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .,!?:;\"'")
    return folded(text)


def track_uri(value: str) -> str:
    """Aceita URI do Spotify ou link aberto; devolve a URI canônica ou ""."""
    text = str(value or "")
    match = re.search(_URI, text, re.I)
    if match and TRACK_URI_PATTERN.fullmatch(match.group(0)):
        return match.group(0)
    match = re.search(r"open\.spotify\.com/(?:[A-Za-z-]+/)*track/([A-Za-z0-9]{10,40})", text, re.I)
    return f"spotify:track:{match.group(1)}" if match else ""


def parse_teaching(value: str) -> dict | None:
    """Frase de ensino → regra pronta para gravar. None quando não é ensino."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    match = _WHEN.search(text) or _IS.match(text)
    if not match:
        return None
    key = trigger_key(match.group("trigger"))
    uri = track_uri(match.group("target"))
    if len(key) < 3 or not uri:
        return None
    return {"trigger": key, "action": "spotify_play", "payload": {"uri": uri}}


def learned_uri(value: str, rules) -> str:
    """URI da preferência que casa com o pedido; o gatilho mais longo vence."""
    text = folded(value)
    best_trigger = ""
    best_uri = ""
    for rule in rules or ():
        if not isinstance(rule, dict):
            continue
        trigger = folded(rule.get("trigger") or "")
        payload = rule.get("payload")
        uri = payload.get("uri") if isinstance(payload, dict) else ""
        if not trigger or not isinstance(uri, str) or not TRACK_URI_PATTERN.fullmatch(uri):
            continue
        if trigger in text and len(trigger) > len(best_trigger):
            best_trigger = trigger
            best_uri = uri
    return best_uri


def rules_from_memories(rows) -> list[dict]:
    """Linhas de jarvis_memories → regras executáveis (kind=preference)."""
    rules = []
    for row in rows or ():
        if not isinstance(row, dict) or row.get("kind") != "preference":
            continue
        metadata = row.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("action") != "spotify_play":
            continue
        trigger = str(metadata.get("trigger") or "").strip()
        payload = metadata.get("payload")
        uri = payload.get("uri") if isinstance(payload, dict) else ""
        if trigger and isinstance(uri, str) and TRACK_URI_PATTERN.fullmatch(uri):
            rules.append({"trigger": trigger, "payload": {"uri": uri}})
    return rules
