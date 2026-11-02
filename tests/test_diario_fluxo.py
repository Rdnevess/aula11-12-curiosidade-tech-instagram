import copy
import unittest
from datetime import date
from pathlib import Path

from scripts.diario import fluxo

FATO = {"titulo": "Sputnik 2", "data": "1957-11-03", "fato": "…", "numeros": [], "fontes": [
    {"dominio": "wikipedia.org", "url": "a"}, {"dominio": "nasa.gov", "url": "b"}]}
ROTEIRO = {"titulo": "Sputnik 2", "trechos": [{"fala": "Oi."}], "legenda_post": "legenda"}
CONF_OK = {"data_confirmada": True, "numeros": [], "fontes": FATO["fontes"]}
DIA = date(2026, 11, 3)


def deps(conf=CONF_OK, historico=None, cliques=(), publicar_erro=None):
    estado = {"hist": historico if historico is not None else {}, "textos": [], "videos": [], "publicados": [],
              "respostas": [], "offset": 0}

    def atualizar(dia_iso, campos):
        estado["hist"].setdefault(dia_iso, {}).update(campos)

    def publicar(mp4, legenda):
        if publicar_erro:
            raise publicar_erro
        estado["publicados"].append((mp4, legenda))
        return {"permalink": "https://instagram/p/1"}

    d = fluxo.Dependencias(
        historico_carregar=lambda: copy.deepcopy(estado["hist"]),
        historico_atualizar=atualizar,
        prechecar=lambda: None,
        pesquisar=lambda dia, usados: dict(FATO),
        gerar_roteiro=lambda fato: (ROTEIRO, 1),
        montar=lambda pasta, roteiro: (Path("out.mp4"), []),
        confirmar=lambda fato, numeros: conf,
        publicar=publicar,
        avisar_texto=lambda t: estado["textos"].append(t),
        avisar_video=lambda mp4, legenda, dia_iso: estado["videos"].append((mp4, dia_iso)),
        ler_cliques=lambda offset: (list(cliques), offset + len(cliques)),
        responder=lambda cid, texto: estado["respostas"].append((cid, texto)),
        offset_ler=lambda: estado["offset"],
        offset_salvar=lambda o: estado.update(offset=o),
        salvar_json=lambda pasta, nome, dados: None,
    )
    return d, estado



class RodarTest(unittest.TestCase):
    def test_publica_quando_a_trava_aprova(self):
        d, e = deps()
        self.assertEqual(fluxo.rodar(DIA, d=d), "publicado")
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "legenda")])
        self.assertEqual(e["hist"]["2026-11-03"]["status"], "publicado")
        self.assertIn("✅", e["textos"][-1])

    def test_segura_e_manda_video(self):
        d, e = deps(conf={**CONF_OK, "data_confirmada": False})
        self.assertEqual(fluxo.rodar(DIA, d=d), "pendente")
        self.assertEqual(e["publicados"], [])
        self.assertEqual(e["videos"], [(Path("out.mp4"), "2026-11-03")])
        self.assertEqual(e["hist"]["2026-11-03"]["status"], "pendente")

    def test_idempotente(self):
        d, e = deps(historico={"2026-11-03": {"titulo": "x", "status": "publicado"}})
        self.assertEqual(fluxo.rodar(DIA, d=d), "pulado")
        self.assertEqual(e["publicados"], [])

    def test_ensaio_nao_publica_nem_marca(self):
        d, e = deps()
        self.assertEqual(fluxo.rodar(DIA, sem_publicar=True, d=d), "ensaio")
        self.assertEqual(e["publicados"], [])
        self.assertNotIn("2026-11-03", e["hist"])
        self.assertIn("ensaio", e["textos"][-1])

    def test_ensaio_usa_pasta_propria(self):
        d, e = deps()
        pastas = []
        d.montar = lambda pasta, roteiro: (pastas.append(pasta), (Path("out.mp4"), []))[1]
        fluxo.rodar(DIA, sem_publicar=True, d=d)
        self.assertEqual(pastas[0].name, "diario-2026-11-03-ensaio")

    def test_erro_avisa_e_propaga(self):
        d, e = deps(publicar_erro=RuntimeError("execução 9: error — Invalid OAuth 2.0 Access Token"))
        with self.assertRaises(RuntimeError):
            fluxo.rodar(DIA, d=d)
        self.assertIn("Instagram TEP", e["textos"][-1])

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
        d, e = deps(conf={**CONF_OK, "data_confirmada": False})

        def avisar_video_quebrado(mp4, legenda, dia_iso):
            raise RuntimeError("telegram fora")

        d.avisar_video = avisar_video_quebrado
        with self.assertRaises(RuntimeError):
            fluxo.rodar(DIA, d=d)
        self.assertIn("aviso no Telegram", e["textos"][-1])

    def test_rodar_nao_apaga_o_que_verificar_gravou_durante_a_montagem(self):
        hist = {"2026-11-02": {"titulo": "Ontem", "status": "pendente", "video": "v.mp4", "legenda_post": "l"}}
        d, e = deps(conf={**CONF_OK, "data_confirmada": False}, historico=hist)

        def montar_demorado(pasta, roteiro):
            # verificar roda em paralelo e descarta o pendente de ontem
            d.historico_atualizar("2026-11-02", {"status": "descartado"})
            return Path("out.mp4"), []

        d.montar = montar_demorado
        self.assertEqual(fluxo.rodar(DIA, d=d), "pendente")
        self.assertEqual(e["hist"]["2026-11-02"]["status"], "descartado")
        self.assertEqual(e["hist"]["2026-11-03"]["status"], "pendente")


