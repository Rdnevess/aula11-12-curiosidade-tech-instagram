"""Exporta os 3 workflows principais da Aula 12 para workflows/aula12-*.json.

O token de verificação do webhook vira <WEBHOOK_VERIFY_TOKEN>; a exportação
falha se algum valor de segredo do .env (aula11 ou .env.n8n) aparecer no JSON.

Uso: python -m scripts.aula12.exportar
"""
import json
import re

from scripts.aula12 import wf_direct, wf_entrada, wf_verificacao
from scripts.aula12.infra import ENV_N8N
from scripts.exportar import normalizar, sem_segredos
from scripts.implantar import buscar_workflow
from scripts.n8n_api import RAIZ, api, carregar_env

ARQUIVOS = {
    wf_verificacao.NOME: RAIZ / "workflows" / "aula12-verificacao-webhook.json",
    wf_entrada.NOME: RAIZ / "workflows" / "aula12-comentarios-direct.json",
    wf_direct.NOME: RAIZ / "workflows" / "aula12-direct-agente.json",
}
MARCA = "<WEBHOOK_VERIFY_TOKEN>"
CHAVES_SEGREDO = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)


def segredos(env):
    """Valores (não vazios) das chaves do .env que são segredos."""
    return [v for k, v in env.items() if CHAVES_SEGREDO.search(k) and v]


def preparar(wf, token, lista_segredos):
    """Texto do JSON exportado, com o token trocado pela marca; erro se sobrar segredo."""
    texto = json.dumps(normalizar(wf), ensure_ascii=False, indent=2) + "\n"
    if token:
        texto = texto.replace(token, MARCA)
    if any(s in texto for s in lista_segredos) or not sem_segredos(json.loads(texto)):
        raise SystemExit(f"possível segredo no JSON de '{wf.get('name')}'; exportação interrompida")
    return texto


def main():
    env = carregar_env()
    lista = segredos(env) + (segredos(carregar_env(ENV_N8N)) if ENV_N8N.exists() else [])
    token = env.get("WEBHOOK_VERIFY_TOKEN", "")
    for nome, arquivo in ARQUIVOS.items():
        existente = buscar_workflow(nome)
        if not existente:
            raise SystemExit(f"workflow '{nome}' não encontrado no n8n; rode scripts.aula12.implantar")
        texto = preparar(api("GET", f"/workflows/{existente['id']}"), token, lista)
        arquivo.write_text(texto, encoding="utf-8")
        print(f"{nome} -> {arquivo.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
