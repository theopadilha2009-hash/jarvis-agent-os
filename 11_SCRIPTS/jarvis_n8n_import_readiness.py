#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "05_EXECUCAO" / "209_N8N_WORKFLOW_PIPELINE"
CARD_DIR = ROOT / "05_EXECUCAO" / "210_N8N_OPERATOR_CARD"
OUT = ROOT / "05_EXECUCAO" / "212_N8N_IMPORT_READINESS"
OUT.mkdir(parents=True, exist_ok=True)

SECRET_PATTERNS = {
    "openai_key": r"sk-[A-Za-z0-9_\-]{20,}",
    "google_key": r"AIza[0-9A-Za-z_\-]{20,}",
    "github_token": r"ghp_[0-9A-Za-z]{20,}",
    "slack_token": r"xox[baprs]-[0-9A-Za-z\-]{20,}",
    "bearer_token": r"Bearer\s+[A-Za-z0-9_\-\.]{24,}",
    "private_key": r"-----BEGIN\s+(?:RSA\s+)?PRIVATE KEY-----",
}

def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"command_error: {exc}"

def load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def latest_named(base: Path, name: str) -> Path | None:
    if not base.exists():
        return None
    files = sorted(base.rglob(name), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def find_export_path(obj: Any) -> str | None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and value.endswith("IMPORT_THIS_IN_N8N.json"):
                return value
            found = find_export_path(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_export_path(item)
            if found:
                return found
    return None

def to_path(value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else ROOT / p

def recursive_credentials_hits(obj: Any, path: str = "$") -> list[str]:
    hits = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}"
            if key == "credentials" and value not in ({}, None, [], ""):
                hits.append(next_path)
            hits.extend(recursive_credentials_hits(value, next_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            hits.extend(recursive_credentials_hits(item, f"{path}[{i}]"))
    return hits

def scan_secret_like(raw: str) -> list[str]:
    hits = []
    for label, pattern in SECRET_PATTERNS.items():
        if re.search(pattern, raw):
            hits.append(label)
    return hits

def node_names(workflow: dict[str, Any]) -> list[str]:
    nodes = workflow.get("nodes") or []
    names = []
    for node in nodes:
        if isinstance(node, dict):
            names.append(str(node.get("name") or node.get("type") or "unnamed"))
    return names

def main() -> int:
    pipeline_path = latest_named(PIPELINE_DIR, "N8N_PIPELINE.json")
    card_path = latest_named(CARD_DIR, "N8N_OPERATOR_CARD.json")

    pipeline = load_json(pipeline_path) or {}
    card = load_json(card_path) or {}

    export_raw = (
        card.get("export_path")
        or find_export_path(card)
        or find_export_path(pipeline)
    )
    export_path = to_path(export_raw)
    workflow = load_json(export_path)

    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    checks["pipeline_json"] = str(pipeline_path.relative_to(ROOT)) if pipeline_path else None
    checks["operator_card_json"] = str(card_path.relative_to(ROOT)) if card_path else None
    checks["export_path"] = str(export_path.relative_to(ROOT)) if export_path and export_path.exists() else export_raw
    checks["export_exists"] = bool(export_path and export_path.exists())
    checks["operator_card_verdict"] = card.get("verdict")
    checks["pipeline_verdict"] = pipeline.get("verdict") or (pipeline.get("summary") or {}).get("verdict")

    if checks["operator_card_verdict"] != "pass":
        blockers.append(f"operator card is not pass: {checks['operator_card_verdict']!r}")
    if checks["pipeline_verdict"] != "pass":
        blockers.append(f"pipeline is not pass: {checks['pipeline_verdict']!r}")
    if not checks["export_exists"]:
        blockers.append("IMPORT_THIS_IN_N8N.json not found")

    if not isinstance(workflow, dict):
        blockers.append("export workflow JSON could not be parsed")
        workflow = {}

    required_keys = ["name", "nodes", "connections", "active"]
    missing_keys = [k for k in required_keys if k not in workflow]
    if missing_keys:
        blockers.append("missing required n8n keys: " + ", ".join(missing_keys))

    nodes = workflow.get("nodes") if isinstance(workflow.get("nodes"), list) else []
    connections = workflow.get("connections") if isinstance(workflow.get("connections"), dict) else {}

    checks["workflow_name"] = workflow.get("name")
    checks["active"] = workflow.get("active")
    checks["nodes"] = len(nodes)
    checks["connections"] = len(connections)
    checks["node_names"] = node_names(workflow)[:30]

    if workflow.get("active") is not False:
        blockers.append(f"workflow active flag must be false, got {workflow.get('active')!r}")

    if len(nodes) < 8:
        blockers.append(f"workflow has too few nodes: {len(nodes)}")

    credential_hits = recursive_credentials_hits(workflow)
    checks["credential_hits"] = credential_hits
    if credential_hits:
        blockers.append("workflow contains non-empty credentials fields")

    raw_export = json.dumps(workflow, ensure_ascii=False)
    secret_hits = scan_secret_like(raw_export)
    checks["secret_hits"] = secret_hits
    if secret_hits:
        blockers.append("secret-like patterns detected: " + ", ".join(secret_hits))

    has_manual = any(
        isinstance(n, dict) and (
            "manualTrigger" in str(n.get("type", ""))
            or "Manual Trigger" in str(n.get("name", ""))
        )
        for n in nodes
    )
    checks["has_manual_trigger"] = has_manual
    if not has_manual:
        warnings.append("manual trigger not detected; import must be reviewed carefully before any run")

    webhook_nodes = [
        str(n.get("name") or n.get("type"))
        for n in nodes
        if isinstance(n, dict) and "webhook" in str(n.get("type", "")).lower()
    ]
    checks["webhook_nodes"] = webhook_nodes
    if webhook_nodes:
        warnings.append("webhook nodes exist; keep workflow inactive until endpoint/credential review")

    checks["git_status"] = run(["git", "status", "-sb"])
    checks["last_commit"] = run(["git", "log", "--oneline", "-1"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "status_real": "local_import_readiness_only_not_n8n_ui_runtime_credential_webhook_or_production_validated",
        "manual_import_steps": [
            "Open n8n manually.",
            "Create or open a test/sandbox workflow area.",
            "Import IMPORT_THIS_IN_N8N.json.",
            "Confirm active=false before saving or executing.",
            "Check every node visually.",
            "Attach credentials only inside n8n Credentials UI.",
            "Run Manual Trigger first.",
            "Do not activate webhook nodes.",
            "Do not send real WhatsApp/email/API calls.",
            "Only move to runtime test after human approval.",
        ],
        "never_claim_yet": [
            "production ready",
            "runtime validated",
            "credentials configured",
            "webhook validated",
            "WhatsApp/email sending validated",
            "client delivery validated",
        ],
    }

    (OUT / "N8N_IMPORT_READINESS.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# JARVIS n8n Import Readiness",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- created_at: `{payload['created_at']}`",
        f"- status_real: `{payload['status_real']}`",
        f"- last_commit: `{checks['last_commit']}`",
        f"- export_path: `{checks['export_path']}`",
        f"- workflow_name: `{checks['workflow_name']}`",
        f"- active: `{checks['active']}`",
        f"- nodes: `{checks['nodes']}`",
        f"- connections: `{checks['connections']}`",
        f"- export_exists: `{checks['export_exists']}`",
        f"- secret_hits: `{checks['secret_hits']}`",
        f"- credential_hits: `{checks['credential_hits']}`",
        "",
        "## Blockers",
        "",
    ]

    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]

    md += [
        "",
        "## Manual import steps",
        "",
    ]
    md += [f"- [ ] {step}" for step in payload["manual_import_steps"]]

    md += [
        "",
        "## Do not claim yet",
        "",
    ]
    md += [f"- {x}" for x in payload["never_claim_yet"]]

    md += [
        "",
        "## Node preview",
        "",
    ]
    md += [f"- {name}" for name in checks["node_names"]]

    md += [
        "",
        "## Git status",
        "",
        "```text",
        checks["git_status"],
        "```",
        "",
    ]

    (OUT / "N8N_IMPORT_READINESS.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_IMPORT_READINESS_DONE")
    print(OUT / "N8N_IMPORT_READINESS.md")
    print(json.dumps({
        "verdict": payload["verdict"],
        "export_exists": checks["export_exists"],
        "active": checks["active"],
        "nodes": checks["nodes"],
        "secret_hits": checks["secret_hits"],
        "credential_hits": len(checks["credential_hits"]),
        "blockers": blockers,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))

    return 0 if payload["verdict"] == "pass" else 1

if __name__ == "__main__":
    raise SystemExit(main())
