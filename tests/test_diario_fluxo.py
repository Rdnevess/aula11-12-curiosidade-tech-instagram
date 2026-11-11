import copy
import unittest
from datetime import date
from pathlib import Path

from scripts.diario import fluxo, historico
from scripts.diario.gemini import ErroGemini
from scripts.diario.openai_busca import ErroOpenAI
from scripts.diario.pesquisa import ErroPesquisa, TemaRepetido

FATO = {"titulo": "Sputnik 2", "data": "1957-11-03", "fato": "…", "numeros": [], "fontes": [
    {"dominio": "wikipedia.org", "url": "a"}, {"dominio": "nasa.gov", "url": "b"}]}
ROTEIRO = {"titulo": "Sputnik 2", "trechos": [{"fala": "Oi."}], "legenda_post": "legenda"}
CONF_OK = {"data_confirmada": True, "numeros": [], "fontes": FATO["fontes"]}
DIA = date(2026, 11, 3)
GRAVE = ["duração 55.0 s acima de 50.0 s"]  # defeito técnico do vídeo: segura para aprovação


def deps(conf=CONF_OK, historico=None, cliques=(), publicar_erro=None, hoje=DIA, problemas_video=()):
    estado = {"hist": historico if historico is not None else {}, "textos": [], "videos": [], "publicados": [],
              "respostas": [], "offset": 0, "botoes": []}

    def atualizar(dia_iso, campos):
        estado["hist"].setdefault(dia_iso, {}).update(campos)

    def publicar(mp4, legenda):
        if publicar_erro:
            raise publicar_erro
        estado["publicados"].append((mp4, legenda))
        return {"permalink": "https://instagram/p/1", "media_id": "1789"}

    d = fluxo.Dependencias(
        historico_carregar=lambda: copy.deepcopy(estado["hist"]),
        historico_atualizar=atualizar,
        prechecar=lambda: None,
        pesquisar=lambda dia, hist, rejeitados: dict(FATO),
        gerar_roteiro=lambda fato: (ROTEIRO, 1),
        montar=lambda pasta, roteiro: (Path("out.mp4"), list(problemas_video)),
        confirmar=lambda fato, numeros: conf,
        publicar=publicar,
        avisar_texto=lambda t: estado["textos"].append(t),
        avisar_video=lambda mp4, legenda, dia_iso: estado["videos"].append((mp4, dia_iso)),
        ler_cliques=lambda offset: (list(cliques), offset + len(cliques)),
        responder=lambda cid, texto: estado["respostas"].append((cid, texto)),
        remover_botoes=lambda message_id: estado["botoes"].append(message_id),
        offset_ler=lambda: estado["offset"],
        offset_salvar=lambda o: estado.update(offset=o),
        salvar_json=lambda pasta, nome, dados: None,
        hoje=lambda: hoje,
    )
    return d, estado



