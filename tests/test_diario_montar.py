import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.diario import montar

ROTEIRO = {
    "titulo": "Sputnik 2", "data": "1957-11-03", "selo": "03 NOV",
    "trechos": [
        {"fala": "Sabia que um cachorro foi ao espaço?", "bloco": "gancho", "dados": {"icone": "satelite", "carimbo": "ÓRBITA"}},
        {"fala": "Em 1957, a União Soviética lançou o Sputnik 2.", "bloco": "data", "dados": {"texto": "03/11/1957"}},
        {"fala": "Ônibus espacial? Não: um satélite de 508 quilos.", "bloco": "numero",
         "dados": {"valor": 508, "prefixo": "", "sufixo": " kg", "legenda": "peso"}},
        {"fala": "A bordo, Laika.", "bloco": "fato", "dados": {"texto": "A bordo: Laika"}},
    ],
    "destaques": ["Sputnik", "Laika"], "legenda_post": "…",
}


class AncorasTest(unittest.TestCase):
    def test_para_no_primeiro_numero_e_normaliza(self):
        self.assertEqual(montar.ancoras([t["fala"] for t in ROTEIRO["trechos"]]),
                         [["em"], ["onibus", "espacial"], ["a", "bordo"]])


class ReelJsonTest(unittest.TestCase):
    def test_estrutura(self):
        r = montar.reel_json(ROTEIRO)
        self.assertEqual(r["lines"], [t["fala"] for t in ROTEIRO["trechos"]])
        self.assertEqual(r["voice"]["mode"], "take")
        self.assertEqual(r["voice"]["voices"], ["Orus"])
        self.assertEqual(r["voice"]["maxSeconds"], 46.5)
        self.assertIn("46 seconds", r["voice"]["note"])
        self.assertEqual(len(r["voice"]["anchors"]), 3)
        self.assertEqual(r["render"]["stage"], "../curiosidade.html")
        d = r["render"]["data"]
        self.assertEqual((d["scene"], d["selo"], d["endAfterLast"], d["endHold"]), ("auto", "03 NOV", True, 2.5))
        self.assertEqual(d["trechos"][2], {"bloco": "numero", "dados": ROTEIRO["trechos"][2]["dados"]})


class CapaTest(unittest.TestCase):
    """Capa do Reel: o Instagram usa o 1º quadro na grade do perfil."""

    def test_capa_com_titulo_e_data_do_evento(self):
        d = montar.reel_json(ROTEIRO)["render"]["data"]
        self.assertEqual(d["capa"], "Sputnik 2")
        self.assertEqual(d["capaData"], "03/11/1957")

    def test_titulo_longo_e_cortado_com_reticencias(self):
        titulo = "O Primeiro Computador Pessoal Vendido em Larga Escala no Mundo"
        capa = montar.reel_json({**ROTEIRO, "titulo": titulo})["render"]["data"]["capa"]
        self.assertLessEqual(len(capa), 40)
        self.assertTrue(capa.endswith("…"))
        self.assertTrue(titulo.startswith(capa[:-1].rstrip()))
        self.assertNotIn(" …", capa)
        self.assertEqual(capa, "O Primeiro Computador Pessoal Vendido…")

    def test_titulo_de_40_caracteres_fica_inteiro(self):
        titulo = "x" * 40
        self.assertEqual(montar.reel_json({**ROTEIRO, "titulo": titulo})["render"]["data"]["capa"], titulo)

    def test_template_escapa_a_capa(self):
        html = (Path(montar.__file__).resolve().parents[2] / "reels" / "curiosidade.html").read_text(encoding="utf-8")
        self.assertTrue("h(d.capa)" in html and 'id="capa"' in html)


