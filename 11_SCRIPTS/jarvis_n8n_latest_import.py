from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "220_N8N_LATEST_IMPORT"


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


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform.startswith("win"):
        subprocess.run(["cmd", "/c", "start", "", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def run(open_folder: bool = False, open_md: bool = False) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    session_dir = latest_dir("05_EXECUCAO/219_N8N_IMPORT_SESSION/*")
    session_json = latest_file("05_EXECUCAO/219_N8N_IMPORT_SESSION/**/N8N_IMPORT_SESSION.json")
    session_md = latest_file("05_EXECUCAO/219_N8N_IMPORT_SESSION/**/OPEN_THIS_FOR_IMPORT.md")
    import_file = latest_file("05_EXECUCAO/219_N8N_IMPORT_SESSION/**/IMPORT_THIS_IN_N8N_GUARDED.json")
    curl_file = latest_file("05_EXECUCAO/219_N8N_IMPORT_SESSION/**/RUN_AFTER_IMPORT_CURL_SMOKE.sh")

    guarded = latest_file("05_EXECUCAO/218_N8N_GUARDED_EXPORT/**/N8N_GUARDED_EXPORT.json")
    testkit = latest_file("05_EXECUCAO/217_N8N_IMPORT_TESTKIT/**/N8N_IMPORT_TESTKIT.json")
    runtime = latest_file("05_EXECUCAO/216_N8N_RUNTIME_SMOKE/**/N8N_RUNTIME_SMOKE.json")

    session_payload = read_json(session_json)
    guarded_payload = read_json(guarded)
    testkit_payload = read_json(testkit)
    runtime_payload = read_json(runtime)

    blockers = []
    warnings = []

    if not session_dir:
        blockers.append("missing latest import session directory")
    if not import_file:
        blockers.append("missing import json file")
    if not session_md:
        blockers.append("missing OPEN_THIS_FOR_IMPORT.md")
    if session_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest import session verdict is not pass")
    if guarded_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest guarded export verdict is not pass")
    if testkit_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest testkit verdict is not pass")
    if runtime_payload.get("verdict") not in {None, "pass"}:
        blockers.append("latest runtime verdict is not pass")

    if session_payload.get("active") is not False and session_payload:
        blockers.append("latest session workflow is not active=false")

    if session_payload.get("nodes") and session_payload.get("nodes") < 5:
        blockers.append("latest session has too few nodes")

    if not curl_file:
        warnings.append("curl smoke helper not found")

    verdict = "pass" if not blockers else "block"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "session_dir": rel(session_dir),
        "open_md": rel(session_md),
        "import_file": rel(import_file),
        "curl_file": rel(curl_file),
        "session_verdict": session_payload.get("verdict"),
        "guarded_verdict": guarded_payload.get("verdict"),
        "testkit_verdict": testkit_payload.get("verdict"),
        "runtime_verdict": runtime_payload.get("verdict"),
        "workflow_name": session_payload.get("workflow_name"),
        "nodes": session_payload.get("nodes"),
        "active": session_payload.get("active"),
        "blockers": blockers,
        "warnings": warnings,
        "status_real": "local_latest_import_pointer_only_not_n8n_ui_or_runtime_validated",
    }

    (out_dir / "N8N_LATEST_IMPORT.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# JARVIS n8n Latest Import",
        "",
        f"- verdict: `{verdict}`",
        f"- session_dir: `{payload['session_dir']}`",
        f"- open_md: `{payload['open_md']}`",
        f"- import_file: `{payload['import_file']}`",
        f"- curl_file: `{payload['curl_file']}`",
        f"- workflow_name: `{payload['workflow_name']}`",
        f"- nodes: `{payload['nodes']}`",
        f"- active: `{payload['active']}`",
        "",
        "## Open manually",
        "",
        "```bash",
        f"open '{payload['session_dir']}'" if sys.platform == "darwin" and payload["session_dir"] else f"# Open folder: {payload['session_dir']}",
        "```",
        "",
        "## Import file",
        "",
        f"`{payload['import_file']}`",
        "",
        "## After importing in n8n",
        "",
        "- keep workflow inactive",
        "- do not configure real credentials yet",
        "- click Execute workflow / Manual Trigger only",
        "- copy the test webhook path",
        "- run the curl smoke helper from the session folder",
        "",
        "## Blockers",
        "",
    ]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]
    md += ["", "Status real: pointer/open helper only.", ""]

    (out_dir / "N8N_LATEST_IMPORT.md").write_text("\n".join(md), encoding="utf-8")

    if open_folder and session_dir:
        open_path(session_dir)
    if open_md and session_md:
        open_path(session_md)

    print("N8N_LATEST_IMPORT_DONE")
    print(out_dir / "N8N_LATEST_IMPORT.md")
    print(json.dumps({
        "verdict": verdict,
        "session_dir": payload["session_dir"],
        "open_md": payload["open_md"],
        "import_file": payload["import_file"],
        "nodes": payload["nodes"],
        "active": payload["active"],
        "blockers": blockers,
        "warnings": warnings,
    }, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open-folder", action="store_true")
    parser.add_argument("--open-md", action="store_true")
    args = parser.parse_args()
    return run(open_folder=args.open_folder, open_md=args.open_md)


if __name__ == "__main__":
    raise SystemExit(main())
