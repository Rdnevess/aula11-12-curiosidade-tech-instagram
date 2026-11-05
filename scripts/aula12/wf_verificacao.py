"""Workflow "Aula 12 - Verificação do webhook" (apostila, seção 3.1).

A Meta faz um GET com hub.mode, hub.verify_token e hub.challenge; se o token
confere, devolvemos o challenge em texto; senão, 403.
"""
import uuid

from scripts.wf_util import ligar, no

NOME = "Aula 12 - Verificação do webhook"
WEBHOOK_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "aula12/verificacao/instagram"))
RESPONDER = "n8n-nodes-base.respondToWebhook"


def _igual(id_, esquerda, direita):
    return {"id": id_, "leftValue": esquerda, "rightValue": direita,
            "operator": {"type": "string", "operation": "equals"}}


def construir(token):
    nos = [
        no("Desafio da Meta", "n8n-nodes-base.webhook", 2, (0, 0), {
            "httpMethod": "GET", "path": "instagram", "responseMode": "responseNode", "options": {},
        }, webhook_id=WEBHOOK_ID),
        no("Token confere?", "n8n-nodes-base.if", 2.2, (220, 0), {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [
                    _igual("modo", "={{ $json.query['hub.mode'] }}", "subscribe"),
                    _igual("token", "={{ $json.query['hub.verify_token'] }}", token),
                ],
                "combinator": "and",
            },
            "options": {},
        }),
        no("Devolver o desafio", RESPONDER, 1.1, (440, -100), {
            "respondWith": "text", "responseBody": "={{ $json.query['hub.challenge'] }}", "options": {},
        }),
        no("Recusar", RESPONDER, 1.1, (440, 100), {
            "respondWith": "text", "responseBody": "Token de verificação inválido",
            "options": {"responseCode": 403},
        }),
    ]
    conexoes = {}
    ligar(conexoes, "Desafio da Meta", "Token confere?")
    ligar(conexoes, "Token confere?", "Devolver o desafio", saida=0)
    ligar(conexoes, "Token confere?", "Recusar", saida=1)
    return {"name": NOME, "nodes": nos, "connections": conexoes, "settings": {"executionOrder": "v1"}}
