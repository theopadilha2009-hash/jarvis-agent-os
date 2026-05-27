#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import subprocess, sys, os, py_compile, shutil

ROOT = Path(__file__).resolve().parents[1]

OUTPUTS = [
    "05_EXECUCAO/43_PRODUCT_PACKS",
    "05_EXECUCAO/44_QUICK_FACTORY",
    "05_EXECUCAO/45_DEMO_PAGES",
    "05_EXECUCAO/46_N8N_STARTERS",
    "05_EXECUCAO/48_SELL_KITS",
    "05_EXECUCAO/50_CLIENT_KITS",
    "05_EXECUCAO/52_EXPORTS",
    "05_EXECUCAO/53_PROPOSAL_PAGES",
    "05_EXECUCAO/55_IDEA_RADAR",
    "05_EXECUCAO/56_CLIENT_HUNT",
    "05_EXECUCAO/57_MARKET_MAP",
    "05_EXECUCAO/58_OPPORTUNITY",
    "05_EXECUCAO/59_LAUNCH",
]

COMMANDS = [
    "jarvis-full", "jarvis-help", "jarvis-produce", "jarvis-client-produce",
    "jarvis-client", "jarvis-demo", "jarvis-n8n", "jarvis-sell",
    "jarvis-index", "jarvis-latest", "jarvis-use-latest",
    "jarvis-export-latest", "jarvis-proposal-pro",
    "jarvis-ideas",
    "jarvis-client-hunt",
    "jarvis-market",
    "jarvis-opportunity",
    "jarvis-launch",
]

def sh(cmd, capture=False, check=True):
    if capture:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    return subprocess.run(cmd, cwd=ROOT, check=check)

def latest_dir(base):
    p = ROOT / base
    if not p.exists():
        return None
    dirs = [x for x in p.iterdir() if x.is_dir()]
    return sorted(dirs)[-1] if dirs else None

def latest_file(base, pattern="*"):
    p = ROOT / base
    if not p.exists():
        return None
    files = [x for x in p.glob(pattern) if x.is_file()]
    return sorted(files)[-1] if files else None

def branch():
    return sh(["git", "branch", "--show-current"], capture=True)

def commit():
    return sh(["git", "log", "--oneline", "-1"], capture=True)

def status():
    return sh(["git", "status", "--short"], capture=True)

def doctor():
    print("JARVIS_DOCTOR_START")
    print("branch:", branch())
    print("commit:", commit())

    scripts = sorted((ROOT / "11_SCRIPTS").glob("*.py"))
    for s in scripts:
        py_compile.compile(str(s), doraise=True)
    print("python_ok:", len(scripts))

    missing = []
    for c in COMMANDS:
        p = ROOT / c
        if not p.exists():
            missing.append(c)
        elif not os.access(p, os.X_OK):
            missing.append(c + " sem chmod +x")
    if missing:
        print("missing:", ", ".join(missing))
        raise SystemExit(1)
    print("commands_ok:", len(COMMANDS))

    print("\nlatest:")
    for base in OUTPUTS:
        item = latest_dir(base)
        if not item and base.endswith("52_EXPORTS"):
            item = latest_file(base, "*.zip")
        if not item:
            item = latest_file(base, "*.md")
        print("-", base + ":", item.relative_to(ROOT) if item else "nenhum")

    print("\ngit_status:")
    print(status() or "clean")
    print("JARVIS_DOCTOR_OK")

def open_latest():
    targets = []
    demo = latest_dir("05_EXECUCAO/45_DEMO_PAGES")
    prop = latest_dir("05_EXECUCAO/53_PROPOSAL_PAGES")
    index = ROOT / "05_EXECUCAO/47_INDEX/index.html"
    if demo and (demo / "index.html").exists():
        targets.append(demo / "index.html")
    if prop and (prop / "index.html").exists():
        targets.append(prop / "index.html")
    if index.exists():
        targets.append(index)
    for t in targets:
        sh(["open", str(t)], check=False)
        print("opened:", t)
    print("JARVIS_OPEN_LATEST_OK")

def copy_msg():
    client = latest_dir("05_EXECUCAO/50_CLIENT_KITS")
    msg = client / "03_MENSAGEM_CLIENTE.md" if client else None
    if not msg or not msg.exists():
        raise SystemExit("mensagem não encontrada")
    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
    p.communicate(msg.read_text(encoding="utf-8"))
    print("JARVIS_COPY_MSG_OK")
    print("arquivo:", msg.relative_to(ROOT))

def report():
    out = ROOT / "05_EXECUCAO/54_REPORTS"
    out.mkdir(parents=True, exist_ok=True)
    file = out / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_jarvis_status.md")
    lines = [
        "# JARVIS Status Report",
        "",
        f"- Branch: `{branch()}`",
        f"- Commit: `{commit()}`",
        "",
        "## Latest artifacts",
    ]
    for base in OUTPUTS:
        item = latest_dir(base)
        if not item and base.endswith("52_EXPORTS"):
            item = latest_file(base, "*.zip")
        if not item:
            item = latest_file(base, "*.md")
        lines.append(f"- `{base}`: `{item.relative_to(ROOT) if item else 'nenhum'}`")
    lines += ["", "## Git status", "```", status() or "clean", "```"]
    file.write_text("\n".join(lines), encoding="utf-8")
    print("JARVIS_REPORT_OK")
    print("arquivo:", file.relative_to(ROOT))

def save():
    msg = " ".join(sys.argv[2:]).strip() or "chore: update JARVIS tools"
    doctor()
    if not status():
        print("nothing_to_commit")
        return
    sh(["git", "add", "-A"])
    sh(["git", "commit", "-m", msg])
    sh(["git", "push", "origin", branch()])
    print("JARVIS_SAVE_OK")

def clean_pattern():
    if len(sys.argv) < 3:
        raise SystemExit('uso: ./jarvis-clean-pattern "texto"')
    pattern = sys.argv[2]
    removed = 0
    for base in OUTPUTS:
        p = ROOT / base
        if not p.exists():
            continue
        for item in p.iterdir():
            if pattern in item.name:
                shutil.rmtree(item) if item.is_dir() else item.unlink()
                removed += 1
    print(f"JARVIS_CLEAN_PATTERN_OK removed={removed}")

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "doctor": doctor()
elif cmd == "open-latest": open_latest()
elif cmd == "copy-msg": copy_msg()
elif cmd == "report": report()
elif cmd == "save": save()
elif cmd == "clean-pattern": clean_pattern()
else: raise SystemExit("uso: doctor|open-latest|copy-msg|report|save|clean-pattern")
