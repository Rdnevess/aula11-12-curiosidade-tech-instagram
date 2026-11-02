"""Roteiro do Reel diário: geração pelo Gemini e validação contra o catálogo de blocos."""
import re
from datetime import date

from scripts.diario import gemini
from scripts.diario.config import MAX_PALAVRAS, selo

ICONES = ("chip", "celular", "computador", "console", "cartucho", "globo", "satelite", "foguete", "robo",
          "servidor", "email", "disquete")
# campo -> limite de caracteres (int), "num" (número), "ano", "icone", "par" (lista de 2 textos ≤ 12) ou "data"
BLOCOS = {
    "gancho": {"icone": "icone", "carimbo": 12},
    "data": {"texto": "data"},
    "numero": {"valor": "num", "prefixo": 4, "sufixo": 6, "legenda": 28},
    "fato": {"texto": 60},
    "linha-do-tempo": {"de": "ano", "ate": "ano", "rotulo": 24},
    "comparacao": {"esquerda": 14, "direita": 14, "rotulos": "par"},
}
OPCIONAIS = {"prefixo", "sufixo"}
PONTUACAO = re.compile(r"[…?!.,:;\"“”()]")

PROMPT = """Escreva o roteiro de um Reel de até 26 segundos de fala, em português do Brasil, para o perfil
@curiosidadetechhoje, sobre o fato abaixo. Use SOMENTE informações do fato.
Fato ({data}): {titulo}. {fato}

Regras:
- 4 a 6 trechos curtos, no máximo {max_palavras} palavras somando todos, tom de criador de conteúdo falando com "você".
- O 1º trecho é um gancho que gera curiosidade; o último fecha a história. Nenhum trecho cita o @ nem pede para seguir.
- Todo trecho começa com uma palavra (nunca com número). Escreva números com algarismos.
- Cada trecho tem um bloco visual do catálogo; dois trechos seguidos não podem usar o mesmo bloco; o 1º é "gancho".
- Catálogo (campo: limite):
  gancho: icone (um de {icones}), carimbo (≤ 12 caracteres, MAIÚSCULAS)
  data: texto ("DD/MM/AAAA" da data do fato)
  numero: valor (número), prefixo (≤ 4, pode ser ""), sufixo (≤ 6, pode ser ""), legenda (≤ 28)
  fato: texto (≤ 60)
  linha-do-tempo: de (ano), ate (ano), rotulo (≤ 24)
  comparacao: esquerda (≤ 14), direita (≤ 14), rotulos (lista com 2 textos ≤ 12)
- Nada de logotipos ou marcas como ícone.
- "destaques": 2 a 4 palavras exatamente como aparecem nas falas (uma palavra cada).
- "legenda_post": 2 a 4 frases sobre o fato, com "Siga @curiosidadetechhoje" e 3 a 5 hashtags.
Responda SOMENTE com JSON:
{{"titulo": "...", "data": "{data}", "selo": "{selo}",
  "trechos": [{{"fala": "...", "bloco": "gancho", "dados": {{"icone": "...", "carimbo": "..."}}}}],
  "destaques": ["..."], "legenda_post": "..."}}"""


class ErroRoteiro(Exception):
    pass


def _palavras(texto):
    return [PONTUACAO.sub("", p).lower() for p in texto.split() if PONTUACAO.sub("", p)]


def _numeros(valor):
    # Regras pt-BR: "," é separador decimal (nunca removido); "." só é separador de
    # milhar quando agrupa dígitos em blocos de exatamente 3 (ex.: "3.000.000").
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = re.sub(r"\d{1,3}(?:\.\d{3})+", lambda m: m.group(0).replace(".", ""), str(valor))
    return set(re.findall(r"\d{2,}", texto))


def numeros_do_roteiro(roteiro):
    achados = set()
    trechos = roteiro.get("trechos")
    for trecho in trechos if isinstance(trechos, list) else []:
        if not isinstance(trecho, dict):
            continue
        achados |= _numeros(trecho.get("fala", ""))
        dados = trecho.get("dados")
        if trecho.get("bloco") != "data" and isinstance(dados, dict):
            for valor in dados.values():
                if not isinstance(valor, list):
                    achados |= _numeros(valor)
    return sorted(achados)