class RodarTest(unittest.TestCase):
    def test_publica_quando_a_trava_aprova(self):
        d, e = deps()
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "legenda")])
        registro = e["hist"]["2026-11-03#1"]
        self.assertEqual(registro["status"], "publicado")
        self.assertEqual(registro["media_id"], "1789")
        self.assertEqual(registro["fato"], FATO["fato"])
        self.assertEqual(registro["fontes"], FATO["fontes"])
        self.assertEqual(registro["falas"], ["Oi."])
        self.assertIn("✅", e["textos"][-1])

    def test_segura_e_manda_video(self):
        d, e = deps(problemas_video=GRAVE)
        self.assertEqual(fluxo.rodar(DIA, d=d), "pendente")
        self.assertEqual(e["publicados"], [])
        self.assertEqual(e["videos"], [(Path("out.mp4"), "2026-11-03#1")])
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "pendente")

    def test_suspeitas_leves_publicam_e_avisam_os_motivos(self):
        # Pedido do usuário (10/11/2026): sem esperar aprovação; o aviso diz por que o post é suspeito.
        d, e = deps(conf={**CONF_OK, "data_confirmada": False})
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "legenda")])
        self.assertEqual(e["videos"], [])
        registro = e["hist"]["2026-11-03#1"]
        self.assertEqual(registro["status"], "publicado")
        self.assertEqual(registro["suspeitas"], ["a checagem cruzada não confirmou a data"])
        self.assertIn("suspeitas", e["textos"][-1])
        self.assertIn("a checagem cruzada não confirmou a data", e["textos"][-1])

    def test_sem_suspeitas_aviso_normal(self):
        d, e = deps()
        fluxo.rodar(DIA, d=d)
        self.assertNotIn("suspeitas", e["textos"][-1])
        self.assertEqual(e["hist"]["2026-11-03#1"].get("suspeitas"), [])

    def test_idempotente(self):
        d, e = deps(historico={"2026-11-03#1": {"titulo": "x", "status": "publicado"}})
        self.assertEqual(fluxo.rodar(DIA, d=d), "pulado")
        self.assertEqual(e["publicados"], [])

    def test_ensaio_nao_publica_nem_marca(self):
        d, e = deps()
        self.assertEqual(fluxo.rodar(DIA, sem_publicar=True, d=d), "ensaio")
        self.assertEqual(e["publicados"], [])
        self.assertNotIn("2026-11-03#1", e["hist"])
        self.assertIn("ensaio", e["textos"][-1])

    def test_ensaio_usa_pasta_propria(self):
        d, e = deps()
        pastas = []
        d.montar = lambda pasta, roteiro: (pastas.append(pasta), (Path("out.mp4"), []))[1]
        fluxo.rodar(DIA, sem_publicar=True, d=d)
        self.assertEqual(pastas[0].name, "diario-2026-11-03-1-ensaio")

    def test_erro_avisa_e_propaga(self):
        d, e = deps(publicar_erro=RuntimeError("execução 9: error — Invalid OAuth 2.0 Access Token"))
        with self.assertRaises(RuntimeError):
            fluxo.rodar(DIA, d=d)
        self.assertIn("Instagram TEP", e["textos"][-1])
        self.assertEqual(len([t for t in e["textos"] if t.startswith("❌")]), 1)

    def test_marca_publicando_antes_de_publicar(self):
        d, e = deps()
        vistos = []
        publicar_original = d.publicar
        d.publicar = lambda mp4, legenda: (vistos.append(e["hist"]["2026-11-03#1"]["status"]),
                                           publicar_original(mp4, legenda))[1]
        fluxo.rodar(DIA, d=d)
        self.assertEqual(vistos, ["publicando"])
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "publicado")

    def test_publicar_falha_marca_erro_publicacao_e_nao_repete(self):
        d, e = deps(publicar_erro=TimeoutError("timed out"))
        with self.assertRaises(TimeoutError):
            fluxo.rodar(DIA, d=d)
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "erro_publicacao")
        self.assertIn("a publicação de Sputnik 2 falhou ou não pôde ser confirmada", e["textos"][-1])
        self.assertIn("confira o Instagram", e["textos"][-1])
        self.assertIn("timed out", e["textos"][-1])
        self.assertEqual(fluxo.rodar(DIA, d=d), "pulado")

    def test_historico_carregar_falha_avisa_e_propaga(self):
        d, e = deps()

        def quebra():
            raise RuntimeError("disco cheio")

        d.historico_carregar = quebra
        with self.assertRaises(RuntimeError):
            fluxo.rodar(DIA, d=d)
        self.assertIn("histórico", e["textos"][-1])

    def test_falha_ao_salvar_historico_apos_publicar_nao_reporta_falha_na_publicacao(self):
        d, e = deps()
        chamadas = []

        atualizar_original = d.historico_atualizar

        def historico_atualizar_quebrado(dia_iso, campos):
            if campos.get("status") == "publicado":
                chamadas.append(campos)
                raise RuntimeError("disco cheio")
            atualizar_original(dia_iso, campos)

        d.historico_atualizar = historico_atualizar_quebrado
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "legenda")])
        self.assertEqual(len(chamadas), 1)
        self.assertFalse(any("falhou em publicação" in t for t in e["textos"]))
        self.assertTrue(any("⚠️" in t for t in e["textos"]))

    def test_pendente_falha_no_aviso_reporta_etapa_aviso_no_telegram(self):
        d, e = deps(problemas_video=GRAVE)

        def avisar_video_quebrado(mp4, legenda, dia_iso):
            raise RuntimeError("telegram fora")

        d.avisar_video = avisar_video_quebrado
        with self.assertRaises(RuntimeError):
            fluxo.rodar(DIA, d=d)
        self.assertIn("aviso no Telegram", e["textos"][-1])

    def _pesquisa_que_falha(self, d, erros):
        chamadas = []
        self.rejeitados_vistos = []

        def pesquisar(dia, hist, rejeitados):
            chamadas.append(historico.temas(hist))
            self.rejeitados_vistos.append(list(rejeitados))
            if erros:
                raise erros.pop(0)
            return dict(FATO)

        d.pesquisar = pesquisar
        return chamadas

    def test_pesquisa_tenta_de_novo_uma_vez(self):
        d, e = deps(historico={"x": {"titulo": "Usado", "status": "manual"}})
        chamadas = self._pesquisa_que_falha(d, [ErroPesquisa("a pesquisa trouxe outro dia")])
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(chamadas, [["Usado"], ["Usado"]])

    def test_pesquisa_falha_tres_vezes_avisa(self):
        d, e = deps()
        chamadas = self._pesquisa_que_falha(d, [ErroGemini("vazio"), ErroPesquisa("outro dia"),
                                                ErroPesquisa("tema já usado")])
        with self.assertRaises(ErroPesquisa):
            fluxo.rodar(DIA, d=d)
        self.assertEqual(len(chamadas), 3)
        self.assertIn("falhou em pesquisa", e["textos"][-1])

    def test_tema_repetido_seguido_de_outro_dia_ainda_tenta_a_terceira(self):
        # Ensaio real de 04/11: 1ª tentativa repetiu o UNIVAC, a 2ª trouxe outro dia; com 2 tentativas o dia ficava sem post.
        d, e = deps()
        chamadas = self._pesquisa_que_falha(d, [TemaRepetido("x", "UNIVAC acerta"), ErroPesquisa("outro dia")])
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(len(chamadas), 3)
        self.assertEqual(self.rejeitados_vistos[-1], ["UNIVAC acerta"])

    def test_pesquisa_erro_openai_tenta_de_novo_uma_vez(self):
        d, e = deps(historico={"x": {"titulo": "Usado", "status": "manual"}})
        chamadas = self._pesquisa_que_falha(d, [ErroOpenAI("OpenAI 429: rate limit")])
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(chamadas, [["Usado"], ["Usado"]])

    def test_tema_repetido_tenta_tres_vezes_e_passa_o_rejeitado(self):
        d, e = deps()
        chamadas = self._pesquisa_que_falha(d, [TemaRepetido("tema já usado: A", "A"),
                                                TemaRepetido("tema já usado: B", "B")])
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(len(chamadas), 3)
        self.assertEqual(self.rejeitados_vistos, [[], ["A"], ["A", "B"]])

    def test_tema_repetido_tres_vezes_avisa(self):
        d, e = deps()
        chamadas = self._pesquisa_que_falha(d, [TemaRepetido("x", "A"), TemaRepetido("x", "B"),
                                                TemaRepetido("tema já usado: C", "C")])
        with self.assertRaises(TemaRepetido):
            fluxo.rodar(DIA, d=d)
        self.assertEqual(len(chamadas), 3)
        self.assertIn("falhou em pesquisa", e["textos"][-1])

    def test_historico_guarda_titulo_da_pesquisa_e_data_do_evento(self):
        d, e = deps()
        d.gerar_roteiro = lambda fato: ({**ROTEIRO, "titulo": "O Cão no Espaço"}, 1)
        fluxo.rodar(DIA, d=d)
        registro = e["hist"]["2026-11-03#1"]
        self.assertEqual(registro["titulo"], "O Cão no Espaço")
        self.assertEqual(registro["titulo_pesquisa"], "Sputnik 2")
        self.assertEqual(registro["data_evento"], "1957-11-03")

    def test_pendente_tambem_guarda_titulo_da_pesquisa_e_data(self):
        d, e = deps(problemas_video=GRAVE)
        fluxo.rodar(DIA, d=d)
        self.assertEqual(e["hist"]["2026-11-03#1"]["data_evento"], "1957-11-03")
        self.assertEqual(e["hist"]["2026-11-03#1"]["titulo_pesquisa"], "Sputnik 2")

    def test_trava_segura_mesmo_acontecimento_com_outro_titulo(self):
        # Caso real (UNIVAC): a pesquisa falsa não filtra; a trava precisa pegar pela data do evento.
        d, e = deps(historico={"2026-11-03#1": {"titulo": "Outro nome", "titulo_pesquisa": "Cadela no espaço",
                                                "data_evento": "1957-11-03", "status": "publicado"}})
        self.assertEqual(fluxo.rodar(DIA, slot=2, d=d), "pendente")
        self.assertTrue(any("tema já publicado antes" in m for m in e["hist"]["2026-11-03#2"]["motivos"]))

    def test_pesquisa_outros_erros_nao_repetem(self):
        d, e = deps()
        chamadas = self._pesquisa_que_falha(d, [RuntimeError("HTTP 403")])
        with self.assertRaises(RuntimeError):
            fluxo.rodar(DIA, d=d)
        self.assertEqual(len(chamadas), 1)

    def test_rodar_nao_apaga_o_que_verificar_gravou_durante_a_montagem(self):
        hist = {"2026-11-02#1": {"titulo": "Ontem", "status": "pendente", "video": "v.mp4", "legenda_post": "l"}}
        d, e = deps(problemas_video=GRAVE, historico=hist)

        def montar_demorado(pasta, roteiro):
            # verificar roda em paralelo e descarta o pendente de ontem
            d.historico_atualizar("2026-11-02#1", {"status": "descartado"})
            return Path("out.mp4"), GRAVE

        d.montar = montar_demorado
        self.assertEqual(fluxo.rodar(DIA, d=d), "pendente")
        self.assertEqual(e["hist"]["2026-11-02#1"]["status"], "descartado")
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "pendente")


