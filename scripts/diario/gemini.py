"""Cliente mínimo do Gemini (generateContent), com busca do Google opcional."""
import json
import urllib.error
import urllib.parse
import urllib.request

URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


class ErroGemini(Exception):
    pass


def _post(url, corpo, chave, timeout=120):
    requisicao = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), method="POST",
                                        headers={"Content-Type": "application/json", "x-goog-api-key": chave})
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        raise ErroGemini(f"Gemini {erro.code}: {erro.read().decode('utf-8', 'replace')[:300]}") from None


def gerar(prompt, chave, modelo, busca=False, json_mode=False, post=_post):
    corpo = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if busca:
        corpo["tools"] = [{"google_search": {}}]
    if json_mode:
        corpo["generationConfig"] = {"responseMimeType": "application/json"}
    resposta = post(URL.format(modelo=modelo), corpo, chave)
    candidato = (resposta.get("candidates") or [{}])[0]
    texto = "".join(p.get("text", "") for p in candidato.get("content", {}).get("parts", []))
    if not texto:
        raise ErroGemini(f"resposta vazia do Gemini ({candidato.get('finishReason', 'sem motivo')})")
    return texto, candidato.get("groundingMetadata", {})


def extrair_json(texto):
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim < inicio:
        raise ErroGemini("a resposta não contém JSON")
    try:
        return json.loads(texto[inicio:fim + 1])
    except ValueError as erro:
        raise ErroGemini(f"JSON inválido na resposta: {erro}") from None


def normalizar_dominio(texto):
    texto = texto.strip().lower()
    if "//" in texto:
        texto = urllib.parse.urlsplit(texto).netloc
    texto = texto.split("/")[0]
    return texto[4:] if texto.startswith("www.") else texto


def fontes_de(metadados):
    fontes, vistas = [], set()
    for pedaco in metadados.get("groundingChunks", []):
        web = pedaco.get("web") or {}
        url, dominio = web.get("uri"), normalizar_dominio(web.get("title", ""))
        if url and dominio and url not in vistas:
            vistas.add(url)
            fontes.append({"dominio": dominio, "url": url})
    return fontes


def dominios(fontes):
    return {f["dominio"] for f in fontes}
