"""Fotos de referência do Reel: busca no Wikimedia Commons, só com licença livre e com o crédito do autor."""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.diario.historico import normalizar_titulo

API = "https://commons.wikimedia.org/w/api.php"
# O Wikimedia recusa pedidos sem User-Agent identificado.
AGENTE = "curiosidadetechhoje/1.0 (bot do Reel diario; https://www.instagram.com/curiosidadetechhoje/)"
LIMITE = 6
LICENCA_LIVRE = re.compile(r"^(public domain|pd\b|cc0|cc by(-sa)? \d)", re.IGNORECASE)
MIMES = {"image/jpeg": "jpg", "image/png": "png"}
# Títulos que costumam ser placas, logos e mapas, não o assunto.
EVITAR = re.compile(r"\b(marker|plaque|logo|map|mapa|signature|assinatura|grave|tumulo|diagram)\b")
MIN_LARGURA, MIN_ALTURA = 800, 600


def termo(roteiro):
    """Termo de busca que o roteiro sugeriu (busca_imagem); None se não houver: sem fotos, nada de chute."""
    valor = roteiro.get("busca_imagem")
    return valor.strip() if isinstance(valor, str) and valor.strip() else None


def _baixar(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        dados = resposta.read()
    return json.loads(dados) if "api.php" in url else dados


def _texto(html):
    html = re.sub(r'<span style="display: ?none;?">.*?</span>', "", html or "", flags=re.DOTALL)
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def autor(artista_html, quem_enviou=None):
    """Nome para o crédito: o campo Artist limpo, com dois casos comuns do Commons resolvidos."""
    texto = _texto(artista_html)
    original = re.match(r"the original uploader was (.+?) at ", texto, re.IGNORECASE)
    if original:
        return original.group(1)
    if re.fullmatch(r"own (work|picture|photo)\.?", texto, re.IGNORECASE):
        texto = quem_enviou or ""
    return texto[:60] or "autor desconhecido"


def filtrar(resposta, busca):
    """Fotos da resposta da API, na ordem da busca: JPEG/PNG grandes, licença livre e com o termo no nome."""
    palavras = normalizar_titulo(busca).split()
    paginas = sorted(((resposta.get("query") or {}).get("pages") or {}).values(), key=lambda p: p.get("index", 0))
    fotos = []
    for pagina in paginas:
        info = (pagina.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licenca = _texto((meta.get("LicenseShortName") or {}).get("value"))
        nome = normalizar_titulo(pagina.get("title", "").removeprefix("File:"))
        if (info.get("mime") not in MIMES or not LICENCA_LIVRE.match(licenca) or EVITAR.search(nome)
                or info.get("width", 0) < MIN_LARGURA or info.get("height", 0) < MIN_ALTURA
                or not all(p in nome.split() for p in palavras) or not info.get("thumburl")):
            continue
        nome_autor = autor((meta.get("Artist") or {}).get("value"), info.get("user"))
        fotos.append({"url": info["thumburl"], "ext": MIMES[info["mime"]], "credito": f"{nome_autor} · {licenca}"})
    return fotos


def preparar(pasta, roteiro, baixar=_baixar, limite=LIMITE):
    """Baixa até `limite` fotos para pasta/img e devolve [{arquivo (relativo à pasta), credito}].

    Melhor esforço: sem termo, sem resultado ou sem rede, o Reel sai sem fotos (como antes).
    """
    busca = termo(roteiro)
    if not busca:
        return []
    consulta = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f"{busca} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size|user",
        "iiurlwidth": 1080})
    try:
        candidatas = filtrar(baixar(f"{API}?{consulta}"), busca)
    except Exception:
        return []
    destino = Path(pasta) / "img"
    destino.mkdir(parents=True, exist_ok=True)
    fotos = []
    for foto in candidatas:
        if len(fotos) >= limite:
            break
        arquivo = f"img/foto{len(fotos) + 1}.{foto['ext']}"
        try:
            (Path(pasta) / arquivo).write_bytes(baixar(foto["url"]))
        except Exception:
            continue
        fotos.append({"arquivo": arquivo, "credito": foto["credito"]})
    return fotos


def creditos_legenda(fotos):
    creditos = list(dict.fromkeys(f["credito"] for f in fotos))
    return f"\n\nImagens: Wikimedia Commons — {'; '.join(creditos)}" if creditos else ""
