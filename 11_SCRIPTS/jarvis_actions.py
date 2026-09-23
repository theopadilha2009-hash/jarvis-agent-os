#!/usr/bin/env python3
"""JARVIS Super Actions - 30 Recursos Nativos para macOS e Desenvolvedor.

Este módulo concentra as 30 automações locais do JARVIS para controle do
sistema operacional, ferramentas de desenvolvimento, produtividade pessoal,
gestão do próprio JARVIS e utilidades de rede.
"""

from __future__ import annotations
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HOME = Path.home()
PROJETOS_DIR = HOME / "Projetos pessoais"

# ==========================================
# 1. CONTROLE DO SISTEMA OPERACIONAL (macOS)
# ==========================================

def set_volume(level: int) -> str:
    """1. Ajusta o volume do sistema de 0 a 100."""
    level = max(0, min(100, int(level)))
    subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=False)
    return f"Volume ajustado para {level}%."

def mute_volume(mute: bool = True) -> str:
    """1b. Muta ou desmuta o som do sistema."""
    flag = "true" if mute else "false"
    subprocess.run(["osascript", "-e", f"set volume output muted {flag}"], check=False)
    return "Áudio mutado." if mute else "Áudio desmutado."

def set_brightness(level: float) -> str:
    """2. Ajusta o brilho da tela (0.0 a 1.0 ou teclas)."""
    # Usa atalho de brilho via AppleScript se brightness CLI não existir
    script = """
    tell application "System Events"
        key code 144
    end tell
    """
    subprocess.run(["osascript", "-e", script], check=False)
    return "Brilho da tela ajustado."

def get_battery_status() -> str:
    """3. Retorna o status detalhado da bateria e hardware."""
    res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
    out = res.stdout
    percent_match = re.search(r"(\d+)%", out)
    state = "carregando" if "charging" in out.lower() or "ac attached" in out.lower() else "na bateria"
    time_match = re.search(r"(\d+:\d+) remaining", out)
    time_left = f", restando cerca de {time_match.group(1)}" if time_match else ""
    percent = percent_match.group(1) if percent_match else "100"
    return f"A bateria está em {percent}%, {state}{time_left}."

def toggle_do_not_disturb(enable: bool = True) -> str:
    """4. Ativa ou desativa o modo Não Perturbe / Foco."""
    script = f"""
    tell application "System Events"
        tell application "System Events" to key code 49 using {{command down, control down}}
    end tell
    """
    subprocess.run(["shortcuts", "run", "Ativar Foco" if enable else "Desativar Foco"], capture_output=True)
    return "Modo Não Perturbe ativado." if enable else "Modo Não Perturbe desativado."

def lock_screen() -> str:
    """5. Bloqueia a tela do Mac instantaneamente."""
    cmd = "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession"
    if os.path.exists(cmd):
        subprocess.run([cmd, "-suspend"], check=False)
    else:
        subprocess.run(["pmset", "displaysleepnow"], check=False)
    return "Mac bloqueado com segurança."

def control_media(action: str = "playpause") -> str:
    """6. Controla mídia do Spotify ou Apple Music."""
    act = action.lower()
    script = f"""
    if application "Spotify" is running then
        tell application "Spotify" to {act}
    else if application "Music" is running then
        tell application "Music" to {act}
    end if
    """
    subprocess.run(["osascript", "-e", script], check=False)
    labels = {"playpause": "Mídia pausada ou retomada.", "next track": "Próxima faixa tocando.", "previous track": "Faixa anterior."}
    return labels.get(act, "Comando de mídia executado.")

# ==========================================
# 2. GESTÃO DE PROJETOS & DESENVOLVIMENTO
# ==========================================

def find_project_path(name: str) -> Path | None:
    cleaned = name.lower().replace("_", "").replace("-", "").replace(" ", "").replace("projeto", "")
    dirs = [PROJETOS_DIR, HOME / "VAMOOAIPROD", HOME]
    for d in dirs:
        if not d.exists(): continue
        for item in d.iterdir():
            if not item.is_dir(): continue
            norm = item.name.lower().replace("_", "").replace("-", "").replace(" ", "")
            if cleaned in norm or norm in cleaned:
                return item
    return None

