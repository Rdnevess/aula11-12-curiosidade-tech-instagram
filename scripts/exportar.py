"""Exporta o workflow para workflows/, gera posts.md e o .zip de entrega (Prática, passo 4).

Só o pacote, sem exportar de novo: python -c "from scripts.exportar import gerar_zip; gerar_zip()"
"""
import json
import re
import zipfile

from scripts import wf_post
from scripts.implantar import buscar_workflow
from scripts.n8n_api import RAIZ, api
from scripts.publicar import RESULTADOS

CAMPOS = ("name", "nodes", "connections", "settings", "pinData", "meta")
ARQUIVO = RAIZ / "workflows" / "post-instagram.json"
POSTS_MD = RAIZ / "posts.md"
ZIP = RAIZ / "entrega-aula11.zip"


def normalizar(wf):
    return {campo: (wf.get(campo) or {}) if campo in ("pinData", "meta") else wf.get(campo) for campo in CAMPOS}


def sem_segredos(wf):
    texto = json.dumps(wf)
    return not re.search(r'"(apiKey|password|accessToken|access_token|token)"\s*:|IG[A-Za-z0-9_-]{100,}', texto)


def gerar_posts_md(resultados):
    linhas = ["# Posts publicados pelo workflow (Aula 11)", "",
              "| # | Arquivo | Tipo | Link | Publicado em | Execução |", "| --- | --- | --- | --- | --- | --- |"]
    for i, r in enumerate(resultados, 1):
        tipo = "Reel" if r["tipo"] == "video" else "imagem"
        quando = r["publicado_em"][:16].replace("T", " ")
        linhas.append(f"| {i} | {r['arquivo']} | {tipo} | {r['permalink']} | {quando} | {r['execucao_id']} |")
    return "\n".join(linhas) + "\n"


def gerar_zip():
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as pacote:
        pacote.write(ARQUIVO, "workflows/post-instagram.json")
        pacote.write(POSTS_MD, "posts.md")
        pacote.write(RAIZ / "LINK-GIT.txt", "LINK-GIT.txt")
    print(f"pacote: {ZIP.name}")


def main():
    wf = normalizar(api("GET", f"/workflows/{buscar_workflow(wf_post.NOME)['id']}"))
    if not sem_segredos(wf):
        raise SystemExit("possível segredo no JSON; exportação interrompida")
    texto = json.dumps(wf, ensure_ascii=False, indent=2) + "\n"
    referencias = texto.count(f'"name": "{wf_post.CREDENCIAL}"')
    if referencias != 5:
        raise SystemExit(f"esperadas 5 referências à credencial, achei {referencias}")
    ARQUIVO.write_text(texto, encoding="utf-8")
    print(f"{wf_post.NOME} -> {ARQUIVO.relative_to(RAIZ)} ({referencias} referências à credencial)")
    POSTS_MD.write_text(gerar_posts_md(json.loads(RESULTADOS.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"posts -> {POSTS_MD.name}")
    gerar_zip()


if __name__ == "__main__":
    main()
