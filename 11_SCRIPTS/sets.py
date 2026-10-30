#!/usr/bin/env python3
"""Sets pessoais: "quando eu falar X, faz isso".

Um set é um gatilho falado + uma lista de passos + uma frase de resposta.
O Theo cria conversando ("quero criar um set novo") e o JARVIS guarda na
memória do dono. O modo Homem de Ferro é só o primeiro set embutido.

Aqui é só parsing: nada de rede, nada de execução.
"""

from __future__ import annotations

import re
import unicodedata

import spotify_control


TRIGGER_PATTERN = re.compile(
    r"^\s*(?:jarvis[,\s]+)?(?:estilo|modo|vibe|set)\s+(?P<name>[\wÀ-ÿ ]{2,40})\s*[.!?]*\s*$",
    re.I,
)

CREATE_PATTERN = re.compile(
    r"\b(?:cri(?:a|e|ar)|mont(?:a|e|ar)|nov[oa])\b.{0,24}\b(?:set|modo|estilo|vibe)\b"
    r"|\b(?:set|modo|estilo)\s+nov[oa]\b",
    re.I,
)

CANCEL_PATTERN = re.compile(r"^\s*(?:cancela(?:r)?|deixa|para|esquece|nada)\b", re.I)

CONFIRM_PATTERN = re.compile(r"^\s*(?:sim|isso|pode|beleza|fechado|salva|confirma|ok)\b", re.I)

AGENDA_STEP_PATTERN = re.compile(r"\b(?:agenda|compromissos|o\s+que\s+tenho)\b", re.I)

_APP_STEP = re.compile(
    r"\b(?:abr(?:a|e|ir)|inici(?:a|e|ar)|coloca(?:r)?\s+no)\b\s+(?:o\s+|a\s+|os\s+|as\s+)?(?P<app>.+)$",
    re.I,
)

_FOLDER_STEP = re.compile(r"\b(?:pasta|folder)\s+(?P<folder>[\wÀ-ÿ ]{2,30})$", re.I)

_THEME_STEP = re.compile(
    r"\b(?:tema|modo)\s+(?P<theme>claro|escuro|light|dark)\b"
    r"|\b(?:muda|troca|p[oõ]e|coloca|deixa)\b.{0,15}\b(?:pro|para\s+o|pra)?\s*(?P<theme2>claro|escuro)\b",
    re.I,
)

_SPLIT = re.compile(r"\s*(?:,|;|\be\s+depois\b|\bdepois\b|\be\b)\s*", re.I)


def folded(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def parse_trigger(value: str) -> str:
    """Frase de ativação inteira, como o Theo falou.

    Guardar só o nome ("foco" em vez de "estilo foco") faria o set disparar em
    qualquer frase que mencionasse a palavra. O gatilho é a frase completa.
    """
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .,!?")
    if not text or len(text) < 3 or len(text) > 60:
        return ""
    if TRIGGER_PATTERN.match(text) or len(text.split()) <= 3:
        return text
    return ""


def parse_steps(value: str) -> list[dict]:
    """\"toca Back in Black, abre o Slack e fala a agenda\" → passos executáveis."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return []
    steps = []
    for raw in _SPLIT.split(text):
        part = raw.strip(" .,!?")
        if not part:
            continue
        uri = spotify_control.named_track_uri(part)
        if uri:
            steps.append({"kind": "spotify", "uri": uri, "label": _track_label(part)})
            continue
        theme = _THEME_STEP.search(part)
        if theme:
            value = (theme.group("theme") or theme.group("theme2") or "").casefold()
            steps.append({"kind": "theme", "value": "light" if value in {"claro", "light"} else "dark"})
            continue
        if AGENDA_STEP_PATTERN.search(part) and len(part) <= 40:
            steps.append({"kind": "agenda"})
            continue
        folder = _FOLDER_STEP.search(part)
        if folder and re.search(r"\b(?:abr[ae]|mostr[ae])\b", part, re.I):
            steps.append({"kind": "folder", "target": folder.group("folder").strip()})
            continue
        app = _APP_STEP.search(part)
        if app:
            name = app.group("app").strip(" .,!?")
            if name and len(name) <= 40:
                steps.append({"kind": "app", "target": name})
                continue
        volume = re.search(r"\bvolume\s+(?:para|em|no)?\s*(\d{1,3})\b", part, re.I)
        if volume:
            steps.append({"kind": "volume", "level": int(volume.group(1))})
            continue
        if re.search(r"\b(?:no\s+)?mudo\b", part, re.I):
            steps.append({"kind": "volume", "level": 0})
            continue
    return steps


def _track_label(value: str) -> str:
    _, name = spotify_control.resolve_track(value)
    return name.title() if name else "a música"


def describe_steps(steps) -> str:
    """Lista falada do que o set faz."""
    parts = []
    for step in steps or ():
        kind = step.get("kind")
        if kind == "spotify":
            parts.append(f"tocar {step.get('label') or 'a música'}")
        elif kind == "app":
            parts.append(f"abrir o {step.get('target')}")
        elif kind == "folder":
            parts.append(f"abrir a pasta {step.get('target')}")
        elif kind == "volume":
            level = step.get("level", 0)
            parts.append("deixar no mudo" if level == 0 else f"pôr o volume em {level}")
        elif kind == "theme":
            parts.append("mudar o tema pra claro" if step.get("value") == "light" else "mudar o tema pra escuro")
        elif kind == "agenda":
            parts.append("falar a sua agenda")
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " e " + parts[-1]


def match(text: str, sets) -> dict | None:
    """Set cujo gatilho aparece no pedido. O gatilho mais longo vence."""
    spoken = folded(text)
    best = None
    best_len = 0
    for item in sets or ():
        if not isinstance(item, dict):
            continue
        trigger = folded(item.get("trigger") or "")
        if not trigger or trigger not in spoken:
            continue
        if len(trigger) > best_len:
            best = item
            best_len = len(trigger)
    return best


def sets_from_memories(rows) -> list[dict]:
    """Linhas de jarvis_memories → sets executáveis (metadata.action=set)."""
    found = []
    for row in rows or ():
        if not isinstance(row, dict) or row.get("kind") != "preference":
            continue
        metadata = row.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("action") != "set":
            continue
        trigger = str(metadata.get("trigger") or "").strip()
        steps = metadata.get("steps")
        if trigger and isinstance(steps, list) and steps:
            found.append({
                "trigger": trigger,
                "steps": [step for step in steps if isinstance(step, dict)],
                "reply": str(metadata.get("reply") or "").strip(),
            })
    return found


def draft_from_memories(rows) -> dict | None:
    """Rascunho de set em construção (metadata.action=set_draft)."""
    for row in rows or ():
        if not isinstance(row, dict) or row.get("kind") != "preference":
            continue
        metadata = row.get("metadata")
        if isinstance(metadata, dict) and metadata.get("action") == "set_draft":
            return {"id": row.get("id"), **metadata}
    return None