class VerificarTest(unittest.TestCase):
    def test_publica_pendente_e_ignora_resolvido(self):
        hist = {"2026-11-03": {"titulo": "Sputnik 2", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"},
                "2026-11-02": {"titulo": "y", "status": "publicado"}}
        cliques = [{"acao": "pub", "dia": "2026-11-03", "id": "a"}, {"acao": "pub", "dia": "2026-11-02", "id": "b"}]
        d, e = deps(historico=hist, cliques=cliques)
        self.assertEqual(fluxo.verificar(d), 2)
        self.assertEqual(e["publicados"], [(Path("out.mp4"), "leg")])
        self.assertEqual(e["hist"]["2026-11-03"]["status"], "publicado")
        self.assertIn("já resolvido", e["respostas"][1][1])
        self.assertEqual(e["offset"], 2)

    def test_descarta(self):
        hist = {"2026-11-03": {"titulo": "S", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        d, e = deps(historico=hist, cliques=[{"acao": "desc", "dia": "2026-11-03", "id": "a"}])
        fluxo.verificar(d)
        self.assertEqual(e["hist"]["2026-11-03"]["status"], "descartado")
        self.assertEqual(e["publicados"], [])

    def test_publicar_falha_mantem_pendente(self):
        hist = {"2026-11-03": {"titulo": "S", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        erro = RuntimeError("execução 9: error — Invalid OAuth 2.0 Access Token")
        d, e = deps(historico=hist, cliques=[{"acao": "pub", "dia": "2026-11-03", "id": "a"}], publicar_erro=erro)
        self.assertEqual(fluxo.verificar(d), 1)
        self.assertEqual(e["hist"]["2026-11-03"]["status"], "pendente")
        self.assertEqual(e["publicados"], [])
        self.assertEqual(e["respostas"], [("a", "Falhou; veja a mensagem.")])
        self.assertIn("Instagram TEP", e["textos"][-1])

    def test_falha_ao_salvar_historico_apos_publicar_continua_e_salva_offset(self):
        hist = {"2026-11-03": {"titulo": "Sputnik 2", "status": "pendente", "video": "out.mp4", "legenda_post": "leg"}}
        cliques = [{"acao": "pub", "dia": "2026-11-03", "id": "a"}]
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


if __name__ == "__main__":
    unittest.main()
