"""Preenche no histórico diário o media_id de cada post (e fato/fontes/falas que faltem).

Chama o workflow "Aula 12 - Posts da conta" (webhook GET), casa cada `permalink`
do histórico com o das mídias da conta (sem query e sem barra final) e grava o
histórico de forma atômica. Os 3 posts manuais (Facemash, Mega Drive, Pentium)
ganham fato/fontes a partir de reels/ROTEIROS.md e falas de reels/<nome>/reel.json;
os publicados pelo fluxo diário sem fato/falas os recebem da pasta de trabalho
(pesquisa.json e roteiro.json).

Uso: python -m scripts.aula12.posts
"""
import copy
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from scripts.diario import historico as hist
from scripts.n8n_api import BASE_URL, RAIZ

REELS = RAIZ / "reels"
URL = f"{BASE_URL}/webhook/aula12-posts"
PUBLICADOS = {"publicado", "manual"}


def _chave_link(link):
    partes = urlsplit(link or "")
    return f"{partes.netloc.lower()}{partes.path.rstrip('/')}"


def _dominio(url):
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _ler_json(caminho):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def roteiros(reels=REELS):
    """{nome: {"fato": ..., "fontes": [...]}} a partir de ROTEIROS.md."""
    texto = (Path(reels) / "ROTEIROS.md").read_text(encoding="utf-8")
    resultado = {}
    secao = None
    for linha in texto.splitlines():
        cabecalho = re.match(r"^###\s+(\S+)", linha)
        if cabecalho:
            secao = cabecalho.group(1)
            resultado[secao] = {"falas_md": [], "fontes": []}
            continue
        if linha.startswith("## "):
            secao = None
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if secao and len(celulas) >= 2 and re.fullmatch(r"s\d+", celulas[0]):
            resultado[secao]["falas_md"].append(celulas[1].replace("**", ""))
    # "## Fontes da pesquisa": "- Rótulo: url · url" com continuação indentada
    atual = None
    blocos = {}
    em_fontes = False
    for linha in texto.splitlines():
        if linha.startswith("## "):
            em_fontes = "fontes" in linha.lower()
            continue
        if not em_fontes:
            continue
        if linha.startswith("- "):
            rotulo = linha[2:].split(":", 1)[0]
            atual = re.sub(r"\s+", "", rotulo.lower())
            blocos[atual] = linha.split(":", 1)[1] if ":" in linha else ""
        elif atual and linha.startswith(" "):
            blocos[atual] += " " + linha
    for nome, dados in resultado.items():
        for rotulo, texto_bloco in blocos.items():
            if rotulo.startswith(nome) or nome in rotulo:
                urls = re.findall(r"https?://[^\s·]+", texto_bloco)
                dados["fontes"] = [{"dominio": _dominio(u), "url": u} for u in urls]
        # a última fala é o convite para seguir a conta, não faz parte do fato
        falas = [f for f in dados.pop("falas_md") if "@curiosidadetechhoje" not in f]
        dados["fato"] = " ".join(falas)
    return resultado


def _pasta(registro):
    if registro.get("pasta"):
        return Path(registro["pasta"])
    if registro.get("video"):
        video = Path(registro["video"])
        return (video if video.is_absolute() else RAIZ / video).parent.parent
    return None


def backfill(historico, midias, reels=REELS):
    """Cópia do histórico com media_id (e fato/fontes/falas) preenchidos onde possível."""
    por_link = {_chave_link(m.get("permalink")): m["id"] for m in midias if m.get("permalink")}
    novo = copy.deepcopy(historico)
    manuais = None
    for chave_post, registro in novo.items():
        if registro.get("status") not in PUBLICADOS:
            continue
        media_id = por_link.get(_chave_link(registro.get("permalink")))
        if media_id:
            registro["media_id"] = media_id
        if chave_post.startswith("manual-"):
            nome = chave_post[len("manual-"):]
            manuais = manuais if manuais is not None else roteiros(reels)
            dados = manuais.get(nome) or {}
            if dados.get("fato"):
                registro["fato"] = dados["fato"]
            if dados.get("fontes"):
                registro["fontes"] = dados["fontes"]
            reel = _ler_json(Path(reels) / nome / "reel.json") or {}
            if reel.get("lines"):
                registro["falas"] = list(reel["lines"])
            continue
        pasta = _pasta(registro)
        if pasta is None:
            continue
        if not registro.get("fato"):
            pesquisa = _ler_json(pasta / "pesquisa.json") or {}
            if pesquisa.get("fato"):
                registro["fato"] = pesquisa["fato"]
            if not registro.get("fontes") and pesquisa.get("fontes"):
                registro["fontes"] = pesquisa["fontes"]
        if not registro.get("falas"):
            roteiro = _ler_json(pasta / "roteiro.json") or {}
            falas = [t.get("fala", "") for t in roteiro.get("trechos", []) if isinstance(t, dict)]
            if falas:
                registro["falas"] = falas
    return novo


def midias_da_resposta(resposta):
    """O webhook devolve o JSON do nó "Posts da conta" ({data: [...]}), às vezes dentro de uma lista."""
    if isinstance(resposta, list):
        resposta = resposta[0] if resposta else {}
    return list((resposta or {}).get("data") or [])


def buscar_midias(url=URL):
    with urllib.request.urlopen(url, timeout=60) as resposta:
        return midias_da_resposta(json.loads(resposta.read().decode("utf-8")))


def main():
    midias = buscar_midias()
    atual = hist.carregar()
    novo = backfill(atual, midias)
    hist.salvar(novo)
    publicados = [k for k, r in novo.items() if r.get("status") in PUBLICADOS]
    com_id = [k for k in publicados if novo[k].get("media_id")]
    print(f"mídias na conta: {len(midias)}; posts no histórico: {len(publicados)}; com media_id: {len(com_id)}")
    for k in publicados:
        r = novo[k]
        print(f"  {k}: media_id={r.get('media_id') or '-'} fato={'sim' if r.get('fato') else 'não'} "
              f"fontes={len(r.get('fontes') or [])} falas={len(r.get('falas') or [])}")


if __name__ == "__main__":
    main()
