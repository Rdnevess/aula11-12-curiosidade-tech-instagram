"""Pesquisa da curiosidade do dia e checagem cruzada, com a busca na web da OpenAI."""
import json
import re
from datetime import date

from scripts.diario import gemini, openai_busca
from scripts.diario.historico import normalizar_titulo

NOMES_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
               "outubro", "novembro", "dezembro"]
CAMPOS = ("titulo", "data", "fato", "numeros")

PROMPT = """Você pesquisa história da tecnologia para um perfil de Instagram em português do Brasil.
Use a busca na web. Encontre UM acontecimento de tecnologia (computação, internet, games, telecomunicações,
eletrônica, exploração espacial ou ciência da computação) que ocorreu em {dia} de {mes}, em qualquer ano até {ano}.
Prefira acontecimentos curiosos, conhecidos do público e com a data exata confirmada por mais de uma fonte.
Não use nenhum destes temas: {usados}.
Use pelo menos 2 sites independentes (domínios diferentes, de preferência fora da Wikipedia) e liste as URLs em fontes.
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


class ErroPesquisa(Exception):
    pass


def pesquisar(dia, usados, chave, modelo, buscar=openai_busca.buscar):
    prompt = PROMPT.format(dia=dia.day, mes=NOMES_MESES[dia.month - 1], ano=dia.year,
                           usados="; ".join(usados) or "nenhum")
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
    if normalizar_titulo(fato["titulo"]) in {normalizar_titulo(u) for u in usados}:
        raise ErroPesquisa(f"tema já usado: {fato['titulo']}")
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