class SlotsRodarTest(unittest.TestCase):
    def test_slot_2_usa_chave_e_pasta_proprias(self):
        d, e = deps(problemas_video=GRAVE)
        pastas = []
        d.montar = lambda pasta, roteiro: (pastas.append(pasta), (Path("out.mp4"), GRAVE))[1]
        self.assertEqual(fluxo.rodar(DIA, slot=2, d=d), "pendente")
        self.assertEqual(e["hist"]["2026-11-03#2"]["status"], "pendente")
        self.assertNotIn("2026-11-03#1", e["hist"])
        self.assertEqual(e["videos"], [(Path("out.mp4"), "2026-11-03#2")])
        self.assertEqual(pastas[0].name, "diario-2026-11-03-2")

    def test_slot_2_roda_mesmo_com_slot_1_resolvido(self):
        d, e = deps(historico={"2026-11-03#1": {"titulo": "Manhã", "status": "publicado"}})
        self.assertEqual(fluxo.rodar(DIA, slot=2, d=d), "publicado")
        self.assertEqual(e["hist"]["2026-11-03#2"]["status"], "publicado")
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "publicado")

    def test_slot_2_idempotente_sem_afetar_slot_1(self):
        d, e = deps(historico={"2026-11-03#2": {"titulo": "x", "status": "pendente"}})
        self.assertEqual(fluxo.rodar(DIA, slot=2, d=d), "pulado")
        self.assertEqual(fluxo.rodar(DIA, slot=1, d=d), "publicado")
        self.assertEqual(e["hist"]["2026-11-03#2"]["status"], "pendente")

    def test_chave_legada_do_dia_bloqueia_so_o_slot_1(self):
        d, e = deps(historico={"2026-11-03": {"titulo": "Mariner 10", "status": "publicado"}})
        self.assertEqual(fluxo.rodar(DIA, slot=1, d=d), "pulado")
        self.assertEqual(fluxo.rodar(DIA, slot=2, d=d), "publicado")
        self.assertEqual(e["hist"]["2026-11-03"], {"titulo": "Mariner 10", "status": "publicado"})

    def test_slot_2_recebe_o_tema_do_slot_1_do_mesmo_dia(self):
        d, e = deps(historico={"2026-11-03#1": {"titulo": "Tema da manhã", "status": "publicado"},
                               "manual-x": {"titulo": "Semente", "status": "manual"}})
        vistos = []
        d.pesquisar = lambda dia, hist, rejeitados: (vistos.append(historico.temas(hist)), dict(FATO))[1]
        fluxo.rodar(DIA, slot=2, d=d)
        self.assertIn("Tema da manhã", vistos[0])
        self.assertIn("Semente", vistos[0])

    def test_mensagens_citam_o_horario_do_slot(self):
        d, e = deps()
        fluxo.rodar(DIA, slot=2, d=d)
        self.assertTrue(e["textos"][-1].startswith("✅"))
        self.assertIn("18h", e["textos"][-1])

    def test_ensaio_do_slot_2_usa_pasta_propria(self):
        d, e = deps()
        pastas = []
        d.montar = lambda pasta, roteiro: (pastas.append(pasta), (Path("out.mp4"), []))[1]
        self.assertEqual(fluxo.rodar(DIA, slot=2, sem_publicar=True, d=d), "ensaio")
        self.assertEqual(pastas[0].name, "diario-2026-11-03-2-ensaio")
        self.assertIn("18h", e["textos"][-1])
        self.assertEqual(e["hist"], {})


