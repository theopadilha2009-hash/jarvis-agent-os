#!/usr/bin/env python3
import csv, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "05_EXECUCAO" / "49_LEAD_INBOX"
OUT.mkdir(parents=True, exist_ok=True)
CSV = OUT / "leads.csv"

args = sys.argv[1:]
if len(args) < 3:
    print('uso: ./jarvis-lead "nome" "telefone" "dor/interesse"')
    raise SystemExit(2)

nome, telefone, dor = args[0], args[1], " ".join(args[2:])
exists = CSV.exists()

row = {
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "nome": nome,
    "telefone": telefone,
    "dor": dor,
    "status": "novo",
    "proxima_acao": "mandar mensagem curta e oferecer demo"
}

with CSV.open("a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=row.keys())
    if not exists:
        w.writeheader()
    w.writerow(row)

msg = f"""Oi {nome}, tudo bem?

Vi que você tem interesse nisso:
{dor}

Eu consigo te mostrar uma demo simples de automação para reduzir esse trabalho manual. Posso te mandar uma prévia curta?"""

(OUT / "ultima_mensagem.md").write_text(msg + "\n", encoding="utf-8")

print("LEAD_INBOX_OK")
print("csv:", CSV.relative_to(ROOT))
print("mensagem:", (OUT / "ultima_mensagem.md").relative_to(ROOT))
