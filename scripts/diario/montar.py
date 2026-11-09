"""Monta o Reel do dia: reel.json → voz (tts.mjs) → vídeo (render.mjs) → conferência."""
import json
import os
import subprocess
from pathlib import Path

from scripts.conferir_reel import ler_video, moov_antes_de_mdat, validar_video
from scripts.diario import imagens
from scripts.diario.config import CHROME, END_HOLD, MAX_FALA, MAX_VIDEO, RAIZ, SKILL
from scripts.diario.texto import ancoras

NOTA = ("Leia em português do Brasil, voz de criador de conteúdo no Instagram: animada, próxima, confiante, "
        "ritmo rápido e claro, sem exagero. Conte como uma curiosidade surpreendente. "
        f"Must fit in about {int(MAX_FALA)} seconds — never slow down. Fale exatamente o texto: ")
# Escolhida pelo usuário em 09/11/2026 entre amostras (a Puck soava apressada/robótica).
VOZ = "Orus"
# Sempre o mesmo modelo: o pro (sem cota no plano gratuito) e o flash soam como duas vozes diferentes.
MODELO_VOZ = "gemini-2.5-flash-preview-tts"
# Fator de aceleração com atempo; 1.0 = sem acelerar (a Puck acelerada 10% soava robótica).
TEMPO_VOZ = 1.0
# Tomadas de voz antes de desistir do alinhamento pelas âncoras (cada uma gasta cota do TTS).
TOMADAS = 2


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


def reel_json(roteiro, fotos=()):
    falas = [t["fala"] for t in roteiro["trechos"]]
    return {
        "lines": falas,
        "pronounce": {},
        "voice": {"mode": "take", "voices": [VOZ], "outDir": "audio", "language": "pt", "note": NOTA,
                  "anchors": ancoras(falas), "maxSeconds": MAX_FALA, "speedupMax": 0.1, "models": [MODELO_VOZ]},
        "render": {"name": "diario", "stage": "../curiosidade.html", "out": "out/{name}.mp4", "build": "build",
                   "fps": 30, "width": 1080, "height": 1920, "lead": 0.25, "cover": "S1+1.0", "pops": True,
                   "data": {"scene": "auto", "selo": roteiro["selo"], "highlight": roteiro["destaques"],
                            "capa": titulo_capa(roteiro.get("titulo")), "capaData": _data_capa(roteiro.get("data")),
                            "endAfterLast": True, "endHold": END_HOLD, "fotos": list(fotos),
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
    # Sem isso, uma tomada que falha sem escrever <voz>.json deixaria a voz de uma execução antiga em uso.
    audio = pasta / "audio"
    if audio.is_dir():
        for item in audio.iterdir():
            if item.is_file():
                item.unlink()


def _duracao(wav):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def segs_proporcionais(linhas, duracao):
    """Divide a tomada entre os trechos pelo número de letras: legenda um pouco menos precisa, mas uma voz só."""
    letras = [max(1, sum(c.isalnum() for c in linha)) for linha in linhas]
    total, inicio, segs = sum(letras), 0, []
    for n in letras:
        fim = round(inicio + duracao * n / total, 3)
        segs.append({"start": inicio, "end": fim})
        inicio = fim
    segs[-1]["end"] = round(duracao, 3)
    return segs


def _voz_sem_alinhar(pasta, linhas, duracao):
    """Usa a última tomada (<voz>.t1.wav) quando as âncoras não casaram: escreve o <voz>.json do modo take."""
    tomada = pasta / "audio" / f"{VOZ}.t1.wav"
    if not tomada.exists():
        return False
    wav = pasta / "audio" / f"{VOZ}.wav"
    tomada.replace(wav)
    dur = duracao(wav)
    if dur > MAX_FALA * 1.1:
        return False
    (pasta / "audio" / f"{VOZ}.json").write_text(json.dumps({
        "mode": "take", "voice": VOZ, "file": str(wav), "duration": round(dur, 3), "lines": linhas,
        "segs": segs_proporcionais(linhas, dur), "alinhamento": "proporcional"}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return True


def acelerar_voz(voz_json, fator):
    """Acelera a tomada (atempo) e reescala os tempos dos trechos no <voz>.json."""
    voz_json = Path(voz_json)
    voz = json.loads(voz_json.read_text(encoding="utf-8"))
    wav = Path(voz["file"])
    rapido = wav.with_name(wav.stem + ".rapido.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", f"atempo={fator}", str(rapido)], check=True)
    rapido.replace(wav)
    voz["duration"] = round(voz["duration"] / fator, 3)
    voz["segs"] = [{"start": round(s["start"] / fator, 3), "end": round(s["end"] / fator, 3)} for s in voz["segs"]]
    voz["tempo"] = fator
    voz_json.write_text(json.dumps(voz, ensure_ascii=False, indent=2), encoding="utf-8")


def montar(pasta, roteiro, executar=subprocess.run, conferir=conferir_video, fotos=imagens.preparar,
           acelerar=acelerar_voz, duracao=_duracao):
    """Gera voz e vídeo. Com fotos, acrescenta os créditos a roteiro["legenda_post"] (é a legenda publicada)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    escolhidas = fotos(pasta, roteiro)
    if escolhidas:
        roteiro["legenda_post"] += imagens.creditos_legenda(escolhidas)
    dados = reel_json(roteiro, escolhidas)
    (pasta / "reel.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    env = {**os.environ, "ENV_FILE": str(RAIZ / ".env"), "CHROME_PATH": CHROME, "TAKES": "1"}
    voz = pasta / "audio" / f"{VOZ}.json"
    mp4 = pasta / "out" / f"diario-{VOZ}.mp4"
    # Só tomada única: o modo segments (uma chamada por frase) trocava o timbre entre as frases.
    saidas = []
    for _ in range(TOMADAS):
        _limpar_audio(pasta)
        r, saida = _rodar(executar, "tts.mjs", ["reel.json", VOZ], pasta, env)
        saidas.append(saida)
        if r.returncode == 0 and voz.exists():
            break
    else:
        if not _voz_sem_alinhar(pasta, dados["lines"], duracao):
            raise ErroMontagem(f"voz falhou: {saidas[-1][-400:]}")
    if TEMPO_VOZ != 1:
        acelerar(voz, TEMPO_VOZ)
    # Idem para o vídeo: um render que falha não pode devolver o mp4 de uma execução antiga.
    mp4.unlink(missing_ok=True)
    r, saida_render = _rodar(executar, "render.mjs", ["reel.json", "--voice", f"audio/{VOZ}.json"], pasta, env)
    if r.returncode != 0 or not mp4.exists():
        raise ErroMontagem(f"render falhou: {saida_render[-400:]}")
    with (pasta / "log.txt").open("a", encoding="utf-8") as log:
        for k, saida in enumerate(saidas, start=1):
            log.write(f"== voz (tomada {k}) ==\n")
            log.write(saida[-4000:] + "\n")
        log.write("== render ==\n")
        log.write(saida_render[-4000:] + "\n")
    return mp4, conferir(mp4)
