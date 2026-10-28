"""Encontra no n8n a credencial Instagram TEP (seção 3.5). O token é cadastrado pela interface, nunca por script."""
from scripts.n8n_api import ErroApi, api
from scripts.wf_post import CREDENCIAL

TIPO = "httpQueryAuth"


def obter_id_credencial():
    for credencial in api("GET", "/credentials?limit=250")["data"]:
        if credencial["name"] == CREDENCIAL and credencial["type"] == TIPO:
            return credencial["id"]
    raise ErroApi(f"Credencial '{CREDENCIAL}' (Query Auth) não encontrada no n8n. "
                  "Cadastre-a pela interface, com Name access_token e o token como Value (apostila, seção 3.5).")


if __name__ == "__main__":
    print(f"{CREDENCIAL}: {obter_id_credencial()}")
