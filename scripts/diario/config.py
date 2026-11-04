"""Constantes e chaves da curiosidade diária."""
from scripts.n8n_api import RAIZ, carregar_env

PASTA_DADOS = RAIZ / "diario"
HISTORICO = PASTA_DADOS / "historico.json"
OFFSET = PASTA_DADOS / "telegram-offset.txt"
PASTA_REELS = RAIZ / "reels"
SKILL = RAIZ / "reels-video" / "scripts"
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"
HORARIO = "09:00"
MODELO = "gemini-3.5-flash"
MODELO_PESQUISA = "gpt-5.4-mini"
MAX_FALA = 26.5
MAX_VIDEO = 30.0
END_HOLD = 2.5
MAX_PALAVRAS = 70
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
NOMES_CHAVES = ("GEMINI_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def chaves():
    env = carregar_env()
    return {nome: env.get(nome, "") for nome in NOMES_CHAVES}


def pasta_do_dia(dia, ensaio=False):
    # O ensaio (--sem-publicar) usa pasta própria: nunca sobrescreve o vídeo real do dia.
    return PASTA_REELS / f"diario-{dia.isoformat()}{'-ensaio' if ensaio else ''}"


def selo(dia):
    return f"{dia.day:02d} {MESES[dia.month - 1]}"
