from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BUILDER_DIR = REPO / "05_EXECUCAO" / "204_N8N_WORKFLOW_BUILDER"
VALIDATOR_DIR = REPO / "05_EXECUCAO" / "205_N8N_WORKFLOW_VALIDATOR"
EXPORT_DIR = REPO / "05_EXECUCAO" / "207_N8N_EXPORT_PACKAGER"
OUT = REPO / "05_EXECUCAO" / "208_N8N_WORKFLOW_LIBRARY"
OUT.mkdir(parents=True, exist_ok=True)


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def latest_files(base: Path, pattern: str, limit: int = 20) -> list[Path]:
    if not base.exists():
        return []
    return sorted(base.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def workflow_name_from_json(path: Path) -> str:
    data = read_json(path)
    return str(data.get("name") or path.parent.name)


def build_library(limit: int = 30) -> dict[str, Any]:
    workflows = latest_files(BUILDER_DIR, "workflow_skeleton.importable.json", limit)
    validations = latest_files(VALIDATOR_DIR, "N8N_VALIDATION.json", limit)
    exports = latest_files(EXPORT_DIR, "MANIFEST.json", limit)

    validation_by_name: dict[str, dict[str, Any]] = {}
    for v in validations:
        data = read_json(v)
        name = str(data.get("workflow_name") or data.get("workflow") or "")
        if name and name not in validation_by_name:
            validation_by_name[name] = {"path": rel(v), "data": data}

    export_by_name: dict[str, dict[str, Any]] = {}
    for e in exports:
        data = read_json(e)
        name = str(data.get("workflow_name") or "")
        if name and name not in export_by_name:
            export_by_name[name] = {"path": rel(e), "data": data}

    items = []
    for wf in workflows:
        wf_data = read_json(wf)
        name = str(wf_data.get("name") or wf.parent.name)
        validation = validation_by_name.get(name)
        export = export_by_name.get(name)

        validation_data = validation["data"] if validation else {}
        export_data = export["data"] if export else {}

        item = {
            "workflow_name": name,
            "workflow_path": rel(wf),
            "active": wf_data.get("active"),
            "node_count": len(wf_data.get("nodes", [])),
            "connection_count": len(wf_data.get("connections", {})),
            "validator_verdict": validation_data.get("verdict"),
            "validator_blockers": validation_data.get("blockers", []),
            "validator_warnings": validation_data.get("warnings", []),
            "validator_secret_hits": validation_data.get("secret_hits", []),
            "validation_report": validation.get("path") if validation else None,
            "export_verdict": export_data.get("verdict"),
            "export_path": export_data.get("export_path"),
            "export_manifest": export.get("path") if export else None,
            "status_real": "indexed_only_not_imported_not_runtime_validated",
        }
        items.append(item)

    latest = items[0] if items else None
    blockers = []

    if not items:
        blockers.append("no generated n8n workflows found")
    if latest:
        if latest.get("active") is not False:
            blockers.append("latest workflow active is not false")
        if latest.get("validator_verdict") != "pass":
            blockers.append(f"latest validator verdict is not pass: {latest.get('validator_verdict')}")
        if latest.get("export_verdict") not in {"pass", None}:
            blockers.append(f"latest export verdict is not pass: {latest.get('export_verdict')}")

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "warn",
        "status_real": "local_n8n_workflow_library_only_not_n8n_runtime_validated",
        "blockers": blockers,
        "counts": {
            "workflows_indexed": len(items),
            "validations_found": len(validations),
            "exports_found": len(exports),
        },
        "latest": latest,
        "items": items,
    }


def write_outputs(data: dict[str, Any]) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = OUT / stamp
    folder.mkdir(parents=True, exist_ok=True)

    json_path = folder / "N8N_WORKFLOW_LIBRARY.json"
    md_path = folder / "N8N_WORKFLOW_LIBRARY.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# JARVIS n8n Workflow Library",
        "",
        f"- verdict: `{data['verdict']}`",
        f"- status_real: `{data['status_real']}`",
        f"- workflows_indexed: `{data['counts']['workflows_indexed']}`",
        f"- validations_found: `{data['counts']['validations_found']}`",
        f"- exports_found: `{data['counts']['exports_found']}`",
        "",
        "## Blockers",
    ]

    if data["blockers"]:
        lines += [f"- {x}" for x in data["blockers"]]
    else:
        lines.append("- none")

    lines += ["", "## Latest"]
    latest = data.get("latest")
    if latest:
        for key in [
            "workflow_name",
            "workflow_path",
            "active",
            "node_count",
            "validator_verdict",
            "export_verdict",
            "export_path",
        ]:
            lines.append(f"- {key}: `{latest.get(key)}`")
    else:
        lines.append("- none")

    lines += ["", "## Recent workflows"]
    for item in data["items"][:15]:
        lines.append("")
        lines.append(f"### {item['workflow_name']}")
        lines.append(f"- workflow: `{item['workflow_path']}`")
        lines.append(f"- validation: `{item['validator_verdict']}`")
        lines.append(f"- export: `{item['export_verdict']}`")
        lines.append(f"- active: `{item['active']}`")
        lines.append(f"- nodes: `{item['node_count']}`")
        lines.append(f"- export_path: `{item['export_path']}`")

    lines += [
        "",
        "Status real: this is an index of generated/local n8n assets only. It does not prove n8n UI import, credentials, webhook, external APIs, or production runtime.",
        "",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", default="build", choices=["build"])
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    data = build_library(limit=args.limit)
    json_path, md_path = write_outputs(data)

    print("N8N_WORKFLOW_LIBRARY_DONE")
    print(md_path)
    print(json.dumps({
        "verdict": data["verdict"],
        "workflows_indexed": data["counts"]["workflows_indexed"],
        "validations_found": data["counts"]["validations_found"],
        "exports_found": data["counts"]["exports_found"],
        "latest_validator": (data.get("latest") or {}).get("validator_verdict"),
        "latest_export": (data.get("latest") or {}).get("export_verdict"),
        "blockers": data["blockers"],
    }, indent=2, ensure_ascii=False))

    return 0 if data["verdict"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
