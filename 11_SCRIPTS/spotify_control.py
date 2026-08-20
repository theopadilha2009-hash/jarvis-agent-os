#!/usr/bin/env python3
"""Pure parsing contract for allowlisted Spotify controls."""

from __future__ import annotations

import re
import unicodedata


TRACK_URI_PATTERN = re.compile(r"^spotify:track:[A-Za-z0-9]{10,40}$")
SAFE_QUERY_PATTERN = re.compile(r"^[\wÀ-ÿ '&.,()_-]{2,120}$", re.UNICODE)
# Pedidos falados curtos → faixa allowlisted. Sem busca livre.
NAMED_TRACKS = {
    "homem de ferro": "spotify:track:4svkPL62HbvyFgf0nHFXAF",
    "iron man": "spotify:track:4svkPL62HbvyFgf0nHFXAF",
}


def folded(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def named_track_uri(value: str) -> str:
    text = folded(value)
    for name, uri in NAMED_TRACKS.items():
        if name in text:
            return uri
    return ""


def control_requested(value: str) -> bool:
    if named_track_uri(value):
        return True
    text = folded(value)
    if "spotify" in text and "musica" in text:
        return True
    controls = (
        "play", "toca", "toque", "tocar", "reprodu", "retoma", "continu", "paus",
        "proxima", "anterior", "volta", "volume", "tocando", "status", "busca", "procura",
        "pesquis", "busqu", "procur", "aleatorio", "shuffle", "repete", "repeticao", "repeat",
    )
    if "spotify" in text and any(token in text for token in controls):
        return True
    return bool(
        re.search(
            r"\b(?:paus\w*|toc\w*|reprodu\w*|volume)\b.{0,35}\b(?:musica|faixa)\b",
            text,
        )
        or re.search(
            r"\b(?:proxim\w*\s+(?:musica|faixa)|(?:musica|faixa)\s+anterior|"
            r"volta\s+para\s+a?\s*(?:musica|faixa)\s+anterior|"
            r"o\s+que\s+(?:esta|ta)\s+tocando)\b",
            text,
        )
    )


def _safe_query(value: str) -> str:
    query = re.sub(r"\s+", " ", str(value or "")).strip(" .,'\"")
    return query if SAFE_QUERY_PATTERN.fullmatch(query) else ""


def command_args(value: str) -> list[str] | None:
    original = re.sub(r"\s+", " ", str(value or "")).strip()
    text = folded(original)
    uri_match = re.search(r"spotify:track:[A-Za-z0-9]{10,40}", original, re.I)
    if uri_match:
        uri = uri_match.group(0)
        return ["play-uri", uri] if TRACK_URI_PATTERN.fullmatch(uri) else None
    named = named_track_uri(original)
    if named:
        return ["play-uri", named]

    volume_match = re.search(r"\bvolume\b[^0-9]{0,30}(\d{1,3})\s*%?", text)
    if volume_match:
        volume = int(volume_match.group(1))
        return ["volume", str(volume)] if 0 <= volume <= 100 else None

    search_match = re.search(
        r"(?i)\b(?:bus(?:ca|car|que)|procur(?:a|ar|e)|pesquis(?:a|ar|e|e))\b\s*"
        r"(?:no\s+spotify\s*)?(?P<query>.+?)(?:\s+(?:no|pelo)\s+spotify)?[.!?]*$",
        original,
    )
    play_query_match = re.search(
        r"(?i)\b(?:to(?:ca|car|que)|reproduz(?:a|ir))\s+(?P<query>.+?)\s+"
        r"(?:no|pelo)\s+spotify\b[.!?]*$",
        original,
    )
    query_match = search_match or play_query_match
    if query_match:
        query = _safe_query(query_match.group("query"))
        return ["search", query] if query else None

    if re.search(r"\b(?:o\s+que\s+(?:esta|ta)\s+tocando|qual\s+(?:musica|faixa)|status)\b", text):
        return ["status"]
    if re.search(r"\b(?:proxima|pula|avanca)\w*\b", text):
        return ["next"]
    if re.search(r"\b(?:(?:musica|faixa)\s+anterior|anterior|volta\w*)\b", text):
        return ["previous"]
    if re.search(r"\b(?:pausa|pause|pausar|pare\s+a\s+musica)\b", text):
        return ["pause"]
    if re.search(r"\b(?:aleatorio|shuffle|embaralh)\w*\b", text):
        disabled = bool(re.search(r"\b(?:desliga|desative|tira|sem|off)\w*\b", text))
        return ["shuffle", "off" if disabled else "on"]
    if re.search(r"\b(?:repete|repeticao|repeat)\w*\b", text):
        disabled = bool(re.search(r"\b(?:desliga|desative|tira|sem|off)\w*\b", text))
        return ["repeat", "off" if disabled else "on"]
    if re.search(r"\b(?:play|toca|toque|tocar|reproduz|retoma|continu)\w*\b", text):
        return ["play"]
    return None


def public_target(args: list[str] | None) -> str:
    if not args:
        return ""
    action = args[0]
    if action in {"search", "play-uri"}:
        return action
    if len(args) > 1 and re.fullmatch(r"[A-Za-z0-9_-]{1,20}", args[1]):
        return f"{action} {args[1]}"[:120]
    return action[:120]
