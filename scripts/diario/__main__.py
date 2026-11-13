"""Curiosidade de tecnologia diária (dois posts por dia: slot 1 às 11:00, slot 2 às 18:00).

Uso:
  python -m scripts.diario rodar [--data AAAA-MM-DD] [--slot 1|2] [--sem-publicar]
  python -m scripts.diario verificar
  python -m scripts.diario recuperar                  (roda um slot de hoje cujo horário foi perdido)
  python -m scripts.diario publicar AAAA-MM-DD#slot     (publica um post pendente, sem o botão)
  python -m scripts.diario telegram-id
  python -m scripts.diario agendar [--confirmar]
"""
import contextlib
import subprocess
import sys
from datetime import date

from scripts.diario import config, fluxo, telegram

TAREFA_ANTIGA = "CuriosidadeTech\\rodar"  # de antes dos dois posts por dia
RETENTATIVA_MIN = 40  # se o post falhar (ex.: Gemini sobrecarregado), tenta de novo 40 min depois


# As tarefas não podem parar por falta de tomada (o PC é um notebook). Sem StartWhenAvailable: ele rodaria
# o slot 2 de ontem hoje cedo; quem cobre horário perdido é o recuperar, que olha só o dia de hoje.
BATERIA = ("powershell -NoProfile -Command \"$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries "
           "-DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew; "
           # No PowerShell 5.1, -Settings não combina com a tarefa vinda pelo pipe: nome e caminho explícitos.
           "Get-ScheduledTask -TaskPath '\\CuriosidadeTech\\' | ForEach-Object { Set-ScheduledTask "
           "-TaskName $_.TaskName -TaskPath $_.TaskPath -Settings $s | Out-Null }\"")


@contextlib.contextmanager
def trava_execucao():
    """Garante um rodar/recuperar por vez (rende False se outro já roda). O Windows solta o
    bloqueio sozinho se o processo morrer, então não sobra trava velha."""
    import msvcrt
    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    with open(config.PASTA_DADOS / "execucao.lock", "a+b") as arquivo:
        arquivo.seek(0)
        try:
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)


def _mais_minutos(hora, minutos):
    h, m = map(int, hora.split(":"))
    total = (h * 60 + m + minutos) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _cmd(nome, argumentos=None):
    """Grava diario/<nome>.cmd, que roda `python -m scripts.diario <argumentos>` e anexa a saída em <nome>.log."""
    argumentos = argumentos or nome
    arquivo = config.PASTA_DADOS / f"{nome}.cmd"
    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(f'@echo off\r\ncd /d "{config.RAIZ}"\r\nset PYTHONIOENCODING=utf-8\r\n'
                       f'"{sys.executable}" -m scripts.diario {argumentos} >> "diario\\{nome}.log" 2>&1\r\n',
                       encoding="utf-8", newline="")
    return arquivo


def agendar(confirmar):
    # Linha de comando em texto (não lista). O caminho tem espaços ("Aula Top Esp Programacao") e o
    # schtasks tira as aspas de fora do /TR; por isso a forma documentada /TR "\"C:\...\x.cmd\"",
    # com aspas internas escapadas que sobram na tarefa salva.
    def tr(nome, argumentos=None):
        return f'/TR "\\"{_cmd(nome, argumentos)}\\""'

    tarefas = []
    for slot, hora in sorted(config.HORARIOS.items()):
        acao = tr(f"rodar-{slot}", f"rodar --slot {slot}")
        tarefas.append(f'schtasks /Create /F /SC DAILY /ST {hora} /TN "CuriosidadeTech\\rodar-{slot}" {acao}')
        # Nova tentativa 40 min depois, com o mesmo .cmd: se o slot já foi resolvido, o rodar só imprime "pulado".
        tarefas.append(f'schtasks /Create /F /SC DAILY /ST {_mais_minutos(hora, RETENTATIVA_MIN)} '
                       f'/TN "CuriosidadeTech\\rodar-{slot}-retentativa" {acao}')
    tarefas.append(f'schtasks /Create /F /SC MINUTE /MO 10 /TN "CuriosidadeTech\\verificar" {tr("verificar")}')
    tarefas.append(f'schtasks /Create /F /SC MINUTE /MO 10 /TN "CuriosidadeTech\\recuperar" {tr("recuperar")}')
    tarefas.append(BATERIA)
    for tarefa in tarefas:
        print(tarefa)
        if confirmar:
            subprocess.run(tarefa, check=True)
    # Só depois de criar as novas: a tarefa única antiga rodaria o slot 1 de novo. Pode não existir: ignora a falha.
    remover = f'schtasks /Delete /TN "{TAREFA_ANTIGA}" /F'
    print(remover)
    if confirmar:
        subprocess.run(remover, check=False)
    else:
        print("(nada foi agendado; rode com --confirmar para criar as tarefas)")


def _valor(resto, opcao):
    """Valor depois de --opcao; None se a opção não veio; sai com o uso se ela veio sem valor."""
    if opcao not in resto:
        return None
    indice = resto.index(opcao) + 1
    if indice >= len(resto):
        sys.exit(__doc__)
    return resto[indice]


def main(argumentos):
    if not argumentos:
        sys.exit(__doc__)
    comando, resto = argumentos[0], argumentos[1:]
    if comando == "rodar":
        data = _valor(resto, "--data")
        dia = date.fromisoformat(data) if data else date.today()
        slot = _valor(resto, "--slot") or "1"
        if slot not in {str(s) for s in config.HORARIOS}:
            sys.exit(__doc__)
        with trava_execucao() as livre:
            print(fluxo.rodar(dia, slot=int(slot), sem_publicar="--sem-publicar" in resto) if livre
                  else "ocupado: outra execução em andamento")
    elif comando == "recuperar":
        with trava_execucao() as livre:
            print(fluxo.recuperar() if livre else "ocupado: outra execução em andamento")
    elif comando == "publicar":
        if not resto:
            sys.exit(__doc__)
        print(fluxo.publicar_pendente(resto[0]))
    elif comando == "verificar":
        print(f"{fluxo.verificar()} clique(s)")
    elif comando == "telegram-id":
        for chat_id, nome in telegram.chats(config.chaves()["TELEGRAM_BOT_TOKEN"]):
            print(f"{chat_id}\t{nome}")
    elif comando == "agendar":
        agendar("--confirmar" in resto)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
