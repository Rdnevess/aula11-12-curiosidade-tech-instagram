"""Trava de confiança: decide se o Reel do dia pode ser publicado sem aprovação.

Desde 10/11/2026 (pedido do usuário) só os motivos graves seguram o post para aprovação; os outros
viram "suspeitas": o post sai e o aviso no Telegram diz quais são.
"""
from scripts.diario.gemini import dominios


def dominio_base(dominio):
    """Extrai o domínio registrável (último label + penúltimo, ou últimos 3 se country-code TLD).

    Exemplos:
    - jpl.nasa.gov → nasa.gov
    - folha.uol.com.br → uol.com.br
    - bbc.co.uk → bbc.co.uk
    - pt.wikipedia.org → wikipedia.org
    """
    labels = dominio.lower().split('.')
    if len(labels) <= 2:
        return dominio.lower()

    # Verifica se é country-code TLD: penúltimo está em {"com","gov","org","edu","net","ac","co"}
    # e último é um code de 2 letras
    if len(labels) >= 3:
        segundo_ultimo = labels[-2]
        ultimo = labels[-1]
        if (segundo_ultimo in {"com", "gov", "org", "edu", "net", "ac", "co"} and
            len(ultimo) == 2 and ultimo.isalpha()):
            # Retorna últimos 3 labels
            return '.'.join(labels[-3:]).lower()

    # Caso padrão: últimos 2 labels
    return '.'.join(labels[-2:]).lower()


def _e_wikipedia(dominio):
    return dominio == "wikipedia.org" or dominio.endswith(".wikipedia.org")


# Vídeo com defeito técnico (o Instagram pode recusar) e tema repetido continuam esperando aprovação.
GRAVES = ("vídeo:", "tema já publicado")


def graves(motivos):
    return [m for m in motivos if m.startswith(GRAVES)]


def decidir(fato, confirmacao, tentativa_roteiro, problemas_video, repetido):
    motivos = []
    doms = dominios(fato.get("fontes") or [])
    doms_base = {dominio_base(d) for d in doms}
    if len(doms_base) < 2 or all(_e_wikipedia(d) for d in doms_base):
        motivos.append(f"pesquisa com poucas fontes independentes (domínios: {', '.join(sorted(doms_base)) or 'nenhum'})")
    if confirmacao.get("data_confirmada") is not True:
        motivos.append("a checagem cruzada não confirmou a data")
    nao_confirmados = [n.get("valor") for n in (confirmacao.get("numeros") or []) if n.get("confirmado") is not True]
    if nao_confirmados:
        motivos.append(f"números não confirmados: {', '.join(map(str, nao_confirmados))}")
    doms_confirmacao = dominios(confirmacao.get("fontes") or [])
    doms_confirmacao_base = {dominio_base(d) for d in doms_confirmacao}
    if len(doms_confirmacao_base) < 2:
        motivos.append("a checagem cruzada achou menos de 2 domínios")
    if tentativa_roteiro > 2:
        motivos.append(f"roteiro só ficou válido na tentativa {tentativa_roteiro}")
    motivos += [f"vídeo: {p}" for p in (problemas_video or [])]
    if repetido:
        motivos.append("tema já publicado antes" + (f" ({repetido})" if isinstance(repetido, str) else ""))
    return not motivos, motivos
