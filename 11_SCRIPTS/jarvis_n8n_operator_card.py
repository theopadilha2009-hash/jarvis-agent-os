from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "210_N8N_OPERATOR_CARD"
OUT.mkdir(parents=True, exist_ok=True)

PIPELINE_DIR = REPO / "05_EXECUCAO" / "209_N8N_WORKFLOW_PIPELINE"
EXPORT_DIR = REPO / "05_EXECUCAO" / "207_N8N_EXPORT_PACKAGER"
LIBRARY_DIR = REPO / "05_EXECUCAO" / "208_N8N_WORKFLOW_LIBRARY"


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return (result.stdout + result.stderr).strip()


def latest_file(base: Path, name: str) -> Path | None:
    if not base.exists():
        return None
    files = sorted(base.rglob(name), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def read_json(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rel(path: Path | None) -> str:
    if not path:
        return ""
    try:
        return str(path.relative_to(REPO))
    except Exception:
        return str(path)


def main() -> int:
    pipeline_json = latest_file(PIPELINE_DIR, "N8N_PIPELINE.json")
    export_json = latest_file(EXPORT_DIR, "N8N_EXPORT.json")
    library_json = latest_file(LIBRARY_DIR, "N8N_WORKFLOW_LIBRARY.json")

    pipeline = read_json(pipeline_json)
    export = read_json(export_json)
    library = read_json(library_json)

    export_path = pipeline.get("export_path") or export.get("export_path") or ""
    if export_path and not Path(export_path).is_absolute():
        export_full = REPO / export_path
    else:
        export_full = Path(export_path) if export_path else None

    git_status = run(["git", "status", "-sb"])
    last_commit = run(["git", "log", "--oneline", "-1"])

    blockers = []
    if not pipeline:
        blockers.append("no pipeline output found")
    if pipeline and pipeline.get("verdict") != "pass":
        blockers.append("latest pipeline is not pass")
    if export_full and not export_full.exists():
        blockers.append("export file missing")
    if pipeline.get("validation") not in ("pass", None):
        blockers.append("validation did not pass")
    if pipeline.get("export") not in ("pass", None):
        blockers.append("export did not pass")
    if pipeline.get("library") not in ("pass", None):
        blockers.append("library did not pass")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "status_real": "local_operator_card_only_not_n8n_runtime_validated",
        "latest_pipeline_json": rel(pipeline_json),
        "latest_export_json": rel(export_json),
        "latest_library_json": rel(library_json),
        "export_path": str(export_path),
        "export_exists": bool(export_full and export_full.exists()),
        "pipeline": {
            "client": pipeline.get("client"),
            "nodes": pipeline.get("nodes"),
            "validation": pipeline.get("validation"),
            "export": pipeline.get("export"),
            "library": pipeline.get("library"),
            "pipeline_blockers": pipeline.get("blockers", []),
        },
        "library": {
            "workflows_indexed": library.get("workflows_indexed"),
            "validations_found": library.get("validations_found"),
            "exports_found": library.get("exports_found"),
            "latest_validator": library.get("latest_validator"),
            "latest_export": library.get("latest_export"),
        },
        "safe_next_commands": [
            'py -3 11_SCRIPTS/jarvis_ops.py n8n-pipeline "WhatsApp AI SDR workflow with logs fallback human transfer and dry-run safety" --client "CLIENT_NAME"',
            "py -3 11_SCRIPTS/jarvis_ops.py n8n-validate",
            "py -3 11_SCRIPTS/jarvis_ops.py n8n-export",
            "py -3 11_SCRIPTS/jarvis_ops.py n8n-library",
            "py -3 11_SCRIPTS/jarvis_ops.py n8n-card",
        ],
        "manual_import_checklist": [
            "Open n8n manually.",
            "Import IMPORT_THIS_IN_N8N.json.",
            "Keep workflow inactive.",
            "Confirm active=false.",
            "Check placeholders and credentials.",
            "Do not add real tokens to JSON.",
            "Run Manual Trigger only.",
            "Do not connect real webhook before approval.",
            "Do not send real WhatsApp/email before dry-run approval.",
        ],
        "git_status": git_status,
        "last_commit": last_commit,
    }

    (OUT / "N8N_OPERATOR_CARD.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        "# JARVIS n8n Operator Card",
        "",
        f"- created_at: `{payload['created_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- status_real: `{payload['status_real']}`",
        f"- last_commit: `{last_commit}`",
        "",
        "## Latest pipeline",
        "",
        f"- client: `{payload['pipeline']['client']}`",
        f"- nodes: `{payload['pipeline']['nodes']}`",
        f"- validation: `{payload['pipeline']['validation']}`",
        f"- export: `{payload['pipeline']['export']}`",
        f"- library: `{payload['pipeline']['library']}`",
        f"- export_path: `{payload['export_path']}`",
        f"- export_exists: `{payload['export_exists']}`",
        "",
        "## Library",
        "",
        f"- workflows_indexed: `{payload['library']['workflows_indexed']}`",
        f"- validations_found: `{payload['library']['validations_found']}`",
        f"- exports_found: `{payload['library']['exports_found']}`",
        f"- latest_validator: `{payload['library']['latest_validator']}`",
        f"- latest_export: `{payload['library']['latest_export']}`",
        "",
        "## Blockers",
        "",
    ]

    if blockers:
        md += [f"- {b}" for b in blockers]
    else:
        md.append("- none")

    md += [
        "",
        "## Safe next commands",
        "",
        "```bash",
        "\n".join(payload["safe_next_commands"]),
        "```",
        "",
        "## Manual import checklist",
        "",
    ]
    md += [f"- [ ] {x}" for x in payload["manual_import_checklist"]]

    md += [
        "",
        "## Git status",
        "",
        "```text",
        git_status,
        "```",
        "",
        "Status real: this card only summarizes local generated n8n artifacts. It does not validate n8n UI import, runtime, credentials, webhooks, WhatsApp/email sending, or production.",
        "",
    ]

    (OUT / "N8N_OPERATOR_CARD.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_OPERATOR_CARD_DONE")
    print(OUT / "N8N_OPERATOR_CARD.md")
    print(json.dumps({
        "verdict": payload["verdict"],
        "export_exists": payload["export_exists"],
        "nodes": payload["pipeline"]["nodes"],
        "validation": payload["pipeline"]["validation"],
        "export": payload["pipeline"]["export"],
        "library": payload["pipeline"]["library"],
        "blockers": blockers,
    }, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
