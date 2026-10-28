"""Peças comuns para descrever workflows do n8n como dicionários."""
import uuid


def no(nome, tipo, versao, posicao, parametros, credenciais=None, webhook_id=None):
    definicao = {
        "parameters": parametros,
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"aula11/{tipo}/{nome}")),
        "name": nome,
        "type": tipo,
        "typeVersion": versao,
        "position": list(posicao),
    }
    if credenciais:
        definicao["credentials"] = credenciais
    if webhook_id:
        definicao["webhookId"] = webhook_id
    return definicao


def ligar(conexoes, origem, destino, tipo="main", saida=0):
    ramos = conexoes.setdefault(origem, {}).setdefault(tipo, [])
    while len(ramos) <= saida:
        ramos.append([])
    ramos[saida].append({"node": destino, "type": tipo, "index": 0})
