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
OUT_ROOT = REPO / "05_EXECUCAO" / "215_RESEARCH_N8N_PIPELINE"


def slug(value: str, fallback: str = "research-n8n") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", (value or "").strip().lower()).strip("-")
    return s[:90] or fallback


def run(cmd: list[str], timeout: int = 240) -> dict[str, Any]:
    started = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        seconds = (datetime.now() - started).total_seconds()
        return {
            "cmd": cmd,
            "exit_code": result.returncode,
            "seconds": round(seconds, 3),
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "output_tail": (result.stdout + result.stderr).strip()[-5000:],
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": cmd,
            "exit_code": 124,
            "seconds": timeout,
            "stdout": "",
            "stderr": "",
            "output_tail": "TIMEOUT",
        }


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


def find_string(obj: Any, suffix: str) -> str | None:
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, str) and value.endswith(suffix):
                return value
            found = find_string(value, suffix)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = find_string(item, suffix)
            if found:
                return found
    return None


def latest_payloads() -> dict[str, Any]:
    investigation_p = latest_file("05_EXECUCAO/203_INTERNET_INVESTIGATION/**/INVESTIGATION.json")
    validation_p = latest_file("05_EXECUCAO/205_N8N_WORKFLOW_VALIDATOR/**/N8N_VALIDATION.json")
    library_p = latest_file("05_EXECUCAO/208_N8N_WORKFLOW_LIBRARY/**/N8N_WORKFLOW_LIBRARY.json")
    card_p = latest_file("05_EXECUCAO/210_N8N_OPERATOR_CARD/N8N_OPERATOR_CARD.json")
    ready_p = latest_file("05_EXECUCAO/212_N8N_IMPORT_READINESS/N8N_IMPORT_READINESS.json")
    webhooks_p = latest_file("05_EXECUCAO/214_N8N_WEBHOOK_SAFETY_REVIEW/N8N_WEBHOOK_SAFETY_REVIEW.json")
    workflow_p = latest_file("05_EXECUCAO/204_N8N_WORKFLOW_BUILDER/**/workflow_skeleton.importable.json")
    export_json_p = latest_file("05_EXECUCAO/207_N8N_EXPORT_PACKAGER/**/*.json")

    investigation = read_json(investigation_p)
    validation = read_json(validation_p)
    library = read_json(library_p)
    card = read_json(card_p)
    ready = read_json(ready_p)
    webhooks = read_json(webhooks_p)
    workflow = read_json(workflow_p)
    export_json = read_json(export_json_p)

    import_export = (
        find_string(card, "IMPORT_THIS_IN_N8N.json")
        or find_string(ready, "IMPORT_THIS_IN_N8N.json")
        or find_string(webhooks, "IMPORT_THIS_IN_N8N.json")
        or find_string(library, "IMPORT_THIS_IN_N8N.json")
    )

    if not import_export:
        latest_import = latest_file("05_EXECUCAO/207_N8N_EXPORT_PACKAGER/**/IMPORT_THIS_IN_N8N.json")
        import_export = str(latest_import.relative_to(REPO)) if latest_import else None

    return {
        "investigation_path": str(investigation_p.relative_to(REPO)) if investigation_p else None,
        "validation_path": str(validation_p.relative_to(REPO)) if validation_p else None,
        "library_path": str(library_p.relative_to(REPO)) if library_p else None,
        "card_path": str(card_p.relative_to(REPO)) if card_p else None,
        "ready_path": str(ready_p.relative_to(REPO)) if ready_p else None,
        "webhooks_path": str(webhooks_p.relative_to(REPO)) if webhooks_p else None,
        "workflow_path": str(workflow_p.relative_to(REPO)) if workflow_p else None,
        "export_json_path": str(export_json_p.relative_to(REPO)) if export_json_p else None,
        "import_export_path": import_export,
        "investigation": investigation,
        "validation": validation,
        "library": library,
        "card": card,
        "ready": ready,
        "webhooks": webhooks,
        "workflow": workflow,
        "export_json": export_json,
    }


def derive_export_verdict(payloads: dict[str, Any]) -> str | None:
    export_json = payloads["export_json"]
    card = payloads["card"]
    library = payloads["library"]

    return (
        export_json.get("verdict")
        or card.get("export")
        or library.get("latest_export")
        or ("pass" if payloads.get("import_export_path") else None)
    )


