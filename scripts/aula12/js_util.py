"""Ponte Python -> Node para testar, sem n8n, a lógica dos nós Code da
Aula 12 (scripts/aula12/js/*.js).

`carregar(nome)` devolve o texto do arquivo (para colar no nó Code).
`chamar(nome, funcao, *args)` executa a função num processo Node e
devolve o resultado (via JSON), permitindo testar a mesma lógica em
unittest.
"""
import json
import subprocess
from pathlib import Path

PASTA_JS = Path(__file__).resolve().parent / "js"


def _caminho(nome):
    return PASTA_JS / f"{nome}.js"


def carregar(nome):
    """Devolve o conteúdo de js/<nome>.js."""
    return _caminho(nome).read_text(encoding="utf-8")


def chamar(nome, funcao, *args):
    """Roda `funcao(*args)` do arquivo js/<nome>.js num processo node e
    devolve o resultado (JSON.parse do retorno).

    Os argumentos vão como JSON. Se o parâmetro correspondente da função
    JS se chamar "corpoBuffer", a string recebida é convertida para
    Buffer (Buffer.from(arg, "utf8")) antes da chamada — é assim que
    `assinaturaValida` recebe o corpo bruto da requisição.

    O caminho do módulo é embutido no script via JSON.stringify (feito
    pelo próprio node, abaixo), o que evita qualquer problema com
    espaços ou barras invertidas no caminho (comum no Windows).
    """
    # ensure_ascii=True (padrão) é propositalmente mantido: o script inteiro
    # (incluindo os dados dos argumentos) vai para o node via argv, e o
    # Windows decodifica argv com a codepage do sistema, não UTF-8 — texto
    # acentuado cru viraria lixo. Em \\uXXXX, o JSON.parse do node devolve
    # os caracteres corretos de volta.
    caminho_js = str(_caminho(nome).resolve())
    argumentos = json.dumps(list(args))

    script = f"""
const caminho = {json.dumps(caminho_js)};
const nomeFuncao = {json.dumps(funcao)};
const mod = require(caminho);
const fn = mod[nomeFuncao];
if (typeof fn !== 'function') {{
  process.stderr.write('funcao nao encontrada: ' + nomeFuncao);
  process.exit(1);
}}
const argsBrutos = {argumentos};
const nomesParametros = (fn.toString().match(/^[^(]*\\(([^)]*)\\)/) || [null, ''])[1]
  .split(',')
  .map((s) => s.trim().split('=')[0].trim())
  .filter(Boolean);
const argsFinais = argsBrutos.map((valor, indice) => {{
  if (nomesParametros[indice] === 'corpoBuffer' && typeof valor === 'string') {{
    return Buffer.from(valor, 'utf8');
  }}
  return valor;
}});
const resultado = fn(...argsFinais);
process.stdout.write(JSON.stringify(resultado === undefined ? null : resultado));
"""

    processo = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if processo.returncode != 0:
        raise RuntimeError(
            f"node falhou ao chamar {nome}.{funcao}: {processo.stderr.strip()}"
        )

    saida = processo.stdout.strip()
    return json.loads(saida) if saida else None
