"""Infra da Aula 12 (Task 4): `.env.n8n` e diff do compose da Aula 09.

Funções puras (sem rede, sem Docker) — ver
docs/superpowers/specs/2026-11-05-aula12-respostas-design.md, seção 1:

- `env_n8n(env)`: conteúdo do `.env.n8n` a partir do `.env` da aula11.
- `compose_atualizado(texto_atual, dominio, pasta_diario)`: acrescenta ao
  serviço `n8n` o `WEBHOOK_URL`, as variáveis de segurança, o `env_file` e o
  volume do diário; acrescenta o serviço `redis` e o volume `redis_data`.
  Idempotente (aplicar duas vezes dá a mesma saída).

Executado como script (`python -m scripts.aula12.infra`): grava o
`.env.n8n` ao lado do compose da Aula 09 (sem nunca imprimir segredos) e
imprime o diff proposto do compose — não grava o compose: isso é feito no
portão do usuário, com backup (Task 4, Step 5).
"""
import difflib
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
AULA09 = RAIZ.parent / "Aula09-workflow"
COMPOSE = AULA09 / "docker-compose.yml"
ENV_N8N = AULA09 / ".env.n8n"

# Variáveis de segurança do n8n exigidas pela Task 4 (além do WEBHOOK_URL,
# que depende do domínio do ngrok). O separador ';' do
# N8N_RESTRICT_FILE_ACCESS_TO foi confirmado lendo
# @n8n/config/dist/configs/security.config.js dentro do contêiner n8n
# (restrictFileAccessTo.split(';')).
VARIAVEIS_N8N = [
    "NODE_FUNCTION_ALLOW_BUILTIN=crypto",
    "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
    "N8N_RESTRICT_FILE_ACCESS_TO=/dados;/home/node/.n8n-files",
]

SERVICO_REDIS = (
    "  redis:\n"
    "    image: redis:7-alpine\n"
    "    container_name: n8n-redis\n"
    "    restart: unless-stopped\n"
    "    volumes:\n"
    "      - redis_data:/data\n"
)


def env_n8n(env):
    """Conteúdo de `Aula09-workflow/.env.n8n` a partir do `.env` da aula11.

    `env` é o dict carregado do `.env` da aula11 (`scripts.n8n_api.carregar_env`).
    Chaves ausentes (ex.: META_APP_SECRET antes da Task 7) saem com valor
    vazio — a chave precisa existir para o `env_file` do compose não falhar.
    """
    return (
        f"META_APP_SECRET={env.get('META_APP_SECRET', '')}\n"
        f"INSTAGRAM_CONTA_ID={env.get('INSTAGRAM_CONTA_ID', '')}\n"
        f"TELEGRAM_CHAT_ID={env.get('TELEGRAM_CHAT_ID', '')}\n"
    )


def _bloco_servico(texto, nome):
    """Casamento do bloco de um serviço: o cabeçalho ("  nome:") e todas as
    linhas do corpo, que têm indentação >= 4 espaços. Precisa ser >= 4 (e
    não apenas "começa com espaço") para não engolir o próximo serviço
    (indentado só com 2 espaços, ex. "  redis:")."""
    padrao = r"^  " + re.escape(nome) + r":\n(?:[ \t]{4,}.*\n?)*"
    return re.search(padrao, texto, re.M)


def _acrescentar_item(bloco, chave, item_sem_marcador, indent_chave="    "):
    """Acrescenta `- item_sem_marcador` na lista `chave:` do bloco (cria a
    chave se faltar); não duplica se o item já estiver presente."""
    indent_item = indent_chave + "  "
    padrao = re.compile(
        r"^" + indent_chave + re.escape(chave) + r":\n(?:" + re.escape(indent_item) + r"-.*\n?)*", re.M
    )
    m = padrao.search(bloco)
    if m:
        if item_sem_marcador in m.group(0):
            return bloco
        fim = m.end()
        return bloco[:fim] + f"{indent_item}- {item_sem_marcador}\n" + bloco[fim:]
    fim_bloco = bloco if bloco.endswith("\n") else bloco + "\n"
    return fim_bloco + f"{indent_chave}{chave}:\n{indent_item}- {item_sem_marcador}\n"


def compose_atualizado(texto_atual, dominio, pasta_diario):
    """Acrescenta ao serviço `n8n` o `WEBHOOK_URL`, as variáveis de
    segurança, o `env_file` e o volume do diário; acrescenta o serviço
    `redis` e o volume `redis_data`. Idempotente."""
    quebra = "\r\n" if "\r\n" in texto_atual else "\n"
    texto = texto_atual.replace("\r\n", "\n")

    m = _bloco_servico(texto, "n8n")
    if m is None:
        raise ValueError("serviço 'n8n' não encontrado no compose")
    bloco = m.group(0)

    for var in [f"WEBHOOK_URL=https://{dominio}"] + VARIAVEIS_N8N:
        chave = var.split("=", 1)[0]
        if not re.search(r"^\s*-\s*" + re.escape(chave) + r"=", bloco, re.M):
            bloco = _acrescentar_item(bloco, "environment", var)

    volume_diario = f'"{pasta_diario}:/dados/diario:ro"'
    if volume_diario not in bloco:
        bloco = _acrescentar_item(bloco, "volumes", volume_diario)

    if "env_file:" not in bloco:
        if not bloco.endswith("\n"):
            bloco += "\n"
        bloco += "    env_file:\n      - .env.n8n\n"

    texto = texto[: m.start()] + bloco + texto[m.end() :]

    if re.search(r"^  redis:\n", texto, re.M) is None:
        pos = m.start() + len(bloco)
        texto = texto[:pos] + SERVICO_REDIS + texto[pos:]

    if re.search(r"^  redis_data:\s*$", texto, re.M) is None:
        texto = re.sub(r"^(volumes:\n)", r"\1  redis_data:\n", texto, count=1, flags=re.M)

    if quebra == "\r\n":
        texto = texto.replace("\n", "\r\n")
    return texto


def diff_compose(atual, proposto):
    """Diff unificado (texto), para mostrar ao usuário no portão da Task 4."""
    return "".join(
        difflib.unified_diff(
            atual.splitlines(keepends=True),
            proposto.splitlines(keepends=True),
            fromfile="docker-compose.yml",
            tofile="docker-compose.yml (proposto)",
        )
    )


if __name__ == "__main__":
    from scripts.n8n_api import carregar_env

    env = carregar_env()
    conteudo_env_n8n = env_n8n(env)
    ENV_N8N.write_text(conteudo_env_n8n, encoding="utf-8")
    faltando = [k for k in ("META_APP_SECRET", "INSTAGRAM_CONTA_ID", "TELEGRAM_CHAT_ID") if not env.get(k)]
    print(f"Gravado {ENV_N8N} ({len(conteudo_env_n8n)} bytes; valores não exibidos).")
    if faltando:
        print(f"Aviso: sem valor ainda para {', '.join(faltando)} (chave gravada vazia).")

    dominio = env.get("NGROK_DOMINIO") or "<NGROK_DOMINIO>"
    pasta_diario = (RAIZ / "diario").as_posix()
    atual = COMPOSE.read_text(encoding="utf-8")
    proposto = compose_atualizado(atual, dominio, pasta_diario)
    print(diff_compose(atual, proposto))