def _validar_dados(i, bloco, dados, problemas):
    for campo, regra in BLOCOS[bloco].items():
        valor = dados.get(campo)
        if valor is None or (valor == "" and campo not in OPCIONAIS):
            problemas.append(f"trecho {i + 1}: falta {campo} no bloco {bloco}")
            continue
        if regra == "icone" and valor not in ICONES:
            problemas.append(f"trecho {i + 1}: ícone fora do catálogo: {valor}")
        elif regra == "num" and (isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor <= 0):
            problemas.append(f"trecho {i + 1}: valor deve ser número positivo")
        elif regra == "ano" and not (isinstance(valor, int) and 1800 <= valor <= date.today().year):
            problemas.append(f"trecho {i + 1}: {campo} deve ser um ano")
        elif regra == "par" and not (isinstance(valor, list) and len(valor) == 2
                                     and all(isinstance(v, str) and 0 < len(v) <= 12 for v in valor)):
            problemas.append(f"trecho {i + 1}: rotulos deve ter 2 textos de até 12 caracteres")
        elif regra == "data" and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", str(valor)):
            problemas.append(f"trecho {i + 1}: data deve ser DD/MM/AAAA")
        elif isinstance(regra, int) and len(str(valor)) > regra:
            problemas.append(f"trecho {i + 1}: {campo} passa de {regra} caracteres")


def validar(roteiro, dia_evento, fato_texto):
    problemas = []
    trechos = roteiro.get("trechos")
    if trechos is None:
        trechos = []
    if not isinstance(trechos, list):
        problemas.append("trechos deve ser uma lista")
        return problemas
    if not 4 <= len(trechos) <= 6:
        problemas.append(f"esperados 4 a 6 trechos, há {len(trechos)}")
    falas = [t.get("fala", "") if isinstance(t, dict) else "" for t in trechos]
    total = sum(len(f.split()) for f in falas)
    if total > MAX_PALAVRAS:
        problemas.append(f"{total} palavras; o máximo é {MAX_PALAVRAS}")
    blocos = [t.get("bloco") if isinstance(t, dict) else None for t in trechos]
    if trechos and blocos[0] != "gancho":
        problemas.append("o 1º trecho deve usar o bloco gancho")
    for i, trecho in enumerate(trechos):
        if not isinstance(trecho, dict):
            problemas.append(f"trecho {i + 1}: deve ser um objeto")
            continue
        bloco, fala = trecho.get("bloco"), trecho.get("fala", "")
        dados = trecho.get("dados")
        if dados is not None and not isinstance(dados, dict):
            problemas.append(f"trecho {i + 1}: dados deve ser um objeto")
            continue
        if bloco not in BLOCOS:
            problemas.append(f"trecho {i + 1}: bloco fora do catálogo: {bloco}")
        else:
            _validar_dados(i, bloco, dados or {}, problemas)
        if i and bloco == blocos[i - 1]:
            problemas.append(f"trecho {i + 1}: mesmo bloco do trecho anterior")
        primeira = _palavras(fala)[:1]
        if not primeira or primeira[0][0].isdigit():
            problemas.append(f"trecho {i + 1}: deve começar com uma palavra, não com número")
        if "@" in fala:
            problemas.append(f"trecho {i + 1}: a fala não pode ter @")
    if roteiro.get("data") != dia_evento.isoformat():
        problemas.append(f"data do roteiro deve ser {dia_evento.isoformat()}")
    if roteiro.get("selo") != selo(dia_evento):
        problemas.append(f"selo deve ser {selo(dia_evento)}")
    palavras = {p for f in falas for p in _palavras(f)}
    for destaque in roteiro.get("destaques") or []:
        if PONTUACAO.sub("", destaque).lower() not in palavras:
            problemas.append(f"destaque '{destaque}' não aparece na fala")
    legenda = roteiro.get("legenda_post", "")
    if len(legenda) > 2200 or "@curiosidadetechhoje" not in legenda or legenda.count("#") < 3:
        problemas.append("legenda_post precisa de @curiosidadetechhoje, 3+ hashtags e até 2.200 caracteres")
    no_fato = _numeros(fato_texto)
    for numero in numeros_do_roteiro(roteiro):
        if numero not in no_fato:
            problemas.append(f"número {numero} não está no fato pesquisado")
    return problemas


def gerar_roteiro(fato, chave, modelo, gerar=gemini.gerar, tentativas=3):
    dia_evento = date.fromisoformat(fato["data"])
    base = PROMPT.format(data=fato["data"], titulo=fato["titulo"], fato=fato["fato"], max_palavras=MAX_PALAVRAS,
                         icones=", ".join(ICONES), selo=selo(dia_evento))
    problemas = []
    for tentativa in range(1, tentativas + 1):
        prompt = base if not problemas else (
            base + "\n\nProblemas da tentativa anterior (corrija todos):\n- " + "\n- ".join(problemas))
        texto, _ = gerar(prompt, chave, modelo, json_mode=True)
        try:
            roteiro = gemini.extrair_json(texto)
        except gemini.ErroGemini as erro:
            problemas = [str(erro)]
            continue
        try:
            problemas = validar(roteiro, dia_evento, fato["fato"])
        except (TypeError, AttributeError, ValueError) as erro:
            problemas = [f"roteiro malformado: {erro}"]
            continue
        if not problemas:
            return roteiro, tentativa
    raise ErroRoteiro("roteiro inválido após " + str(tentativas) + " tentativas: " + "; ".join(problemas))
