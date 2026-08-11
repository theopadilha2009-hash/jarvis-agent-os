#!/usr/bin/env python3
"""Offline evaluation of the production JARVIS request router."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "07_RELATORIOS" / "02_TECNICOS" / "ULTIMO_AGENT_RUNTIME_EVAL.md"


def load_gateway():
    spec = importlib.util.spec_from_file_location("jarvis_eval_gateway", ROOT / "api" / "index.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("gateway module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCENARIOS = [
    ("oi jarvis", "assistant", "concise", False, False, 0),
    ("me conta uma piada curta", "assistant", "concise", False, False, 0),
    ("fala alguma coisa para mim", "assistant", "concise", False, False, 0),
    ("você está funcionando?", "assistant", "concise", False, False, 0),
    ("qual é a diferença entre RAM e armazenamento?", "assistant", "concise", False, False, 0),
    ("o que você acha desta arquitetura?", "assistant", "detailed", False, False, 0),
    ("como você melhoraria meu fluxo de trabalho?", "assistant", "balanced", False, False, 0),
    ("quais são as melhores opções para organizar um projeto grande?", "assistant", "balanced", False, False, 0),
    ("compare REST e GraphQL com prós e contras", "assistant", "detailed", False, False, 0),
    ("analise este plano e detalhe os riscos", "assistant", "detailed", False, False, 0),
    ("crie um checklist de debug para uma API lenta", "assistant", "detailed", False, False, 0),
    ("explique passo a passo como funciona OAuth", "assistant", "detailed", False, False, 0),
    ("pesquise as notícias mais recentes de inteligência artificial", "research", "detailed", True, False, 0),
    ("busque na internet a versão atual do Next.js", "research", "detailed", True, False, 0),
    ("qual é o preço atual do iPhone no Brasil?", "research", "detailed", True, False, 0),
    ("compare preços atuais de notebooks gamer", "research", "detailed", True, False, 0),
    ("pesquise projetos públicos de assistente pessoal no GitHub", "research", "detailed", True, False, 0),
    ("procure repos similares ao Open Interpreter no GitHub", "research", "detailed", True, False, 0),
    ("quanto custa um Honda Civic G8 usado na OLX e Webmotors?", "research", "detailed", True, False, 0),
    ("preço do Corolla usado hoje", "research", "detailed", True, False, 0),
    ("abra o Spotify", "open_application", "concise", False, False, 0),
    ("abra a Steam", "open_application", "concise", False, False, 0),
    ("abra o calendário", "open_application", "concise", False, False, 0),
    ("feche o Spotify", "close_application", "concise", False, False, 0),
    ("feche o Google Chrome", "close_application", "concise", False, False, 0),
    ("tire um print da tela", "screen_capture", "concise", False, False, 0),
    ("abra a gravação de tela", "screen_record", "concise", False, False, 0),
    ("mostre meus repositórios do GitHub", "github_overview", "concise", False, False, 0),
    ("meu computador está travando, analise a memória", "system_memory", "detailed", False, False, 0),
    ("mostre os arquivos grandes do armazenamento", "storage_scan", "concise", False, False, 0),
    ("abra o Spotify e depois tire um print da tela", "device_run", "concise", False, False, 2),
    ("abra a Steam, tire um print da tela e depois feche a Steam", "device_run", "concise", False, False, 3),
    ("abra o calendário e então abra o Spotify", "device_run", "concise", False, False, 2),
    ("mostre o GitHub e depois tire um print da tela", "device_run", "concise", False, False, 2),
    ("analise a memória do Mac e depois abra o Spotify", "device_run", "detailed", False, False, 2),
    ("eu prefiro respostas curtas e diretas", "assistant", "concise", False, True, 0),
    ("minha preferência é usar azul em vez de roxo", "assistant", "concise", False, True, 0),
    ("decidi que o Jarvis será meu painel pessoal", "assistant", "concise", False, True, 0),
    ("meu objetivo principal é automatizar tarefas repetitivas", "assistant", "concise", False, True, 0),
    ("a partir de agora quero que o Jarvis sempre cite fontes", "assistant", "concise", False, True, 0),
    ("hoje eu prefiro respostas longas", "assistant", "concise", False, False, 0),
    ("por enquanto eu nunca quero áudio", "assistant", "concise", False, False, 0),
    ("guarde na memória minha preferência por respostas curtas", "memory_save", "concise", False, True, 0),
    ("salve esta decisão na memória", "memory_save", "concise", False, False, 0),
    ("mostre minhas memórias", "assistant", "concise", False, False, 0),
    ("adicione comprar café na agenda", "agenda_note", "concise", False, False, 0),
    ("mostre minha agenda", "agenda_view", "concise", False, False, 0),
    ("adicione uma tarefa revisar o Jarvis", "task_add", "concise", False, False, 0),
    ("mande mensagem no WhatsApp para Arthur", "message_draft", "concise", False, False, 0),
    ("token=" + "x" * 20, "blocked_secret", "concise", False, False, 0),
]


def evaluate(module):
    results = []
    for index, (prompt, route, profile, search, memory, steps) in enumerate(SCENARIOS, start=1):
        actual = module.agent_request_contract(prompt)
        expected = {"route": route, "profile": profile, "search": search, "memory": memory, "steps": steps}
        matched = all(actual.get(key) == value for key, value in expected.items())
        results.append({"id": index, "prompt": prompt, "expected": expected, "actual": actual, "passed": matched})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="JARVIS Agent Runtime evaluation")
    parser.add_argument("--json", action="store_true", help="print the full machine-readable result")
    args = parser.parse_args(argv)
    print("JARVIS Agent Runtime Eval")
    print("Status real: 50 pedidos avaliados localmente contra o roteador de produção; nenhuma API externa chamada.")
    module = load_gateway()
    results = evaluate(module)
    passed = sum(row["passed"] for row in results)
    total = len(results)
    payload = {
        "protocol": "jarvis-agent-eval/1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0.0,
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Resultado: {passed}/{total} ({payload['pass_rate']:.1f}%).")
        for row in results:
            if not row["passed"]:
                print(f"FALHA #{row['id']}: {row['prompt']}")
                print(f"  esperado={row['expected']}")
                print(f"  recebido={row['actual']}")
    if os.environ.get("JARVIS_NO_REPORT") == "1":
        print("Relatório: desativado por JARVIS_NO_REPORT=1.")
    else:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        failures = [row for row in results if not row["passed"]]
        lines = [
            "# JARVIS Agent Runtime Eval",
            "",
            f"- Generated: {payload['generated_at']}",
            f"- Result: {passed}/{total} ({payload['pass_rate']:.1f}%)",
            "- Scope: production routing contract; no external APIs called",
            "",
            "## Failures",
            "",
            *(f"- #{row['id']} `{row['prompt']}`" for row in failures),
            *( ["- None."] if not failures else [] ),
            "",
            "Produção: nada alterado.",
        ]
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório: {REPORT.relative_to(ROOT)}")
    print("Produção: nada alterado.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
