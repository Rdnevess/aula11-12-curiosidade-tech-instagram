"""Fluxo diário: rodar (pesquisa → vídeo → trava → publica ou pede aprovação) e verificar (cliques do Telegram)."""
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from scripts.diario import config, historico, trava
from scripts.diario.gemini import ErroGemini
from scripts.diario.openai_busca import ErroOpenAI
from scripts.diario.pesquisa import ErroPesquisa

TENTATIVAS_PESQUISA = 2


@dataclass
class Dependencias:
    historico_carregar: Callable
    historico_atualizar: Callable
    prechecar: Callable
    pesquisar: Callable
    gerar_roteiro: Callable
    montar: Callable
    confirmar: Callable
    publicar: Callable
    avisar_texto: Callable
    avisar_video: Callable
    ler_cliques: Callable
    responder: Callable
    remover_botoes: Callable
    offset_ler: Callable
    offset_salvar: Callable
    salvar_json: Callable
    hoje: Callable = date.today

    @classmethod
    def reais(cls):
        from scripts.diario import montar, pesquisa, roteiro, telegram
        from scripts.n8n_api import api
        from scripts.publicar import publicar_arquivo

        k = config.chaves()
        token, chat = k["TELEGRAM_BOT_TOKEN"], k["TELEGRAM_CHAT_ID"]

        def prechecar():
            faltando = [n for n, v in k.items() if not v]
            if faltando:
                raise RuntimeError(f"faltam no .env: {', '.join(faltando)}")
            if "out_range=tv" not in (config.SKILL / "render.mjs").read_text(encoding="utf-8"):
                raise RuntimeError("render.mjs da skill sem o ajuste out_range=tv (veja a memória do projeto)")
            api("GET", "/workflows?limit=1")

        def salvar_json(pasta, nome, dados):
            Path(pasta).mkdir(parents=True, exist_ok=True)
            (Path(pasta) / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

        return cls(
            historico_carregar=historico.carregar,
            historico_atualizar=historico.atualizar,
            prechecar=prechecar,
            pesquisar=lambda dia, usados: pesquisa.pesquisar(dia, usados, k["OPENAI_API_KEY"], config.MODELO_PESQUISA),
            gerar_roteiro=lambda fato: roteiro.gerar_roteiro(fato, k["GEMINI_API_KEY"], config.MODELO),
            montar=montar.montar,
            confirmar=lambda fato, numeros: pesquisa.confirmar(fato, numeros, k["OPENAI_API_KEY"],
                                                               config.MODELO_PESQUISA),
            publicar=publicar_arquivo,
            avisar_texto=lambda texto: telegram.enviar_texto(token, chat, texto),
            avisar_video=lambda mp4, legenda, dia_iso: telegram.enviar_video(token, chat, mp4, legenda, dia_iso),
            ler_cliques=lambda offset: telegram.ler_cliques(token, chat, offset),
            responder=lambda cid, texto: telegram.responder(token, cid, texto),
            remover_botoes=lambda message_id: telegram.remover_botoes(token, chat, message_id),
            offset_ler=lambda: int(config.OFFSET.read_text()) if config.OFFSET.exists() else 0,
            offset_salvar=lambda o: (config.OFFSET.parent.mkdir(parents=True, exist_ok=True),
                                     config.OFFSET.write_text(str(o))),
            salvar_json=salvar_json,
        )


def mensagem_erro(etapa, erro):
    texto = str(erro)
    if "Invalid OAuth" in texto:
        return (f"❌ falhou em {etapa}: o token do Instagram foi recusado. "
                "Renove a credencial Instagram TEP no n8n e aprove o vídeo pendente depois.")
    return f"❌ falhou em {etapa}: {texto[:500]}"


def _fontes(fato):
    return ", ".join(sorted({f["dominio"] for f in fato.get("fontes", [])})) or "nenhuma"


def _aviso_pos_publicacao(permalink, erro):
    return f"⚠️ publicado ({permalink}), mas falhou ao salvar o histórico: {erro}"


def _tentar(funcao, *args):
    """Chamada de melhor esforço: uma falha aqui não pode interromper o fluxo."""
    try:
        funcao(*args)
        return True
    except Exception:
        return False


def texto_erro_publicacao(titulo, erro):
    texto = (f"❌ a publicação de {titulo} falhou ou não pôde ser confirmada — "
             f"confira o Instagram antes de tentar de novo: {str(erro)[:500]}")
    if "Invalid OAuth" in str(erro):
        texto += "\n(o token do Instagram foi recusado: renove a credencial Instagram TEP no n8n)"
    return texto


def _publicar(d, dia_iso, titulo, video, legenda, campos=None, rodape=""):
    """Publica com o histórico sempre à frente: "publicando" antes, "publicado"/"erro_publicacao" depois.

    Uma exceção depois do envio (tempo esgotado, link ausente...) não prova que o post não foi ao ar,
    por isso o dia fica "erro_publicacao": não é publicado de novo sozinho nem por um novo clique.
    Devolve (resultado, None) ou (None, erro) — o erro já foi avisado no Telegram.
    """
    d.historico_atualizar(dia_iso, {**(campos or {}), "status": "publicando"})
    try:
        resultado = d.publicar(video, legenda)
    except Exception as erro:
        _tentar(d.historico_atualizar, dia_iso, {"status": "erro_publicacao", "erro": str(erro)[:500]})
        _tentar(d.avisar_texto, texto_erro_publicacao(titulo, erro))
        return None, erro
    # Publicação já aconteceu: uma falha daqui em diante não pode parecer falha de publicação.
    try:
        d.historico_atualizar(dia_iso, {"status": "publicado", "permalink": resultado["permalink"],
                                        "publicado_em": datetime.now().astimezone().isoformat(timespec="seconds")})
    except Exception as erro_pos:
        _tentar(d.avisar_texto, _aviso_pos_publicacao(resultado["permalink"], erro_pos))
        return resultado, None
    _tentar(d.avisar_texto, f"✅ Publicado: {titulo}\n{resultado['permalink']}{rodape}")
    return resultado, None


def rodar(dia, sem_publicar=False, d=None):
    from scripts.diario.roteiro import numeros_do_roteiro
    from scripts.diario.telegram import texto_pendente

    d = d or Dependencias.reais()
    chave = dia.isoformat()
    etapa = "histórico"
    avisado = False
    try:
        hist = d.historico_carregar()
        if not sem_publicar and historico.ja_resolvido(hist, chave):
            return "pulado"
        etapa = "pré-checagem"
        d.prechecar()
        etapa = "pesquisa"
        usados = historico.temas(hist)
        for tentativa_pesquisa in range(1, TENTATIVAS_PESQUISA + 1):
            try:
                fato = d.pesquisar(dia, usados)
                break
            except (ErroPesquisa, ErroGemini, ErroOpenAI):
                # A busca da OpenAI às vezes traz outro dia, um tema repetido, JSON quebrado ou falha da API: tenta mais uma vez.
                if tentativa_pesquisa == TENTATIVAS_PESQUISA:
                    raise
        etapa = "roteiro"
        roteiro, tentativa = d.gerar_roteiro(fato)
        pasta = config.pasta_do_dia(dia, ensaio=sem_publicar)
        d.salvar_json(pasta, "pesquisa.json", fato)
        d.salvar_json(pasta, "roteiro.json", roteiro)
        etapa = "vídeo"
        mp4, problemas = d.montar(pasta, roteiro)
        etapa = "checagem cruzada"
        confirmacao = d.confirmar(fato, numeros_do_roteiro(roteiro))
        d.salvar_json(pasta, "checagem.json", confirmacao)
        ok, motivos = trava.decidir(fato, confirmacao, tentativa, problemas, historico.repetido(hist, roteiro["titulo"]))
        if sem_publicar:
            d.avisar_texto(f"🧪 ensaio {chave}: {roteiro['titulo']} — "
                           f"{'publicaria sozinho' if ok else 'seguraria: ' + '; '.join(motivos)}")
            return "ensaio"
        base = {"titulo": roteiro["titulo"], "fontes": fato.get("fontes", []), "video": str(mp4),
                "legenda_post": roteiro["legenda_post"], "pasta": str(pasta)}
        if ok:
            etapa = "publicação"
            _, erro_pub = _publicar(d, chave, roteiro["titulo"], mp4, roteiro["legenda_post"], base,
                                    f"\nFontes: {_fontes(fato)}")
            if erro_pub:
                avisado = True
                raise erro_pub
            return "publicado"
        etapa = "histórico"
        d.historico_atualizar(chave, {**base, "status": "pendente", "motivos": motivos})
        etapa = "aviso no Telegram"
        d.avisar_video(mp4, texto_pendente(roteiro, fato, motivos), chave)
        return "pendente"
    except Exception as erro:
        if not avisado:
            d.avisar_texto(mensagem_erro(etapa, erro))
        raise


def _tratar_clique(d, clique):
    dia_iso = clique["dia"]
    # Relido a cada clique: rodar pode ter gravado algo, e um clique anterior do mesmo lote também.
    registro = d.historico_carregar().get(dia_iso)
    if not registro or registro.get("status") != "pendente":
        _tentar(d.responder, clique["id"], "Esse dia já resolvido: nada a fazer.")
        return
    if clique["acao"] == "desc":
        d.historico_atualizar(dia_iso, {"status": "descartado"})
        _tentar(d.responder, clique["id"], "Descartado.")
        _tentar(d.avisar_texto, f"🗑 Descartado: {registro.get('titulo', dia_iso)}")
        return
    if dia_iso != d.hoje().isoformat():
        # O vídeo diz "hoje" e traz o selo do dia: publicá-lo em outro dia estaria errado.
        d.historico_atualizar(dia_iso, {"status": "expirado"})
        _tentar(d.responder, clique["id"], "Expirou.")
        _tentar(d.avisar_texto, f"⌛ expirou: o vídeo era para {dia_iso[8:10]}/{dia_iso[5:7]} "
                                f"({registro.get('titulo', '')}); não foi publicado.")
        return
    _, erro = _publicar(d, dia_iso, registro["titulo"], Path(registro["video"]), registro["legenda_post"])
    _tentar(d.responder, clique["id"], "Falhou; veja a mensagem." if erro else "Publicado!")


def verificar(d=None):
    d = d or Dependencias.reais()
    cliques, novo = d.ler_cliques(d.offset_ler())
    try:
        for clique in cliques:
            try:
                _tratar_clique(d, clique)
            except Exception as erro:
                _tentar(d.avisar_texto, mensagem_erro(f"clique {clique['acao']} de {clique['dia']}", erro))
            if clique.get("message_id") is not None:
                # Melhor esforço: com polling a cada 10 min, o Telegram pode recusar mexer em cliques antigos.
                _tentar(d.remover_botoes, clique["message_id"])
    finally:
        d.offset_salvar(novo)
    return len(cliques)