class PublicarPendenteTest(unittest.TestCase):
    def test_publica_o_pendente_de_hoje(self):
        hist = {"2026-11-03#1": {"titulo": "Sputnik 2", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        d, e = deps(historico=hist)
        self.assertEqual(fluxo.publicar_pendente("2026-11-03#1", d=d), "publicado")
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "leg")])
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "publicado")

    def test_nao_publica_o_que_nao_esta_pendente(self):
        d, e = deps(historico={"2026-11-03#1": {"titulo": "S", "status": "publicado", "video": "v", "legenda_post": "l"}})
        self.assertEqual(fluxo.publicar_pendente("2026-11-03#1", d=d), "nada a fazer: status publicado")
        self.assertEqual(e["publicados"], [])

    def test_nao_publica_pendente_de_outro_dia(self):
        hist = {"2026-11-02#1": {"titulo": "Ontem", "status": "pendente", "video": "v", "legenda_post": "l"}}
        d, e = deps(historico=hist)
        self.assertIn("outro dia", fluxo.publicar_pendente("2026-11-02#1", d=d))
        self.assertEqual(e["publicados"], [])

    def test_falha_na_publicacao_propaga(self):
        hist = {"2026-11-03#1": {"titulo": "S", "status": "pendente", "video": "v", "legenda_post": "l"}}
        d, e = deps(historico=hist, publicar_erro=RuntimeError("Invalid OAuth"))
        with self.assertRaises(RuntimeError):
            fluxo.publicar_pendente("2026-11-03#1", d=d)
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "erro_publicacao")


