"""Workflow "Aula 12 - Comentários e Direct" (apostila, seções 4 a 6.4, com melhorias).

Webhook POST com corpo bruto -> assinatura conferida -> um item por evento ->
Switch: comentário (histórico + palavra-chave + antispam no Redis + réplica)
ou mensagem (sub-workflow "Aula 12 - Direct com agente").

Ramo de comentário: o nó Histórico (Read File) roda uma vez por comentário e
devolve um item só com o arquivo (binário "data"), pareado (pairedItem) com o
item de entrada. O Code "Responder?" junta as duas coisas: o evento vem de
$('Tipo de evento').itemMatching(i) (o item do Switch que gerou a leitura) e o
histórico, do binário do próprio item i.
"""
import uuid

from scripts.aula12.js_util import carregar
from scripts.aula12.wf_direct import ler_historico
from scripts.wf_post import GRAPH, _graph
from scripts.wf_util import ligar, no

NOME = "Aula 12 - Comentários e Direct"
WEBHOOK_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "aula12/entrada/instagram"))
COMENTARIO = ["Histórico", "Responder?", "Já respondido?", "Primeira vez?", "Responder comentário",
              "Marcar respondido"]
TTL_ANTISPAM = 2592000  # 30 dias

CODIGO_ASSINATURA = carregar("assinatura") + """
// ---- Nó "Conferir assinatura" ----
// O Webhook entrega o corpo bruto no binário "data" (opção Raw Body). Sem
// assinatura válida, o item é descartado e o workflow termina aqui.
const saida = [];
const itens = $input.all();
for (let i = 0; i < itens.length; i++) {
  const buf = await this.helpers.getBinaryDataBuffer(i, 'data');
  const cabecalho = (itens[i].json.headers || {})['x-hub-signature-256'];
  if (!assinaturaValida(buf, cabecalho, $env.META_APP_SECRET)) continue;
  saida.push({ json: { corpo: JSON.parse(buf.toString('utf8')) }, pairedItem: i });
}
return saida;
"""

CODIGO_EVENTOS = carregar("eventos") + """
// ---- Nó "Separar eventos" ----
return $input.all().flatMap((item) =>
  separarEventos(item.json.corpo, $env.INSTAGRAM_CONTA_ID).map((evento) => ({ json: evento })));
"""

CODIGO_RESPONDER = carregar("comentario") + """
// ---- Nó "Responder?" ----
// Item i: binário "data" = historico.json (nó Histórico); o evento é o item do
// Switch pareado com ele. Sem resposta (null), o comentário termina aqui.
const saida = [];
const itens = $input.all();
for (let i = 0; i < itens.length; i++) {
  const evento = $('Tipo de evento').itemMatching(i).json;
  const buf = await this.helpers.getBinaryDataBuffer(i, 'data');
  const historico = JSON.parse(buf.toString('utf8'));
  const r = respostaComentario(evento, historico, $env.INSTAGRAM_CONTA_ID);
  if (!r) continue;
  saida.push({ json: { comentario_id: evento.comentario_id, ...r }, pairedItem: i });
}
return saida;
"""


def _regra(chave):
    return {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict",
                                       "version": 2},
                           "conditions": [{"id": chave, "leftValue": "={{ $json.tipo }}", "rightValue": chave,
                                           "operator": {"type": "string", "operation": "equals"}}],
                           "combinator": "and"},
            "renameOutput": True, "outputKey": chave}


def construir(ids, id_direct):
    redis = {"redis": {"id": ids["redis"], "name": "Redis"}}
    x = lambda i, y=0: (i * 220, y)
    nos = [
        no("Evento do Instagram", "n8n-nodes-base.webhook", 2, x(0), {
            "httpMethod": "POST", "path": "instagram", "responseMode": "onReceived",
            "options": {"rawBody": True},
        }, webhook_id=WEBHOOK_ID),
        no("Conferir assinatura", "n8n-nodes-base.code", 2, x(1), {"jsCode": CODIGO_ASSINATURA}),
        no("Separar eventos", "n8n-nodes-base.code", 2, x(2), {"jsCode": CODIGO_EVENTOS}),
        no("Tipo de evento", "n8n-nodes-base.switch", 3.2, x(3), {
            "rules": {"values": [_regra("comentario"), _regra("mensagem")]}, "options": {},
        }),
        ler_historico("Histórico", x(4, -100)),
        no("Responder?", "n8n-nodes-base.code", 2, x(5, -100), {"jsCode": CODIGO_RESPONDER}),
        no("Já respondido?", "n8n-nodes-base.redis", 1, x(6, -100), {
            "operation": "get", "propertyName": "ja", "key": "={{ $json.chave }}", "keyType": "automatic",
            "options": {},
        }, credenciais=redis),
        no("Primeira vez?", "n8n-nodes-base.if", 2.2, x(7, -100), {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{"id": "ja", "leftValue": "={{ $json.ja }}", "rightValue": "",
                                "operator": {"type": "string", "operation": "empty", "singleValue": True}}],
                "combinator": "and",
            },
            "options": {},
        }),
        _graph("Responder comentário", x(8, -100), "POST",
               "=" + GRAPH + "/{{ $('Responder?').item.json.comentario_id }}/replies", ids["instagram"],
               campos=[("message", "={{ $('Responder?').item.json.resposta }}")]),
        no("Marcar respondido", "n8n-nodes-base.redis", 1, x(9, -100), {
            "operation": "set", "key": "={{ $('Responder?').item.json.chave }}", "value": "1",
            "keyType": "string", "expire": True, "ttl": TTL_ANTISPAM,
        }, credenciais=redis),
        no("Direct com agente", "n8n-nodes-base.executeWorkflow", 1.2, x(4, 100), {
            "source": "database",
            "workflowId": {"__rl": True, "mode": "id", "value": id_direct},
            "workflowInputs": {
                "mappingMode": "defineBelow",
                "value": {"remetente": "={{ $json.remetente }}", "texto": "={{ $json.texto }}"},
                "matchingColumns": [],
                "schema": [{"id": c, "displayName": c, "required": False, "defaultMatch": False, "display": True,
                            "canBeUsedToMatch": True, "type": "string"} for c in ("remetente", "texto")],
                "attemptToConvertTypes": False,
                "convertFieldsToString": True,
            },
            "mode": "once",
            "options": {"waitForSubWorkflow": True},
        }),
    ]
    conexoes = {}
    ligar(conexoes, "Evento do Instagram", "Conferir assinatura")
    ligar(conexoes, "Conferir assinatura", "Separar eventos")
    ligar(conexoes, "Separar eventos", "Tipo de evento")
    ligar(conexoes, "Tipo de evento", "Histórico", saida=0)
    ligar(conexoes, "Tipo de evento", "Direct com agente", saida=1)
    for a, b in zip(COMENTARIO, COMENTARIO[1:]):
        ligar(conexoes, a, b)  # em "Primeira vez?" isso liga só a saída 0 (true)
    return {"name": NOME, "nodes": nos, "connections": conexoes, "settings": {"executionOrder": "v1"}}
