from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "218_N8N_GUARDED_EXPORT"


def slug(value: str, fallback: str = "guarded-export") -> str:
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


def source_export() -> Path | None:
    candidates = [
        latest_file("05_EXECUCAO/207_N8N_EXPORT_PACKAGER/**/IMPORT_THIS_IN_N8N.json"),
        latest_file("05_EXECUCAO/204_N8N_WORKFLOW_BUILDER/**/workflow_skeleton.importable.json"),
    ]
    return next((p for p in candidates if p and p.exists()), None)


def has_manual_trigger(workflow: dict[str, Any]) -> bool:
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if "manualtrigger" in str(node.get("type", "")).lower():
            return True
        if "manual trigger" in str(node.get("name", "")).lower():
            return True
    return False


def credential_hits(workflow: dict[str, Any]) -> int:
    hits = 0
    for node in workflow.get("nodes", []):
        if isinstance(node, dict) and node.get("credentials"):
            hits += 1
    return hits


def secret_hits(raw: str) -> list[str]:
    patterns = [
        r"sk-[A-Za-z0-9_-]{12,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"ghp_[A-Za-z0-9]{20,}",
        r"AIza[A-Za-z0-9_-]{20,}",
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{8,}",
    ]
    hits = []
    for pat in patterns:
        if re.search(pat, raw):
            hits.append(pat)
    return hits


def inject_manual_trigger(workflow: dict[str, Any]) -> bool:
    if has_manual_trigger(workflow):
        return False

    nodes = workflow.setdefault("nodes", [])
    nodes.insert(0, {
        "id": "jarvis-manual-trigger-import-guard",
        "name": "Manual Trigger - Import Guard",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [-620, -380],
        "parameters": {},
    })
    workflow.setdefault("connections", {})
    return True


def run(client: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{ts}_{slug(client)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    src = source_export()
    workflow = read_json(src)
    blockers = []
    warnings = []

    if not src:
        blockers.append("missing source export")
    if not workflow:
        blockers.append("source export unreadable")
    if workflow.get("active") is not False:
        workflow["active"] = False
        warnings.append("forced active=false in guarded export")

    before_manual = has_manual_trigger(workflow)
    injected = inject_manual_trigger(workflow)
    after_manual = has_manual_trigger(workflow)

    raw = json.dumps(workflow, ensure_ascii=False)
    sh = secret_hits(raw)
    ch = credential_hits(workflow)

    if sh:
        blockers.append("secret-like content detected")
    if ch:
        blockers.append(f"credential hits detected: {ch}")
    if not after_manual:
        blockers.append("manual trigger still missing")
    if len(workflow.get("nodes", [])) < 5:
        blockers.append("workflow has too few nodes")

    guarded_path = out_dir / "IMPORT_THIS_IN_N8N_GUARDED.json"
    guarded_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

    verdict = "pass" if not blockers else "block"

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "client": client,
        "source_export": str(src.relative_to(REPO)) if src else None,
        "guarded_export": str(guarded_path.relative_to(REPO)),
        "workflow_name": workflow.get("name"),
        "active": workflow.get("active"),
        "nodes": len(workflow.get("nodes", [])),
        "manual_before": before_manual,
        "manual_after": after_manual,
        "manual_injected": injected,
        "credential_hits": ch,
        "secret_hits": sh,
        "blockers": blockers,
        "warnings": warnings,
        "status_real": "guarded_import_copy_only_not_n8n_ui_or_runtime_validated",
    }

    (out_dir / "N8N_GUARDED_EXPORT.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# JARVIS n8n Guarded Export",
        "",
        f"- verdict: `{verdict}`",
        f"- source_export: `{payload['source_export']}`",
        f"- guarded_export: `{payload['guarded_export']}`",
        f"- active: `{payload['active']}`",
        f"- nodes: `{payload['nodes']}`",
        f"- manual_before: `{payload['manual_before']}`",
        f"- manual_after: `{payload['manual_after']}`",
        f"- manual_injected: `{payload['manual_injected']}`",
        "",
        "## Blockers",
        "",
    ]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]
    md += ["", "Status real: guarded local import copy only.", ""]

    (out_dir / "N8N_GUARDED_EXPORT.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_GUARDED_EXPORT_DONE")
    print(out_dir / "N8N_GUARDED_EXPORT.md")
    print(json.dumps({
        "verdict": verdict,
        "guarded_export": payload["guarded_export"],
        "active": payload["active"],
        "nodes": payload["nodes"],
        "manual_after": payload["manual_after"],
        "manual_injected": payload["manual_injected"],
        "blockers": blockers,
        "warnings": warnings,
    }, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="guarded-export")
    args = parser.parse_args()
    return run(args.client)


if __name__ == "__main__":
    raise SystemExit(main())
