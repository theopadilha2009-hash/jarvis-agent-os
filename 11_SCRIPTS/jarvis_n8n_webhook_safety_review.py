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
OUT = ROOT / "05_EXECUCAO" / "214_N8N_WEBHOOK_SAFETY_REVIEW"
OUT.mkdir(parents=True, exist_ok=True)

SECRET_PATTERNS = {
    "openai_key": r"sk-[A-Za-z0-9_\-]{20,}",
    "google_key": r"AIza[0-9A-Za-z_\-]{20,}",
    "github_token": r"ghp_[0-9A-Za-z]{20,}",
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
        for value in obj.values():
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

def scan_secret_like(raw: str) -> list[str]:
    hits = []
    for label, pattern in SECRET_PATTERNS.items():
        if re.search(pattern, raw):
            hits.append(label)
    return hits

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

def has_manual_trigger(workflow: dict[str, Any]) -> bool:
    for node in workflow.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", "")).lower()
        node_name = str(node.get("name", "")).lower()
        if "manualtrigger" in node_type or "manual trigger" in node_name:
            return True
    return False

def is_webhook_node(node: dict[str, Any]) -> bool:
    node_type = str(node.get("type", "")).lower()
    return "webhook" in node_type

def webhook_info(node: dict[str, Any]) -> dict[str, Any]:
    params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}

    path = (
        params.get("path")
        or params.get("webhookPath")
        or params.get("endpoint")
        or ""
    )

    method = (
        params.get("httpMethod")
        or params.get("method")
        or params.get("requestMethod")
        or "UNKNOWN"
    )

    response_mode = (
        params.get("responseMode")
        or params.get("response")
        or "UNKNOWN"
    )

    auth = (
        params.get("authentication")
        or params.get("auth")
        or params.get("security")
        or "none_or_not_configured"
    )

    node_name = str(node.get("name") or "unnamed")
    node_type = str(node.get("type") or "unknown")

    risks = []
    if not path:
        risks.append("missing webhook path")
    if str(method).upper() in {"GET", "UNKNOWN"}:
        risks.append("method should be reviewed")
    if str(auth).lower() in {"none", "none_or_not_configured", "", "noauth"}:
        risks.append("no explicit auth configured")
    if "test" not in str(path).lower() and "staging" not in str(path).lower() and "dry" not in str(path).lower():
        risks.append("path is not obviously test/staging/dry-run")

    return {
        "name": node_name,
        "type": node_type,
        "path": path,
        "method": str(method).upper(),
        "response_mode": response_mode,
        "auth": auth,
        "risk_level": "medium" if risks else "low",
        "risks": risks,
        "position": node.get("position"),
    }

