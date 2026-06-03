from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "136_LOCAL_BRAIN_SMOKE"
REPORT = OUT / "LOCAL_BRAIN_SMOKE.md"
STATE = OUT / "LOCAL_BRAIN_SMOKE.json"
BRAIN_STATE = REPO / "05_EXECUCAO" / "133_BRAIN_ROUTER" / "BRAIN_ROUTER_STATE.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def smoke(goal: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    prompt = (
        goal.strip()
        or "Responda em 5 bullets curtos como melhorar a autonomia do Jarvis Agent OS."
    )

    code, output = run([
        sys.executable,
        "11_SCRIPTS/jarvis_brain_router.py",
        "prompt",
        prompt,
        "--task",
        "code",
        "--prefer",
        "ollama",
        "--allow-calls",
    ])

    brain_payload = {}
    if BRAIN_STATE.exists():
        brain_payload = json.loads(BRAIN_STATE.read_text(encoding="utf-8", errors="replace"))

    model_response = brain_payload.get("model_response") or {}
    text = str(model_response.get("text") or "").strip()

    ok = code == 0 and bool(text)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": prompt,
        "code": code,
        "ok": ok,
        "model": model_response.get("model"),
        "response_length": len(text),
        "response_preview": text[:1500],
        "raw_output_tail": output[-3000:] if output else "",
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Local Brain Smoke — Block 136",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"OK: `{payload['ok']}`",
        f"Model: `{payload.get('model')}`",
        f"Response length: `{payload['response_length']}`",
        "",
        "## Response preview",
        "",
        "```text",
        payload["response_preview"] or "-",
        "```",
        "",
        "## Raw output tail",
        "",
        "```text",
        payload["raw_output_tail"] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("LOCAL_BRAIN_SMOKE_DONE")
    print(REPORT)
    print(json.dumps({
        "ok": payload["ok"],
        "model": payload.get("model"),
        "response_length": payload["response_length"],
        "preview": payload["response_preview"][:500],
    }, ensure_ascii=False, indent=2))

    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 136 Local Brain Smoke")
    parser.add_argument("goal", nargs="*", default=[])
    args = parser.parse_args()

    goal = " ".join(args.goal).strip()
    return smoke(goal)


if __name__ == "__main__":
    raise SystemExit(main())
