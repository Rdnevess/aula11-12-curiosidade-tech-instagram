"""Histórico da curiosidade diária: um registro por post, com a chave "AAAA-MM-DD#<slot>".

Chaves antigas continuam valendo: "AAAA-MM-DD" (de antes dos dois posts por dia, equivale ao slot 1)
e as da semente ("manual-*"), que só servem para não repetir temas.
"""
import copy
import json
import os
import re
import tempfile
import time
import unicodedata
from datetime import date
from pathlib import Path

from scripts.diario.config import HISTORICO

SEMENTE = {
    "manual-facemash": {"titulo": "Facemash", "status": "manual", "permalink": "https://www.instagram.com/reel/DfOlhhNiHPo/"},
    "manual-megadrive": {"titulo": "Lançamento do Mega Drive", "status": "manual", "permalink": "https://www.instagram.com/reel/DfOl3bsH5gq/"},
    "manual-pentium": {"titulo": "Bug FDIV do Pentium", "status": "manual", "permalink": "https://www.instagram.com/reel/DfOmIDxDSob/"},
}
# "publicando" e "erro_publicacao": o post pode já estar no ar; nunca repetir a publicação sozinho.
RESOLVIDOS = {"publicado", "pendente", "publicando", "erro_publicacao"}
CHAVE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:#(\d+))?$")


def chave(dia, slot):
    """Chave do post: "2026-11-04#1". dia pode ser date ou "AAAA-MM-DD"."""
    return f"{dia.isoformat() if isinstance(dia, date) else dia}#{slot}"


def separar(chave_post):
    """"2026-11-04#2" -> (date, 2); legado "2026-11-03" -> (date, None); qualquer outra -> (None, None)."""
    achado = CHAVE.match(chave_post or "")
    if not achado:
        return None, None
    try:
        dia = date.fromisoformat(achado.group(1))
    except ValueError:
        return None, None
    return dia, int(achado.group(2)) if achado.group(2) else None


def carregar(caminho=HISTORICO):
    caminho = Path(caminho)
    if not caminho.exists():
        return copy.deepcopy(SEMENTE)
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar(dados, caminho=HISTORICO):
    """Grava de forma atômica: escreve num temporário ao lado e troca com os.replace."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=caminho.name + ".", suffix=".tmp", dir=caminho.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(dados, ensure_ascii=False, indent=2) + "\n")
        for tentativa in range(5):
            try:
                os.replace(temporario, caminho)
                break
            except PermissionError:  # no Windows, outro processo pode estar lendo o arquivo neste instante
                if tentativa == 4:
                    raise
                time.sleep(0.2)
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)


def atualizar(chave_post, campos, caminho=HISTORICO):
    """Relê o arquivo, muda só o registro de chave_post e grava.

    rodar (demorado) e verificar (a cada 10 min) podem rodar ao mesmo tempo: gravar o dicionário
    inteiro carregado no início apagaria o que o outro comando gravou nesse meio-tempo.
    """
    dados = carregar(caminho)
    registro = registrar(dados, chave_post, campos)
    salvar(dados, caminho)
    return registro


def registrar(dados, chave_post, campos):
    dados.setdefault(chave_post, {}).update(campos)
    return dados[chave_post]


def ja_resolvido(dados, chave_post):
    if dados.get(chave_post, {}).get("status") in RESOLVIDOS:
        return True
    # O registro legado "AAAA-MM-DD" é o post da manhã daquele dia: bloqueia o slot 1.
    dia, slot = separar(chave_post)
    return slot == 1 and dados.get(dia.isoformat(), {}).get("status") in RESOLVIDOS


def temas(dados):
    return [r["titulo"] for r in dados.values() if r.get("titulo")]


def normalizar_titulo(titulo):
    sem_acento = unicodedata.normalize("NFD", titulo).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower()).split())


def repetido(dados, titulo):
    alvo = normalizar_titulo(titulo)
    return any(normalizar_titulo(t) == alvo for t in temas(dados))
