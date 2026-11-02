"""Publica um arquivo pelo formulário do workflow e anota o resultado em posts/resultados.json (seção 4.9).

Uso: python -m scripts.publicar <arquivo .jpg|.jpeg|.mp4|.mov> "<legenda>"
ATENÇÃO: cada execução publica um post público na conta conectada ao app.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from scripts import wf_post
from scripts.execucoes import esperar_execucao, saida_json, ultimo_id
from scripts.implantar import buscar_workflow
from scripts.n8n_api import BASE_URL, RAIZ

URL_FORM = f"{BASE_URL}/form/post-instagram"
RESULTADOS = RAIZ / "posts" / "resultados.json"
TIPOS_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4", ".mov": "video/quicktime"}
LIMITE_S = 420  # 30 verificações de 10 s, mais upload e publicação


def nomes_campos(html):
    arquivo = None
    for tag in re.findall(r"<input\b[^>]*>", html):
        if re.search(r"type=['\"]file['\"]", tag):
            arquivo = re.search(r"name=['\"]([^'\"]+)['\"]", tag).group(1)
    texto = re.search(r"<textarea\b[^>]*\bname=['\"]([^'\"]+)['\"]", html)
    if not arquivo or not texto:
        raise ValueError("o formulário não tem os campos de arquivo e de legenda")
    return arquivo, texto.group(1)


def montar_multipart(textos, arquivo, limite):
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode("utf-8")
              for nome, valor in textos]
    campo, nome_arquivo, mime, conteudo = arquivo
    cabecalho = (f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"; filename="{nome_arquivo}"\r\n'
                 f"Content-Type: {mime}\r\n\r\n")
    partes.append(cabecalho.encode("utf-8") + conteudo + b"\r\n")
    return b"".join(partes) + f"--{limite}--\r\n".encode("utf-8")


def registrar(resultado, caminho=RESULTADOS):
    caminho = Path(caminho)
    lista = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else []
    lista.append(resultado)
    caminho.write_text(json.dumps(lista, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _url_status(form_waiting_url):
    partes = urllib.parse.urlsplit(form_waiting_url)
    return urllib.parse.urlunsplit((partes.scheme, partes.netloc, partes.path + "/n8n-execution-status",
                                    partes.query, partes.fragment))


def _enviar(caminho, legenda):
    with urllib.request.urlopen(URL_FORM, timeout=30) as resposta:
        campo_arquivo, campo_texto = nomes_campos(resposta.read().decode("utf-8"))
    limite = uuid.uuid4().hex
    corpo = montar_multipart([(campo_texto, legenda)],
                             (campo_arquivo, caminho.name, TIPOS_MIME[caminho.suffix.lower()], caminho.read_bytes()),
                             limite)
    requisicao = urllib.request.Request(URL_FORM, data=corpo, method="POST",
                                        headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    with urllib.request.urlopen(requisicao, timeout=120) as resposta:
        texto = resposta.read()
    try:
        espera = json.loads(texto).get("formWaitingUrl")
    except ValueError:
        espera = None
    if not espera:
        return
    # Com um nó Form Ending, o formulário vira multi-etapas: espera o status "form-waiting",
    # busca a página final e faz o POST vazio que libera o nó em espera (como na Aula 10).
    fim, situacao = time.time() + LIMITE_S, ""
    while time.time() < fim and situacao not in ("form-waiting", "success", "error"):
        time.sleep(2)
        with urllib.request.urlopen(_url_status(espera), timeout=30) as resposta:
            situacao = resposta.read().decode("utf-8").strip()
    if situacao == "form-waiting":
        urllib.request.urlopen(espera, timeout=30).close()
        urllib.request.urlopen(urllib.request.Request(espera, data=b"", method="POST"), timeout=30).close()


class ErroPublicacao(Exception):
    pass


def publicar_arquivo(caminho, legenda):
    caminho = Path(caminho)
    if caminho.suffix.lower() not in TIPOS_MIME or not caminho.is_file():
        raise ErroPublicacao(f"arquivo inválido: {caminho} (use .jpg, .jpeg, .mp4 ou .mov)")
    workflow_id = buscar_workflow(wf_post.NOME)["id"]
    antes = ultimo_id(workflow_id)
    _enviar(caminho, legenda)
    execucao = esperar_execucao(workflow_id, antes, limite_s=LIMITE_S)
    if execucao["status"] != "success":
        erro = execucao["data"]["resultData"].get("error", {})
        raise ErroPublicacao(f"execução {execucao['id']}: {execucao['status']} — {erro.get('message', 'sem mensagem')}"
                             f"{' | ' + erro['description'] if erro.get('description') else ''}")
    post = saida_json(execucao, "Link do post")
    resultado = {"arquivo": caminho.name, "tipo": saida_json(execucao, "Preparar mídia")["tipo"],
                 "permalink": post["permalink"], "execucao_id": execucao["id"],
                 "publicado_em": datetime.now().astimezone().isoformat(timespec="seconds")}
    registrar(resultado)
    return resultado


def main(argumentos):
    if len(argumentos) != 2:
        sys.exit(__doc__)
    try:
        resultado = publicar_arquivo(Path(argumentos[0]), argumentos[1])
    except ErroPublicacao as erro:
        sys.exit(str(erro))
    print(f"{resultado['tipo']} publicado: {resultado['permalink']} (execução {resultado['execucao_id']})")


if __name__ == "__main__":
    main(sys.argv[1:])
