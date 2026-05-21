from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

CATEGORIES = [
    ("workspace checks", "05_EXECUCAO/04_WORKSPACE_CHECKS"),
    ("task starts", "05_EXECUCAO/06_TASK_STARTS"),
    ("executor handoffs", "05_EXECUCAO/07_EXECUTOR_HANDOFFS"),
    ("task briefs", "05_EXECUCAO/08_TASK_BRIEFS"),
    ("auto-task runs", "05_EXECUCAO/09_AUTO_TASK_RUNS"),
    ("mode plans", "05_EXECUCAO/11_MODE_PLANS"),
    ("generated prompts", "06_PROMPTS/99_GENERATED"),
    ("logs", "09_LOGS"),
    ("project index", "04_PROJETOS/_INDEX"),
    ("release checks", "10_TESTES/RELEASE_CHECKS"),
    ("smoke tests", "10_TESTES/SMOKE_TESTS"),
    ("safety gates", "10_TESTES/SAFETY_GATES"),
]

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()

def git_status():
    out = run(["git", "status", "--short"])
    return out.splitlines() if out else []

def main():
    lines = git_status()

    print("JARVIS — Theo Padilha AI Worker Pending Artifacts")
    print("")
    print("Status real: inspeção local de Git. Nada alterado.")
    print("")

    if not lines:
        print("Git status: limpo")
        print("")
        print("Nada para versionar.")
        return

    print("Git status:")
    for line in lines:
        print(f"- {line}")
    print("")

    print("Categorias detectadas:")
    detected = []

    for label, path in CATEGORIES:
        hits = [x for x in lines if path in x]
        if hits:
            detected.append(path)
            print(f"- {label}: {len(hits)} item(ns)")

    other = []
    for line in lines:
        if not any(path in line for _, path in CATEGORIES):
            other.append(line)

    if other:
        print(f"- outros: {len(other)} item(ns)")

    print("")
    print("Comando de add sugerido:")

    if detected:
        print("git add \\")
        for i, path in enumerate(detected):
            suffix = " \\" if i < len(detected) - 1 else ""
            print(f"  {path}{suffix}")
    else:
        print("# revisar manualmente antes de git add")

    print("")
    print("Regra:")
    print("- Rode secret-scan antes de commit se houver prompts/logs novos.")
    print("- Commitar artefatos gerados é aceitável quando representam um marco útil.")
    print("- Não versionar .env, tokens, chaves, cookies, QR codes ou workflows com segredo.")

if __name__ == "__main__":
    main()
