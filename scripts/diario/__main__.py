"""Curiosidade de tecnologia diária.

Uso:
  python -m scripts.diario rodar [--data AAAA-MM-DD] [--sem-publicar]
  python -m scripts.diario verificar
  python -m scripts.diario telegram-id
  python -m scripts.diario agendar [--confirmar]
"""
import subprocess
import sys
from datetime import date

from scripts.diario import config, fluxo, telegram


def _cmd(subcomando):
    arquivo = config.PASTA_DADOS / f"{subcomando}.cmd"
    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(f'@echo off\r\ncd /d "{config.RAIZ}"\r\nset PYTHONIOENCODING=utf-8\r\n'
                       f'"{sys.executable}" -m scripts.diario {subcomando} >> "diario\\{subcomando}.log" 2>&1\r\n',
                       encoding="utf-8", newline="")
    return arquivo


def agendar(confirmar):
    # Linha de comando em texto (não lista). O caminho tem espaços ("Aula Top Esp Programacao") e o
    # schtasks tira as aspas de fora do /TR; por isso a forma documentada /TR "\"C:\...\x.cmd\"",
    # com aspas internas escapadas que sobram na tarefa salva.
    def tr(subcomando):
        return f'/TR "\\"{_cmd(subcomando)}\\""'

    tarefas = [
        f'schtasks /Create /F /SC DAILY /ST {config.HORARIO} /TN "CuriosidadeTech\\rodar" {tr("rodar")}',
        f'schtasks /Create /F /SC MINUTE /MO 10 /TN "CuriosidadeTech\\verificar" {tr("verificar")}',
    ]
    for tarefa in tarefas:
        print(tarefa)
        if confirmar:
            subprocess.run(tarefa, check=True)
    if not confirmar:
        print("(nada foi agendado; rode com --confirmar para criar as tarefas)")


def main(argumentos):
    if not argumentos:
        sys.exit(__doc__)
    comando, resto = argumentos[0], argumentos[1:]
    if comando == "rodar":
        if "--data" in resto:
            indice = resto.index("--data") + 1
            if indice >= len(resto):
                sys.exit(__doc__)
            dia = date.fromisoformat(resto[indice])
        else:
            dia = date.today()
        print(fluxo.rodar(dia, sem_publicar="--sem-publicar" in resto))
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
