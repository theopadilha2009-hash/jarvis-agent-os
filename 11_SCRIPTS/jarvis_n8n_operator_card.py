#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "05_EXECUCAO" / "209_N8N_WORKFLOW_PIPELINE"
OUT_DIR = ROOT / "05_EXECUCAO" / "210_N8N_OPERATOR_CARD"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def latest_pipeline_json():
    if not PIPELINE_DIR.exists():
        return None, None

    candidates = sorted(
        PIPELINE_DIR.rglob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for path in candidates:
        data = load_json(path)
        if isinstance(data, dict) and ("summary" in data or "artifacts" in data or "verdict" in data):
            return path, data

    return None, None

def verdict_of(value):
    if isinstance(value, dict):
        return value.get("verdict") or value.get("status")
    if isinstance(value, str):
        return value
    return None

def deep_find_export_path(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and value.endswith("IMPORT_THIS_IN_N8N.json"):
                return value
            found = deep_find_export_path(value)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = deep_find_export_path(item)
            if found:
                return found
    return None

def as_repo_path(value):
    if not value:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return ROOT / p

def main():
    pipeline_path, data = latest_pipeline_json()
    blockers = []

    if not data:
        summary = {}
        artifacts = {}
        blockers.append("missing pipeline JSON")
    else:
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else data
        artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}

    pipeline_verdict = verdict_of(data.get("verdict") if data else None) or verdict_of(summary.get("verdict"))
    validation = verdict_of(summary.get("validation_verdict") or summary.get("validation") or summary.get("validator") or (data.get("validation") if data else None))
    export = verdict_of(summary.get("export_verdict") or summary.get("export") or summary.get("packager") or (data.get("export") if data else None))
    library = verdict_of(summary.get("library_verdict") or summary.get("library") or (data.get("library") if data else None))

    nodes = (
        summary.get("nodes")
        or summary.get("node_count")
        or summary.get("workflow_nodes")
        or None
    )

    export_path_raw = (
        artifacts.get("export_path")
        or artifacts.get("import_path")
        or summary.get("export_path")
        or deep_find_export_path(data)
    )
    export_path = as_repo_path(export_path_raw)
    export_exists = bool(export_path and export_path.exists())

    if pipeline_verdict != "pass":
        blockers.append(f"pipeline verdict is {pipeline_verdict!r}")
    if validation != "pass":
        blockers.append(f"validation is {validation!r}")
    if export != "pass":
        blockers.append(f"export is {export!r}")
    if library != "pass":
        blockers.append(f"library is {library!r}")
    if not export_exists:
        blockers.append("export file missing")
    if not nodes:
        blockers.append("nodes count missing")

    payload = {
        "verdict": "pass" if not blockers else "block",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pipeline_json": str(pipeline_path.relative_to(ROOT)) if pipeline_path else None,
        "export_exists": export_exists,
        "export_path": str(export_path.relative_to(ROOT)) if export_path and export_path.exists() else export_path_raw,
        "nodes": nodes,
        "active": summary.get("active", False),
        "pipeline": pipeline_verdict,
        "validation": validation,
        "export": export,
        "library": library,
        "blockers": blockers,
        "status_real": "operator card reads latest local n8n pipeline/export only",
    }

    md = OUT_DIR / "N8N_OPERATOR_CARD.md"
    js = OUT_DIR / "N8N_OPERATOR_CARD.json"

    md.write_text(
        "# JARVIS n8n Operator Card\n\n"
        f"- Verdict: `{payload['verdict']}`\n"
        f"- Nodes: `{payload['nodes']}`\n"
        f"- Pipeline: `{payload['pipeline']}`\n"
        f"- Validation: `{payload['validation']}`\n"
        f"- Export: `{payload['export']}`\n"
        f"- Library: `{payload['library']}`\n"
        f"- Export exists: `{payload['export_exists']}`\n"
        f"- Export path: `{payload['export_path']}`\n"
        f"- Status real: `{payload['status_real']}`\n\n"
        "## Blockers\n"
        + ("\n".join(f"- {b}" for b in blockers) if blockers else "- none")
        + "\n",
        encoding="utf-8",
    )
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("N8N_OPERATOR_CARD_DONE")
    print(str(md))
    print(json.dumps({
        "verdict": payload["verdict"],
        "export_exists": payload["export_exists"],
        "nodes": payload["nodes"],
        "validation": payload["validation"],
        "export": payload["export"],
        "library": payload["library"],
        "blockers": payload["blockers"],
    }, ensure_ascii=False, indent=2))

    raise SystemExit(0 if payload["verdict"] == "pass" else 1)

if __name__ == "__main__":
    main()
