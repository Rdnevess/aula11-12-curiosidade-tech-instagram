"""Fluxo diário: rodar (pesquisa → vídeo → trava → publica ou pede aprovação) e verificar (cliques do Telegram)."""
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from scripts.diario import config, historico, trava


@dataclass
class Dependencias:
    historico_carregar: Callable
    historico_salvar: Callable
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
    offset_ler: Callable
    offset_salvar: Callable
    salvar_json: Callable

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
            historico_salvar=historico.salvar,
            prechecar=prechecar,
            pesquisar=lambda dia, usados: pesquisa.pesquisar(dia, usados, k["GEMINI_API_KEY"], config.MODELO),
            gerar_roteiro=lambda fato: roteiro.gerar_roteiro(fato, k["GEMINI_API_KEY"], config.MODELO),
            montar=montar.montar,
            confirmar=lambda fato, numeros: pesquisa.confirmar(fato, numeros, k["GEMINI_API_KEY"], config.MODELO),
            publicar=publicar_arquivo,
            avisar_texto=lambda texto: telegram.enviar_texto(token, chat, texto),
            avisar_video=lambda mp4, legenda, dia_iso: telegram.enviar_video(token, chat, mp4, legenda, dia_iso),
            ler_cliques=lambda offset: telegram.ler_cliques(token, chat, offset),
            responder=lambda cid, texto: telegram.responder(token, cid, texto),
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


def rodar(dia, sem_publicar=False, d=None):
    from scripts.diario.roteiro import numeros_do_roteiro
    from scripts.diario.telegram import texto_pendente

    d = d or Dependencias.reais()
    hist, chave = d.historico_carregar(), dia.isoformat()
    if not sem_publicar and historico.ja_resolvido(hist, chave):
        return "pulado"
    etapa = "pré-checagem"
    try:
        d.prechecar()
        etapa = "pesquisa"
        fato = d.pesquisar(dia, historico.temas(hist))
        etapa = "roteiro"
        roteiro, tentativa = d.gerar_roteiro(fato)
        pasta = config.pasta_do_dia(dia)
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
            resultado = d.publicar(mp4, roteiro["legenda_post"])
            historico.registrar(hist, chave, {**base, "status": "publicado", "permalink": resultado["permalink"],
                                              "publicado_em": datetime.now().astimezone().isoformat(timespec="seconds")})
            d.historico_salvar(hist)
            d.avisar_texto(f"✅ Publicado: {roteiro['titulo']}\n{resultado['permalink']}\nFontes: {_fontes(fato)}")
            return "publicado"
        historico.registrar(hist, chave, {**base, "status": "pendente", "motivos": motivos})
        d.historico_salvar(hist)
        d.avisar_video(mp4, texto_pendente(roteiro, fato, motivos), chave)
        return "pendente"
    except Exception as erro:
        d.avisar_texto(mensagem_erro(etapa, erro))
        raise


def verificar(d=None):
    d = d or Dependencias.reais()
    hist = d.historico_carregar()
    cliques, novo = d.ler_cliques(d.offset_ler())
    for clique in cliques:
        registro = hist.get(clique["dia"])
        if not registro or registro.get("status") != "pendente":
            d.responder(clique["id"], "Esse dia já resolvido: nada a fazer.")
            continue
        if clique["acao"] == "desc":
            registro["status"] = "descartado"
            d.historico_salvar(hist)
            d.responder(clique["id"], "Descartado.")
            continue
        try:
            resultado = d.publicar(Path(registro["video"]), registro["legenda_post"])
        except Exception as erro:
            d.responder(clique["id"], "Falhou; veja a mensagem.")
            d.avisar_texto(mensagem_erro("publicação", erro))
            continue
        registro.update(status="publicado", permalink=resultado["permalink"],
                        publicado_em=datetime.now().astimezone().isoformat(timespec="seconds"))
        d.historico_salvar(hist)
        d.responder(clique["id"], "Publicado!")
        d.avisar_texto(f"✅ Publicado: {registro['titulo']}\n{resultado['permalink']}")
    d.offset_salvar(novo)
    return len(cliques)
