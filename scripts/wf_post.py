"""Workflow "Aula 11 - Post no Instagram" (apostila, seção 4), com vídeo publicado como Reel."""
from scripts.wf_util import ligar, no

NOME = "Aula 11 - Post no Instagram"
CREDENCIAL = "Instagram TEP"

CODIGO_PREPARAR = """// O formulário entrega o arquivo com o rótulo do campo como chave do binário.
// Aqui ele passa a se chamar "midia"; o tipo (imagem ou vídeo) e a legenda vão para o JSON.
const TIPOS = { 'image/jpeg': 'imagem', 'video/mp4': 'video', 'video/quicktime': 'video' };
const item = $input.first();
const chave = Object.keys(item.binary ?? {})[0];
if (!chave) throw new Error('Nenhum arquivo recebido do formulário.');
const arquivo = item.binary[chave];
const tipo = TIPOS[arquivo.mimeType];
if (!tipo) throw new Error(`O Instagram aceita JPEG, MP4 ou MOV; o arquivo é ${arquivo.mimeType}.`);
const legenda = item.json.legenda ?? item.json.Legenda ?? '';
return [{ json: { arquivo: arquivo.fileName, tipo, legenda }, binary: { midia: arquivo } }];
"""

HTTP = "n8n-nodes-base.httpRequest"
GRAPH = "https://graph.instagram.com"
WEBHOOK_FORM = "5b2d7c10-4e1a-4f6b-8c3d-1a0c11000001"
WEBHOOK_ESPERA = "5b2d7c10-4e1a-4f6b-8c3d-1a0c11000002"
WEBHOOK_FIM = "5b2d7c10-4e1a-4f6b-8c3d-1a0c11000003"
ORDEM = ["Novo post", "Preparar mídia", "Hospedar mídia", "Link direto", "Conta do Instagram",
         "Criar contêiner", "Aguardar processamento", "Status do contêiner", "Pronto?", "Falhou",
         "Publicar", "Link do post", "Post publicado"]

# Primeiro link assinado /dl/ da página do arquivo no tmpfiles.org (seção 4.5).
LINK = r"""$('Link direto').item.json.pagina.match(/https:\/\/tmpfiles\.org\/dl\/[^"]+/)[0]"""
LEGENDA = "$('Preparar mídia').item.json.legenda"
# Imagem: image_url (como na apostila). Vídeo: Reel, com media_type=REELS e video_url.
QUERY_CONTEINER = (
    "={{ JSON.stringify($('Preparar mídia').item.json.tipo === 'video'"
    f" ? {{ media_type: 'REELS', video_url: {LINK}, caption: {LEGENDA} }}"
    f" : {{ image_url: {LINK}, caption: {LEGENDA} }}) }}}}"
)


def _graph(nome, posicao, metodo, url, id_credencial, campos=None, json_query=None):
    parametros = {"method": metodo, "url": url, "authentication": "genericCredentialType",
                  "genericAuthType": "httpQueryAuth", "options": {}}
    if campos:
        parametros.update(sendQuery=True, specifyQuery="keypair",
                          queryParameters={"parameters": [{"name": k, "value": v} for k, v in campos]})
    if json_query:
        parametros.update(sendQuery=True, specifyQuery="json", jsonQuery=json_query)
    credenciais = {"httpQueryAuth": {"id": id_credencial, "name": CREDENCIAL}}
    return no(nome, HTTP, 4.2, posicao, parametros, credenciais=credenciais)


def _regra(chave, condicao):
    return {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                           "conditions": [condicao], "combinator": "and"},
            "renameOutput": True, "outputKey": chave}


