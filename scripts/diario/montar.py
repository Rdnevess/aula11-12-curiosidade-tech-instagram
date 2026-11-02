"""Monta o Reel do dia: reel.json → voz (tts.mjs) → vídeo (render.mjs) → conferência."""
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

from scripts.conferir_reel import ler_video, moov_antes_de_mdat, validar_video
from scripts.diario.config import CHROME, END_HOLD, MAX_FALA, MAX_VIDEO, RAIZ, SKILL

NOTA = ("Leia em português do Brasil, voz de criador de conteúdo no Instagram: animada, próxima, confiante, "
        "ritmo rápido e claro, sem exagero. Conte como uma curiosidade surpreendente. Must fit in about 25 seconds "
        "— never slow down. Fale exatamente o texto: ")
ESTILO = ("Leia em português do Brasil, voz de criador de conteúdo no Instagram: animada, próxima, confiante, "
          "ritmo rápido mas claro. Fale exatamente o texto:")


class ErroMontagem(Exception):
    pass


def norm(palavra):
    sem_acento = unicodedata.normalize("NFD", palavra.lower())
    return re.sub(r"[^a-z0-9]", "", sem_acento)


def ancoras(falas):
    resultado = []
    for fala in falas[1:]:
        palavras = []
        for bruta in fala.split():
            n = norm(bruta)
            if not n:
                continue
            if n[0].isdigit():
                break
            palavras.append(n)
            if len(palavras) == 2:
                break
        resultado.append(palavras)
    return resultado


def reel_json(roteiro):
    falas = [t["fala"] for t in roteiro["trechos"]]
    return {
        "lines": falas,
        "pronounce": {},
        "voice": {"mode": "take", "voices": ["Puck"], "outDir": "audio", "language": "pt", "note": NOTA,
                  "anchors": ancoras(falas), "maxSeconds": MAX_FALA, "speedupMax": 0.1},
        "render": {"name": "diario", "stage": "../curiosidade.html", "out": "out/{name}.mp4", "build": "build",
                   "fps": 30, "width": 1080, "height": 1920, "lead": 0.25, "cover": "S1+1.0", "pops": True,
                   "data": {"scene": "auto", "selo": roteiro["selo"], "highlight": roteiro["destaques"],
                            "endAfterLast": True, "endHold": END_HOLD,
                            "trechos": [{"bloco": t["bloco"], "dados": t["dados"]} for t in roteiro["trechos"]]}},
    }


def conferir_video(mp4):
    problemas = validar_video(ler_video(mp4), max_duracao=MAX_VIDEO)
    if not moov_antes_de_mdat(mp4):
        problemas.append("sem +faststart")
    return problemas


def _rodar(executar, script, args, pasta, env):
    r = executar(["node", str(SKILL / script), *args], cwd=str(pasta), env=env, capture_output=True, text=True,
                 encoding="utf-8", errors="replace")
    return r, (r.stdout or "") + (r.stderr or "")


def montar(pasta, roteiro, executar=subprocess.run, conferir=conferir_video):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    dados = reel_json(roteiro)
    arquivo = pasta / "reel.json"
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    env = {**os.environ, "ENV_FILE": str(RAIZ / ".env"), "CHROME_PATH": CHROME, "TAKES": "2"}
    r, saida_take = _rodar(executar, "tts.mjs", ["reel.json", "Puck"], pasta, env)
    saida_segments = ""
    if r.returncode != 0 or "ALINHAMENTO SUSPEITO" in saida_take or not (pasta / "audio" / "Puck.json").exists():
        dados["voice"] = {"mode": "segments", "voices": ["Puck"], "outDir": "audio", "style": ESTILO}
        dados["render"]["gap"] = 0.1
        arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        r, saida_segments = _rodar(executar, "tts.mjs", ["reel.json", "Puck"], pasta, env)
        if r.returncode != 0:
            raise ErroMontagem(f"voz falhou: {saida_segments[-400:]}")
    r, saida_render = _rodar(executar, "render.mjs", ["reel.json", "--voice", "audio/Puck.json"], pasta, env)
    mp4 = pasta / "out" / "diario-Puck.mp4"
    if r.returncode != 0 or not mp4.exists():
        raise ErroMontagem(f"render falhou: {saida_render[-400:]}")
    with (pasta / "log.txt").open("a", encoding="utf-8") as log:
        log.write("== voz (take) ==\n")
        log.write(saida_take[-4000:] + "\n")
        if saida_segments:
            log.write("== voz (segments) ==\n")
            log.write(saida_segments[-4000:] + "\n")
        log.write("== render ==\n")
        log.write(saida_render[-4000:] + "\n")
    return mp4, conferir(mp4)
