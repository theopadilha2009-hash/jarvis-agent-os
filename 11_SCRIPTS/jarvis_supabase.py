#!/usr/bin/env python3
"""Acesso mínimo ao Supabase do JARVIS pelos comandos locais.

As credenciais ficam no worker.env que o device worker já usa — o terminal não
tem cópia própria. Sem credencial, quem chama cai no modo local.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


WORKER_ENV = Path.home() / "Library" / "Application Support" / "JARVIS" / "worker.env"


def credentials() -> tuple[str, str]:
    """URL e chave server-side do worker.env. ("","") quando indisponível."""
    if not WORKER_ENV.is_file():
        return "", ""
    values = {}
    try:
        for raw in WORKER_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    except OSError:
        return "", ""
    return values.get("SUPABASE_URL", "").rstrip("/"), values.get("SUPABASE_SERVICE_ROLE_KEY", "")


def rest(base: str, key: str, table: str, method: str = "GET", query: str = "", body=None):
    url = f"{base}/rest/v1/{table}"
    if query:
        url = f"{url}?{query}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        raw = response.read(4_000_000)
    return json.loads(raw.decode("utf-8")) if raw else []
