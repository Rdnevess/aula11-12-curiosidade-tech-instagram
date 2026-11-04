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
Use a busca na web. Encontre UM acontecimento de TECNOLOGIA E COMPUTAÇÃO que ocorreu em {dia} de {mes},
em qualquer ano até {ano}: hardware, software, computadores, internet, games, inteligência artificial,
telecomunicações, eletrônica, programação, empresas e produtos de tecnologia.
Missões espaciais só valem quando o fato é sobre a tecnologia em si (um computador de bordo, um chip, um software,
um sistema de comunicação, uma inovação de engenharia); nesse caso o roteiro deve focar na tecnologia, não na missão.
Prefira acontecimentos curiosos, conhecidos do público e com a data exata confirmada por mais de uma fonte.
Não use nenhum destes temas: {usados}.
Não repita nenhum desses acontecimentos, nem o mesmo acontecimento com outro nome ou outro ângulo.
Nomes proibidos (o acontecimento escolhido não pode envolver nenhum deles): {nomes}.
{rejeitados}Use pelo menos 2 sites independentes (domínios diferentes, de preferência fora da Wikipedia) e liste as URLs em fontes.
Responda SOMENTE com um objeto JSON, sem texto antes ou depois:
{{"titulo": "nome curto do acontecimento",
  "data": "AAAA-MM-DD",
  "fato": "3 a 5 frases em português com quem, o quê, onde, a data e os números exatos",
  "numeros": ["cada número citado no fato, como aparece no texto"],
  "fontes": ["URLs das páginas que você usou"]}}"""

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


class TemaRepetido(ErroPesquisa):
    """A pesquisa trouxe um acontecimento já usado; titulo vai como exclusão explícita na próxima tentativa."""

    def __init__(self, mensagem, titulo):
        super().__init__(mensagem)
        self.titulo = titulo


def pesquisar(dia, hist, chave, modelo, buscar=openai_busca.buscar, rejeitados=()):
    """hist = dicionário do histórico (historico.carregar); rejeitados = títulos recusados nas tentativas anteriores."""
    extra = REJEITADOS.format(titulos="; ".join(f'"{t}"' for t in rejeitados)) if rejeitados else ""
    prompt = PROMPT.format(dia=dia.day, mes=NOMES_MESES[dia.month - 1], ano=dia.year,
                           usados="; ".join(historico.temas_com_data(hist)) or "nenhum", rejeitados=extra,
                           nomes=", ".join(historico.nomes_usados(hist, rejeitados)) or "nenhum")
    texto, fontes = buscar(prompt, chave, modelo)
    fato = gemini.extrair_json(texto)
    faltando = [c for c in CAMPOS if not fato.get(c)]
    if faltando:
        raise ErroPesquisa(f"pesquisa sem os campos: {', '.join(faltando)}")
    try:
        data = date.fromisoformat(fato["data"])
    except ValueError:
        raise ErroPesquisa(f"data inválida na pesquisa: {fato['data']}") from None
    if (data.month, data.day) != (dia.month, dia.day) or data.year > dia.year:
        raise ErroPesquisa(f"a pesquisa trouxe outro dia: {fato['data']}")
    motivo = historico.ja_usado(hist, fato["titulo"], fato["data"])
    if motivo:
        raise TemaRepetido(f"tema já usado: {fato['titulo']} ({motivo})", fato["titulo"])
    fato["fontes"] = fontes
    return fato


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