def construir(id_credencial):
    x = lambda i: (i * 220, 0)
    nos = [
        no("Novo post", "n8n-nodes-base.formTrigger", 2.5, x(0), {
            "formTitle": "Publicar no Instagram",
            "formDescription": "Escolha uma imagem JPEG ou um vídeo MP4/MOV do computador e escreva a legenda. "
                               "Imagem vira post; vídeo vira Reel. O post sai na conta conectada ao app.",
            "formFields": {"values": [
                {"fieldLabel": "Mídia", "fieldName": "midia", "fieldType": "file", "multipleFiles": False,
                 "acceptFileTypes": ".jpg,.jpeg,.mp4,.mov", "requiredField": True},
                {"fieldLabel": "Legenda", "fieldName": "legenda", "fieldType": "textarea", "requiredField": True},
            ]},
            "options": {"path": "post-instagram"},
        }, webhook_id=WEBHOOK_FORM),
        no("Preparar mídia", "n8n-nodes-base.code", 2, x(1), {"jsCode": CODIGO_PREPARAR}),
        no("Hospedar mídia", HTTP, 4.2, x(2), {
            "method": "POST", "url": "https://tmpfiles.org/api/v1/upload", "sendBody": True,
            "contentType": "multipart-form-data",
            "bodyParameters": {"parameters": [
                {"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "midia"}]},
            "options": {},
        }),
        no("Link direto", HTTP, 4.2, x(3), {
            "url": "={{ $json.data.url.replace('http://', 'https://') }}",
            "options": {"response": {"response": {"responseFormat": "text", "outputPropertyName": "pagina"}}},
        }),
        _graph("Conta do Instagram", x(4), "GET", f"{GRAPH}/me", id_credencial,
               campos=[("fields", "user_id,username")]),
        _graph("Criar contêiner", x(5), "POST", "=" + GRAPH + "/{{ $json.user_id }}/media", id_credencial,
               json_query=QUERY_CONTEINER),
        no("Aguardar processamento", "n8n-nodes-base.wait", 1.1, x(6), {"amount": 10, "unit": "seconds"},
           webhook_id=WEBHOOK_ESPERA),
        _graph("Status do contêiner", x(7), "GET", "=" + GRAPH + "/{{ $('Criar contêiner').item.json.id }}",
               id_credencial, campos=[("fields", "status_code")]),
        no("Pronto?", "n8n-nodes-base.switch", 3.2, x(8), {
            "rules": {"values": [
                _regra("Pronto", {"id": "pronto", "leftValue": "={{ $json.status_code }}", "rightValue": "FINISHED",
                                  "operator": {"type": "string", "operation": "equals"}}),
                _regra("Falhou", {"id": "falha",
                                  "leftValue": "={{ ['ERROR', 'EXPIRED'].includes($json.status_code) "
                                               "|| $runIndex >= 29 }}",
                                  "rightValue": "",
                                  "operator": {"type": "boolean", "operation": "true", "singleValue": True}}),
            ]},
            "options": {"fallbackOutput": "extra", "renameFallbackOutput": "Aguardar"},
        }),
        no("Falhou", "n8n-nodes-base.stopAndError", 1, (x(9)[0], 220), {
            "errorType": "errorMessage",
            "errorMessage": "=Contêiner {{ $('Criar contêiner').item.json.id }} "
                            "({{ $('Preparar mídia').item.json.tipo }}) não ficou pronto: "
                            "status {{ $json.status_code }}.",
        }),
        _graph("Publicar", x(9), "POST", "=" + GRAPH + "/{{ $('Conta do Instagram').item.json.user_id }}/media_publish",
               id_credencial, campos=[("creation_id", "={{ $('Criar contêiner').item.json.id }}")]),
        _graph("Link do post", x(10), "GET", "=" + GRAPH + "/{{ $json.id }}", id_credencial,
               campos=[("fields", "permalink,timestamp")]),
        no("Post publicado", "n8n-nodes-base.form", 2.5, x(11), {
            "operation": "completion", "completionTitle": "Post publicado",
            "completionMessage": "={{ $json.permalink }}", "options": {},
        }, webhook_id=WEBHOOK_FIM),
    ]
    conexoes = {}
    for a, b in zip(ORDEM[:9], ORDEM[1:9]):
        ligar(conexoes, a, b)
    ligar(conexoes, "Pronto?", "Publicar", saida=0)
    ligar(conexoes, "Pronto?", "Falhou", saida=1)
    ligar(conexoes, "Pronto?", "Aguardar processamento", saida=2)
    ligar(conexoes, "Publicar", "Link do post")
    ligar(conexoes, "Link do post", "Post publicado")
    return {"name": NOME, "nodes": nos, "connections": conexoes, "settings": {"executionOrder": "v1"}}
