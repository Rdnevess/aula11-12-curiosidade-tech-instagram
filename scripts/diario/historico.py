"""Histórico da curiosidade diária: um registro por dia de execução (AAAA-MM-DD)."""
import copy
import json
import re
import unicodedata
from pathlib import Path

from scripts.diario.config import HISTORICO

SEMENTE = {
    "manual-facemash": {"titulo": "Facemash", "status": "manual", "permalink": "https://www.instagram.com/reel/DfOlhhNiHPo/"},
    "manual-megadrive": {"titulo": "Lançamento do Mega Drive", "status": "manual", "permalink": "https://www.instagram.com/reel/DfOl3bsH5gq/"},
    "manual-pentium": {"titulo": "Bug FDIV do Pentium", "status": "manual", "permalink": "https://www.instagram.com/reel/DfOmIDxDSob/"},
}
RESOLVIDOS = {"publicado", "pendente"}


def carregar(caminho=HISTORICO):
    caminho = Path(caminho)
    if not caminho.exists():
        return copy.deepcopy(SEMENTE)
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar(dados, caminho=HISTORICO):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def registrar(dados, dia_iso, campos):
    dados.setdefault(dia_iso, {}).update(campos)
    return dados[dia_iso]


def ja_resolvido(dados, dia_iso):
    return dados.get(dia_iso, {}).get("status") in RESOLVIDOS


def temas(dados):
    return [r["titulo"] for r in dados.values() if r.get("titulo")]


def normalizar_titulo(titulo):
    sem_acento = unicodedata.normalize("NFD", titulo).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower()).split())


def repetido(dados, titulo):
    alvo = normalizar_titulo(titulo)
    return any(normalizar_titulo(t) == alvo for t in temas(dados))
