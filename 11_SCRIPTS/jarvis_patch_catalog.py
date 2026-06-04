from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "147_PATCH_CATALOG"
REPORT = OUT / "PATCH_CATALOG.md"
STATE = OUT / "PATCH_CATALOG.json"

CATALOG = [
    {
        "id": "repo_snapshot_v1",
        "title": "Repo snapshot helper",
        "target": "11_SCRIPTS/jarvis_repo_snapshot.py",
        "type": "new_helper",
        "priority": 1,
        "size": "small",
        "goal": "Create a local repo state snapshot with branch, status, and latest commits.",
    },
    {
        "id": "operator_brief_v1",
        "title": "Operator brief helper",
        "target": "11_SCRIPTS/jarvis_operator_brief.py",
        "type": "new_helper",
        "priority": 2,
        "size": "small",
        "goal": "Create a short operator brief from current repo state.",
    },
    {
        "id": "daily_checkpoint_v1",
        "title": "Daily checkpoint helper",
        "target": "11_SCRIPTS/jarvis_daily_checkpoint.py",
        "type": "new_helper",
        "priority": 3,
        "size": "small",
        "goal": "Create a simple daily checkpoint note for the operator.",
    },
]


def enrich(item: dict) -> dict:
    target = REPO / item["target"]
    enriched = dict(item)
    enriched["exists"] = target.exists()
    enriched["state"] = "done" if target.exists() else "ready"
    return enriched


def payload() -> dict:
    items = [enrich(item) for item in CATALOG]
    ready = [item for item in items if item["state"] == "ready"]
    done = [item for item in items if item["state"] == "done"]

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(items),
        "ready_count": len(ready),
        "done_count": len(done),
        "items": items,
        "next": ready[0] if ready else None,
    }


def write_report(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Patch Catalog — Block 147",
        "",
        f"Generated at: `{data['created_at']}`",
        f"Total: `{data['total']}`",
        f"Ready: `{data['ready_count']}`",
        f"Done: `{data['done_count']}`",
        "",
        "## Next",
        "",
    ]

    if data["next"]:
        lines.append(f"- `{data['next']['id']}` — `{data['next']['target']}`")
    else:
        lines.append("- No ready patch.")

    lines += [
        "",
        "## Catalog",
        "",
    ]

    for item in data["items"]:
        lines.append(
            f"- `{item['id']}` — state=`{item['state']}` — priority=`{item['priority']}` — `{item['target']}`"
        )

    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def show(action: str) -> int:
    data = payload()
    write_report(data)

    if action == "next":
        output = {
            "next": data["next"],
            "ready_count": data["ready_count"],
        }
    else:
        output = {
            "total": data["total"],
            "ready_count": data["ready_count"],
            "done_count": data["done_count"],
            "items": data["items"],
            "next": data["next"],
        }

    print("PATCH_CATALOG_DONE")
    print(REPORT)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 147 Patch Catalog")
    parser.add_argument("action", choices=["list", "next", "report"], default="list")
    args = parser.parse_args()
    return show(args.action)


if __name__ == "__main__":
    raise SystemExit(main())
