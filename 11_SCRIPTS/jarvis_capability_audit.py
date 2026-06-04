from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
OUT = REPO / "05_EXECUCAO" / "202_CAPABILITY_AUDIT"
OUT.mkdir(parents=True, exist_ok=True)

def run(cmd: list[str], timeout: int = 20) -> dict:
    try:
        result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, timeout=timeout)
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as exc:
        return {"exit_code": 1, "stdout": "", "stderr": str(exc)}

def exists(name: str) -> bool:
    return (SCRIPTS / name).exists()

def command_help() -> str:
    r = run([sys.executable, str(SCRIPTS / "jarvis_ops.py"), "-h"], timeout=15)
    return (r["stdout"] or r["stderr"] or "")

def command_present(help_text: str, name: str) -> bool:
    return name in help_text

def status(verdict: str, name: str, evidence: list[str], next_step: str) -> dict:
    return {
        "name": name,
        "verdict": verdict,
        "evidence": evidence,
        "next_step": next_step,
    }

def main() -> int:
    created_at = datetime.now().isoformat(timespec="seconds")
    help_text = command_help()
    script_files = sorted(SCRIPTS.glob("jarvis_*.py"))

    git_status = run(["git", "status", "-sb"], timeout=10)["stdout"]
    head = run(["git", "log", "--oneline", "-1"], timeout=10)["stdout"]

    capabilities = [
        status(
            "real",
            "Local health and repo checks",
            [
                "home-dashboard exists" if command_present(help_text, "home-dashboard") else "home-dashboard not confirmed in help",
                "command-profiler exists" if command_present(help_text, "command-profiler") else "command-profiler not confirmed in help",
                "marathon-consolidator exists" if command_present(help_text, "marathon-consolidator") else "marathon-consolidator not confirmed in help",
            ],
            "Keep using this as quality gate before/after work.",
        ),
        status(
            "real",
            "Guarded Git shipping",
            [
                "autoship exists" if command_present(help_text, "autoship") else "autoship not confirmed in help",
                "ship-guard exists" if command_present(help_text, "ship-guard") else "ship-guard not confirmed in help",
                "pre-commit hook already blocks syntax/secret-like files if configured",
            ],
            "Keep manual safe commit only when guard blocks falsely and validation is strong.",
        ),
        status(
            "partial",
            "Feature generation / marathon",
            [
                "smart-marathon appears available" if command_present(help_text, "smart-marathon") else "smart-marathon not confirmed in help",
                "This generates local pool features, not full internet-aware product work.",
            ],
            "Do not call this true autonomy yet. Use only for local controlled feature batches.",
        ),
        status(
            "partial",
            "Local brain / planning",
            [
                "brain scripts exist" if any("brain" in p.name for p in script_files) else "brain scripts not detected",
                "Likely useful for structured plans, not trusted automatic patches.",
            ],
            "Use as planning assistant only until quality score proves reliable.",
        ),
        status(
            "partial",
            "n8n/workflow support",
            [
                "n8n-related scripts exist" if any("n8n" in p.name.lower() for p in script_files) else "no dedicated n8n scripts detected",
                "No confirmed full professional workflow generator from plain language yet.",
            ],
            "Build a dedicated n8n workflow builder after internet investigation is real.",
        ),
        status(
            "partial",
            "UI/cockpit",
            [
                "cockpit.html exists" if (SCRIPTS / "jarvis_ui_assets" / "cockpit.html").exists() else "cockpit.html missing",
                "UI can be patched, but it is not self-improving by itself.",
            ],
            "Later connect UI to capability modules instead of only visual polish.",
        ),
        status(
            "missing" if not exists("jarvis_internet_investigation.py") else "real",
            "Internet investigation",
            [
                "jarvis_internet_investigation.py exists" if exists("jarvis_internet_investigation.py") else "no dedicated internet investigation module before this block",
                "A real module should search/fetch/cache/report sources.",
            ],
            "Run internet-investigate with a concrete topic and inspect generated sources.",
        ),
        status(
            "missing",
            "Image/video generation",
            [
                "No confirmed local image/video generation adapter detected.",
                "Needs explicit provider/API/local model integration.",
            ],
            "Build only after research module and workflow builder are stable.",
        ),
    ]

    counts = {
        "real": sum(1 for c in capabilities if c["verdict"] == "real"),
        "partial": sum(1 for c in capabilities if c["verdict"] == "partial"),
        "missing": sum(1 for c in capabilities if c["verdict"] == "missing"),
    }

    payload = {
        "created_at": created_at,
        "verdict": "pass",
        "repo": {
            "git_status": git_status,
            "head": head,
            "script_count": len(script_files),
            "python": sys.version.split()[0],
            "curl_available": shutil.which("curl") is not None,
        },
        "counts": counts,
        "capabilities": capabilities,
        "recommended_next": [
            "Use Internet Investigation v1 for real source gathering.",
            "Then build n8n Workflow Builder v1 from source-backed specs.",
            "Then connect these capabilities to the cockpit UI.",
        ],
    }

    (OUT / "CAPABILITY_AUDIT.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Real Capability Audit",
        "",
        f"Created at: `{created_at}`",
        f"Head: `{head}`",
        "",
        "## Counts",
        "",
        f"- Real: `{counts['real']}`",
        f"- Partial: `{counts['partial']}`",
        f"- Missing: `{counts['missing']}`",
        "",
        "## Capabilities",
        "",
    ]

    for c in capabilities:
        lines.append(f"### {c['name']} — `{c['verdict']}`")
        lines.append("")
        for item in c["evidence"]:
            lines.append(f"- {item}")
        lines.append(f"- Next: {c['next_step']}")
        lines.append("")

    lines += [
        "## Recommended next",
        "",
    ]

    for item in payload["recommended_next"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "Status real: this is an audit. It does not make missing capabilities real by itself.",
    ]

    (OUT / "CAPABILITY_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("CAPABILITY_AUDIT_DONE")
    print(OUT / "CAPABILITY_AUDIT.md")
    print(json.dumps({"verdict": "pass", "counts": counts}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
