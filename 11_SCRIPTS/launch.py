#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import subprocess
import sys

ROOT = Path.cwd()

niche = " ".join(sys.argv[1:]).strip()
if not niche:
    print('uso: ./jarvis-launch "nicho"')
    raise SystemExit(2)

def sh(cmd, check=True):
    print("\nRUN:", " ".join(cmd))
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

client = f"{niche.title()} Teste"
idea = f"Mini landing page + WhatsApp rastreável para {niche}"

OUT = ROOT / "05_EXECUCAO/59_LAUNCH"
OUT.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
report = OUT / f"{ts}_launch.md"

print("JARVIS_LAUNCH_START")
print("nicho:", niche)
print("cliente:", client)
print("ideia:", idea)

sh(["./jarvis-opportunity", niche])
sh(["./jarvis-full", client, idea])
sh(["./jarvis-proposal-pro"])
sh(["./jarvis-latest"])
sh(["./jarvis-copy-msg"], check=False)
sh(["./jarvis-open-latest"], check=False)
sh(["./jarvis-report"])

items = {
    "product_pack": latest_dir("05_EXECUCAO/43_PRODUCT_PACKS"),
    "demo": latest_dir("05_EXECUCAO/45_DEMO_PAGES"),
    "n8n": latest_dir("05_EXECUCAO/46_N8N_STARTERS"),
    "sell_kit": latest_dir("05_EXECUCAO/48_SELL_KITS"),
    "client_kit": latest_dir("05_EXECUCAO/50_CLIENT_KITS"),
    "export_zip": latest_file("05_EXECUCAO/52_EXPORTS", "*.zip"),
    "proposal": latest_dir("05_EXECUCAO/53_PROPOSAL_PAGES"),
    "opportunity": latest_file("05_EXECUCAO/58_OPPORTUNITY", "*.md"),
}

lines = []
lines.append("# JARVIS Launch Report")
lines.append("")
lines.append(f"- Nicho: {niche}")
lines.append(f"- Cliente teste: {client}")
lines.append(f"- Ideia: {idea}")
lines.append("")
lines.append("## Arquivos gerados")
lines.append("")
for name, item in items.items():
    lines.append(f"- {name}: `{item.relative_to(ROOT) if item else 'nenhum'}`")
lines.append("")
lines.append("## Próxima ação")
lines.append("")
lines.append("1. Ver a demo aberta no navegador")
lines.append("2. Ver a proposta aberta no navegador")
lines.append("3. Conferir a mensagem copiada")
lines.append("4. Mandar para 3 prospects reais")
lines.append("5. Medir resposta")
lines.append("")
lines.append("## Reusar")
lines.append("")
lines.append("```bash")
lines.append(f'./jarvis-launch "{niche}"')
lines.append("```")

report.write_text("\n".join(lines), encoding="utf-8")

print("\nJARVIS_LAUNCH_OK")
print("report:", report.relative_to(ROOT))
print("mensagem_cliente: copiada se existia")
print("demo/proposta/index: abertos se existiam")
