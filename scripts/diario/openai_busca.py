"""Cliente mínimo da API Responses da OpenAI, com a ferramenta web_search."""
import json
import urllib.error
import urllib.parse
import urllib.request

from scripts.diario import gemini

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


def _normalizar_comparacao(url):
    """Forma usada só para comparar URLs: sem query/fragmento, sem "/" final, host sem www."""
    partes = urllib.parse.urlsplit(url)
    dominio = partes.netloc.lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]
    return f"{dominio}{partes.path.rstrip('/')}"


def _urls_consultadas(saida):
    urls = []
    for item in saida:
        if item.get("type") != "web_search_call":
            continue
        for fonte in (item.get("action") or {}).get("sources") or []:
            url = fonte.get("url") if fonte.get("type") == "url" else None
            if url:
                urls.append(url)
    return urls


def _urls_listadas_na_resposta(texto):
    try:
        dados = gemini.extrair_json(texto)
    except gemini.ErroGemini:
        return []
    fontes = dados.get("fontes")
    if not isinstance(fontes, list):
        return []
    return [f for f in fontes if isinstance(f, str)]


def _fontes_de(saida, texto):
    fontes, vistas = [], set()

    def adicionar(url):
        url_normalizada = _normalizar_url(url)
        chave = _normalizar_comparacao(url_normalizada)
        if chave in vistas:
            return
        vistas.add(chave)
        fontes.append({"dominio": _normalizar_dominio(url_normalizada), "url": url_normalizada})

    for item in saida:
        if item.get("type") != "message":
            continue
        for conteudo in item.get("content", []):
            for anotacao in conteudo.get("annotations", []):
                if anotacao.get("type") == "url_citation" and anotacao.get("url"):
                    adicionar(anotacao.get("url"))

    listadas = {_normalizar_comparacao(url) for url in _urls_listadas_na_resposta(texto)}
    if listadas:
        for url in _urls_consultadas(saida):
            if _normalizar_comparacao(url) in listadas:
                adicionar(url)

    return fontes


def buscar(prompt, chave, modelo, post=_post):
    corpo = {"model": modelo, "tools": [{"type": "web_search"}], "input": prompt,
             "include": ["web_search_call.action.sources"]}
    resposta = post(corpo, chave)
    saida = resposta.get("output") or []
    texto = "".join(conteudo.get("text", "") for item in saida if item.get("type") == "message"
                    for conteudo in item.get("content", []))
    if not texto:
        raise ErroOpenAI("resposta vazia da OpenAI")
    return texto, _fontes_de(saida, texto)