def build_report(goal: str, query: str, client: str, max_results: int) -> int:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_ROOT / f"{ts}_{slug(client)}_{slug(goal)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    ops = [sys.executable, "11_SCRIPTS/jarvis_ops.py"]
    research_query = query.strip() or goal.strip()

    steps = [
        ("internet_investigation", ops + ["internet-investigate", research_query, "--max-results", str(max_results)]),
        ("n8n_builder", ops + ["n8n-builder", goal, "--client", client]),
        ("n8n_validate", ops + ["n8n-validate"]),
        ("n8n_export", ops + ["n8n-export"]),
        ("n8n_library", ops + ["n8n-library"]),
        ("n8n_card", ops + ["n8n-card"]),
        ("n8n_ready", ops + ["n8n-ready"]),
        ("n8n_webhooks", ops + ["n8n-webhooks"]),
    ]

    results = []
    blockers = []

    for name, cmd in steps:
        print(f"\n--- RUN {name} ---")
        result = run(cmd)
        result["name"] = name
        results.append(result)
        print(result["output_tail"])
        if result["exit_code"] != 0:
            blockers.append(f"{name} failed with exit_code={result['exit_code']}")

    payloads = latest_payloads()

    investigation = payloads["investigation"]
    validation = payloads["validation"]
    card = payloads["card"]
    ready = payloads["ready"]
    webhooks = payloads["webhooks"]

    source_count = investigation.get("source_count", 0)
    ok_source_count = investigation.get("ok_source_count", 0)
    validation_verdict = validation.get("verdict")
    export_verdict = derive_export_verdict(payloads)
    card_verdict = card.get("verdict")
    ready_verdict = ready.get("verdict")
    webhooks_verdict = webhooks.get("verdict")

    if ok_source_count <= 0:
        blockers.append("internet investigation returned zero usable sources")
    if validation_verdict != "pass":
        blockers.append(f"n8n validation is {validation_verdict}")
    if export_verdict != "pass":
        blockers.append(f"n8n export is {export_verdict}")
    if card_verdict != "pass":
        blockers.append(f"n8n card is {card_verdict}")
    if ready_verdict != "pass":
        blockers.append(f"n8n ready is {ready_verdict}")
    if webhooks_verdict != "pass":
        blockers.append(f"n8n webhooks is {webhooks_verdict}")

    verdict = "pass" if not blockers else "block"

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "goal": goal,
        "query": research_query,
        "client": client,
        "source_count": source_count,
        "ok_source_count": ok_source_count,
        "validation": validation_verdict,
        "export": export_verdict,
        "card": card_verdict,
        "ready": ready_verdict,
        "webhooks": webhooks_verdict,
        "workflow_path": payloads["workflow_path"],
        "import_export_path": payloads["import_export_path"],
        "blockers": blockers,
        "steps": results,
        "payload_paths": {k: v for k, v in payloads.items() if k.endswith("_path")},
        "status_real": "internet_research_plus_local_n8n_generation_validation_export_only",
        "not_validated": [
            "not imported in n8n UI",
            "not runtime-tested in n8n",
            "no real credentials connected",
            "no real webhook activated",
            "no production usage",
        ],
    }

    (out_dir / "RESEARCH_N8N_PIPELINE.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# JARVIS Research → n8n Pipeline",
        "",
        f"- verdict: `{verdict}`",
        f"- client: `{client}`",
        f"- goal: `{goal}`",
        f"- query: `{research_query}`",
        f"- source_count: `{source_count}`",
        f"- ok_source_count: `{ok_source_count}`",
        f"- validation: `{validation_verdict}`",
        f"- export: `{export_verdict}`",
        f"- card: `{card_verdict}`",
        f"- ready: `{ready_verdict}`",
        f"- webhooks: `{webhooks_verdict}`",
        "",
        "## Generated artifacts",
        "",
        f"- workflow: `{payloads['workflow_path']}`",
        f"- import_export: `{payloads['import_export_path']}`",
        f"- investigation: `{payloads['investigation_path']}`",
        "",
        "## Blockers",
        "",
    ]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += [
        "",
        "## Status real",
        "",
        "Generated from real internet investigation plus local n8n builder/validator/export/library/card/readiness/webhook review.",
        "Still not imported or runtime-tested inside the n8n UI.",
        "",
        "## Step results",
        "",
    ]
    md += [f"- `{r['name']}` exit=`{r['exit_code']}` seconds=`{r['seconds']}`" for r in results]

    (out_dir / "RESEARCH_N8N_PIPELINE.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\nRESEARCH_N8N_PIPELINE_DONE")
    print(out_dir / "RESEARCH_N8N_PIPELINE.md")
    print(json.dumps({
        "verdict": verdict,
        "source_count": source_count,
        "ok_source_count": ok_source_count,
        "validation": validation_verdict,
        "export": export_verdict,
        "ready": ready_verdict,
        "webhooks": webhooks_verdict,
        "import_export_path": payloads["import_export_path"],
        "blockers": blockers,
    }, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "goal",
        nargs="?",
        default="Professional n8n WhatsApp AI SDR workflow with logs fallback human transfer dry-run safety and import checklist",
    )
    parser.add_argument("--query", default="")
    parser.add_argument("--client", default="research-n8n-smoke")
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()

    return build_report(args.goal, args.query, args.client, args.max_results)


if __name__ == "__main__":
    raise SystemExit(main())
