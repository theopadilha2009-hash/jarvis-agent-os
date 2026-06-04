from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
OUT = REPO / "05_EXECUCAO" / "209_N8N_WORKFLOW_PIPELINE"
OUT.mkdir(parents=True, exist_ok=True)

BUILDER_DIR = REPO / "05_EXECUCAO" / "204_N8N_WORKFLOW_BUILDER"
VALIDATOR_DIR = REPO / "05_EXECUCAO" / "205_N8N_WORKFLOW_VALIDATOR"
EXPORT_DIR = REPO / "05_EXECUCAO" / "207_N8N_EXPORT_PACKAGER"
LIBRARY_DIR = REPO / "05_EXECUCAO" / "208_N8N_WORKFLOW_LIBRARY"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def latest(base: Path, pattern: str) -> Path | None:
    if not base.exists():
        return None
    files = list(base.rglob(pattern))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_step(name: str, args: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, str(SCRIPTS / "jarvis_ops.py"), *args]
    started = datetime.now()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
    finished = datetime.now()

    output = (result.stdout or "") + (result.stderr or "")
    print(output, end="" if output.endswith("\n") else "\n")

    return {
        "name": name,
        "cmd": " ".join(args),
        "exit_code": result.returncode,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "output_tail": output[-4000:],
    }


def slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", text.strip().lower()).strip("-")
    return value[:90] or "n8n-pipeline"


def build_report(goal: str, client: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_json = latest(BUILDER_DIR, "workflow_skeleton.importable.json")
    validation_json = latest(VALIDATOR_DIR, "N8N_VALIDATION.json")
    export_manifest = latest(EXPORT_DIR, "MANIFEST.json")
    library_json = latest(LIBRARY_DIR, "N8N_WORKFLOW_LIBRARY.json")

    workflow_data = read_json(workflow_json)
    validation_data = read_json(validation_json)
    export_data = read_json(export_manifest)
    library_data = read_json(library_json)

    step_failures = [s for s in steps if s["exit_code"] != 0]
    blockers: list[str] = []

    if step_failures:
        blockers.append("one or more pipeline steps failed")
    if validation_data.get("verdict") != "pass":
        blockers.append(f"validator verdict is not pass: {validation_data.get('verdict')}")
    if export_data.get("verdict") != "pass":
        blockers.append(f"export verdict is not pass: {export_data.get('verdict')}")
    if library_data.get("verdict") != "pass":
        blockers.append(f"library verdict is not pass: {library_data.get('verdict')}")
    if workflow_data.get("active") is not False:
        blockers.append("workflow active is not false")

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "goal": goal,
        "client": client,
        "status_real": "generated_validated_exported_indexed_locally_not_n8n_runtime_validated",
        "blockers": blockers,
        "steps": steps,
        "artifacts": {
            "workflow_json": rel(workflow_json),
            "validation_json": rel(validation_json),
            "export_manifest": rel(export_manifest),
            "export_path": export_data.get("export_path"),
            "library_json": rel(library_json),
        },
        "summary": {
            "workflow_name": workflow_data.get("name"),
            "active": workflow_data.get("active"),
            "nodes": len(workflow_data.get("nodes", [])),
            "validation_verdict": validation_data.get("verdict"),
            "validation_blockers": validation_data.get("blockers", []),
            "validation_warnings": validation_data.get("warnings", []),
            "secret_hits": validation_data.get("secret_hits", []),
            "export_verdict": export_data.get("verdict"),
            "library_verdict": library_data.get("verdict"),
        },
        "next_manual_steps": [
            "Open n8n manually.",
            "Import IMPORT_THIS_IN_N8N.json.",
            "Keep workflow inactive first.",
            "Configure credentials in n8n UI.",
            "Run manual/mock test.",
            "Only after approval: configure webhook/runtime.",
            "Do not call production validated until real n8n execution passes.",
        ],
    }


def write_outputs(data: dict[str, Any]) -> Path:
    folder = OUT / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug(data['client'])}"
    folder.mkdir(parents=True, exist_ok=True)

    json_path = folder / "N8N_PIPELINE.json"
    md_path = folder / "N8N_PIPELINE.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# JARVIS n8n One-Command Pipeline",
        "",
        f"- verdict: `{data['verdict']}`",
        f"- client: `{data['client']}`",
        f"- goal: `{data['goal']}`",
        f"- status_real: `{data['status_real']}`",
        "",
        "## Summary",
    ]

    for k, v in data["summary"].items():
        lines.append(f"- {k}: `{v}`")

    lines += ["", "## Artifacts"]
    for k, v in data["artifacts"].items():
        lines.append(f"- {k}: `{v}`")

    lines += ["", "## Blockers"]
    if data["blockers"]:
        lines += [f"- {x}" for x in data["blockers"]]
    else:
        lines.append("- none")

    lines += ["", "## Steps"]
    for step in data["steps"]:
        lines.append(f"- `{step['name']}` exit=`{step['exit_code']}` cmd=`{step['cmd']}`")

    lines += ["", "## Next manual steps"]
    lines += [f"- {x}" for x in data["next_manual_steps"]]
    lines += ["", "Status real: local generation/validation/export/index only. No n8n UI import, credentials, webhook, runtime or production validation.", ""]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("goal", nargs="?", default="WhatsApp AI SDR workflow with logs fallback human transfer and dry-run safety")
    parser.add_argument("--client", default="pipeline-smoke")
    args = parser.parse_args()

    steps = [
        run_step("builder", ["n8n-builder", args.goal, "--client", args.client]),
        run_step("validator", ["n8n-validate"]),
        run_step("export", ["n8n-export"]),
        run_step("library", ["n8n-library"]),
    ]

    data = build_report(args.goal, args.client, steps)
    md_path = write_outputs(data)

    print("N8N_WORKFLOW_PIPELINE_DONE")
    print(md_path)
    print(json.dumps({
        "verdict": data["verdict"],
        "client": data["client"],
        "nodes": data["summary"]["nodes"],
        "validation": data["summary"]["validation_verdict"],
        "export": data["summary"]["export_verdict"],
        "library": data["summary"]["library_verdict"],
        "export_path": data["artifacts"]["export_path"],
        "blockers": data["blockers"],
    }, indent=2, ensure_ascii=False))

    return 0 if data["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
