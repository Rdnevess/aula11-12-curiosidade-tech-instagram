"""Constantes e chaves da curiosidade diária."""
from scripts.n8n_api import RAIZ, carregar_env

PASTA_DADOS = RAIZ / "diario"
HISTORICO = PASTA_DADOS / "historico.json"
OFFSET = PASTA_DADOS / "telegram-offset.txt"
PASTA_REELS = RAIZ / "reels"
SKILL = RAIZ / "reels-video" / "scripts"
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"
# Dois posts por dia (horário local, America/Cuiaba): slot -> hora da tarefa agendada.
HORARIOS = {1: "09:00", 2: "11:00"}
MODELO = "gemini-3.5-flash"
MODELO_RESERVA = "gemini-3.5-flash-lite"
MODELO_PESQUISA = "gpt-5.4-mini"
# Vídeo de até 50 s (pedido do usuário em 09/11/2026): fala + lead + cartão final (END_HOLD) cabem nele.
MAX_FALA = 46.5
MAX_VIDEO = 50.0
END_HOLD = 2.5
MAX_PALAVRAS = 115
MIN_PALAVRAS = 75
MIN_TRECHOS, MAX_TRECHOS = 5, 8
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
NOMES_CHAVES = ("GEMINI_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def chaves():
    env = carregar_env()
    return {nome: env.get(nome, "") for nome in NOMES_CHAVES}


def hora_curta(slot):
    """"09:00" -> "09h", para as mensagens do Telegram."""
    return f"{HORARIOS[slot][:2]}h"


def pasta_do_dia(dia, slot, ensaio=False):
    # Uma pasta por slot; o ensaio (--sem-publicar) usa pasta própria: nunca sobrescreve o vídeo real.
    return PASTA_REELS / f"diario-{dia.isoformat()}-{slot}{'-ensaio' if ensaio else ''}"


def selo(dia):
    return f"{dia.day:02d} {MESES[dia.month - 1]}"
