#!/usr/bin/env python3
"""Point jarvis-theo.vercel.app at a jarvis-agent-os production deployment.

Merge on GitHub does not move the public alias. This script is the last step
after `vercel --prod` on project jarvis-agent-os.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ALIAS = "jarvis-theo.vercel.app"
PRODUCTION_URL = f"https://{PRODUCTION_ALIAS}"
VERCEL_PROJECT = "jarvis-agent-os"
ALLOWED_HOST_PATTERN = re.compile(r"^jarvis-agent-os(?:-[a-z0-9-]+)?\.vercel\.app$")
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def run(argv: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=os.environ.copy(),
    )


def deployment_host(value: str) -> str:
    text = ANSI_ESCAPE.sub("", str(value or "")).strip()
    text = re.sub(r"^https://", "", text, flags=re.I).split("/")[0].strip().casefold()
    if not ALLOWED_HOST_PATTERN.fullmatch(text):
        return ""
    return text


def latest_production_host(vercel: str) -> str:
    listed = run([vercel, "ls", VERCEL_PROJECT, "--prod", "--json"], timeout=90)
    raw = listed.stdout or listed.stderr or ""
    if listed.returncode == 0:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        rows = []
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = payload.get("deployments") or payload.get("data") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            host = deployment_host(str(row.get("url") or row.get("urlHostname") or ""))
            if host:
                return host
    hosts = []
    for match in re.findall(r"https://[A-Za-z0-9.-]+\.vercel\.app", ANSI_ESCAPE.sub("", raw)):
        host = deployment_host(match)
        if host and host not in hosts:
            hosts.append(host)
    return hosts[0] if hosts else ""


def apply_alias(deployment: str, vercel: str | None = None, preview: bool = False) -> dict:
    host = deployment_host(deployment)
    binary = vercel or shutil.which("vercel")
    if not host:
        raise ValueError("Deploy fora do projeto jarvis-agent-os.")
    if not binary:
        raise ValueError("Vercel CLI não encontrado.")
    if preview:
        return {
            "ok": True,
            "preview": True,
            "deployment": f"https://{host}",
            "alias": PRODUCTION_URL,
            "command": [binary, "alias", "set", host, PRODUCTION_ALIAS],
        }
    aliased = run([binary, "alias", "set", host, PRODUCTION_ALIAS], timeout=180)
    output = (aliased.stdout or "") + "\n" + (aliased.stderr or "")
    if aliased.returncode != 0:
        raise RuntimeError(f"A Vercel recusou o alias ({aliased.returncode}).")
    return {
        "ok": True,
        "preview": False,
        "deployment": f"https://{host}",
        "alias": PRODUCTION_URL,
        "output": output.strip()[:2_000],
    }


def production_health() -> dict:
    request = Request(
        f"{PRODUCTION_URL}/status",
        headers={"Accept": "application/json", "User-Agent": "jarvis-promote-production/1"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read(200_000).decode("utf-8"))
    if response.status != 200 or not payload.get("ok") or payload.get("service") != "jarvis-web":
        raise RuntimeError("jarvis-theo.vercel.app não confirmou /status.")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alias jarvis-theo.vercel.app no último deploy de jarvis-agent-os")
    parser.add_argument("--deployment", help="URL ou host do deploy (opcional; senão usa o último --prod)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    preview = bool(args.dry_run or os.environ.get("JARVIS_NO_REPORT") == "1")
    print("JARVIS — Promote Production")
    print("Status real: aponta jarvis-theo.vercel.app para um deploy de jarvis-agent-os.")
    try:
        vercel = shutil.which("vercel")
        if preview:
            host = deployment_host(args.deployment or "")
            if vercel and not host:
                try:
                    host = latest_production_host(vercel)
                except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
                    host = ""
            print(f"Deploy: https://{host}" if host else "Deploy: último jarvis-agent-os --prod (consulta no live)")
            print(f"Alias: {PRODUCTION_URL}")
            print(f"Preview: vercel alias set {host or '<deploy>'} {PRODUCTION_ALIAS}")
            print("Modo preview: nenhum alias foi alterado.")
            print("Produção: nada alterado.")
            return 0
        if not vercel:
            raise RuntimeError("Vercel CLI não está instalado.")
        host = deployment_host(args.deployment or "") or latest_production_host(vercel)
        if not host:
            raise RuntimeError("Não achei um deploy de produção do jarvis-agent-os.")
        result = apply_alias(host, vercel, preview=False)
        print(f"Deploy: {result['deployment']}")
        print(f"Alias: {result['alias']}")
        health = production_health()
        print(f"Saúde: {health.get('status_real') or 'web_cockpit_ready'}")
        print(f"Produção: {PRODUCTION_URL} aponta para {result['deployment']}.")
        return 0
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, json.JSONDecodeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Falha: {error}")
        print("Produção: nada alterado." if preview else "Produção: alias não confirmado.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
