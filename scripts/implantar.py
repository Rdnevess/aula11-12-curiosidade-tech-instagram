"""Cria ou atualiza o workflow da aula no n8n e o publica (deixa /form/post-instagram no ar).

Uso: python -m scripts.implantar
"""
from scripts import wf_post
from scripts.configurar_n8n import obter_id_credencial
from scripts.n8n_api import api


def buscar_workflow(nome):
    for wf in api("GET", "/workflows?limit=250")["data"]:
        if wf["name"] == nome and not wf.get("isArchived"):
            return wf
    return None


def implantar(definicao):
    existente = buscar_workflow(definicao["name"])
    if existente:
        wf = api("PUT", f"/workflows/{existente['id']}", definicao)
    else:
        wf = api("POST", "/workflows", definicao)
    api("POST", f"/workflows/{wf['id']}/publish", {"versionId": wf["versionId"]})
    return wf["id"]


if __name__ == "__main__":
    definicao = wf_post.construir(obter_id_credencial())
    print(f"{definicao['name']}: {implantar(definicao)} publicado")