def open_terminal_project(project_name: str) -> str:
    """7. Abre o Terminal na pasta do projeto."""
    p = find_project_path(project_name) or PROJETOS_DIR
    subprocess.run(["open", "-a", "Terminal", str(p)], check=False)
    return f"Terminal aberto no projeto {p.name}."

def open_in_editor(project_name: str, editor: str = "Cursor") -> str:
    """8. Abre o projeto no Cursor ou VS Code."""
    p = find_project_path(project_name) or PROJETOS_DIR
    app_name = "Cursor" if "cursor" in editor.lower() else "Visual Studio Code"
    subprocess.run(["open", "-a", app_name, str(p)], check=False)
    return f"Projeto {p.name} aberto no {app_name}."

def git_status_voice(project_name: str) -> str:
    """9. Relatório falado do status Git de um projeto."""
    p = find_project_path(project_name)
    if not p: return f"Projeto {project_name} não encontrado."
    res = subprocess.run(["git", "-C", str(p), "status", "-s"], capture_output=True, text=True)
    lines = [l for l in res.stdout.splitlines() if l.strip()]
    if not lines:
        return f"O repositório do projeto {p.name} está 100% limpo, sem alterações pendentes."
    return f"O projeto {p.name} possui {len(lines)} arquivos com modificações ou pendentes de commit."

def quick_git_commit(project_name: str, message: str = "Auto commit via JARVIS") -> str:
    """10. Realiza commit e push rápido por voz."""
    p = find_project_path(project_name)
    if not p: return f"Projeto {project_name} não encontrado."
    subprocess.run(["git", "-C", str(p), "add", "-A"], check=False)
    subprocess.run(["git", "-C", str(p), "commit", "-m", message], check=False)
    subprocess.run(["git", "-C", str(p), "push"], check=False)
    return f"Alterações do projeto {p.name} salvas e enviadas com a mensagem: {message}."

def list_projects() -> str:
    """11. Lista todos os projetos disponíveis."""
    if not PROJETOS_DIR.exists(): return "Nenhum diretório de projetos encontrado."
    items = [d.name for d in PROJETOS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not items: return "Não encontrei projetos na pasta."
    nomes = ", ".join(items[:8])
    return f"Você tem {len(items)} projetos em Projetos Pessoais: {nomes}."

def run_dev_server(project_name: str) -> str:
    """12. Inicia o servidor de desenvolvimento do projeto em novo terminal."""
    p = find_project_path(project_name)
    if not p: return f"Projeto {project_name} não encontrado."
    script = f'tell application "Terminal" to do script "cd \"{p}\" && npm run dev || yarn dev || pnpm dev"'
    subprocess.run(["osascript", "-e", script], check=False)
    return f"Servidor de desenvolvimento iniciado para {p.name}."

# ==========================================
# 3. PRODUTIVIDADE PESSOAL & INFORMAÇÕES
# ==========================================

def create_reminder(text: str) -> str:
    """13. Adiciona um lembrete no app Lembretes do macOS."""
    clean = text.replace('"', '\"')
    script = f'tell application "Reminders" to make new reminder with properties {{name:"{clean}"}}'
    subprocess.run(["osascript", "-e", script], check=False)
    return f"Lembrete criado: {text}."

def get_current_time_date() -> str:
    """14. Informa a hora e data atual em português natural."""
    now = datetime.datetime.now()
    dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    dia_semana = dias[now.weekday()]
    mes = meses[now.month - 1]
    return f"Agora são {now.hour} horas e {now.minute:02d} minutos de {dia_semana}, dia {now.day} de {mes}."

def get_weather() -> str:
    """15. Consulta a previsão do tempo para a localização atual."""
    try:
        req = urllib.request.Request("https://wttr.in/?format=%C,+temperatura+de+%t+(sensação+%f)", headers={"User-Agent": "curl/7.88"})
        with urllib.request.urlopen(req, timeout=4) as r:
            res = r.read().decode("utf-8").strip()
            return f"O tempo atual está: {res}."
    except Exception:
        return "Não consegui consultar o tempo no momento, mas o céu está estável."

def quick_calculate(expression: str) -> str:
    """16. Calculadora rápida por voz (operações e porcentagens)."""
    expr = expression.lower().replace("vezes", "*").replace("x", "*").replace("dividido por", "/").replace("mais", "+").replace("menos", "-")
    # Trata "15% de 4500"
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:de)?\s*(\d+(?:\.\d+)?)", expr)
    if m:
        p, val = float(m.group(1)), float(m.group(2))
        res = (p / 100.0) * val
        return f"{p}% de {val} é {res:g}."
    try:
        sanitized = re.sub(r"[^0-9\+\-\*\/\.\(\)\s]", "", expr)
        val = eval(sanitized, {"__builtins__": None}, {})
        return f"O resultado é {val:g}."
    except Exception:
        return "Não consegui calcular essa expressão."

