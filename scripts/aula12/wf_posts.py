"""Workflow auxiliar "Aula 12 - Posts da conta" (apostila, seção 5.1).

Em vez do gatilho Manual da apostila, um Webhook GET (responde com a saída do
último nó), para que o script de mapeamento de media_id possa chamá-lo.
"""
import uuid

from scripts.wf_post import GRAPH, _graph
from scripts.wf_util import ligar, no

NOME = "Aula 12 - Posts da conta"
WEBHOOK_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "aula12/posts/aula12-posts"))


def construir(id_instagram):
    nos = [
        no("Pedido", "n8n-nodes-base.webhook", 2, (0, 0), {
            "httpMethod": "GET", "path": "aula12-posts", "responseMode": "lastNode", "options": {},
        }, webhook_id=WEBHOOK_ID),
        _graph("Posts da conta", (220, 0), "GET", f"{GRAPH}/me/media", id_instagram,
               campos=[("fields", "id,permalink,caption,timestamp,media_type"), ("limit", "100")]),
    ]
    conexoes = {}
    ligar(conexoes, "Pedido", "Posts da conta")
    return {"name": NOME, "nodes": nos, "connections": conexoes, "settings": {"executionOrder": "v1"}}