class VerificarTest(unittest.TestCase):
    def test_publica_pendente_e_ignora_resolvido(self):
        hist = {"2026-11-03#1": {"titulo": "Sputnik 2", "status": "pendente", "video": "out.mp4", "legenda_post": "leg",
                                 "fato": FATO["fato"], "fontes": FATO["fontes"], "falas": ["Oi."]},
                "2026-11-02#1": {"titulo": "y", "status": "publicado"}}
        cliques = [{"acao": "pub", "chave": "2026-11-03#1", "id": "a"}, {"acao": "pub", "chave": "2026-11-02#1", "id": "b"}]
        d, e = deps(historico=hist, cliques=cliques)
        self.assertEqual(fluxo.verificar(d), 2)
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "leg")])
        registro = e["hist"]["2026-11-03#1"]
        self.assertEqual(registro["status"], "publicado")
        self.assertEqual(registro["media_id"], "1789")
        self.assertEqual(registro["fato"], FATO["fato"])
        self.assertEqual(registro["fontes"], FATO["fontes"])
        self.assertIn("já resolvido", e["respostas"][1][1])
        self.assertEqual(e["offset"], 2)

    def test_descarta(self):
        hist = {"2026-11-03#1": {"titulo": "S", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        d, e = deps(historico=hist, cliques=[{"acao": "desc", "chave": "2026-11-03#1", "id": "a"}])
        fluxo.verificar(d)
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "descartado")
        self.assertEqual(e["publicados"], [])

    def test_publicar_falha_marca_erro_publicacao_e_novo_clique_nao_faz_nada(self):
        hist = {"2026-11-03#1": {"titulo": "S", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        erro = RuntimeError("execução 9: error — Invalid OAuth 2.0 Access Token")
        cliques = [{"acao": "pub", "chave": "2026-11-03#1", "id": "a"}, {"acao": "pub", "chave": "2026-11-03#1", "id": "b"}]
        d, e = deps(historico=hist, cliques=cliques, publicar_erro=erro)
        self.assertEqual(fluxo.verificar(d), 2)
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "erro_publicacao")
        self.assertEqual(e["publicados"], [])
        self.assertEqual(e["respostas"][0], ("a", "Falhou; veja a mensagem."))
        self.assertIn("já resolvido", e["respostas"][1][1])
        avisos = [t for t in e["textos"] if t.startswith("❌")]
        self.assertEqual(len(avisos), 1)
        self.assertIn("a publicação de S falhou ou não pôde ser confirmada", avisos[0])
        self.assertIn("Instagram TEP", avisos[0])

    def test_falha_ao_salvar_historico_apos_publicar_continua_e_salva_offset(self):
        hist = {"2026-11-03#1": {"titulo": "Sputnik 2", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        cliques = [{"acao": "pub", "chave": "2026-11-03#1", "id": "a"}]
        d, e = deps(historico=hist, cliques=cliques)
        chamadas = []

        atualizar_original = d.historico_atualizar

        def historico_atualizar_quebrado(dia_iso, campos):
            if campos.get("status") == "publicado":
                chamadas.append(campos)
                raise RuntimeError("disco cheio")
            atualizar_original(dia_iso, campos)

        d.historico_atualizar = historico_atualizar_quebrado
        self.assertEqual(fluxo.verificar(d), 1)
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "leg")])
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(e["offset"], 1)
        self.assertFalse(any("falhou em publicação" in t for t in e["textos"]))
        self.assertTrue(any("⚠️" in t for t in e["textos"]))


    def test_responder_quebrado_nao_interrompe_nem_esconde_avisos(self):
        hist = {"2026-11-03#1": {"titulo": "Sputnik 2", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"},
                "2026-11-01#1": {"titulo": "Velho", "status": "pendente", "video": "v.mp4", "legenda_post": "l"}}
        cliques = [{"acao": "pub", "chave": "2026-11-03#1", "id": "a", "message_id": 7},
                   {"acao": "desc", "chave": "2026-11-01#1", "id": "b", "message_id": 8}]
        d, e = deps(historico=hist, cliques=cliques)

        def responder(cid, texto):
            raise RuntimeError("Telegram answerCallbackQuery: Bad Request: query is too old")

        def remover_botoes(message_id):
            e["botoes"].append(message_id)
            raise RuntimeError("message is not modified")

        d.responder, d.remover_botoes = responder, remover_botoes
        self.assertEqual(fluxo.verificar(d), 2)
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "publicado")
        self.assertEqual(e["hist"]["2026-11-01#1"]["status"], "descartado")
        self.assertTrue(any(t.startswith("✅") for t in e["textos"]))
        self.assertTrue(any(t.startswith("🗑") and "Velho" in t for t in e["textos"]))
        self.assertEqual(e["botoes"], [7, 8])
        self.assertEqual(e["offset"], 2)

    def test_responder_quebrado_nao_esconde_falha_de_publicacao(self):
        hist = {"2026-11-03#1": {"titulo": "S", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        d, e = deps(historico=hist, cliques=[{"acao": "pub", "chave": "2026-11-03#1", "id": "a"}],
                    publicar_erro=RuntimeError("timed out"))
        d.responder = lambda cid, texto: (_ for _ in ()).throw(RuntimeError("query is too old"))
        self.assertEqual(fluxo.verificar(d), 1)
        self.assertTrue(any(t.startswith("❌") for t in e["textos"]))

    def test_erro_inesperado_num_clique_avisa_e_segue_para_o_proximo(self):
        hist = {"2026-11-03#1": {"titulo": "S", "status": "pendente"},  # sem video/legenda: registro quebrado
                "2026-11-01#1": {"titulo": "Velho", "status": "pendente"}}
        cliques = [{"acao": "pub", "chave": "2026-11-03#1", "id": "a"}, {"acao": "desc", "chave": "2026-11-01#1", "id": "b"}]
        d, e = deps(historico=hist, cliques=cliques)
        self.assertEqual(fluxo.verificar(d), 2)
        self.assertTrue(any(t.startswith("❌") for t in e["textos"]))
        self.assertEqual(e["hist"]["2026-11-01#1"]["status"], "descartado")
        self.assertEqual(e["offset"], 2)

    def test_pendente_de_outro_dia_expira_em_vez_de_publicar(self):
        hist = {"2026-11-01#1": {"titulo": "Velho", "status": "pendente", "video": "v.mp4", "legenda_post": "l"}}
        d, e = deps(historico=hist, cliques=[{"acao": "pub", "chave": "2026-11-01#1", "id": "a"}])
        self.assertEqual(fluxo.verificar(d), 1)
        self.assertEqual(e["publicados"], [])
        self.assertEqual(e["hist"]["2026-11-01#1"]["status"], "expirado")
        self.assertIn("⌛ expirou: o vídeo era para 01/11", e["textos"][-1])

    def test_clique_age_so_no_slot_certo(self):
        hist = {"2026-11-03#1": {"titulo": "Manhã", "status": "pendente", "video": "m.mp4", "legenda_post": "l1"},
                "2026-11-03#2": {"titulo": "Tarde", "status": "pendente", "video": "t.mp4", "legenda_post": "l2"}}
        d, e = deps(historico=hist, cliques=[{"acao": "pub", "chave": "2026-11-03#2", "id": "a"}])
        self.assertEqual(fluxo.verificar(d), 1)
        self.assertEqual(e["publicados"], [(Path("t.mp4"), "l2")])
        self.assertEqual(e["hist"]["2026-11-03#2"]["status"], "publicado")
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "pendente")
        self.assertIn("18h", e["textos"][-1])

    def test_descartar_slot_1_nao_mexe_no_slot_2(self):
        hist = {"2026-11-03#1": {"titulo": "Manhã", "status": "pendente", "video": "m.mp4", "legenda_post": "l1"},
                "2026-11-03#2": {"titulo": "Tarde", "status": "pendente", "video": "t.mp4", "legenda_post": "l2"}}
        d, e = deps(historico=hist, cliques=[{"acao": "desc", "chave": "2026-11-03#1", "id": "a"}])
        fluxo.verificar(d)
        self.assertEqual(e["hist"]["2026-11-03#1"]["status"], "descartado")
        self.assertEqual(e["hist"]["2026-11-03#2"]["status"], "pendente")
        self.assertIn("11h", e["textos"][-1])

    def test_expira_pela_data_da_chave(self):
        hist = {"2026-11-02#2": {"titulo": "Ontem", "status": "pendente", "video": "v.mp4", "legenda_post": "l"},
                "2026-11-03#2": {"titulo": "Hoje", "status": "pendente", "video": "h.mp4", "legenda_post": "l"}}
        cliques = [{"acao": "pub", "chave": "2026-11-02#2", "id": "a"}, {"acao": "pub", "chave": "2026-11-03#2", "id": "b"}]
        d, e = deps(historico=hist, cliques=cliques)
        self.assertEqual(fluxo.verificar(d), 2)
        self.assertEqual(e["hist"]["2026-11-02#2"]["status"], "expirado")
        self.assertEqual(e["hist"]["2026-11-03#2"]["status"], "publicado")
        self.assertEqual(e["publicados"], [(Path("h.mp4"), "l")])
        self.assertTrue(any("⌛ expirou: o vídeo era para 02/11" in t for t in e["textos"]))

    def test_clique_legado_sem_slot_continua_funcionando(self):
        hist = {"2026-11-03": {"titulo": "Antigo", "status": "pendente", "video": "a.mp4", "legenda_post": "l"}}
        d, e = deps(historico=hist, cliques=[{"acao": "pub", "chave": "2026-11-03", "id": "a"}])
        fluxo.verificar(d)
        self.assertEqual(e["hist"]["2026-11-03"]["status"], "publicado")
        self.assertEqual(e["publicados"], [(Path("a.mp4"), "l")])

    def test_chave_sem_data_valida_nao_publica(self):
        hist = {"manual-x": {"titulo": "Semente", "status": "pendente", "video": "a.mp4", "legenda_post": "l"}}
        d, e = deps(historico=hist, cliques=[{"acao": "pub", "chave": "manual-x", "id": "a"}])
        fluxo.verificar(d)
        self.assertEqual(e["publicados"], [])
        self.assertEqual(e["hist"]["manual-x"]["status"], "expirado")


if __name__ == "__main__":
    unittest.main()
