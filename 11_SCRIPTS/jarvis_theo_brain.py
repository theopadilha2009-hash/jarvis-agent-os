#!/usr/bin/env python3
"""Slim OpenRouter client for JARVIS-THEO.

Fast models first. One model per try. Rotate key on auth/quota, model on 400.
Does not import the web gateway. Does not write files.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FAST_MODELS = (
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "google/gemma-4-26b-a4b-it:free",
    "openai/gpt-oss-20b:free",
    "openrouter/free",
)
SYSTEM = (
    "Você é o JARVIS, assistente pessoal do Theo Padilha (lab local, um operador). "
    "Responda em PT-BR, curto e direto. "
    "Fatos seus: voz principal Pocket TTS local (portuguese + bill_boerst), sem cota e sem chave; "
    "se o servidor local cair, o Mac usa o `say`. Cockpit web em /speech. "
    "Login do Theo = o mesmo do Ultron. Contas de amigo usam JARVIS + modo code, sem Mac. "
    "Você pesquisa a web quando o pedido pede fonte, preço, notícia ou documentação. "
    "Você NÃO grava, substitui, apaga nem executa código no disco neste chat. "
    "Você NÃO faz deploy, merge, push, PR nem publica nada. "
    "Se pedirem para criar ou editar arquivo, mostre o rascunho e diga que só aplica com /aplicar. "
    "Nunca toque .env. Não finja que um teste passou. "
    "Não diga que consegue executar o que você não executa. "
    "Se uma rota OpenRouter falhar, admita e continue útil com o que souber."
)
CAREFUL_SYSTEM = (
    SYSTEM
    + " MODO CALMA: o pedido é melhoria de verdade. "
    "Primeiro mostre que entendeu. Depois um plano com no máximo 3 passos pequenos. "
    "Não proponha mega-refactor. Não fale de deploy/merge como ação sua. "
    "Espere o Theo escolher o próximo passo antes de detalhar código longo."
)
CAREFUL_RE = re.compile(
    r"\b(?:melhor(?:ar|ia)?|deploy|merge|refator|c[oó]digo|arquivo|substitu|"
    r"criar|implement|commit|pr\b|produ[cç][aã]o|escrev)\b",
    re.I,
)
KEY_RETRY = {401, 402, 403, 408, 409, 429, 500, 502, 503, 504}
MODEL_RETRY = {400, 404, 408, 409, 422, 429, 500, 502, 503, 504}


def configured_keys(environ: dict | None = None) -> list[str]:
    env = environ if environ is not None else os.environ
    keys: list[str] = []
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_FALLBACK_API_KEY"):
        value = str(env.get(name) or "").strip()
        if value and value not in keys:
            keys.append(value)
    for value in str(env.get("OPENROUTER_API_KEYS") or "").split(","):
        value = value.strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def extract_text(data: dict) -> str:
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        return "\n".join(str(item.get("text") or "") for item in content if isinstance(item, dict)).strip()
    return str(content or "").strip()


def _post(api_key: str, model: str, messages: list[dict], timeout: int) -> dict:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 420,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "JARVIS-THEO",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def chat(
    prompt: str,
    history: list[dict] | None = None,
    *,
    keys: list[str] | None = None,
    models: tuple[str, ...] | None = None,
    timeout: int = 12,
    poster=None,
) -> dict:
    api_keys = list(keys if keys is not None else configured_keys())
    model_list = tuple(models or FAST_MODELS)
    send = poster or _post
    if not api_keys:
        return {
            "ok": False,
            "status": 401,
            "error": "Nenhuma chave OpenRouter carregada.",
            "retryable": False,
            "attempts": [],
        }
    system = CAREFUL_SYSTEM if CAREFUL_RE.search(prompt or "") else SYSTEM
    messages = [{"role": "system", "content": system}]
    for row in (history or [])[-8:]:
        role = row.get("role")
        content = str(row.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    attempts = []
    last_status = 0
    last_error = ""
    key_failover = False
    for key_index, api_key in enumerate(api_keys):
        for model in model_list:
            try:
                data = send(api_key, model, messages, timeout)
                text = extract_text(data)
                if not text:
                    attempts.append({"model": model, "outcome": "empty"})
                    continue
                attempts.append({"model": model, "outcome": "ok"})
                used = data.get("model") or model
                return {
                    "ok": True,
                    "status": 200,
                    "message": text,
                    "model": used,
                    "provider": "openrouter",
                    "openrouter_key_failover": key_failover,
                    "attempts": attempts,
                    "model_routing": {
                        "selected": used,
                        "compatibility_fallback": len(attempts) > 1,
                        "compatibility_attempts": attempts,
                    },
                }
            except urllib.error.HTTPError as error:
                last_status = error.code
                last_error = f"HTTP {error.code}"
                attempts.append({"model": model, "outcome": f"http_{error.code}"})
                if error.code in KEY_RETRY and key_index + 1 < len(api_keys):
                    key_failover = True
                    break
                if error.code in MODEL_RETRY:
                    continue
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
                last_status = 504
                last_error = error.__class__.__name__
                attempts.append({"model": model, "outcome": "timeout_or_network"})
                continue
        else:
            continue
        continue

    return {
        "ok": False,
        "status": last_status or 502,
        "error": (
            "Tentei as rotas rápidas e as chaves de reserva. "
            f"Último erro: {last_error or 'sem resposta'}."
        ),
        "retryable": True,
        "openrouter_key_failover": key_failover,
        "attempts": attempts,
        "message": (
            "Tentei as rotas rápidas e as chaves de reserva. "
            f"Último erro: {last_error or 'sem resposta'}."
        ),
    }