class MontarTest(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp()) / "diario-2026-11-03"
        self.comandos = []
        self.acelerados = []

    def montar(self, executar, roteiro=ROTEIRO, fotos=lambda pasta, roteiro: [], **kw):
        return montar.montar(self.pasta, roteiro, executar=executar, conferir=lambda p: [], fotos=fotos,
                             acelerar=lambda voz, fator: self.acelerados.append((voz, fator)),
                             duracao=lambda wav: 20.0, **kw)

    def executar_falso(self, saida_tts="Orus t1: 20.0 s · ok"):
        def executar(cmd, cwd, env, capture_output, text, encoding, errors):
            self.comandos.append((cmd, env))
            if "tts.mjs" in cmd[1]:
                (Path(cwd) / "audio").mkdir(parents=True, exist_ok=True)
                (Path(cwd) / "audio" / "Orus.json").write_text("{}", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout=saida_tts, stderr="")
            (Path(cwd) / "out").mkdir(parents=True, exist_ok=True)
            (Path(cwd) / "out" / "diario-Orus.mp4").write_bytes(b"x")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return executar

    def test_voz_render_e_conferencia(self):
        mp4, problemas = self.montar(self.executar_falso())
        self.assertEqual(mp4, self.pasta / "out" / "diario-Orus.mp4")
        self.assertEqual(problemas, [])
        self.assertEqual(json.loads((self.pasta / "reel.json").read_text(encoding="utf-8"))["voice"]["mode"], "take")
        self.assertIn("ENV_FILE", self.comandos[0][1])
        self.assertIn("CHROME_PATH", self.comandos[1][1])
        self.assertEqual(self.comandos[0][1]["TAKES"], "1")  # uma tomada só: poupa a cota diária do TTS

    def test_um_modelo_de_voz_so(self):
        # Pro e flash soam como vozes diferentes: sempre o mesmo modelo.
        self.montar(self.executar_falso())
        voz = json.loads((self.pasta / "reel.json").read_text(encoding="utf-8"))["voice"]
        self.assertEqual(voz["models"], [montar.MODELO_VOZ])

    def test_voz_orus_sem_aceleracao(self):
        # A Puck acelerada com atempo soava robótica; a Orus já cabe no tempo sem acelerar.
        self.montar(self.executar_falso())
        self.assertEqual(montar.VOZ, "Orus")
        self.assertEqual(self.acelerados, [])
        self.assertEqual(json.loads((self.pasta / "reel.json").read_text(encoding="utf-8"))["voice"]["voices"], ["Orus"])

    def test_aceleracao_quando_configurada(self):
        original = montar.TEMPO_VOZ
        montar.TEMPO_VOZ = 1.1
        try:
            self.montar(self.executar_falso())
        finally:
            montar.TEMPO_VOZ = original
        self.assertEqual(self.acelerados, [(self.pasta / "audio" / "Orus.json", 1.1)])

    def _take_sem_alinhar(self, tomadas_ok):
        """tts que só escreve Orus.json na tomada nº tomadas_ok (0 = nunca); sempre deixa Orus.t1.wav."""
        modos = []

        def executar(cmd, cwd, **kw):
            if "tts.mjs" in cmd[1]:
                modos.append(json.loads((Path(cwd) / "reel.json").read_text(encoding="utf-8"))["voice"]["mode"])
                self.assertFalse((Path(cwd) / "audio" / "Orus.json").exists())
                (Path(cwd) / "audio").mkdir(parents=True, exist_ok=True)
                (Path(cwd) / "audio" / "Orus.t1.wav").write_bytes(b"wav")
                if len(modos) == tomadas_ok:
                    (Path(cwd) / "audio" / "Orus.json").write_text("{}", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="ALINHAMENTO SUSPEITO (trecho 2)", stderr="")
            return self.executar_falso()(cmd, cwd=cwd, **kw)
        return executar, modos

    def test_alinhamento_falhou_refaz_a_tomada_nunca_segments(self):
        self._velhos()
        executar, modos = self._take_sem_alinhar(tomadas_ok=2)
        self.montar(executar)
        self.assertEqual(modos, ["take", "take"])
        self.assertIn("ALINHAMENTO SUSPEITO", (self.pasta / "log.txt").read_text(encoding="utf-8"))

    def test_duas_tomadas_sem_alinhar_dividem_pelo_texto(self):
        executar, modos = self._take_sem_alinhar(tomadas_ok=0)
        self.montar(executar)
        self.assertEqual(modos, ["take", "take"])
        voz = json.loads((self.pasta / "audio" / "Orus.json").read_text(encoding="utf-8"))
        self.assertEqual(voz["mode"], "take")
        self.assertEqual(Path(voz["file"]), self.pasta / "audio" / "Orus.wav")
        self.assertTrue((self.pasta / "audio" / "Orus.wav").exists())
        self.assertEqual(len(voz["segs"]), len(ROTEIRO["trechos"]))
        self.assertEqual(voz["segs"][0]["start"], 0)
        self.assertAlmostEqual(voz["segs"][-1]["end"], 20.0)

    def test_sem_audio_nenhum_falha(self):
        def executar(cmd, cwd, **kw):
            if "tts.mjs" in cmd[1]:
                return SimpleNamespace(returncode=1, stdout="", stderr="TTS falhou")
            return self.executar_falso()(cmd, cwd=cwd, **kw)
        with self.assertRaises(montar.ErroMontagem):
            self.montar(executar)

    def test_render_falhou(self):
        def executar(cmd, **kw):
            if "tts.mjs" in cmd[1]:
                return self.executar_falso()(cmd, **kw)
            return SimpleNamespace(returncode=1, stdout="", stderr="Chrome não abriu")
        with self.assertRaises(montar.ErroMontagem):
            self.montar(executar)

    def test_fotos_vao_para_o_reel_e_creditos_para_a_legenda(self):
        roteiro = json.loads(json.dumps(ROTEIRO))
        fotos = [{"arquivo": "img/foto1.jpg", "credito": "Fulano · CC BY 4.0"}]
        self.montar(self.executar_falso(), roteiro=roteiro, fotos=lambda pasta, r: fotos)
        dados = json.loads((self.pasta / "reel.json").read_text(encoding="utf-8"))["render"]["data"]
        self.assertEqual(dados["fotos"], fotos)
        self.assertTrue(roteiro["legenda_post"].endswith("Wikimedia Commons — Fulano · CC BY 4.0"))

    def _velhos(self):
        (self.pasta / "audio").mkdir(parents=True, exist_ok=True)
        (self.pasta / "audio" / "Orus.json").write_text('{"velho": true}', encoding="utf-8")
        (self.pasta / "audio" / "Orus.t1.wav").write_bytes(b"velho")
        (self.pasta / "out").mkdir(parents=True, exist_ok=True)
        (self.pasta / "out" / "diario-Orus.mp4").write_bytes(b"velho")

    def test_render_sem_mp4_novo_falha_mesmo_com_mp4_velho(self):
        self._velhos()

        def executar(cmd, cwd, **kw):
            if "tts.mjs" in cmd[1]:
                return self.executar_falso()(cmd, cwd=cwd, **kw)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with self.assertRaises(montar.ErroMontagem):
            self.montar(executar)


class SegsProporcionaisTest(unittest.TestCase):
    def test_divide_pelo_numero_de_letras(self):
        segs = montar.segs_proporcionais(["aaaa", "bb", "cc"], 8.0)
        self.assertEqual(segs, [{"start": 0, "end": 4.0}, {"start": 4.0, "end": 6.0}, {"start": 6.0, "end": 8.0}])


class PastaDoDiaTest(unittest.TestCase):
    def test_ensaio_tem_pasta_propria(self):
        from datetime import date
        from scripts.diario import config
        dia = date(2026, 11, 3)
        self.assertEqual(config.pasta_do_dia(dia, 1).name, "diario-2026-11-03-1")
        self.assertEqual(config.pasta_do_dia(dia, 1, ensaio=True).name, "diario-2026-11-03-1-ensaio")


if __name__ == "__main__":
    unittest.main()
