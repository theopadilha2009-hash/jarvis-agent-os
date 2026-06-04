from pathlib import Path
import ast
import json
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "11_SCRIPTS"
OUT_DIR = ROOT / "05_EXECUCAO" / "187_MARATHON_CONSOLIDATOR"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def analyze():
    scripts = sorted(SCRIPT_DIR.glob("jarvis_*.py"))
    rows = []
    groups = {}
    warnings = []

    for p in scripts:
        text = p.read_text(encoding="utf-8", errors="replace")
        name = p.stem
        parts = name.replace("jarvis_", "").split("_")
        domain = parts[0] if parts else "unknown"
        action = parts[-1] if len(parts) > 1 else "unknown"
        lines = text.count("\n") + 1

        funcs = []
        classes = []
        try:
            tree = ast.parse(text)
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        except Exception as e:
            warnings.append({"file": str(p.relative_to(ROOT)), "warning": f"ast_parse_failed: {e}"})

        shallow = lines < 80
        huge = lines > 900

        if shallow:
            warnings.append({"file": str(p.relative_to(ROOT)), "warning": "possibly_shallow_script", "lines": lines})
        if huge:
            warnings.append({"file": str(p.relative_to(ROOT)), "warning": "possibly_huge_script", "lines": lines})

        row = {
            "file": str(p.relative_to(ROOT)),
            "name": name,
            "domain": domain,
            "action": action,
            "lines": lines,
            "functions": len(funcs),
            "classes": len(classes),
            "shallow": shallow,
            "huge": huge,
        }
        rows.append(row)

        groups.setdefault(domain, {"count": 0, "lines": 0, "actions": {}})
        groups[domain]["count"] += 1
        groups[domain]["lines"] += lines
        groups[domain]["actions"][action] = groups[domain]["actions"].get(action, 0) + 1

    dup_map = {}
    for r in rows:
        key = (r["domain"], r["action"])
        dup_map.setdefault(key, []).append(r["file"])

    duplicates = [
        {"domain": k[0], "action": k[1], "count": len(v), "files": v[:12]}
        for k, v in dup_map.items()
        if len(v) >= 8
    ]

    top_domains = sorted(
        [{"domain": k, **v} for k, v in groups.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "verdict": "pass",
        "script_count": len(rows),
        "total_lines": sum(r["lines"] for r in rows),
        "domain_count": len(groups),
        "warnings_count": len(warnings),
        "top_domains": top_domains[:40],
        "top_big_scripts": sorted(rows, key=lambda x: x["lines"], reverse=True)[:30],
        "duplicates_by_domain_action": duplicates[:80],
        "warnings_sample": warnings[:120],
        "recommendation": [
            "Do not run more marathon batches yet.",
            "Use this command as the stable feature inventory.",
            "Optimize deep_sweep next because profiler marks it as slowest.",
            "Add quality rules before more bulk generation.",
        ],
    }
    return payload


def write_report(payload):
    json_path = OUT_DIR / "MARATHON_CONSOLIDATOR.json"
    md_path = OUT_DIR / "MARATHON_CONSOLIDATOR.md"

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# JARVIS Marathon Consolidator",
        "",
        f"- verdict: {payload['verdict']}",
        f"- scripts: {payload['script_count']}",
        f"- lines: {payload['total_lines']}",
        f"- domains: {payload['domain_count']}",
        f"- warnings: {payload['warnings_count']}",
        "",
        "## Top domains",
    ]

    for d in payload["top_domains"][:25]:
        md.append(f"- {d['domain']}: {d['count']} scripts / {d['lines']} lines")

    md += ["", "## Biggest scripts"]
    for r in payload["top_big_scripts"][:20]:
        md.append(f"- {r['file']}: {r['lines']} lines")

    md += ["", "## Duplicate-looking domain/action groups"]
    for d in payload["duplicates_by_domain_action"][:30]:
        md.append(f"- {d['domain']} / {d['action']}: {d['count']} files")

    md += ["", "## Recommendation"]
    for item in payload["recommendation"]:
        md.append(f"- {item}")

    md.append("")
    md.append("Status real: analysis/index only. No cleanup applied.")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    return md_path


def main():
    payload = analyze()
    md_path = write_report(payload)
    print("MARATHON_CONSOLIDATOR_DONE")
    print(md_path)
    print(json.dumps({
        "verdict": payload["verdict"],
        "scripts": payload["script_count"],
        "lines": payload["total_lines"],
        "domains": payload["domain_count"],
        "warnings": payload["warnings_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
