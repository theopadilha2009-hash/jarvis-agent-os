#!/usr/bin/env python3
"""Pure parsing contract for allowlisted Spotify controls."""

from __future__ import annotations

import re
import unicodedata


TRACK_URI_PATTERN = re.compile(r"^spotify:track:[A-Za-z0-9]{10,40}$")
# "/" é necessário para "AC/DC"; ":" continua fora porque separa URI de faixa.
SAFE_QUERY_PATTERN = re.compile(r"^[\wÀ-ÿ '&.,()_/-]{2,120}$", re.UNICODE)
# Pedidos falados curtos → faixa allowlisted. Sem busca livre.
# "Back In Black" — AC/DC, do álbum Iron Man 2. ID conferido por Theo em
# open.spotify.com/track/2iEGj7kAwH7HAa5epwYwLB (2026-10-30).
BACK_IN_BLACK_URI = "spotify:track:2iEGj7kAwH7HAa5epwYwLB"
NAMED_TRACKS = {
    # Escolha do Theo (2026-10-30): "música do Homem de Ferro" é a do CD do
    # Iron Man 2, não o Iron Man do Black Sabbath.
    "homem de ferro": BACK_IN_BLACK_URI,
    "iron man": BACK_IN_BLACK_URI,
    "back in black": BACK_IN_BLACK_URI,
}


def folded(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


# Preferências que o Theo ensinou falando (jarvis_memories, kind=preference).
# Vencem o catálogo fixo: quem manda é o que ele pediu por último, não o código.
_LEARNED_TRACKS: dict[str, str] = {}


def set_learned_tracks(rules) -> None:
    """Regras de preferences.rules_from_memories() → gatilho normalizado e URI."""
    global _LEARNED_TRACKS
    learned = {}
    for rule in rules or ():
        if not isinstance(rule, dict):
            continue
        payload = rule.get("payload")
        uri = payload.get("uri") if isinstance(payload, dict) else ""
        trigger = folded(rule.get("trigger") or "")
        if trigger and isinstance(uri, str) and TRACK_URI_PATTERN.fullmatch(uri):
            learned[trigger] = uri
    _LEARNED_TRACKS = learned


def learned_tracks() -> dict[str, str]:
    return dict(_LEARNED_TRACKS)


def resolve_track(value: str) -> tuple[str, str]:
    """Nome falado → (uri, nome canônico). ("", "") quando fora do catálogo."""
    text = folded(value)
    best = ""
    for name in _LEARNED_TRACKS:
        if name in text and len(name) > len(best):
            best = name
    if best:
        return _LEARNED_TRACKS[best], best
    for name, uri in NAMED_TRACKS.items():
        if name in text:
            return uri, name
    return "", ""


def named_track_uri(value: str) -> str:
    return resolve_track(value)[0]


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

    # "abre o spotify" sozinho: abrir o app, sem tocar nada.
    if re.search(r"\b(?:abr(?:e|ir|a)|inici(?:a|e|ar))\w*\b.{0,24}\bspotify\b", text):
        return ["open"]

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
