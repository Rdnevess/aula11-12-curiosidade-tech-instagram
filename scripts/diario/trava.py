"""Trava de confiança: decide se o Reel do dia pode ser publicado sem aprovação."""
from scripts.diario.gemini import dominios


def _e_wikipedia(dominio):
    return dominio == "wikipedia.org" or dominio.endswith(".wikipedia.org")


def decidir(fato, confirmacao, tentativa_roteiro, problemas_video, repetido):
    motivos = []
    doms = dominios(fato.get("fontes") or [])
    if len(doms) < 2 or all(_e_wikipedia(d) for d in doms):
        motivos.append(f"pesquisa com poucas fontes independentes (domínios: {', '.join(sorted(doms)) or 'nenhum'})")
    if confirmacao.get("data_confirmada") is not True:
        motivos.append("a checagem cruzada não confirmou a data")
    nao_confirmados = [n.get("valor") for n in (confirmacao.get("numeros") or []) if n.get("confirmado") is not True]
    if nao_confirmados:
        motivos.append(f"números não confirmados: {', '.join(map(str, nao_confirmados))}")
    if len(dominios(confirmacao.get("fontes") or [])) < 2:
        motivos.append("a checagem cruzada achou menos de 2 domínios")
    if tentativa_roteiro > 2:
        motivos.append(f"roteiro só ficou válido na tentativa {tentativa_roteiro}")
    motivos += [f"vídeo: {p}" for p in (problemas_video or [])]
    if repetido:
        motivos.append("tema já publicado antes")
    return not motivos, motivos
