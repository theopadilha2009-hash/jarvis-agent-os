from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "223_N8N_EVIDENCE_LEDGER"
LEDGER = OUT / "N8N_EVIDENCE_LEDGER.jsonl"
CSV_LEDGER = OUT / "N8N_EVIDENCE_LEDGER.csv"


def slug(value: str, fallback: str = "evidence") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip().lower()).strip("-")
    return s[:90] or fallback


def latest_file(pattern: str) -> Path | None:
    files = [p for p in REPO.glob(pattern) if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def latest_dir(pattern: str) -> Path | None:
    dirs = [p for p in REPO.glob(pattern) if p.is_dir()]
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(REPO))
    except Exception:
        return str(path)


def load_records() -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    records = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            pass
    return records


def write_csv(records: list[dict[str, Any]]) -> None:
    fields = [
        "created_at",
        "client",
        "stage",
        "verdict",
        "workflow_id",
        "execution_id",
        "webhook_path",
        "import_file",
        "notes",
    ]
    with CSV_LEDGER.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({k: r.get(k, "") for k in fields})


def latest_context() -> dict[str, Any]:
    session_dir = latest_dir("05_EXECUCAO/219_N8N_IMPORT_SESSION/*")
    import_file = session_dir / "IMPORT_THIS_IN_N8N_GUARDED.json" if session_dir else latest_file("05_EXECUCAO/219_N8N_IMPORT_SESSION/**/IMPORT_THIS_IN_N8N_GUARDED.json")
    latest_import_report = latest_file("05_EXECUCAO/220_N8N_LATEST_IMPORT/**/N8N_LATEST_IMPORT.json")
    verify_report = latest_file("05_EXECUCAO/222_N8N_MANUAL_IMPORT_VERIFIER/**/N8N_MANUAL_IMPORT_VERIFICATION.json")

    latest_payload = read_json(latest_import_report)
    verify_payload = read_json(verify_report)

    return {
        "session_dir": rel(session_dir),
        "import_file": rel(import_file),
        "latest_import_report": rel(latest_import_report),
        "verify_report": rel(verify_report),
        "nodes": latest_payload.get("nodes") or verify_payload.get("nodes"),
        "active": latest_payload.get("active") if "active" in latest_payload else verify_payload.get("active"),
        "last_status_level": verify_payload.get("status_level"),
        "last_verification_verdict": verify_payload.get("verdict"),
    }


def add_record(
    client: str,
    stage: str,
    verdict: str,
    workflow_id: str,
    execution_id: str,
    webhook_path: str,
    notes: str,
) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = latest_context()

    allowed_stages = {
        "local_ready",
        "imported",
        "manual_trigger",
        "curl_smoke",
        "credentials_review",
        "approved_for_activation",
        "production_activated",
        "rollback",
    }

    blockers = []
    warnings = []

    if stage not in allowed_stages:
        blockers.append(f"invalid stage: {stage}")
    if verdict not in {"pass", "block", "warn", "unknown"}:
        blockers.append(f"invalid verdict: {verdict}")
    if stage in {"imported", "manual_trigger", "curl_smoke", "credentials_review", "approved_for_activation"} and not workflow_id:
        warnings.append("workflow_id not provided")
    if stage in {"manual_trigger", "curl_smoke"} and not execution_id:
        warnings.append("execution_id not provided")
    if stage == "curl_smoke" and not webhook_path:
        warnings.append("webhook_path not provided")
    if stage == "production_activated":
        blockers.append("production_activated evidence must not be recorded by this local ledger without explicit separate authorization")

    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "client": client,
        "stage": stage,
        "verdict": "block" if blockers else verdict,
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "webhook_path": webhook_path,
        "import_file": ctx.get("import_file"),
        "session_dir": ctx.get("session_dir"),
        "nodes": ctx.get("nodes"),
        "active": ctx.get("active"),
        "last_status_level": ctx.get("last_status_level"),
        "last_verification_verdict": ctx.get("last_verification_verdict"),
        "blockers": blockers,
        "warnings": warnings,
        "notes": notes,
        "status_real": "local_evidence_ledger_only_no_n8n_action",
    }

    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    records = load_records()
    write_csv(records)

    print("N8N_EVIDENCE_LEDGER_ADD_DONE")
    print(json.dumps({
        "verdict": record["verdict"],
        "stage": stage,
        "ledger": rel(LEDGER),
        "csv": rel(CSV_LEDGER),
        "records": len(records),
        "blockers": blockers,
        "warnings": warnings,
    }, indent=2))

    return 0 if not blockers else 1


