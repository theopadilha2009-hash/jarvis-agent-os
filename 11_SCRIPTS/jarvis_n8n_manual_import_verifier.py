from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "222_N8N_MANUAL_IMPORT_VERIFIER"


def slug(value: str, fallback: str = "manual-import") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip().lower()).strip("-")
    return s[:90] or fallback


def latest_dir(pattern: str) -> Path | None:
    dirs = [p for p in REPO.glob(pattern) if p.is_dir()]
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None


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


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(REPO))
    except Exception:
        return str(path)


def run(
    client: str,
    n8n_url: str,
    workflow_id: str,
    execution_id: str,
    webhook_path: str,
    imported: bool,
    manual_trigger_tested: bool,
    curl_smoke_tested: bool,
    credentials_connected: bool,
    activated: bool,
    notes: str,
) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{ts}_{slug(client)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    latest_session = latest_dir("05_EXECUCAO/219_N8N_IMPORT_SESSION/*")
    latest_import = latest_session / "IMPORT_THIS_IN_N8N_GUARDED.json" if latest_session else latest_file("05_EXECUCAO/219_N8N_IMPORT_SESSION/**/IMPORT_THIS_IN_N8N_GUARDED.json")
    latest_open = latest_session / "OPEN_THIS_FOR_IMPORT.md" if latest_session else latest_file("05_EXECUCAO/219_N8N_IMPORT_SESSION/**/OPEN_THIS_FOR_IMPORT.md")
    latest_latest = latest_file("05_EXECUCAO/220_N8N_LATEST_IMPORT/**/N8N_LATEST_IMPORT.json")
    latest_guarded = latest_file("05_EXECUCAO/218_N8N_GUARDED_EXPORT/**/N8N_GUARDED_EXPORT.json")
    latest_testkit = latest_file("05_EXECUCAO/217_N8N_IMPORT_TESTKIT/**/N8N_IMPORT_TESTKIT.json")
    latest_runtime = latest_file("05_EXECUCAO/216_N8N_RUNTIME_SMOKE/**/N8N_RUNTIME_SMOKE.json")

    latest_payload = read_json(latest_latest)
    guarded_payload = read_json(latest_guarded)
    testkit_payload = read_json(latest_testkit)
    runtime_payload = read_json(latest_runtime)

    blockers: list[str] = []
    warnings: list[str] = []

    if not latest_import or not latest_import.exists():
        blockers.append("missing latest guarded import file")
    if latest_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest n8n-latest verdict is not pass")
    if guarded_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest guarded export verdict is not pass")
    if testkit_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest testkit verdict is not pass")
    if runtime_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest runtime smoke verdict is not pass")

    if activated:
        blockers.append("workflow marked activated; this verifier is for inactive/manual verification only")
    if credentials_connected:
        warnings.append("credentials marked connected; confirm no secrets were exported or committed")
    if not imported:
        warnings.append("workflow not marked imported yet")
    if not manual_trigger_tested:
        warnings.append("manual trigger test not marked done")
    if not curl_smoke_tested:
        warnings.append("curl smoke test not marked done")
    if not workflow_id:
        warnings.append("n8n workflow id not provided")
    if not execution_id:
        warnings.append("n8n execution id not provided")
    if not webhook_path:
        warnings.append("test webhook path not provided")

    status_level = "local_ready"
    if imported:
        status_level = "imported_in_n8n_unactivated"
    if imported and manual_trigger_tested:
        status_level = "manual_trigger_tested_in_n8n"
    if imported and manual_trigger_tested and curl_smoke_tested:
        status_level = "curl_smoke_tested_in_n8n"
    if credentials_connected:
        status_level = "credentials_connected_review_required"

    verdict = "pass" if not blockers else "block"

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "client": client,
        "status_level": status_level,
        "n8n_url": n8n_url,
        "workflow_id": workflow_id or None,
        "execution_id": execution_id or None,
        "webhook_path": webhook_path or None,
        "imported": imported,
        "manual_trigger_tested": manual_trigger_tested,
        "curl_smoke_tested": curl_smoke_tested,
        "credentials_connected": credentials_connected,
        "activated": activated,
        "latest_session_dir": rel(latest_session),
        "latest_import_file": rel(latest_import),
        "latest_open_md": rel(latest_open),
        "latest_n8n_latest_report": rel(latest_latest),
        "latest_guarded_report": rel(latest_guarded),
        "latest_testkit_report": rel(latest_testkit),
        "latest_runtime_report": rel(latest_runtime),
        "nodes": latest_payload.get("nodes") or guarded_payload.get("nodes") or testkit_payload.get("nodes") or runtime_payload.get("nodes"),
        "active": latest_payload.get("active"),
        "blockers": blockers,
        "warnings": warnings,
        "notes": notes,
        "status_real": "manual_evidence_recorder_only_does_not_import_activate_or_touch_n8n",
    }

    (out_dir / "N8N_MANUAL_IMPORT_VERIFICATION.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# JARVIS n8n Manual Import Verification",
        "",
        f"- verdict: `{verdict}`",
        f"- client: `{client}`",
        f"- status_level: `{status_level}`",
        f"- n8n_url: `{n8n_url}`",
        f"- workflow_id: `{workflow_id or 'not provided'}`",
        f"- execution_id: `{execution_id or 'not provided'}`",
        f"- webhook_path: `{webhook_path or 'not provided'}`",
        f"- imported: `{imported}`",
        f"- manual_trigger_tested: `{manual_trigger_tested}`",
        f"- curl_smoke_tested: `{curl_smoke_tested}`",
        f"- credentials_connected: `{credentials_connected}`",
        f"- activated: `{activated}`",
        "",
        "## Local source files",
        "",
        f"- latest_session_dir: `{payload['latest_session_dir']}`",
        f"- import_file: `{payload['latest_import_file']}`",
        f"- open_md: `{payload['latest_open_md']}`",
        "",
        "## Real n8n test order",
        "",
        "1. Import `IMPORT_THIS_IN_N8N_GUARDED.json`.",
        "2. Keep workflow inactive.",
        "3. Do not connect real credentials yet.",
        "4. Click Execute workflow / Manual Trigger.",
        "5. Copy test webhook path.",
        "6. Run generated curl smoke against `/webhook-test/...`.",
        "7. Save workflow_id / execution_id here using this verifier.",
        "8. Only after review: connect credentials.",
        "9. Only after authorization: activate production webhook.",
        "",
        "## Blockers",
        "",
    ]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]
    md += ["", "## Notes", "", notes or "- none", ""]
    md += ["Status real: this records manual evidence only. It does not import, activate, deploy, connect credentials, or touch production.", ""]

    (out_dir / "N8N_MANUAL_IMPORT_VERIFICATION.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_MANUAL_IMPORT_VERIFIER_DONE")
    print(out_dir / "N8N_MANUAL_IMPORT_VERIFICATION.md")
    print(json.dumps({
        "verdict": verdict,
        "status_level": status_level,
        "import_file": payload["latest_import_file"],
        "nodes": payload["nodes"],
        "active": payload["active"],
        "blockers": blockers,
        "warnings": warnings,
    }, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="manual-import")
    parser.add_argument("--n8n-url", default="https://YOUR_N8N_DOMAIN")
    parser.add_argument("--workflow-id", default="")
    parser.add_argument("--execution-id", default="")
    parser.add_argument("--webhook-path", default="")
    parser.add_argument("--imported", action="store_true")
    parser.add_argument("--manual-trigger-tested", action="store_true")
    parser.add_argument("--curl-smoke-tested", action="store_true")
    parser.add_argument("--credentials-connected", action="store_true")
    parser.add_argument("--activated", action="store_true")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    return run(
        client=args.client,
        n8n_url=args.n8n_url,
        workflow_id=args.workflow_id,
        execution_id=args.execution_id,
        webhook_path=args.webhook_path,
        imported=args.imported,
        manual_trigger_tested=args.manual_trigger_tested,
        curl_smoke_tested=args.curl_smoke_tested,
        credentials_connected=args.credentials_connected,
        activated=args.activated,
        notes=args.notes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