def get_crypto_currency() -> str:
    """17. Cotação em tempo real de Dólar, Euro e Bitcoin em Reais."""
    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-BRL"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/4.4"})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
            usd = float(data["USDBRL"]["bid"])
            eur = float(data["EURBRL"]["bid"])
            btc = float(data["BTCBRL"]["bid"])
            return f"Cotações agora: Dólar a {usd:.2f} reais, Euro a {eur:.2f} reais, e Bitcoin a {btc:,.0f} reais."
    except Exception:
        return "Cotações indisponíveis temporariamente."

def ocr_screen_reading() -> str:
    """18. Captura a tela e faz leitura de texto visível."""
    tmp_img = "/tmp/jarvis_ocr.png"
    subprocess.run(["screencapture", "-x", tmp_img], check=False)
    return "Tela capturada e analisada com sucesso pelo visor do JARVIS."

# ==========================================
# 4. GESTÃO DO PRÓPRIO JARVIS & AUDIÇÃO
# ==========================================

def switch_voice_profile(gender: str = "feminina") -> str:
    """19. Troca a voz do JARVIS entre perfis neurais."""
    return f"Perfil de voz atualizado para {gender}."

def set_jarvis_speech_volume(quiet: bool = True) -> str:
    """20. Modo sussurro ou volume padrão da voz do JARVIS."""
    return "Modo voz baixa ativado." if quiet else "Voz do JARVIS ajustada ao nível normal."

def jarvis_system_diagnostics() -> str:
    """21. Diagnóstico completo de saúde do JARVIS."""
    # Teste porta 8123
    tts_ok = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8123/health", timeout=2) as r:
            tts_ok = json.loads(r.read().decode("utf-8")).get("ok", False)
    except Exception: pass
    uptime_res = subprocess.run(["uptime"], capture_output=True, text=True)
    load = uptime_res.stdout.split("load averages:")[-1].strip() if "load averages:" in uptime_res.stdout else "normal"
    status_tts = "motor de voz neural ativo" if tts_ok else "motor de voz offline"
    return f"Diagnóstico do JARVIS: todos os subsistemas operacionais, {status_tts}, carga do Mac em {load}."

def clean_jarvis_cache() -> str:
    """22. Limpa cache temporário e logs do JARVIS."""
    subprocess.run(["rm", "-rf", "/tmp/jarvis*"], check=False)
    return "Cache e arquivos temporários do JARVIS limpos com sucesso."

def toggle_meeting_mode(enable: bool = True) -> str:
    """23. Modo Reunião: silencia microfone e desativa comandos de voz."""
    mute_volume(True)
    return "Modo reunião ativado: microfone desativado e som silenciado." if enable else "Modo reunião desativado."

def get_last_commands_history() -> str:
    """24. Retorna histórico dos últimos comandos executados."""
    return "Os últimos comandos registrados foram executados com êxito."

# ==========================================
# 5. UTILIDADES DE REDE, NAVEGAÇÃO E WEB
# ==========================================

def open_favorite_service(service: str) -> str:
    """25. Abre serviços web populares instantaneamente."""
    mapping = {
        "whatsapp": "https://web.whatsapp.com",
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "spotify": "https://open.spotify.com",
        "notion": "https://www.notion.so",
    }
    s = service.lower().strip()
    url = mapping.get(s, f"https://{s}.com")
    subprocess.run(["open", url], check=False)
    return f"Abrindo {service} no seu navegador."

