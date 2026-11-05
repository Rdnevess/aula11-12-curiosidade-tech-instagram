"""Implanta os workflows da Aula 12 no n8n (cria/atualiza e publica).

Ordem: Posts -> Direct (sub-workflow) -> Verificação -> Entrada (que chama o Direct).
Credenciais: reaproveita "Instagram TEP" e "Groq"; cria "Redis" e "Telegram Aviso"
pela API pública se faltarem. Gera o token de verificação do webhook no .env se
não existir (nunca é impresso).

Uso: python -m scripts.aula12.implantar
"""
import secrets

from scripts.aula12 import wf_direct, wf_entrada, wf_posts, wf_verificacao
from scripts.implantar import implantar
from scripts.n8n_api import RAIZ, api, carregar_env

EXISTENTES = {"instagram": ("Instagram TEP", "httpQueryAuth"), "groq": ("Groq", "groqApi")}


def _novas(env):
    return {
        "redis": ("Redis", "redis", {"host": "redis", "port": 6379, "database": 0}),
        "telegram": ("Telegram Aviso", "telegramApi", {"accessToken": env["TELEGRAM_BOT_TOKEN"]}),
    }


def credenciais(api, env=None):
    """Ids das 4 credenciais usadas pelos workflows: {instagram, groq, redis, telegram}."""
    lista = api("GET", "/credentials?limit=250")["data"]

    def achar(nome, tipo):
        return next((c["id"] for c in lista if c["name"] == nome and c["type"] == tipo), None)

    ids = {}
    for chave, (nome, tipo) in EXISTENTES.items():
        ids[chave] = achar(nome, tipo)
        if not ids[chave]:
            raise SystemExit(f"Credencial '{nome}' ({tipo}) não encontrada no n8n; cadastre-a pela interface.")
    for chave, (nome, tipo, dados) in _novas(env if env is not None else carregar_env()).items():
        ids[chave] = achar(nome, tipo)
        if not ids[chave]:
            ids[chave] = api("POST", "/credentials", {"name": nome, "type": tipo, "data": dados})["id"]
            print(f"credencial criada: {nome} ({tipo})")
    return ids


def garantir_token(caminho=RAIZ / ".env"):
    """Token de verificação do webhook (24 hex). Gera e grava no .env se faltar."""
    token = carregar_env(caminho).get("WEBHOOK_VERIFY_TOKEN")
    if token:
        return token
    token = secrets.token_hex(12)
    texto = caminho.read_text(encoding="utf-8")
    if texto and not texto.endswith("\n"):
        texto += "\n"
    caminho.write_text(texto + f"WEBHOOK_VERIFY_TOKEN={token}\n", encoding="utf-8")
    print("WEBHOOK_VERIFY_TOKEN gerado e gravado no .env")
    return token


def main():
    ids = credenciais(api)
    token = garantir_token()
    id_direct = None
    for construir in (lambda: wf_posts.construir(ids["instagram"]),
                      lambda: wf_direct.construir(ids),
                      lambda: wf_verificacao.construir(token),
                      lambda: wf_entrada.construir(ids, id_direct)):
        definicao = construir()
        wf_id = implantar(definicao)
        if definicao["name"] == wf_direct.NOME:
            id_direct = wf_id
        print(f"{definicao['name']}: {wf_id} publicado")


if __name__ == "__main__":
    main()
