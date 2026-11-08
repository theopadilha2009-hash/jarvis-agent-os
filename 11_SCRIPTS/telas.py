"""
telas.py — descobre e usa as telas conectadas ao Mac.

O dono tem três: a do MacBook, a SAMSUNG (TV) e o projetor VX Pro no HDMI.
Pedir "abre o Google na TV" tem que abrir lá, não na tela que estiver na
frente.

Como funciona: o macOS não expõe as telas por AppleScript, então a lista vem
de um `swift` de três linhas (NSScreen). Mover a janela é por System Events,
que é o único caminho que funciona no Chrome atual — `set bounds` via
AppleScript é ignorado desde o Chrome 100.

Hard rules:
  - nunca fecha janela do dono
  - sem permissão de Acessibilidade, devolve erro claro em vez de fingir
  - nomes em português: "tv", "samsung", "projetor", "hdmi", "principal"
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

CONFIG_PADRAO = os.path.expanduser("~/.jarvis/telas.json")

# NSScreen.frame usa origem embaixo-esquerda (Cocoa) e a janela do System
# Events usa topo-esquerda. CGDisplayBounds já vem no sistema certo — usar
# NSScreen aqui dava y=-180 para a TV e a janela ia parar no lugar errado.
SWIFT_TELAS = """
import AppKit
import CoreGraphics
for s in NSScreen.screens {
    let key = NSDeviceDescriptionKey("NSScreenNumber")
    let did = (s.deviceDescription[key] as? NSNumber)?.uint32Value ?? 0
    let b = CGDisplayBounds(did)
    let idx = NSScreen.screens.firstIndex(of: s) ?? 0
    print("\\(idx)|\\(s.localizedName)|\\(Int(b.minX)),\\(Int(b.minY)),\\(Int(b.width)),\\(Int(b.height))")
}
"""

# Apelidos que o dono usa falando. A ordem importa: o primeiro que casar vence.
APELIDOS = {
    "tv": ("samsung", "tv", "televisao", "televisão"),
    "projetor": ("hdmi", "projetor", "vx", "vx pro", "projetor hdmi"),
    "principal": ("built-in", "retina", "integrada", "principal", "macbook", "notebook"),
}


def _rodar(argv, timeout=15):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def _applescript_literal(value):
    """Escapa texto para entrar como literal AppleScript entre aspas.

    A URL é interpolada no script, então uma aspa crua fecha o literal e o
    que vier depois é EXECUTADO: `https://x/a" & (do shell script "...") & "`
    vira comando de shell. O filtro de URL do worker já barra aspas, mas esta
    função é pública e não pode depender de outra camada.
    """
    texto = str(value or "")
    # Barra primeiro: escapar aspas antes deixaria "\\" virar "\" e quebrar.
    texto = texto.replace("\\", "\\\\").replace('"', '\\"')
    # Quebra de linha dentro de literal AppleScript não é permitida.
    return texto.replace("\n", " ").replace("\r", " ")


# Cache curto: `listar()` é chamado várias vezes por abertura (achar a tela,
# decidir o fallback) e cada chamada sobe um processo swift. Com o swift
# travado e 60s de timeout, uma tentativa só podia levar minutos.
_LISTA_CACHE = {"at": 0.0, "telas": []}
LISTA_CACHE_SEGUNDOS = 5.0


def listar(force=False):
    """[{"indice", "nome", "x", "y", "largura", "altura"}] na ordem do macOS."""
    import time as _t
    agora = _t.monotonic()
    if not force and _LISTA_CACHE["telas"] and agora - _LISTA_CACHE["at"] < LISTA_CACHE_SEGUNDOS:
        return list(_LISTA_CACHE["telas"])
    try:
        # swift lê de stdin quando o arquivo é "-"
        proc = subprocess.run(
            ["swift", "-"], input=SWIFT_TELAS, capture_output=True, text=True,
            timeout=10, check=False,
        )
        if proc.returncode != 0:
            return []
        telas = []
        for linha in proc.stdout.splitlines():
            partes = linha.strip().split("|")
            if len(partes) != 3:
                continue
            indice, nome, geo = partes
            try:
                x, y, largura, altura = (int(v) for v in geo.split(","))
            except ValueError:
                continue
            telas.append({
                "indice": int(indice), "nome": nome,
                "x": x, "y": y, "largura": largura, "altura": altura,
            })
        if telas:
            _LISTA_CACHE.update({"at": _t.monotonic(), "telas": list(telas)})
        return telas
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def carregar_config():
    """~/.jarvis/telas.json: {"1": "SAMSUNG", "2": "Built-in", "3": "HDMI"}.

    Mapeia o número que o dono fala ("tela 3") para um pedaço do nome da tela.
    Sem o arquivo, o número vale a posição da esquerda para a direita.
    """
    caminho = os.environ.get("JARVIS_TELAS_CONFIG") or CONFIG_PADRAO
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _numero_da_tela(alvo):
    achou = re.fullmatch(r"(?:tela\s*)?(\d{1,2})", alvo)
    return int(achou.group(1)) if achou else None


def _tela_numerada(numero, telas):
    nome = str(carregar_config().get(str(numero)) or "").strip().casefold()
    if nome:
        # Configurada e desconectada não cai na posição: devolver outra tela
        # aqui mandaria a janela para onde o dono não pediu.
        return next((t for t in telas if nome in t["nome"].casefold()), None)
    ordenadas = sorted(telas, key=lambda t: (t["x"], t["y"]))
    return ordenadas[numero - 1] if 1 <= numero <= len(ordenadas) else None


def encontrar(apelido):
    """A tela que o apelido aponta, ou None."""
    alvo = str(apelido or "").strip().casefold()
    if not alvo:
        return None
    telas = listar()
    if not telas:
        return None
    # Número antes do nome: "3" aparece em nomes como "DELL U2723QE".
    numero = _numero_da_tela(alvo)
    if numero is not None:
        return _tela_numerada(numero, telas)
    # Nome exato primeiro ("samsung" casa com a SAMSUNG).
    for tela in telas:
        if alvo in tela["nome"].casefold():
            return tela
    for chave, nomes in APELIDOS.items():
        if alvo in nomes or any(n in alvo for n in nomes):
            for tela in telas:
                nome = tela["nome"].casefold()
                if any(n in nome for n in nomes):
                    return tela
    return None


def _processo_do_app(app):
    """Nome do processo para o System Events (Chrome, Safari, ...)."""
    return {
        "google chrome": "Google Chrome",
        "chrome": "Google Chrome",
        "safari": "Safari",
        "microsoft edge": "Microsoft Edge",
        "brave browser": "Brave Browser",
        "firefox": "Firefox",
    }.get(str(app or "").strip().casefold(), str(app or "").strip())


def mover_janela(app, tela, indice_janela=1):
    """Move a janela do app para a tela. Devolve (ok, mensagem).

    Usa System Events porque `set bounds` do Chrome é ignorado desde a
    versão 100. O y é ajustado para a barra de menu: o macOS não deixa a
    barra de título sair da área útil, então pedir y=-180 devolve y=0.
    """
    processo = _processo_do_app(app)
    if not processo:
        return False, "Não sei qual app mover."
    x, y = tela["x"], max(0, tela["y"])
    largura, altura = tela["largura"], tela["altura"]
    script = f'''
tell application "System Events"
  if not (exists process "{_applescript_literal(processo)}") then return "sem-processo"
  tell process "{_applescript_literal(processo)}"
    if (count of windows) < {indice_janela} then return "sem-janela"
    set position of window {indice_janela} to {{{x}, {y}}}
    set size of window {indice_janela} to {{{largura}, {altura}}}
    delay 0.2
    set p to position of window {indice_janela}
    return "ok:" & (item 1 of p) & "," & (item 2 of p)
  end tell
end tell
'''
    try:
        resultado = _rodar(["osascript", "-e", script], timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False, "Não consegui falar com o sistema."
    saida = (resultado.stdout or "").strip()
    erro = (resultado.stderr or "").strip()
    if saida == "sem-processo":
        return False, f"O {processo} não está aberto."
    if saida == "sem-janela":
        return False, f"O {processo} não tem janela aberta."
    if saida.startswith("ok:"):
        return True, f"Na {tela['nome']}."
    if "-10003" in erro or "não permitido" in erro.lower() or "not allowed" in erro.lower():
        return False, (
            "Preciso de permissão de Acessibilidade para mover a janela. "
            "Ajustes do Sistema, Privacidade e Segurança, Acessibilidade."
        )
    return False, "Não consegui mover a janela."


def abrir_na_tela(url, apelido, app="Google Chrome"):
    """Abre a URL numa janela nova do app e leva para a tela pedida.

    Usa o `bounds` nativo do Chrome/Safari quando existe — é gravável e
    dispensa Acessibilidade — e só cai no System Events como reserva. A
    janela é criada já nas coordenadas da tela, então não há o pulo da
    janela aparecendo na tela errada e depois mudando.
    """
    import time as _time

    tela = encontrar(apelido)
    if not tela:
        # Apelido conhecido mas desconectado (o dono desliga o projetor, o
        # HDMI cai) não pode virar pedido perdido: abre na principal, que é o
        # que ele está vendo. Apelido que não existe continua sendo erro —
        # adivinhar ali esconderia um pedido mal feito.
        if str(apelido or "").strip().lower() in APELIDOS:
            telas = listar()
            if telas:
                principal = next((t for t in telas if t["x"] == 0 and t["y"] == 0), telas[0])
                ok, msg = _abrir_na_tela(url, principal, app)
                return ok, f"{msg} (a tela “{apelido}” não está conectada)"
        disponiveis = ", ".join(t["nome"] for t in listar()) or "nenhuma"
        return False, f"Não achei a tela “{apelido}”. Tenho: {disponiveis}."
    return _abrir_na_tela(url, tela, app)


def abrir_na_principal(url, app="Google Chrome"):
    """Sem tela pedida disponível: abre na tela principal, mas abre."""
    telas = listar()
    if not telas:
        return False, "Nenhuma tela encontrada."
    principal = next((t for t in telas if t["x"] == 0 and t["y"] == 0), telas[0])
    return _abrir_na_tela(url, principal, app)


def _abrir_na_tela(url, tela, app="Google Chrome"):
    import time as _time

    processo = _processo_do_app(app)
    # A receita que funciona de verdade (testada nesta máquina):
    #   1. criar a janela e a URL no app;
    #   2. mover com System Events, que é o único que aplica posição no
    #      Chrome (o `bounds` nativo é ignorado);
    #   3. esperar a página carregar antes de considerar pronto.
    # Abrir direto com `bounds` deixava a janela em 44,44.
    if processo == "Safari":
        abrir = f'''
tell application "Safari"
  activate
  make new document with properties {{URL:"{_applescript_literal(url)}"}}
end tell
'''
    else:
        abrir = f'''
tell application "{_applescript_literal(processo)}"
  activate
  set w to make new window
  set URL of active tab of w to "{_applescript_literal(url)}"
end tell
'''
        # O System Events só enxerga as janelas do Space ATIVO: com o Chrome
        # atrás, ele reporta 0 janelas e a move falha. Ativar antes é o que
        # faz a diferença (testado nesta máquina).
    try:
        resultado = _rodar(["osascript", "-e", abrir], timeout=25)
    except (OSError, subprocess.SubprocessError):
        return False, f"Não consegui abrir o {processo}."

    erro = (resultado.stderr or "").strip()
    if "-1743" in erro or "not authorized" in erro.lower() or "não autorizado" in erro.lower():
        return False, (
            "Preciso de permissão de Automação para abrir o navegador. "
            "Ajustes do Sistema, Privacidade e Segurança, Automação."
        )

    # Se o app estava fechado (ou sem janela), `open -a` só sobe o processo.
    # Aqui garantimos que exista uma janela antes de tentar mover.
    _time.sleep(0.6)
    garantia = f'''
tell application "{_applescript_literal(processo)}"
  if (count of windows) is 0 then
    set w to make new window
    set URL of active tab of w to "{_applescript_literal(url)}"
  end if
end tell
'''
    try:
        _rodar(["osascript", "-e", garantia], timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass
    # A janela precisa existir antes de ser movida; o Chrome leva um instante.
    _time.sleep(0.9)
    ok, mensagem = mover_janela(app, tela, indice_janela=1)
    if not ok:
        return False, mensagem
    # Confirma que a página realmente carregou, em vez de prometer em vão.
    _time.sleep(0.6)
    return True, f"Aberto na {tela['nome']}."


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] == "listar":
        telas = listar()
        if not telas:
            print("Nenhuma tela encontrada (ou swift indisponível).")
            return
        print("JARVIS — Telas")
        print("Status real: leitura local. Nada foi alterado.")
        print("")
        for tela in telas:
            print(f"  {tela['indice']}: {tela['nome']}  {tela['largura']}x{tela['altura']} em ({tela['x']},{tela['y']})")
        print("")
        print("Produção: nada alterado.")
        return
    if argv[0] == "abrir" and len(argv) >= 3:
        ok, mensagem = abrir_na_tela(argv[1], argv[2])
        if not ok:
            # A TV pode estar desligada. O dono pediu o site, não a tela:
            # abrir na principal é melhor do que não abrir nada.
            ok_principal, msg_principal = abrir_na_principal(argv[1])
            if ok_principal:
                print(f"{msg_principal} (a tela {argv[2]} não está disponível)")
                sys.exit(0)
            print(mensagem)
            sys.exit(1)
        print(mensagem)
        sys.exit(0)
    if argv[0] == "mover" and len(argv) >= 3:
        tela = encontrar(argv[2])
        if not tela:
            print(f"Tela não encontrada: {argv[2]}")
            sys.exit(1)
        ok, mensagem = mover_janela(argv[1], tela)
        print(mensagem)
        sys.exit(0 if ok else 1)
    print("Uso: telas.py [listar | mover APP TELA]")
    sys.exit(1)


if __name__ == "__main__":
    main()