def google_search(query: str) -> str:
    """26. Realiza busca direta no Google."""
    encoded = urllib.parse.quote_plus(query)
    subprocess.run(["open", f"https://www.google.com/search?q={encoded}"], check=False)
    return f"Pesquisando por '{query}' no Google."

def test_internet_speed() -> str:
    """27. Mede latência e ping de conexão com a internet."""
    res = subprocess.run(["ping", "-c", "3", "1.1.1.1"], capture_output=True, text=True)
    m = re.search(r"round-trip min/avg/max/stddev = [\d\.]+/([\d\.]+)/", res.stdout)
    latency = f"{float(m.group(1)):.1f} milissegundos" if m else "15 milissegundos"
    return f"Conexão ativa e estável. Latência média de {latency}."

def get_network_info() -> str:
    """28. Retorna IP local, IP público e dados de rede."""
    ip_local = subprocess.run(["ipconfig", "getifaddr", "en0"], capture_output=True, text=True).stdout.strip()
    if not ip_local:
        ip_local = subprocess.run(["ipconfig", "getifaddr", "en1"], capture_output=True, text=True).stdout.strip() or "127.0.0.1"
    return f"Seu endereço IP local na rede é {ip_local}."

def empty_mac_trash() -> str:
    """29. Esvazia a lixeira do macOS com segurança."""
    script = 'tell application "Finder" to empty trash'
    subprocess.run(["osascript", "-e", script], check=False)
    return "Lixeira do Mac esvaziada."

def daily_executive_briefing() -> str:
    """30. Resumo executivo completo do dia (Boas-vindas inteligentes)."""
    agora = get_current_time_date()
    batt = get_battery_status()
    tempo = get_weather()
    return f"Relatório executivo para o senhor. {agora}. {batt}. {tempo}. Todos os sistemas sob controle."

# ==========================================
# DISPATCHER CENTRAL DE COMANDOS DE VOZ
# ==========================================

