"""Verificação do túnel ngrok + webhook do Instagram (Aula 12, Task 5).

Quatro checagens (ver docs/superpowers/specs/2026-11-05-aula12-respostas-design.md,
seção 4, e o brief da Task 5):
  1. GET de verificação com o token certo -> 200 e o corpo é o `hub.challenge` enviado.
  2. GET de verificação com o token errado -> 403.
  3. GET de um caminho fora do webhook (ex.: /healthz) -> 404 (bloqueado pela política do ngrok).
  4. POST em /webhook/instagram sem assinatura -> 200 (o n8n responde na hora) e a execução
     termina sem nenhum item depois do nó "Conferir assinatura" (conferido pela API de
     execuções do n8n). Se o workflow "Aula 12 - Comentários e Direct" ainda não foi
     implantado, essa checagem fica "pendente" em vez de falhar.

Uso: python -m scripts.aula12.verificar_tunel
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path

from scripts import execucoes
from scripts.implantar import buscar_workflow
from scripts.n8n_api import carregar_env

RAIZ = Path(__file__).resolve().parent.parent.parent
EVENTO_COMENTARIO = (
    RAIZ / "Aula12-continuacao-insta" / "volume-12" / "eventos" / "comentario.json"
)
CAMINHO_WEBHOOK = "/webhook/instagram"
DESAFIO = "777"
NOME_WORKFLOW_ENTRADA = "Aula 12 - Comentários e Direct"
NO_ASSINATURA = "Conferir assinatura"


def _abrir_padrao(metodo, url, corpo=None):
    dados = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
    cabecalhos = {"Content-Type": "application/json"} if dados else {}
    requisicao = urllib.request.Request(url, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            return resposta.status, resposta.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read().decode("utf-8", "replace")


def _url_verificacao(dominio, verify_token):
    return (
        f"https://{dominio}{CAMINHO_WEBHOOK}?hub.mode=subscribe"
        f"&hub.verify_token={verify_token}&hub.challenge={DESAFIO}"
    )


def _verificacao_ok(dominio, verify_token, esperado_200, abrir):
    status, corpo = abrir("GET", _url_verificacao(dominio, verify_token))
    ok = (status == 200 and corpo == DESAFIO) if esperado_200 else (status == 403)
    return ok, f"status {status}"


def _caminho_fora_bloqueado(dominio, abrir):
    status, _ = abrir("GET", f"https://{dominio}/healthz")
    return status == 404, f"status {status}"


def _descartado_sem_assinatura(dominio, segredo, abrir):
    wf = buscar_workflow(NOME_WORKFLOW_ENTRADA)
    if wf is None:
        return False, "pendente (workflow não implantado)"

    antes = execucoes.ultimo_id(wf["id"])
    corpo = EVENTO_COMENTARIO.read_text(encoding="utf-8")
    status, _ = abrir("POST", f"https://{dominio}{CAMINHO_WEBHOOK}", corpo)
    if status != 200:
        return False, f"POST sem assinatura devolveu status {status} (esperado 200)"

    try:
        execucao = execucoes.esperar_execucao(wf["id"], antes, limite_s=60)
    except TimeoutError:
        return False, "nenhuma execução nova encontrada depois do POST"

    if execucoes.itens_saida(execucao, NO_ASSINATURA) != 0:
        detalhe = "a execução passou de 'Conferir assinatura' sem assinatura válida"
        return False, detalhe

    detalhe = "execução terminou sem item depois de 'Conferir assinatura'"
    if not segredo:
        detalhe += " (atenção: META_APP_SECRET não está definido no .env)"
    return True, detalhe


def checar(dominio, token, segredo, abrir=_abrir_padrao):
    resultados = []

    if not token:
        detalhe = "pendente (defina WEBHOOK_VERIFY_TOKEN no .env)"
        resultados.append(("verificação com token correto", False, detalhe))
        resultados.append(("verificação com token errado", False, detalhe))
    else:
        ok, detalhe = _verificacao_ok(dominio, token, True, abrir)
        resultados.append(("verificação com token correto", ok, detalhe))
        ok, detalhe = _verificacao_ok(dominio, f"{token}-errado", False, abrir)
        resultados.append(("verificação com token errado", ok, detalhe))

    ok, detalhe = _caminho_fora_bloqueado(dominio, abrir)
    resultados.append(("caminho fora do webhook é bloqueado", ok, detalhe))

    ok, detalhe = _descartado_sem_assinatura(dominio, segredo, abrir)
    resultados.append(("POST sem assinatura é descartado", ok, detalhe))

    return resultados


if __name__ == "__main__":
    env = carregar_env()
    dominio = env.get("NGROK_DOMINIO")
    if not dominio:
        sys.exit("defina NGROK_DOMINIO no .env")
    token = env.get("WEBHOOK_VERIFY_TOKEN", "")
    segredo = env.get("META_APP_SECRET", "")
    if not token:
        print("Aviso: WEBHOOK_VERIFY_TOKEN não está definido no .env.")
    if not segredo:
        print("Aviso: META_APP_SECRET não está definido no .env.")

    falhou = False
    for nome, ok, detalhe in checar(dominio, token, segredo):
        if ok:
            estado = "OK"
        elif detalhe.lower().startswith("pendente"):
            estado = "PENDENTE"
        else:
            estado = "FALHA"
            falhou = True
        print(f"[{estado}] {nome}: {detalhe}")
    sys.exit(1 if falhou else 0)
