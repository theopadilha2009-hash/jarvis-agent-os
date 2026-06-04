from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUILDER_DIR = REPO / "05_EXECUCAO" / "204_N8N_WORKFLOW_BUILDER"
VALIDATOR_DIR = REPO / "05_EXECUCAO" / "205_N8N_WORKFLOW_VALIDATOR"
OUT = REPO / "05_EXECUCAO" / "207_N8N_EXPORT_PACKAGER"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def latest_file(base: Path, pattern: str) -> Path | None:
    files = sorted(base.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in value.lower())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:90] or "n8n-workflow"


def package() -> int:
    workflow = latest_file(BUILDER_DIR, "workflow_skeleton.importable.json")
    validation = latest_file(VALIDATOR_DIR, "N8N_VALIDATION.json")

    blockers = []
    if not workflow:
        blockers.append("no workflow_skeleton.importable.json found")
    if not validation:
        blockers.append("no N8N_VALIDATION.json found")

    validation_data = {}
    workflow_data = {}

    if validation:
        validation_data = load_json(validation)
        if validation_data.get("verdict") != "pass":
            blockers.append(f"latest validator verdict is not pass: {validation_data.get('verdict')}")
        if validation_data.get("blockers_count", validation_data.get("blockers", 0)) not in (0, [], None):
            blockers.append("validator has blockers")
        if validation_data.get("secret_hits_count", validation_data.get("secret_hits", 0)) not in (0, [], None):
            blockers.append("validator has secret hits")

    if workflow:
        workflow_data = load_json(workflow)
        if workflow_data.get("active") is not False:
            blockers.append("workflow active must be false")
        if not workflow_data.get("nodes"):
            blockers.append("workflow has no nodes")
        if not workflow_data.get("connections"):
            blockers.append("workflow has no connections")

    name = workflow_data.get("name", "jarvis-n8n-workflow") if workflow_data else "jarvis-n8n-workflow"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{stamp}_{safe_name(name)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    export_path = out_dir / "IMPORT_THIS_IN_N8N.json"
    manifest_path = out_dir / "MANIFEST.json"
    readme_path = out_dir / "README_IMPORT_CHECKLIST.md"

    if workflow:
        shutil.copy2(workflow, export_path)

    manifest = {
        "created_at": now(),
        "verdict": "pass" if not blockers else "block",
        "workflow_name": name,
        "source_workflow": str(workflow.relative_to(REPO)) if workflow else None,
        "source_validation": str(validation.relative_to(REPO)) if validation else None,
        "export_path": str(export_path.relative_to(REPO)) if workflow else None,
        "blockers": blockers,
        "status_real": "local_export_package_only_not_imported_not_runtime_validated",
        "safety": {
            "active_false_required": True,
            "secrets_not_allowed": True,
            "dry_run_first": True,
            "human_approval_before_real_send": True,
            "not_production": True,
        },
        "workflow_stats": {
            "nodes": len(workflow_data.get("nodes", [])) if workflow_data else 0,
            "connections": len(workflow_data.get("connections", {})) if workflow_data else 0,
            "active": workflow_data.get("active") if workflow_data else None,
        },
        "validation_summary": validation_data,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    readme = [
        "# JARVIS n8n Export Package",
        "",
        f"- Verdict: `{manifest['verdict']}`",
        f"- Workflow: `{name}`",
        f"- Export JSON: `{manifest['export_path']}`",
        f"- Status real: `{manifest['status_real']}`",
        "",
        "## Import checklist",
        "",
        "1. Import `IMPORT_THIS_IN_N8N.json` into n8n.",
        "2. Confirm workflow imports with `active=false`.",
        "3. Do not add real credentials inside JSON.",
        "4. Configure credentials only in n8n Credentials UI.",
        "5. Run Manual Trigger / mock test first.",
        "6. Validate logs, fallback, human transfer, dry-run send guard.",
        "7. Only after approval, connect real webhook/API.",
        "8. Only after controlled test, consider production activation.",
        "",
        "## Safety notes",
        "",
        "- This package is JSON import QA only.",
        "- It is not runtime validation.",
        "- It is not credential validation.",
        "- It is not production approval.",
        "- Real WhatsApp/email/client sending needs human approval.",
        "",
        "## Blockers",
        "",
    ]

    if blockers:
        readme += [f"- {b}" for b in blockers]
    else:
        readme.append("- none")

    readme_path.write_text("\n".join(readme) + "\n", encoding="utf-8")

    print("N8N_EXPORT_PACKAGER_DONE")
    print(readme_path)
    print(json.dumps({
        "verdict": manifest["verdict"],
        "workflow": name,
        "export_path": manifest["export_path"],
        "nodes": manifest["workflow_stats"]["nodes"],
        "active": manifest["workflow_stats"]["active"],
        "blockers": blockers,
    }, indent=2, ensure_ascii=False))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", default="package", choices=["package"])
    args = parser.parse_args()
    return package()


if __name__ == "__main__":
    raise SystemExit(main())
