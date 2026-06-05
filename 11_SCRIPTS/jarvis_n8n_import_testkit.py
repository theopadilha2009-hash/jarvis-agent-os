from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "217_N8N_IMPORT_TESTKIT"


def slug(value: str, fallback: str = "n8n-testkit") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip().lower()).strip("-")
    return s[:90] or fallback


def latest_file(pattern: str) -> Path | None:
    files = [p for p in REPO.glob(pattern) if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def find_latest_export() -> Path | None:
    candidates = [
        latest_file("05_EXECUCAO/207_N8N_EXPORT_PACKAGER/**/IMPORT_THIS_IN_N8N.json"),
        latest_file("05_EXECUCAO/204_N8N_WORKFLOW_BUILDER/**/workflow_skeleton.importable.json"),
    ]
    return next((p for p in candidates if p and p.exists()), None)


def node_names(workflow: dict[str, Any]) -> list[str]:
    return [str(n.get("name", "")) for n in workflow.get("nodes", []) if isinstance(n, dict)]


def node_types(workflow: dict[str, Any]) -> list[str]:
    return [str(n.get("type", "")) for n in workflow.get("nodes", []) if isinstance(n, dict)]


def webhook_nodes(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        t = str(node.get("type", "")).lower()
        name = str(node.get("name", ""))
        if "webhook" in t and "respond" not in t:
            params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
            out.append({
                "name": name,
                "type": node.get("type"),
                "path": params.get("path") or params.get("webhookPath") or "REVIEW_PATH_IN_N8N",
                "method": str(params.get("httpMethod") or params.get("method") or "POST").upper(),
                "auth": params.get("authentication") or params.get("auth") or "none_or_not_configured",
            })
    return out


def has_manual_trigger(workflow: dict[str, Any]) -> bool:
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if "manualtrigger" in str(node.get("type", "")).lower() or "manual trigger" in str(node.get("name", "")).lower():
            return True
    return False


def make_payloads(out_dir: Path) -> dict[str, str]:
    payloads = {
        "01_normal_lead.json": {
            "event": "message",
            "fromMe": False,
            "message": {"text": "Oi, quero saber mais sobre atendimento"},
            "contact": {"name": "Lead Teste", "phone": "5500000000000"},
            "source": "jarvis-testkit",
        },
        "02_human_transfer.json": {
            "event": "message",
            "fromMe": False,
            "message": {"text": "Quero falar com um humano"},
            "contact": {"name": "Lead Humano", "phone": "5500000000001"},
            "source": "jarvis-testkit",
        },
        "03_empty_message.json": {
            "event": "message",
            "fromMe": False,
            "message": {"text": ""},
            "contact": {"name": "Lead Vazio", "phone": "5500000000002"},
            "source": "jarvis-testkit",
        },
        "04_anti_loop_from_me.json": {
            "event": "message",
            "fromMe": True,
            "message": {"text": "Mensagem enviada pelo bot"},
            "contact": {"name": "Bot", "phone": "5500000000003"},
            "source": "n8n",
        },
        "05_low_context.json": {
            "event": "message",
            "fromMe": False,
            "message": {"text": "oi"},
            "contact": {"name": "Lead Curto", "phone": "5500000000004"},
            "source": "jarvis-testkit",
        },
    }

    written = {}
    for name, payload in payloads.items():
        p = out_dir / name
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written[name] = str(p.relative_to(REPO))
    return written


def run(client: str, base_url: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{ts}_{slug(client)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    export_path = find_latest_export()
    workflow = read_json(export_path)

    blockers = []
    warnings = []

    if not export_path:
        blockers.append("missing latest n8n export")
    if workflow.get("active") is not False:
        blockers.append("workflow active must be false before import test kit")
    if not has_manual_trigger(workflow):
        warnings.append("manual trigger not found in selected export; keep import inactive and use n8n-ready/manual-guard before real run")
    if len(node_names(workflow)) < 5:
        blockers.append("workflow has too few nodes")

    webhooks = webhook_nodes(workflow)
    if not webhooks:
        warnings.append("no inbound webhook nodes found")
    else:
        for wh in webhooks:
            if wh["path"] in {"", "REVIEW_PATH_IN_N8N"}:
                warnings.append(f"{wh['name']}: webhook path must be reviewed after import")
            if str(wh["auth"]).lower() in {"none", "none_or_not_configured", "", "noauth"}:
                warnings.append(f"{wh['name']}: auth not configured; keep inactive/test-only")

    payload_files = make_payloads(out_dir)

    curl_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'BASE_URL="${1:-' + base_url.rstrip("/") + '}"',
        'WEBHOOK_PATH="${2:-REVIEW_PATH_AFTER_IMPORT}"',
        'TARGET="$BASE_URL/webhook-test/$WEBHOOK_PATH"',
        "",
        'echo "Target: $TARGET"',
        "",
    ]

    for fname in payload_files:
        curl_lines += [
            f'echo "\\n--- POST {fname} ---"',
            f'curl -sS -X POST "$TARGET" -H "Content-Type: application/json" --data-binary "@{fname}"',
            "echo",
            "",
        ]

    curl_path = out_dir / "run_curl_smoke.sh"
    curl_path.write_text("\n".join(curl_lines), encoding="utf-8")
    curl_path.chmod(0o755)

    verdict = "pass" if not blockers else "block"

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "client": client,
        "workflow_path": str(export_path.relative_to(REPO)) if export_path else None,
        "workflow_name": workflow.get("name"),
        "active": workflow.get("active"),
        "nodes": len(node_names(workflow)),
        "manual_trigger": has_manual_trigger(workflow),
        "webhooks": webhooks,
        "payload_files": payload_files,
        "curl_script": str(curl_path.relative_to(REPO)),
        "blockers": blockers,
        "warnings": warnings,
        "status_real": "local_import_testkit_only_not_n8n_ui_or_runtime_validated_manual_trigger_checked_by_ready_guard",
        "not_validated": [
            "not imported in n8n UI",
            "not executed in n8n runtime",
            "no credentials connected",
            "no real webhook activated",
            "no production",
        ],
    }

    (out_dir / "N8N_IMPORT_TESTKIT.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# JARVIS n8n Import Test Kit",
        "",
        f"- verdict: `{verdict}`",
        f"- client: `{client}`",
        f"- workflow: `{payload['workflow_path']}`",
        f"- active: `{payload['active']}`",
        f"- nodes: `{payload['nodes']}`",
        f"- manual_trigger: `{payload['manual_trigger']}`",
        f"- curl_script: `{payload['curl_script']}`",
        "",
        "## Files",
        "",
    ]

    for name, path in payload_files.items():
        md.append(f"- `{name}` → `{path}`")

    md += ["", "## Webhooks", ""]
    if webhooks:
        for wh in webhooks:
            md.append(f"- `{wh['name']}` method=`{wh['method']}` path=`{wh['path']}` auth=`{wh['auth']}`")
    else:
        md.append("- none")

    md += ["", "## Blockers", ""]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]

    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]

    md += [
        "",
        "## How to use after n8n import",
        "",
        "```bash",
        f"cd {out_dir.relative_to(REPO)}",
        "./run_curl_smoke.sh https://YOUR_N8N_DOMAIN YOUR_WEBHOOK_TEST_PATH",
        "```",
        "",
        "Status real: generated local payload/curl kit only. Import/runtime still manual.",
        "",
    ]

    (out_dir / "N8N_IMPORT_TESTKIT.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_IMPORT_TESTKIT_DONE")
    print(out_dir / "N8N_IMPORT_TESTKIT.md")
    print(json.dumps({
        "verdict": verdict,
        "workflow_path": payload["workflow_path"],
        "nodes": payload["nodes"],
        "manual_trigger": payload["manual_trigger"],
        "payload_count": len(payload_files),
        "curl_script": payload["curl_script"],
        "blockers": blockers,
        "warnings": warnings,
    }, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="n8n-import-testkit")
    parser.add_argument("--base-url", default="https://YOUR_N8N_DOMAIN")
    args = parser.parse_args()
    return run(args.client, args.base_url)


if __name__ == "__main__":
    raise SystemExit(main())
