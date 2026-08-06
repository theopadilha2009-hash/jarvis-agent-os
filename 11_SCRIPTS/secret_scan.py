from pathlib import Path
import subprocess
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    "__pycache__",
}

SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".tar", ".gz",
    ".mp4", ".mov", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".DS_Store"
}

SECRET_PATTERNS = [
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("openrouter_key", re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("supabase_personal_token", re.compile(r"\bsbp_[A-Za-z0-9]{20,}\b")),
    ("vercel_token", re.compile(r"\bvcp_[A-Za-z0-9]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}\b")),
    ("jwt_like", re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("assignment_secret", re.compile(
        r"(?i)\b(api[_-]?key|apikey|token|password|passwd|senha|secret|service_role|authorization|bearer|cookie)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-./+=]{16,})"
    )),
]

SAFE_PLACEHOLDERS = [
    "[REDACTED]",
    "REDACTED",
    "abc123",
    "example",
    "placeholder",
    "your_",
    "seu_",
    "minha_",
    "dummy",
    "fake",
    "test",
]

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()

def is_probably_binary(path):
    try:
        data = path.read_bytes()[:2048]
        return b"\0" in data
    except Exception:
        return True

def should_skip(path):
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False

def safe_value(line):
    low = line.lower()
    return any(x.lower() in low for x in SAFE_PLACEHOLDERS)

def scan_file(path):
    hits = []

    if should_skip(path) or is_probably_binary(path):
        return hits

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return hits

    for i, line in enumerate(text.splitlines(), start=1):
        if safe_value(line):
            continue

        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                hits.append({
                    "file": str(path.relative_to(ROOT)),
                    "line": i,
                    "pattern": name,
                })

    return hits

def main():
    print("JARVIS — Theo Padilha AI Worker Secret Scan")
    print("")

    tracked = run(["git", "ls-files"]).splitlines()
    all_hits = []

    forbidden_files = [
        f for f in tracked
        if f.endswith((".env", ".pem", ".key", ".p12", ".pfx"))
        or "/.env" in f
        or Path(f).name.startswith(".env")
    ]

    for f in tracked:
        path = ROOT / f
        if path.exists():
            all_hits.extend(scan_file(path))

    if forbidden_files:
        print("FALHA  Arquivos secretos pelo nome estão versionados:")
        for f in forbidden_files[:30]:
            print(f"- {f}")
        print("")

    if all_hits:
        print("FALHA  Possíveis segredos em conteúdo versionado:")
        for h in all_hits[:80]:
            print(f"- {h['file']}:{h['line']} [{h['pattern']}] valor oculto")
        print("")

    passed = not forbidden_files and not all_hits

    if passed:
        print("OK  Nenhum segredo óbvio detectado em arquivos versionados.")
        print("")
        print("Resultado: SECRET SCAN PASSOU")
    else:
        print("Resultado: SECRET SCAN COM PENDÊNCIAS")

    print("Status real: varredura local. Nenhum segredo foi impresso.")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
