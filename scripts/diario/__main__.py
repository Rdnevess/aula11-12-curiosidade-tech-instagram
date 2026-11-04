"""Curiosidade de tecnologia diária (dois posts por dia: slot 1 às 09:00, slot 2 às 11:00).

Uso:
  python -m scripts.diario rodar [--data AAAA-MM-DD] [--slot 1|2] [--sem-publicar]
  python -m scripts.diario verificar
  python -m scripts.diario telegram-id
  python -m scripts.diario agendar [--confirmar]
"""
import subprocess
import sys
from datetime import date

from scripts.diario import config, fluxo, telegram

TAREFA_ANTIGA = "CuriosidadeTech\\rodar"  # de antes dos dois posts por dia


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

    tarefas = [
        f'schtasks /Create /F /SC DAILY /ST {hora} /TN "CuriosidadeTech\\rodar-{slot}" '
        f'{tr(f"rodar-{slot}", f"rodar --slot {slot}")}'
        for slot, hora in sorted(config.HORARIOS.items())
    ]
    tarefas.append(f'schtasks /Create /F /SC MINUTE /MO 10 /TN "CuriosidadeTech\\verificar" {tr("verificar")}')
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
        print(fluxo.rodar(dia, slot=int(slot), sem_publicar="--sem-publicar" in resto))
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
