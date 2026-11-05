"""Workflow "Aula 12 - Direct com agente" (apostila, seção 6, com melhorias).

Sub-workflow chamado pelo workflow de entrada para cada mensagem do Direct:
lê o histórico diário, monta o prompt de sistema com os posts da conta, chama
o agente (Groq, memória no Redis por remetente), retira a marca [ENCAMINHAR],
envia a resposta e, se for o caso, avisa o dono no Telegram.
"""
from scripts.aula12.js_util import carregar
from scripts.wf_post import CREDENCIAL, GRAPH, HTTP
from scripts.wf_util import ligar, no

NOME = "Aula 12 - Direct com agente"
HISTORICO = "/dados/diario/historico.json"
ORDEM = ["Mensagem recebida", "Histórico", "Base da conta", "Atendente", "Encaminhar?",
         "Enviar resposta", "Avisar dono?", "Aviso no Telegram"]

CODIGO_BASE = carregar("agente") + """
// ---- Nó "Base da conta" ----
// Cada item traz, no binário "data", o historico.json lido pelo nó Histórico;
// remetente e texto vêm do gatilho, pelo item pareado.
const saida = [];
const itens = $input.all();
for (let i = 0; i < itens.length; i++) {
  const buf = await this.helpers.getBinaryDataBuffer(i, 'data');
  const historico = JSON.parse(buf.toString('utf8'));
  const msg = $('Mensagem recebida').itemMatching(i).json;
  saida.push({
    json: { remetente: msg.remetente, texto: msg.texto, sistema: promptSistema(historico) },
    pairedItem: i,
  });
}
return saida;
"""

CODIGO_ENCAMINHAR = carregar("agente") + """
// ---- Nó "Encaminhar?" ----
// Retira a marca [ENCAMINHAR] da resposta do agente e corta em 900 caracteres.
return $input.all().map((item, i) => ({ json: separarEncaminhar(item.json.output), pairedItem: i }));
"""

CORPO_RESPOSTA = ("={{ JSON.stringify({ recipient: { id: $('Mensagem recebida').item.json.remetente }, "
                  "message: { text: $json.texto } }) }}")


def ler_historico(nome, posicao):
    """Nó Read File do histórico diário (binário em "data")."""
    return no(nome, "n8n-nodes-base.readWriteFile", 1, posicao, {
        "operation": "read", "fileSelector": HISTORICO, "options": {"dataPropertyName": "data"},
    })


def construir(ids):
    x = lambda i: (i * 220, 0)
    nos = [
        no("Mensagem recebida", "n8n-nodes-base.executeWorkflowTrigger", 1.1, x(0), {
            "inputSource": "workflowInputs",
            "workflowInputs": {"values": [{"name": "remetente", "type": "string"},
                                          {"name": "texto", "type": "string"}]},
        }),
        ler_historico("Histórico", x(1)),
        no("Base da conta", "n8n-nodes-base.code", 2, x(2), {"jsCode": CODIGO_BASE}),
        no("Atendente", "@n8n/n8n-nodes-langchain.agent", 3.1, x(3), {
            "promptType": "define", "text": "={{ $json.texto }}",
            "options": {"systemMessage": "={{ $json.sistema }}"},
        }),
        no("Encaminhar?", "n8n-nodes-base.code", 2, x(4), {"jsCode": CODIGO_ENCAMINHAR}),
        no("Enviar resposta", HTTP, 4.2, x(5), {
            "method": "POST", "url": f"{GRAPH}/v21.0/me/messages",
            "authentication": "genericCredentialType", "genericAuthType": "httpQueryAuth",
            "sendBody": True, "specifyBody": "json", "jsonBody": CORPO_RESPOSTA, "options": {},
        }, credenciais={"httpQueryAuth": {"id": ids["instagram"], "name": CREDENCIAL}}),
        no("Avisar dono?", "n8n-nodes-base.if", 2.2, x(6), {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{"id": "encaminhar", "leftValue": "={{ $('Encaminhar?').item.json.encaminhar }}",
                                "rightValue": "",
                                "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
                "combinator": "and",
            },
            "options": {},
        }),
        no("Aviso no Telegram", "n8n-nodes-base.telegram", 1.2, x(7), {
            "resource": "message", "operation": "sendMessage",
            "chatId": "={{ $env.TELEGRAM_CHAT_ID }}",
            "text": "=\U0001F4E9 Direct para você: {{ $('Mensagem recebida').item.json.texto }}",
            "additionalFields": {"appendAttribution": False},
        }, credenciais={"telegramApi": {"id": ids["telegram"], "name": "Telegram Aviso"}}),
        no("Modelo", "@n8n/n8n-nodes-langchain.lmChatGroq", 1, (x(3)[0] - 80, 220), {
            "model": "openai/gpt-oss-120b", "options": {"temperature": 0.3},
        }, credenciais={"groqApi": {"id": ids["groq"], "name": "Groq"}}),
        no("Memória", "@n8n/n8n-nodes-langchain.memoryRedisChat", 1.5, (x(3)[0] + 80, 220), {
            "sessionIdType": "customKey",
            "sessionKey": "={{ $('Mensagem recebida').item.json.remetente }}",
            "sessionTTL": 604800,
            "contextWindowLength": 10,
        }, credenciais={"redis": {"id": ids["redis"], "name": "Redis"}}),
    ]
    conexoes = {}
    for a, b in zip(ORDEM, ORDEM[1:]):
        ligar(conexoes, a, b)  # em "Avisar dono?" isso liga só a saída 0 (true)
    ligar(conexoes, "Modelo", "Atendente", "ai_languageModel")
    ligar(conexoes, "Memória", "Atendente", "ai_memory")
    return {"name": NOME, "nodes": nos, "connections": conexoes, "settings": {"executionOrder": "v1"}}