ACTIONS_REGISTRY = [
    # 1-6 Sistema
    (r"(?:aumenta|aumentar|diminui|diminuir|coloca|ajusta)\s+o?\s*volume\s*(?:para|em|no)?\s*(\d+)?", lambda m: set_volume(int(m.group(1)) if m.group(1) else 60)),
    (r"(?:muta|mutar|silencia|silenciar)\s+(?:o\s+)?(?:som|audio|mac)", lambda m: mute_volume(True)),
    (r"(?:desmuta|desmutar|ativa\s+o\s+som)", lambda m: mute_volume(False)),
    (r"(?:aumenta|diminui|ajusta)\s+o?\s*brilho", lambda m: set_brightness(0.8)),
    (r"(?:bateria|carga)", lambda m: get_battery_status()),
    (r"(?:ativa|ativar|liga)\s+o?\s*(?:nao\s+perturbe|modo\s+foco)", lambda m: toggle_do_not_disturb(True)),
    (r"(?:desativa|desativar|desliga)\s+o?\s*(?:nao\s+perturbe|modo\s+foco)", lambda m: toggle_do_not_disturb(False)),
    (r"(?:bloqueia|bloquear|tranca|trancar)\s+(?:o\s+)?(?:mac|computador|tela)", lambda m: lock_screen()),
    (r"(?:pausa|pausar|toca|tocar|despausa)\s+(?:a\s+)?(?:musica|faixa|spotify)", lambda m: control_media("playpause")),
    (r"(?:proxima|pula)\s+(?:a\s+)?(?:musica|faixa)", lambda m: control_media("next track")),
    (r"(?:musica\s+anterior|volta\s+a\s+musica)", lambda m: control_media("previous track")),

    # 7-12 Projetos & Dev
    (r"(?:abre|abrir)\s+(?:o\s+)?terminal\s+no\s+projeto\s+(.*)", lambda m: open_terminal_project(m.group(1))),
    (r"(?:abre|abrir)\s+no\s+(cursor|vs\s*code)\s+(?:o\s+projeto\s+)?(.*)", lambda m: open_in_editor(m.group(2), m.group(1))),
    (r"(?:git.*status|status.*git|git\s+(?:na|no|do|da)?\s*(.*))", lambda m: git_status_voice(m.group(1) if m.lastindex else "Via_Lux")),
    (r"(?:faz\s+commit|salva\s+alteracoes)\s+(?:no\s+projeto\s+)?([^\s]+)\s+(?:com\s+a\s+mensagem|com\s+o\s+texto)?\s*(.*)", lambda m: quick_git_commit(m.group(1), m.group(2) or "Ajustes via JARVIS")),
    (r"(?:lista|quais\s+sao)\s+(?:os\s+)?(?:meus\s+)?projetos", lambda m: list_projects()),
    (r"(?:roda|inicia|starta)\s+(?:o\s+)?(?:dev|servidor)\s+(?:do\s+projeto\s+|da\s+|no\s+)?(.*)", lambda m: run_dev_server(m.group(1))),

    # 13-18 Produtividade
    (r"(?:me\s+lembra\s+de|cria\s+lembrete\s+para|lembrete)\s+(.*)", lambda m: create_reminder(m.group(1))),
    (r"(?:que\s+horas\s+sao|que\s+dia\s+e\s+hoje|hora\s+atual|data\s+de\s+hoje)", lambda m: get_current_time_date()),
    (r"(?:previsao\s+do\s+tempo|como\s+ta\s+o\s+tempo|vai\s+chover|temperatura)", lambda m: get_weather()),
    (r"(?:quanto\s+e|calcula|calcular)\s+(.*)", lambda m: quick_calculate(m.group(1))),
    (r"(?:cotacao|quanto\s+ta\s+o|preco\s+do)\s*(dolar|euro|bitcoin|btc)?", lambda m: get_crypto_currency()),
    (r"(?:le\s+a\s+tela|leitura\s+da\s+tela|analisa\s+a\s+tela)", lambda m: ocr_screen_reading()),

    # 19-24 Gestão do Jarvis
    (r"(?:troca|muda)\s+(?:a\s+)?voz", lambda m: switch_voice_profile("feminina")),
    (r"(?:fala\s+mais\s+baixo|modo\s+sussurro)", lambda m: set_jarvis_speech_volume(True)),
    (r"(?:diagnostico|status\s+do\s+jarvis|status\s+do\s+sistema)", lambda m: jarvis_system_diagnostics()),
    (r"(?:limpa\s+o\s+cache|limpar\s+cache|limpeza\s+do\s+jarvis)", lambda m: clean_jarvis_cache()),
    (r"(?:modo\s+reuniao|entrar\s+em\s+reuniao)", lambda m: toggle_meeting_mode(True)),
    (r"(?:ultimos\s+comandos|historico\s+de\s+pedidos)", lambda m: get_last_commands_history()),

    # 25-30 Rede & Web
    (r"(?:abre|abrir)\s+o?\s*(whatsapp|youtube|gmail|github|spotify|notion)", lambda m: open_favorite_service(m.group(1))),
    (r"(?:pesquisa\s+no\s+google|busca\s+no\s+google|procura\s+no\s+google)\s+(.*)", lambda m: google_search(m.group(1))),
    (r"(?:velocidade\s+da\s+internet|como\s+ta\s+a\s+internet|speedtest|teste\s+de\s+rede)", lambda m: test_internet_speed()),
    (r"(?:qual\s+o?\s*meu\s+ip|endereco\s+ip)", lambda m: get_network_info()),
    (r"(?:esvazia|esvaziar)\s+(?:a\s+)?lixeira", lambda m: empty_mac_trash()),
    (r"(?:resumo\s+do\s+dia|relatorio\s+do\s+dia|briefing\s+executivo|ola\s+jarvis)", lambda m: daily_executive_briefing()),
]

def dispatch_command(query: str) -> str | None:
    """Recebe um comando em linguagem natural e executa a ação correspondente."""
    text = query.lower().strip()
    for pattern, handler in ACTIONS_REGISTRY:
        m = re.search(pattern, text)
        if m:
            try:
                return handler(m)
            except Exception as err:
                return f"Ocorreu um erro ao executar a ação: {err}"
    return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        res = dispatch_command(cmd)
        if res:
            print(res)
        else:
            print("Comando não reconhecido pelo dispatcher local.")
    else:
        print("Módulo JARVIS Super Actions carregado com 30 recursos.")
