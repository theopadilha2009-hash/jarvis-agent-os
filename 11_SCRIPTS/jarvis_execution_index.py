from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "153_EXECUTION_INDEX"
REPORT = OUT / "EXECUTION_INDEX.md"
STATE = OUT / "EXECUTION_INDEX.json"


def file_info(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
        "name": path.name,
        "suffix": path.suffix,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def collect(limit: int = 80) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)

    files = []
    if EXEC.exists():
        for path in EXEC.rglob("*"):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if path.suffix.lower() not in [".md", ".json", ".txt"]:
                continue
            files.append(file_info(path))

    files.sort(key=lambda item: item["modified_at"], reverse=True)

    dirs = []
    if EXEC.exists():
        for path in EXEC.iterdir():
            if path.is_dir():
                dirs.append({
                    "path": str(path.relative_to(REPO)).replace("\\", "/"),
                    "name": path.name,
                })

    dirs.sort(key=lambda item: item["name"], reverse=True)

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "execution_root_exists": EXEC.exists(),
        "directory_count": len(dirs),
        "file_count": len(files),
        "directories": dirs[:limit],
        "recent_files": files[:limit],
    }


def write(data: dict) -> None:
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Execution Index — Block 153",
        "",
        f"Created at: `{data['created_at']}`",
        f"Execution root exists: `{data['execution_root_exists']}`",
        f"Directories: `{data['directory_count']}`",
        f"Files: `{data['file_count']}`",
        "",
        "## Recent files",
        "",
    ]

    for item in data["recent_files"][:30]:
        lines.append(f"- `{item['path']}` size=`{item['size_bytes']}` modified=`{item['modified_at']}`")

    lines += [
        "",
        "## Recent directories",
        "",
    ]

    for item in data["directories"][:40]:
        lines.append(f"- `{item['path']}`")

    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def run_index() -> int:
    data = collect()
    write(data)

    print("EXECUTION_INDEX_DONE")
    print(REPORT)
    print(json.dumps({
        "directory_count": data["directory_count"],
        "file_count": data["file_count"],
        "latest_file": data["recent_files"][0]["path"] if data["recent_files"] else None,
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 153 Execution Index")
    parser.add_argument("action", choices=["index"], default="index")
    args = parser.parse_args()

    if args.action == "index":
        return run_index()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
