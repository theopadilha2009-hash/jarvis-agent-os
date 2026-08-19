#!/usr/bin/env python3
"""Allowlisted Mac/web execution parsers shared by the gateway and device worker.

No arbitrary shell. Values are extracted from explicit natural-language
requests and validated before any adapter runs.
"""

from __future__ import annotations

from urllib.parse import urlparse
import json
import re


PAYLOAD_SCHEMA = "jarvis-device-payload/1"
MAX_TEXT_CHARS = 4_000
HTTPS_URL_PATTERN = re.compile(r"https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+", re.I)
BLOCKED_HOST_PATTERN = re.compile(
    r"^(?:localhost|127\.|0\.|169\.254\.|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|"
    r"metadata(?:\.google\.internal)?|(?:.+\.)?local)$",
    re.I,
)
CLIPBOARD_PATTERN = re.compile(
    r"\b(?:copi(?:a|e|ar))\b.{0,48}?\b(?:"
    r"(?:para|pra|pro)\s+(?:a\s+)?(?:[aá]rea\s+de\s+transfer[eê]ncia|clipboard)|"
    r"isso|isto|este\s+texto|o\s+texto"
    r")\b\s*[:\-]?\s*(?P<body>.+)$",
    re.I | re.S,
)
SPEAK_PATTERN = re.compile(
    r"\b(?:ler\s+em\s+voz\s+alta|fal(?:a|e|ar)\s+no\s+mac|diz(?:er)?\s+no\s+mac)\b"
    r"\s*[:\-]?\s*(?P<body>.*)$",
    re.I | re.S,
)
NOTIFY_PATTERN = re.compile(
    r"\b(?:avis(?:a|e|ar)|notific(?:a|e|ar))\b.{0,48}\bno\s+mac\b\s*[:\-]?\s*(?P<body>.+)$",
    re.I | re.S,
)
VOLUME_PATTERN = re.compile(
    r"\b(?:silenci(?:a|e|ar)|mute)\b.{0,24}\b(?:mac|sistema|computador)\b|"
    r"\bvolume\s+d[oa]\s+(?:mac|sistema|computador)\b.{0,24}"
    r"(?:(?P<level>\d{1,3})|(?P<max>m[aá]ximo)|(?P<mute>mudo|zero))",
    re.I,
)
FOLDER_PATTERN = re.compile(
    r"\b(?:abr(?:a|e|ir)|mostr(?:a|e|ar))\b.{0,48}?\b(?:o\s+finder\s+(?:em|no|na|nos|nas)\s+)?"
    r"(?:pasta\s+)?(?P<folder>downloads?|desktop|mesa|documentos|documents|home|in[ií]cio)\b",
    re.I,
)
MAC_OPEN_HINT = re.compile(r"\bno\s+(?:meu\s+)?(?:mac|computador)\b", re.I)
FOLDER_ALIASES = {
    "download": "downloads",
    "downloads": "downloads",
    "desktop": "desktop",
    "mesa": "desktop",
    "documentos": "documents",
    "documents": "documents",
    "home": "home",
    "inicio": "home",
    "início": "home",
}
FOLDER_LABELS = {
    "downloads": "Downloads",
    "desktop": "Desktop",
    "documents": "Documentos",
    "home": "pasta pessoal",
}


def _clean_body(value: str) -> str:
    text = str(value or "").strip(" \t\r\n:-")
    text = re.sub(r"\s+", " ", text).strip(" \"“”'")
    return text[:MAX_TEXT_CHARS]


def payload_json(kind: str, value: str, **extra: object) -> str:
    row = {"schema": PAYLOAD_SCHEMA, "kind": str(kind), "value": str(value)[:MAX_TEXT_CHARS]}
    row.update(extra)
    return json.dumps(row, ensure_ascii=False)


def payload_from_text(raw: str) -> dict:
    text = str(raw or "").strip()
    if text.startswith("{"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            value = {}
        if isinstance(value, dict) and value.get("schema") == PAYLOAD_SCHEMA:
            return value
    return {}


def safe_https_url(value: str) -> str:
    text = str(value or "").strip().rstrip(").,;")
    if len(text) > 500 or not HTTPS_URL_PATTERN.fullmatch(text):
        return ""
    parsed = urlparse(text)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host or BLOCKED_HOST_PATTERN.match(host):
        return ""
    if parsed.username or parsed.password:
        return ""
    return text


def extract_https_url(text: str) -> str:
    match = HTTPS_URL_PATTERN.search(str(text or ""))
    return safe_https_url(match.group(0)) if match else ""


def clipboard_text(command: str, raw: str = "") -> str:
    payload = payload_from_text(raw or command)
    if payload.get("kind") == "clipboard_set":
        return _clean_body(str(payload.get("value") or ""))
    match = CLIPBOARD_PATTERN.search(str(command or ""))
    return _clean_body(match.group("body")) if match else ""


def speak_text(command: str, raw: str = "") -> str:
    payload = payload_from_text(raw or command)
    if payload.get("kind") == "speak":
        return _clean_body(str(payload.get("value") or ""))
    match = SPEAK_PATTERN.search(str(command or ""))
    return _clean_body(match.group("body")) if match else ""


def notify_text(command: str, raw: str = "") -> str:
    payload = payload_from_text(raw or command)
    if payload.get("kind") == "notify":
        return _clean_body(str(payload.get("value") or ""))
    match = NOTIFY_PATTERN.search(str(command or ""))
    return _clean_body(match.group("body")) if match else ""


def volume_level(command: str, target: str = "", raw: str = "") -> int | None:
    if re.fullmatch(r"\d{1,3}", str(target or "").strip()):
        level = int(target)
        return level if 0 <= level <= 100 else None
    payload = payload_from_text(raw or command)
    if payload.get("kind") == "volume_set":
        try:
            level = int(str(payload.get("value") or ""))
        except ValueError:
            return None
        return level if 0 <= level <= 100 else None
    match = VOLUME_PATTERN.search(str(command or ""))
    if not match:
        return None
    if match.group("mute") or re.search(r"\b(?:silenci|mute)\b", match.group(0), re.I):
        return 0
    if match.group("max"):
        return 100
    if match.group("level"):
        level = int(match.group("level"))
        return level if 0 <= level <= 100 else None
    return None


def folder_id(command: str, target: str = "", raw: str = "") -> str:
    alias = FOLDER_ALIASES.get(str(target or "").strip().casefold())
    if alias:
        return alias
    payload = payload_from_text(raw or command)
    if payload.get("kind") == "open_folder":
        alias = FOLDER_ALIASES.get(str(payload.get("value") or "").strip().casefold())
        if alias:
            return alias
    match = FOLDER_PATTERN.search(str(command or ""))
    if not match:
        return ""
    return FOLDER_ALIASES.get(match.group("folder").casefold(), "")


def mac_open_requested(command: str) -> bool:
    return bool(MAC_OPEN_HINT.search(str(command or "")))
