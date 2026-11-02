"""Confere um reel.json da série e o MP4 renderizado (formato, duração, faststart, loudness).

Uso: python -m scripts.conferir_reel <reel.json> [<video.mp4>]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ARROBA = "@curiosidadetechhoje"
CENAS = {"facemash", "megadrive", "pentium"}
MAX_FALA = 16.5
MAX_PALAVRAS = 48
MAX_VIDEO = 20.0
PONTUACAO = re.compile(r"[…?!.,:;]")


def validar_reel(dados):
    problemas = []
    linhas = dados.get("lines", [])
    voz = dados.get("voice", {})
    render = dados.get("render", {})
    cena = render.get("data", {})
    if not 4 <= len(linhas) <= 6:
        problemas.append(f"esperados 4 a 6 trechos, há {len(linhas)}")
    if voz.get("mode") != "take" or voz.get("voices") != ["Puck"]:
        problemas.append("voz deve ser só Puck, em modo take")
    if len(voz.get("anchors", [])) != len(linhas) - 1:
        problemas.append("âncoras: deve haver uma por trecho a partir do 2º")
    if voz.get("maxSeconds", 99) > MAX_FALA:
        problemas.append(f"maxSeconds deve ser ≤ {MAX_FALA}")
    if not linhas or ARROBA not in linhas[-1]:
        problemas.append(f"o último trecho deve ser o CTA com {ARROBA}")
    if ARROBA not in dados.get("pronounce", {}):
        problemas.append(f"pronounce precisa dizer como falar {ARROBA}")
    if render.get("stage") != "../curiosidade.html" or cena.get("scene") not in CENAS:
        problemas.append("render deve usar ../curiosidade.html com uma cena da série")
    if (render.get("fps"), render.get("width"), render.get("height")) != (30, 1080, 1920):
        problemas.append("formato deve ser 1080x1920 a 30 fps")
    palavras = {PONTUACAO.sub("", p).lower() for linha in linhas for p in linha.split()}
    for destaque in cena.get("highlight", []):
        if destaque.lower() not in palavras:
            problemas.append(f"destaque '{destaque}' não aparece na fala")
    total = sum(len(linha.split()) for linha in linhas)
    if total > MAX_PALAVRAS:
        problemas.append(f"{total} palavras na fala; o máximo para caber em {MAX_FALA} s é {MAX_PALAVRAS}")
    return problemas


def validar_video(info):
    problemas = []
    if info["duracao"] > MAX_VIDEO:
        problemas.append(f"duração {info['duracao']:.2f} s passa de {MAX_VIDEO:.0f} s")
    if (info["largura"], info["altura"]) != (1080, 1920):
        problemas.append(f"resolução {info['largura']}x{info['altura']}, esperado 1080x1920")
    if round(info["fps"]) != 30:
        problemas.append(f"{info['fps']} fps, esperado 30")
    if info["vcodec"] != "h264" or info["pix_fmt"] != "yuv420p":
        problemas.append(f"vídeo {info['vcodec']}/{info['pix_fmt']}, esperado h264/yuv420p")
    if info["acodec"] != "aac":
        problemas.append(f"áudio {info['acodec']}, esperado aac")
    return problemas


def ler_video(caminho):
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate",
         "-of", "json", str(caminho)],
        capture_output=True, text=True, check=True).stdout
    dados = json.loads(saida)
    v = next(s for s in dados["streams"] if s["codec_type"] == "video")
    a = next((s for s in dados["streams"] if s["codec_type"] == "audio"), None)
    num, den = v["r_frame_rate"].split("/")
    return {"duracao": float(dados["format"]["duration"]), "largura": v["width"], "altura": v["height"],
            "fps": int(num) / int(den), "vcodec": v["codec_name"], "pix_fmt": v["pix_fmt"],
            "acodec": a["codec_name"] if a else None}


def moov_antes_de_mdat(caminho):
    with open(caminho, "rb") as f:
        while cabecalho := f.read(8):
            if len(cabecalho) < 8:
                break
            tamanho, tipo = int.from_bytes(cabecalho[:4], "big"), cabecalho[4:]
            if tipo in (b"moov", b"mdat"):
                return tipo == b"moov"
            if tamanho == 1:
                tamanho = int.from_bytes(f.read(8), "big") - 8
            elif tamanho == 0:
                break
            f.seek(tamanho - 8, 1)
    return False


def loudness_de(saida_ebur128):
    achado = re.search(r"Integrated loudness:\s*I:\s*(-?\d+(?:\.\d+)?) LUFS", saida_ebur128)
    return float(achado.group(1)) if achado else None


def _loudness(caminho):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(caminho), "-af", "ebur128",
                        "-f", "null", "-"], capture_output=True, text=True)
    return loudness_de(r.stderr)


def main(argumentos):
    if not 1 <= len(argumentos) <= 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    problemas = validar_reel(json.loads(Path(argumentos[0]).read_text(encoding="utf-8")))
    if len(argumentos) == 2:
        video = Path(argumentos[1])
        info = ler_video(video)
        problemas += validar_video(info)
        if not moov_antes_de_mdat(video):
            problemas.append("sem +faststart (moov depois de mdat)")
        lufs = _loudness(video)
        if lufs is None or not -17 <= lufs <= -13:
            problemas.append(f"loudness {lufs} LUFS fora de -17 a -13")
        print(f"{video.name}: {info['duracao']:.2f} s, {lufs} LUFS")
    for p in problemas:
        print(f"- {p}")
    print("ok" if not problemas else f"{len(problemas)} problema(s)")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
