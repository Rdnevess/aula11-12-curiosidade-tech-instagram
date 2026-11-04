"""Cliente mínimo da API Responses da OpenAI, com a ferramenta web_search."""
import json
import urllib.error
import urllib.parse
import urllib.request

URL = "https://api.openai.com/v1/responses"


class ErroOpenAI(Exception):
    pass


def _post(corpo, chave, timeout=180):
    requisicao = urllib.request.Request(URL, data=json.dumps(corpo).encode("utf-8"), method="POST",
                                        headers={"Content-Type": "application/json", "Authorization": f"Bearer {chave}"})
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        raise ErroOpenAI(f"OpenAI {erro.code}: {erro.read().decode('utf-8', 'replace')[:300]}") from None
    except urllib.error.URLError as erro:
        raise ErroOpenAI(f"OpenAI: falha de rede ({type(erro.reason).__name__})") from None


def _normalizar_url(url):
    partes = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((partes.scheme, partes.netloc, partes.path, "", partes.fragment))


def _normalizar_dominio(url):
    dominio = urllib.parse.urlsplit(url).netloc.lower()
    return dominio[4:] if dominio.startswith("www.") else dominio


def _fontes_de(saida):
    fontes, vistas = [], set()
    for item in saida:
        if item.get("type") != "message":
            continue
        for conteudo in item.get("content", []):
            for anotacao in conteudo.get("annotations", []):
                url = anotacao.get("url") if anotacao.get("type") == "url_citation" else None
                if not url:
                    continue
                url_normalizada = _normalizar_url(url)
                if url_normalizada in vistas:
                    continue
                vistas.add(url_normalizada)
                fontes.append({"dominio": _normalizar_dominio(url_normalizada), "url": url_normalizada})
    return fontes


def buscar(prompt, chave, modelo, post=_post):
    corpo = {"model": modelo, "tools": [{"type": "web_search"}], "input": prompt}
    resposta = post(corpo, chave)
    saida = resposta.get("output") or []
    texto = "".join(conteudo.get("text", "") for item in saida if item.get("type") == "message"
                    for conteudo in item.get("content", []))
    if not texto:
        raise ErroOpenAI("resposta vazia da OpenAI")
    return texto, _fontes_de(saida)
