"""Monta o Reel do dia: reel.json → voz (tts.mjs) → vídeo (render.mjs) → conferência."""
import json
import os
import subprocess
from pathlib import Path

from scripts.conferir_reel import ler_video, moov_antes_de_mdat, validar_video
from scripts.diario.config import CHROME, END_HOLD, MAX_FALA, MAX_VIDEO, RAIZ, SKILL
from scripts.diario.texto import ancoras

NOTA = ("Leia em português do Brasil, voz de criador de conteúdo no Instagram: animada, próxima, confiante, "
        "ritmo rápido e claro, sem exagero. Conte como uma curiosidade surpreendente. Must fit in about 25 seconds "
        "— never slow down. Fale exatamente o texto: ")
ESTILO = ("Leia em português do Brasil, voz de criador de conteúdo no Instagram: animada, próxima, confiante, "
          "ritmo rápido mas claro. Fale exatamente o texto:")


class ErroMontagem(Exception):
    pass


MAX_CAPA = 40


def titulo_capa(titulo, limite=MAX_CAPA):
    """Título curto para a capa (1º quadro): corta na última palavra inteira e põe "…"."""
    titulo = " ".join(str(titulo or "").split())
    if len(titulo) <= limite:
        return titulo
    corte = titulo[:limite - 1]
    if " " in corte:
        corte = corte.rsplit(" ", 1)[0]
    return corte.rstrip(" ,.:;—–-") + "…"


def _data_capa(data_iso):
    """"1957-11-03" -> "03/11/1957"; vazio se a data não vier no formato esperado."""
    partes = str(data_iso or "").split("-")
    return "/".join(reversed(partes)) if len(partes) == 3 else ""


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
                            "capa": titulo_capa(roteiro.get("titulo")), "capaData": _data_capa(roteiro.get("data")),
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


def _limpar_audio(pasta):
    # Sem isso, uma tomada que falha sem escrever Puck.json deixaria a voz de uma execução antiga em uso.
    audio = pasta / "audio"
    if audio.is_dir():
        for item in audio.iterdir():
            if item.is_file():
                item.unlink()


def montar(pasta, roteiro, executar=subprocess.run, conferir=conferir_video):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    dados = reel_json(roteiro)
    arquivo = pasta / "reel.json"
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    env = {**os.environ, "ENV_FILE": str(RAIZ / ".env"), "CHROME_PATH": CHROME, "TAKES": "1"}
    voz = pasta / "audio" / "Puck.json"
    mp4 = pasta / "out" / "diario-Puck.mp4"
    _limpar_audio(pasta)
    r, saida_take = _rodar(executar, "tts.mjs", ["reel.json", "Puck"], pasta, env)
    saida_segments = ""
    if r.returncode != 0 or "ALINHAMENTO SUSPEITO" in saida_take or not voz.exists():
        dados["voice"] = {"mode": "segments", "voices": ["Puck"], "outDir": "audio", "style": ESTILO}
        dados["render"]["gap"] = 0.1
        arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        _limpar_audio(pasta)
        r, saida_segments = _rodar(executar, "tts.mjs", ["reel.json", "Puck"], pasta, env)
        if r.returncode != 0 or not voz.exists():
            raise ErroMontagem(f"voz falhou: {saida_segments[-400:]}")
    # Idem para o vídeo: um render que falha não pode devolver o mp4 de uma execução antiga.
    mp4.unlink(missing_ok=True)
    r, saida_render = _rodar(executar, "render.mjs", ["reel.json", "--voice", "audio/Puck.json"], pasta, env)
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
