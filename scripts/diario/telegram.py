"""Bot do Telegram: avisos, vídeo com botões Publicar/Descartar e leitura dos cliques (polling)."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from scripts.publicar import montar_multipart

API = "https://api.telegram.org/bot{token}/{metodo}"
CLIQUE = re.compile(r"^(pub|desc):(\d{4}-\d{2}-\d{2})$")
LIMITE_LEGENDA = 1024


class ErroTelegram(Exception):
    pass


def _post(token, metodo, campos=None, arquivo=None, timeout=120):
    url = API.format(token=token, metodo=metodo)
    campos = {k: str(v) for k, v in (campos or {}).items()}
    if arquivo:
        limite = uuid.uuid4().hex
        corpo = montar_multipart(list(campos.items()), arquivo, limite)
        cabecalhos = {"Content-Type": f"multipart/form-data; boundary={limite}"}
    else:
        corpo = urllib.parse.urlencode(campos).encode("utf-8")
        cabecalhos = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=corpo, headers=cabecalhos), timeout=timeout) as r:
            resposta = json.loads(r.read())
    except urllib.error.HTTPError as erro:
        raise ErroTelegram(f"Telegram {metodo} {erro.code}: {erro.read().decode('utf-8', 'replace')[:200]}") from None
    except urllib.error.URLError as erro:
        raise ErroTelegram(f"Telegram {metodo}: falha de rede ({type(erro.reason).__name__})") from None
    if not resposta.get("ok"):
        raise ErroTelegram(f"Telegram {metodo}: {resposta.get('description')}")
    return resposta.get("result")


def chamar(token, metodo, campos=None, arquivo=None, post=_post):
    return post(token, metodo, campos, arquivo)


def teclado(dia_iso):
    return {"inline_keyboard": [[{"text": "✅ Publicar", "callback_data": f"pub:{dia_iso}"},
                                 {"text": "🗑 Descartar", "callback_data": f"desc:{dia_iso}"}]]}


def texto_pendente(roteiro, fato, motivos):
    fontes = "\n".join(f"• {f['dominio']}" for f in fato.get("fontes", [])[:5]) or "• nenhuma"
    falas = " ".join(t["fala"] for t in roteiro["trechos"])

    # Construir cabeçalho e rodapé para preservá-los
    header = f"⏸ Aguardando aprovação: {roteiro['titulo']} ({fato.get('data', '')})\n\n"
    footer = f"\n\nFontes:\n{fontes}\n\nRoteiro: {falas}"

    # Calcular quanto espaço está disponível para motivos
    motivos_str = '; '.join(motivos)
    motivos_prefix = "Motivos: "

    max_motivos_len = LIMITE_LEGENDA - len(header) - len(footer) - len(motivos_prefix)

    if max_motivos_len < 0:
        max_motivos_len = 0

    # Truncar motivos se necessário para caber dentro do limite
    truncado = False
    if len(motivos_str) > max_motivos_len:
        motivos_str = motivos_str[:max_motivos_len]
        truncado = True

    if truncado:
        motivos_str += "…"

    texto = header + motivos_prefix + motivos_str + footer

    # Verificação final de segurança
    if len(texto) > LIMITE_LEGENDA:
        texto = texto[:LIMITE_LEGENDA - 1] + "…"

    return texto


def enviar_texto(token, chat, texto, chamar=chamar):
    return chamar(token, "sendMessage", {"chat_id": chat, "text": texto[:4096], "disable_web_page_preview": "true"})


def enviar_video(token, chat, caminho, legenda, dia_iso=None, chamar=chamar):
    campos = {"chat_id": chat, "caption": legenda[:LIMITE_LEGENDA], "supports_streaming": "true"}
    if dia_iso:
        campos["reply_markup"] = json.dumps(teclado(dia_iso))
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroTelegram(f"vídeo não encontrado: {caminho.name}")
    conteudo = caminho.read_bytes()
    return chamar(token, "sendVideo", campos, ("video", caminho.name, "video/mp4", conteudo))


def ler_cliques(token, chat, offset, chamar=chamar):
    atualizacoes = chamar(token, "getUpdates", {"offset": offset, "timeout": 0,
                                                "allowed_updates": json.dumps(["callback_query", "message"])}) or []
    cliques, novo = [], offset
    for u in atualizacoes:
        novo = max(novo, u["update_id"] + 1)
        cq = u.get("callback_query")
        if not cq or str(cq.get("message", {}).get("chat", {}).get("id")) != str(chat):
            continue
        achado = CLIQUE.match(cq.get("data") or "")
        if achado:
            cliques.append({"acao": achado.group(1), "dia": achado.group(2), "id": cq["id"],
                            "message_id": cq["message"].get("message_id")})
    return cliques, novo


def responder(token, callback_id, texto, chamar=chamar):
    return chamar(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": texto[:200]})


def remover_botoes(token, chat, message_id, chamar=chamar):
    """Tira os botões Publicar/Descartar da mensagem do vídeo (o clique já foi tratado)."""
    return chamar(token, "editMessageReplyMarkup", {"chat_id": chat, "message_id": message_id,
                                                    "reply_markup": json.dumps({"inline_keyboard": []})})


def chats(token, chamar=chamar):
    vistos = []
    for u in chamar(token, "getUpdates", {"timeout": 0}) or []:
        chat = (u.get("message") or {}).get("chat")
        if chat and (str(chat["id"]), chat.get("first_name") or chat.get("title", "")) not in vistos:
            vistos.append((str(chat["id"]), chat.get("first_name") or chat.get("title", "")))
    return vistos
