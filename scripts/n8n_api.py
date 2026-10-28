"""Cliente mínimo da API pública do n8n, com as chaves lidas do .env."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("N8N_URL", "http://localhost:5678")


class ErroApi(Exception):
    pass


def carregar_env(caminho=RAIZ / ".env"):
    valores = {}
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def api(metodo, caminho, corpo=None):
    env = carregar_env()
    dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{BASE_URL}/api/v1{caminho}",
        data=dados,
        method=metodo,
        headers={
            "X-N8N-API-KEY": env["N8N_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=60) as resposta:
            texto = resposta.read().decode("utf-8")
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace")[:500]
        raise ErroApi(f"{metodo} {caminho} -> {erro.code}: {detalhe}") from None
    return json.loads(texto) if texto else None
