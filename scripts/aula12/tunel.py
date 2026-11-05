"""Túnel ngrok sempre ligado para o webhook do Instagram (Aula 12, Task 5).

Gera `diario/tunel.cmd` (um loop que sobe o ngrok com a política de tráfego
e reinicia se ele cair) e agenda a tarefa `CuriosidadeTech\\tunel` para rodar
no logon do Windows.

Uso: python -m scripts.aula12.tunel [--confirmar]
(sem --confirmar, só imprime o que seria feito)
"""
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.n8n_api import carregar_env

RAIZ = Path(__file__).resolve().parent.parent.parent
PASTA_DADOS = RAIZ / "diario"
POLITICA = Path(__file__).resolve().parent / "ngrok-politica.yml"
PORTA = 5678
TAREFA = "CuriosidadeTech\\tunel"
# ngrok instalado pelo winget pode não estar no PATH de uma tarefa agendada
# (que roda num ambiente diferente do terminal interativo); por isso o
# caminho absoluto de instalação serve de reserva.
NGROK_PADRAO = (
    r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages"
    r"\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
)


def ngrok_exe():
    return shutil.which("ngrok") or NGROK_PADRAO


def comando(dominio, politica, ngrok=None):
    exe = ngrok or ngrok_exe()
    return (
        f'"{exe}" http --url={dominio} --traffic-policy-file="{politica}" {PORTA} --log=stdout '
        f'>> "diario\\tunel.log"'
    )


def escrever_cmd(dominio, politica, ngrok=None):
    """Grava diario/tunel.cmd: um loop que sobe o ngrok e, se ele sair (queda,
    erro, etc.), espera 30 s e sobe de novo. CRLF puro (newline=""), como o
    .cmd da Aula 11 (scripts/diario/__main__.py)."""
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA_DADOS / "tunel.cmd"
    conteudo = (
        "@echo off\r\n"
        f'cd /d "{RAIZ}"\r\n'
        ":loop\r\n"
        f"{comando(dominio, politica, ngrok)}\r\n"
        "timeout /t 30 /nobreak >nul\r\n"
        "goto loop\r\n"
    )
    arquivo.write_text(conteudo, encoding="utf-8", newline="")
    return arquivo


def tarefa(cmd_path):
    # Mesma forma documentada em scripts/diario/__main__.py: o caminho tem
    # espaços e o schtasks tira as aspas de fora do /TR, por isso as aspas
    # internas escapadas que sobram na tarefa salva.
    return f'schtasks /Create /F /SC ONLOGON /TN "{TAREFA}" /TR "\\"{cmd_path}\\""'


def agendar(dominio, confirmar, ngrok=None):
    arquivo = escrever_cmd(dominio, POLITICA, ngrok)
    linha = tarefa(arquivo)
    print(linha)
    if confirmar:
        subprocess.run(linha, check=True)
    else:
        print("(nada foi agendado; rode com --confirmar para criar a tarefa)")


def main(argumentos):
    env = carregar_env()
    dominio = env.get("NGROK_DOMINIO")
    if not dominio:
        sys.exit("defina NGROK_DOMINIO no .env")
    agendar(dominio, "--confirmar" in argumentos)


if __name__ == "__main__":
    main(sys.argv[1:])
