"""Pesquisa da curiosidade do dia e checagem cruzada, com a busca na web da OpenAI."""
import json
import re
from datetime import date

from scripts.diario import gemini, openai_busca
from scripts.diario import historico

NOMES_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
               "outubro", "novembro", "dezembro"]
CAMPOS = ("titulo", "data", "fato", "numeros")

PROMPT = """Você pesquisa história da tecnologia para um perfil de Instagram em português do Brasil.
Use a busca na web. Encontre {quantos} acontecimentos DIFERENTES de TECNOLOGIA E COMPUTAÇÃO, cada um que ocorreu em {dia} de {mes},
em qualquer ano até {ano}: hardware, software, computadores, internet, games, inteligência artificial,
telecomunicações, eletrônica, programação, empresas e produtos de tecnologia.
Missões espaciais só valem quando o fato é sobre a tecnologia em si (um computador de bordo, um chip, um software,
um sistema de comunicação, uma inovação de engenharia); nesse caso o roteiro deve focar na tecnologia, não na missão.
Prefira acontecimentos curiosos, conhecidos do público e com a data exata confirmada por mais de uma fonte.
Os candidatos não podem ser o mesmo acontecimento entre si; coloque o melhor primeiro.
Não use nenhum destes temas: {usados}.
Não repita nenhum desses acontecimentos, nem o mesmo acontecimento com outro nome ou outro ângulo.
Nomes proibidos (o acontecimento escolhido não pode envolver nenhum deles): {nomes}.
{rejeitados}Para cada candidato, use pelo menos 2 sites independentes (domínios diferentes, de preferência fora da
Wikipedia) e liste as URLs em fontes.
Responda SOMENTE com um objeto JSON, sem texto antes ou depois:
{{"candidatos": [
  {{"titulo": "nome curto do acontecimento",
    "data": "AAAA-MM-DD",
    "fato": "3 a 5 frases em português com quem, o quê, onde, a data e os números exatos",
    "numeros": ["cada número citado no fato, como aparece no texto"],
    "fontes": ["URLs das páginas que você usou para este acontecimento"]}}
]}}"""

PROMPT_CONFIRMAR = """Use a busca na web para conferir, em fontes independentes, as afirmações abaixo.
Acontecimento: {titulo}
Data afirmada: {data}
Fato: {fato}
Números a conferir: {numeros}
Use pelo menos 2 sites independentes (domínios diferentes, de preferência fora da Wikipedia) e liste as URLs em fontes.
Responda SOMENTE com um objeto JSON:
{{"data_confirmada": true ou false,
  "numeros": [{{"valor": "número como foi dado", "confirmado": true ou false}}],
  "fontes": ["URLs das páginas que você usou"]}}"""


REJEITADOS = ("Nas tentativas anteriores você sugeriu {titulos}: esse acontecimento já foi publicado. "
              "Escolha OUTRO acontecimento, sem relação com ele.\n")


class ErroPesquisa(Exception):
    pass


# Vários candidatos numa só busca: em datas com um acontecimento dominante (Firefox 1.0 em 9/11), o modelo
# insiste nele mesmo proibido; pedindo vários, sobra um que ainda não foi usado.
CANDIDATOS = 5


class TemaRepetido(ErroPesquisa):
    """Todos os candidatos já foram usados; titulos vão como exclusão explícita na próxima tentativa."""

    def __init__(self, mensagem, titulo, titulos=None):
        super().__init__(mensagem)
        self.titulo = titulo
        self.titulos = list(titulos or [titulo])


def pesquisar(dia, hist, chave, modelo, buscar=openai_busca.buscar, rejeitados=()):
    """hist = dicionário do histórico (historico.carregar); rejeitados = títulos recusados nas tentativas anteriores."""
    extra = REJEITADOS.format(titulos="; ".join(f'"{t}"' for t in rejeitados)) if rejeitados else ""
    prompt = PROMPT.format(quantos=CANDIDATOS, dia=dia.day, mes=NOMES_MESES[dia.month - 1], ano=dia.year,
                           usados="; ".join(historico.temas_com_data(hist)) or "nenhum", rejeitados=extra,
                           nomes=", ".join(historico.nomes_usados(hist, rejeitados)) or "nenhum")
    texto, fontes = buscar(prompt, chave, modelo)
    resposta = gemini.extrair_json(texto)
    # Aceita também um acontecimento só, sem a lista (o formato antigo do prompt).
    candidatos = resposta.get("candidatos") if isinstance(resposta.get("candidatos"), list) else [resposta]
    erros, repetidos = [], []
    for fato in (c for c in candidatos if isinstance(c, dict)):
        erro = _erro_do_candidato(fato, dia)
        if erro:
            erros.append(erro)
            continue
        motivo = historico.ja_usado(hist, fato["titulo"], fato["data"])
        if motivo:
            repetidos.append((fato["titulo"], motivo))
            continue
        listadas = fato.get("fontes") if isinstance(fato.get("fontes"), list) else None
        fato["fontes"] = openai_busca.filtrar_fontes(fontes, listadas) if listadas else fontes
        return fato
    if repetidos:
        raise TemaRepetido("tema já usado: " + "; ".join(f"{t} ({m})" for t, m in repetidos),
                           repetidos[0][0], [t for t, _ in repetidos])
    raise ErroPesquisa("; ".join(erros) or "pesquisa sem candidatos")


def _erro_do_candidato(fato, dia):
    faltando = [c for c in CAMPOS if not fato.get(c)]
    if faltando:
        return f"pesquisa sem os campos: {', '.join(faltando)}"
    try:
        data = date.fromisoformat(fato["data"])
    except (TypeError, ValueError):
        return f"data inválida na pesquisa: {fato['data']}"
    if (data.month, data.day) != (dia.month, dia.day) or data.year > dia.year:
        return f"a pesquisa trouxe outro dia: {fato['data']}"
    return None


def confirmar(fato, numeros, chave, modelo, buscar=openai_busca.buscar):
    prompt = PROMPT_CONFIRMAR.format(titulo=fato["titulo"], data=fato["data"], fato=fato["fato"],
                                     numeros=json.dumps(numeros, ensure_ascii=False))
    texto, fontes = buscar(prompt, chave, modelo)
    resposta = gemini.extrair_json(texto)
    numeros_resposta = [n for n in resposta.get("numeros", []) if isinstance(n, dict)]

    # Ensure every requested number is represented
    digitos_respondidos = {re.sub(r"\D", "", str(n.get("valor", ""))): n for n in numeros_resposta}
    numeros_final = list(numeros_resposta)
    for num_solicitado in numeros:
        digitos_solicitados = re.sub(r"\D", "", str(num_solicitado))
        if digitos_solicitados and digitos_solicitados not in digitos_respondidos:
            numeros_final.append({"valor": num_solicitado, "confirmado": False})

    return {"data_confirmada": resposta.get("data_confirmada") is True,
            "numeros": numeros_final,
            "fontes": fontes}