def report(client: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    records = load_records()
    if client:
        records = [r for r in records if r.get("client") == client]

    ctx = latest_context()
    blockers = []
    warnings = []

    if not ctx.get("import_file"):
        blockers.append("missing latest import file")
    if not records:
        warnings.append("no evidence records yet")

    latest_by_stage = {}
    for r in records:
        latest_by_stage[r.get("stage", "unknown")] = r

    recommended_next = "run n8n-latest and import guarded file manually"
    if latest_by_stage.get("imported"):
        recommended_next = "run manual trigger in n8n and record execution evidence"
    if latest_by_stage.get("manual_trigger"):
        recommended_next = "run curl smoke against webhook-test path and record evidence"
    if latest_by_stage.get("curl_smoke"):
        recommended_next = "review credentials and only connect after approval"
    if latest_by_stage.get("credentials_review"):
        recommended_next = "stop here unless explicit authorization for activation exists"

    verdict = "pass" if not blockers else "block"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{ts}_report_{slug(client or 'all')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "client": client or "all",
        "record_count": len(records),
        "latest_context": ctx,
        "latest_by_stage": latest_by_stage,
        "recommended_next": recommended_next,
        "blockers": blockers,
        "warnings": warnings,
        "status_real": "local_evidence_report_only",
    }

    (out_dir / "N8N_EVIDENCE_LEDGER_REPORT.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# JARVIS n8n Evidence Ledger Report",
        "",
        f"- verdict: `{verdict}`",
        f"- client: `{client or 'all'}`",
        f"- records: `{len(records)}`",
        f"- import_file: `{ctx.get('import_file')}`",
        f"- recommended_next: `{recommended_next}`",
        "",
        "## Latest by stage",
        "",
    ]

    if latest_by_stage:
        for stage, r in latest_by_stage.items():
            md.append(f"- `{stage}` verdict=`{r.get('verdict')}` workflow=`{r.get('workflow_id') or '-'}` execution=`{r.get('execution_id') or '-'}`")
    else:
        md.append("- none")

    md += ["", "## Blockers", ""]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]
    md += ["", "## Status real", "", "Local evidence ledger only. No import, activation, credentials, webhook or production action is performed.", ""]

    (out_dir / "N8N_EVIDENCE_LEDGER_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_EVIDENCE_LEDGER_REPORT_DONE")
    print(out_dir / "N8N_EVIDENCE_LEDGER_REPORT.md")
    print(json.dumps({
        "verdict": verdict,
        "records": len(records),
        "recommended_next": recommended_next,
        "blockers": blockers,
        "warnings": warnings,
    }, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--client", default="n8n-manual")
    p_add.add_argument("--stage", default="local_ready")
    p_add.add_argument("--verdict", default="pass")
    p_add.add_argument("--workflow-id", default="")
    p_add.add_argument("--execution-id", default="")
    p_add.add_argument("--webhook-path", default="")
    p_add.add_argument("--notes", default="")

    p_report = sub.add_parser("report")
    p_report.add_argument("--client", default="")

    args = parser.parse_args()

    if args.cmd == "add":
        return add_record(
            client=args.client,
            stage=args.stage,
            verdict=args.verdict,
            workflow_id=args.workflow_id,
            execution_id=args.execution_id,
            webhook_path=args.webhook_path,
            notes=args.notes,
        )

    if args.cmd == "report":
        return report(client=args.client)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