def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    pipeline_path = latest_named(PIPELINE_DIR, "N8N_PIPELINE.json")
    pipeline = load_json(pipeline_path) or {}

    export_raw = find_export_path(pipeline)
    export_path = to_path(export_raw)
    workflow = load_json(export_path)

    if not pipeline_path:
        blockers.append("missing latest N8N_PIPELINE.json")
    if not export_path or not export_path.exists():
        blockers.append("missing IMPORT_THIS_IN_N8N.json")
    if not isinstance(workflow, dict):
        blockers.append("export workflow JSON could not be parsed")
        workflow = {}

    raw_workflow = json.dumps(workflow, ensure_ascii=False)
    secret_hits = scan_secret_like(raw_workflow)
    credential_hits = recursive_credentials_hits(workflow)
    if secret_hits:
        blockers.append("secret-like patterns detected: " + ", ".join(secret_hits))
    if credential_hits:
        blockers.append("non-empty credentials fields detected")

    active = workflow.get("active")
    if active is not False:
        blockers.append(f"workflow active must be false before webhook review, got {active!r}")

    manual_trigger = has_manual_trigger(workflow)
    if not manual_trigger:
        blockers.append("manual trigger missing")

    nodes = workflow.get("nodes") if isinstance(workflow.get("nodes"), list) else []
    webhooks = [webhook_info(n) for n in nodes if isinstance(n, dict) and is_webhook_node(n)]

    if not webhooks:
        warnings.append("no webhook nodes found")
    else:
        warnings.append("webhook nodes exist; keep workflow inactive until endpoint/credential review")

    for wh in webhooks:
        if wh["risks"]:
            warnings.append(f"{wh['name']}: " + "; ".join(wh["risks"]))

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "warnings": warnings,
        "pipeline_json": str(pipeline_path.relative_to(ROOT)) if pipeline_path else None,
        "export_path": str(export_path.relative_to(ROOT)) if export_path and export_path.exists() else export_raw,
        "workflow_name": workflow.get("name"),
        "active": active,
        "nodes": len(nodes),
        "manual_trigger": manual_trigger,
        "webhook_count": len(webhooks),
        "webhooks": webhooks,
        "secret_hits": secret_hits,
        "credential_hits": len(credential_hits),
        "git_status": run(["git", "status", "-sb"]),
        "last_commit": run(["git", "log", "--oneline", "-1"]),
        "status_real": "local_webhook_review_only_not_n8n_runtime_endpoint_credential_or_production_validated",
        "activation_checklist": [
            "Keep workflow active=false after import.",
            "Confirm every webhook path is unique and belongs to test/staging first.",
            "Confirm HTTP method expected by provider.",
            "Attach credentials only inside n8n Credentials UI.",
            "Run Manual Trigger first.",
            "Use mock/dry-run for outbound sends.",
            "Only connect real webhook after human approval.",
            "Only activate after endpoint, logs, rollback, and owner are defined.",
        ],
        "never_claim_yet": [
            "webhook validated in n8n UI",
            "runtime validated",
            "credentials configured",
            "production-ready",
            "safe for real leads/client/patients",
        ],
    }

    (OUT / "N8N_WEBHOOK_SAFETY_REVIEW.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# JARVIS n8n Webhook Safety Review",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- workflow_name: `{payload['workflow_name']}`",
        f"- active: `{payload['active']}`",
        f"- nodes: `{payload['nodes']}`",
        f"- manual_trigger: `{payload['manual_trigger']}`",
        f"- webhook_count: `{payload['webhook_count']}`",
        f"- secret_hits: `{payload['secret_hits']}`",
        f"- credential_hits: `{payload['credential_hits']}`",
        f"- status_real: `{payload['status_real']}`",
        f"- export_path: `{payload['export_path']}`",
        "",
        "## Blockers",
    ]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += ["", "## Warnings"]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]

    md += ["", "## Webhooks"]
    if webhooks:
        for wh in webhooks:
            md += [
                "",
                f"### {wh['name']}",
                f"- type: `{wh['type']}`",
                f"- method: `{wh['method']}`",
                f"- path: `{wh['path']}`",
                f"- auth: `{wh['auth']}`",
                f"- response_mode: `{wh['response_mode']}`",
                f"- risk_level: `{wh['risk_level']}`",
                "- risks:",
            ]
            md += [f"  - {r}" for r in wh["risks"]] if wh["risks"] else ["  - none"]
    else:
        md += ["- none"]

    md += ["", "## Activation checklist"]
    md += [f"- [ ] {x}" for x in payload["activation_checklist"]]
    md += ["", "## Do not claim yet"]
    md += [f"- {x}" for x in payload["never_claim_yet"]]
    md += ["", "## Git status", "```text", payload["git_status"], "```", ""]

    (OUT / "N8N_WEBHOOK_SAFETY_REVIEW.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_WEBHOOK_SAFETY_REVIEW_DONE")
    print(OUT / "N8N_WEBHOOK_SAFETY_REVIEW.md")
    print(json.dumps({
        "verdict": payload["verdict"],
        "active": payload["active"],
        "nodes": payload["nodes"],
        "manual_trigger": payload["manual_trigger"],
        "webhook_count": payload["webhook_count"],
        "secret_hits": payload["secret_hits"],
        "credential_hits": payload["credential_hits"],
        "blockers": blockers,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))

    return 0 if payload["verdict"] == "pass" else 1

if __name__ == "__main__":
    raise SystemExit(main())
