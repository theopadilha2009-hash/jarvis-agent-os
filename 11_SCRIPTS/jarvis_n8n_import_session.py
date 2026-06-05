from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "219_N8N_IMPORT_SESSION"


def slug(value: str, fallback: str = "import-session") -> str:
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


def latest_guarded_export() -> Path | None:
    return latest_file("05_EXECUCAO/218_N8N_GUARDED_EXPORT/**/IMPORT_THIS_IN_N8N_GUARDED.json")


def latest_testkit() -> Path | None:
    return latest_file("05_EXECUCAO/217_N8N_IMPORT_TESTKIT/**/N8N_IMPORT_TESTKIT.json")


def latest_runtime() -> Path | None:
    return latest_file("05_EXECUCAO/216_N8N_RUNTIME_SMOKE/**/N8N_RUNTIME_SMOKE.json")


def node_summary(workflow: dict[str, Any]) -> list[str]:
    rows = []
    for i, node in enumerate(workflow.get("nodes", []), start=1):
        if not isinstance(node, dict):
            continue
        rows.append(f"{i:02d}. {node.get('name')} | {node.get('type')}")
    return rows


def run(client: str, n8n_url: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{ts}_{slug(client)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    guarded = latest_guarded_export()
    testkit = latest_testkit()
    runtime = latest_runtime()

    workflow = read_json(guarded)
    testkit_payload = read_json(testkit)
    runtime_payload = read_json(runtime)

    blockers = []
    warnings = []

    if not guarded:
        blockers.append("missing guarded export")
    if not workflow:
        blockers.append("guarded export unreadable")
    if workflow.get("active") is not False:
        blockers.append("guarded export is not active=false")
    if len(workflow.get("nodes", [])) < 5:
        blockers.append("guarded export has too few nodes")
    if not any("manualtrigger" in str(n.get("type", "")).lower() for n in workflow.get("nodes", []) if isinstance(n, dict)):
        blockers.append("manual trigger missing in guarded export")
    if not testkit:
        warnings.append("latest import testkit report not found")
    if not runtime:
        warnings.append("latest runtime smoke report not found")
    if testkit_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest testkit verdict is not pass")
    if runtime_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest runtime verdict is not pass")

    import_copy = out_dir / "IMPORT_THIS_IN_N8N_GUARDED.json"
    if guarded:
        shutil.copy2(guarded, import_copy)

    session = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "client": client,
        "n8n_url": n8n_url,
        "guarded_export_source": str(guarded.relative_to(REPO)) if guarded else None,
        "session_import_file": str(import_copy.relative_to(REPO)) if guarded else None,
        "testkit_report": str(testkit.relative_to(REPO)) if testkit else None,
        "runtime_report": str(runtime.relative_to(REPO)) if runtime else None,
        "workflow_name": workflow.get("name"),
        "active": workflow.get("active"),
        "nodes": len(workflow.get("nodes", [])),
        "blockers": blockers,
        "warnings": warnings,
        "status_real": "local_import_session_pack_only_not_n8n_ui_or_runtime_validated",
    }

    (out_dir / "N8N_IMPORT_SESSION.json").write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

    n8n_clean = n8n_url.rstrip("/")
    test_path = "REPLACE_WITH_TEST_WEBHOOK_PATH_AFTER_IMPORT"

    curl_smoke = f'''#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${{1:-{n8n_clean}}}"
WEBHOOK_PATH="${{2:-{test_path}}}"
TARGET="$BASE_URL/webhook-test/$WEBHOOK_PATH"

echo "Target: $TARGET"
echo "Use only after importing workflow into n8n and clicking Execute workflow."

for f in payloads/*.json; do
  echo "\\n--- POST $f ---"
  curl -sS -X POST "$TARGET" -H "Content-Type: application/json" --data-binary "@$f"
  echo
done
'''
    (out_dir / "RUN_AFTER_IMPORT_CURL_SMOKE.sh").write_text(curl_smoke, encoding="utf-8")
    (out_dir / "RUN_AFTER_IMPORT_CURL_SMOKE.sh").chmod(0o755)

    payload_dir = out_dir / "payloads"
    payload_dir.mkdir(exist_ok=True)

    payloads = {
        "01_normal_lead.json": {"event": "message", "fromMe": False, "message": {"text": "Oi, quero saber mais sobre atendimento"}, "contact": {"name": "Lead Teste", "phone": "5500000000000"}, "source": "jarvis-import-session"},
        "02_human_transfer.json": {"event": "message", "fromMe": False, "message": {"text": "Quero falar com um humano"}, "contact": {"name": "Lead Humano", "phone": "5500000000001"}, "source": "jarvis-import-session"},
        "03_empty_message.json": {"event": "message", "fromMe": False, "message": {"text": ""}, "contact": {"name": "Lead Vazio", "phone": "5500000000002"}, "source": "jarvis-import-session"},
        "04_anti_loop_from_me.json": {"event": "message", "fromMe": True, "message": {"text": "Mensagem enviada pelo bot"}, "contact": {"name": "Bot", "phone": "5500000000003"}, "source": "n8n"},
        "05_low_context.json": {"event": "message", "fromMe": False, "message": {"text": "oi"}, "contact": {"name": "Lead Curto", "phone": "5500000000004"}, "source": "jarvis-import-session"},
    }

    for name, payload in payloads.items():
        (payload_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# JARVIS n8n Import Session Pack",
        "",
        f"- verdict: `{session['verdict']}`",
        f"- client: `{client}`",
        f"- n8n_url: `{n8n_url}`",
        f"- import_file: `{session['session_import_file']}`",
        f"- workflow_name: `{session['workflow_name']}`",
        f"- active: `{session['active']}`",
        f"- nodes: `{session['nodes']}`",
        "",
        "## 1. Import",
        "",
        "Import this file in n8n:",
        "",
        f"`{session['session_import_file']}`",
        "",
        "After import:",
        "- keep workflow inactive",
        "- do not add real credentials yet",
        "- click Manual Trigger / Execute workflow only",
        "- copy the test webhook path from n8n",
        "",
        "## 2. Run curl smoke",
        "",
        "```bash",
        f"cd {out_dir.relative_to(REPO)}",
        f"./RUN_AFTER_IMPORT_CURL_SMOKE.sh {n8n_clean} {test_path}",
        "```",
        "",
        "## 3. Node summary",
        "",
    ]

    md += [f"- {row}" for row in node_summary(workflow)] if workflow else ["- missing workflow"]

    md += ["", "## Blockers", ""]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]

    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]

    md += [
        "",
        "## Status real",
        "",
        "This only creates an import session pack. It does not import into n8n, connect credentials, activate webhook, or validate production.",
        "",
    ]

    (out_dir / "OPEN_THIS_FOR_IMPORT.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_IMPORT_SESSION_DONE")
    print(out_dir / "OPEN_THIS_FOR_IMPORT.md")
    print(json.dumps({
        "verdict": session["verdict"],
        "import_file": session["session_import_file"],
        "nodes": session["nodes"],
        "blockers": blockers,
        "warnings": warnings,
        "open": str((out_dir / "OPEN_THIS_FOR_IMPORT.md").relative_to(REPO)),
    }, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="n8n-import-session")
    parser.add_argument("--n8n-url", default="https://YOUR_N8N_DOMAIN")
    args = parser.parse_args()
    return run(args.client, args.n8n_url)


if __name__ == "__main__":
    raise SystemExit(main())
