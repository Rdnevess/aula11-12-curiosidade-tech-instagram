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
        self.assertEqual(r["voice"]["voices"], ["Puck"])
        self.assertEqual(r["voice"]["maxSeconds"], 26.5)
        self.assertEqual(len(r["voice"]["anchors"]), 3)
        self.assertEqual(r["render"]["stage"], "../curiosidade.html")
        d = r["render"]["data"]
        self.assertEqual((d["scene"], d["selo"], d["endAfterLast"], d["endHold"]), ("auto", "03 NOV", True, 2.5))
        self.assertEqual(d["trechos"][2], {"bloco": "numero", "dados": ROTEIRO["trechos"][2]["dados"]})


class MontarTest(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp()) / "diario-2026-11-03"
        self.comandos = []

    def executar_falso(self, saida_tts="Puck t1: 20.0 s · ok"):
        def executar(cmd, cwd, env, capture_output, text, encoding, errors):
            self.comandos.append((cmd, env))
            if "tts.mjs" in cmd[1]:
                (Path(cwd) / "audio").mkdir(parents=True, exist_ok=True)
                (Path(cwd) / "audio" / "Puck.json").write_text("{}", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout=saida_tts, stderr="")
            (Path(cwd) / "out").mkdir(parents=True, exist_ok=True)
            (Path(cwd) / "out" / "diario-Puck.mp4").write_bytes(b"x")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return executar

    def test_voz_render_e_conferencia(self):
        mp4, problemas = montar.montar(self.pasta, ROTEIRO, executar=self.executar_falso(), conferir=lambda p: [])
        self.assertEqual(mp4, self.pasta / "out" / "diario-Puck.mp4")
        self.assertEqual(problemas, [])
        self.assertEqual(json.loads((self.pasta / "reel.json").read_text(encoding="utf-8"))["voice"]["mode"], "take")
        self.assertIn("ENV_FILE", self.comandos[0][1])
        self.assertIn("CHROME_PATH", self.comandos[1][1])

    def test_alinhamento_suspeito_refaz_em_segments(self):
        montar.montar(self.pasta, ROTEIRO, executar=self.executar_falso("ALINHAMENTO SUSPEITO no trecho 2"),
                      conferir=lambda p: [])
        tts = [c for c, _ in self.comandos if "tts.mjs" in c[1]]
        self.assertEqual(len(tts), 2)
        reel = json.loads((self.pasta / "reel.json").read_text(encoding="utf-8"))
        self.assertEqual(reel["voice"]["mode"], "segments")
        self.assertEqual(reel["render"]["gap"], 0.1)
        log_content = (self.pasta / "log.txt").read_text(encoding="utf-8")
        self.assertIn("ALINHAMENTO SUSPEITO", log_content)

    def test_render_falhou(self):
        def executar(cmd, **kw):
            if "tts.mjs" in cmd[1]:
                return self.executar_falso()(cmd, **kw)
            return SimpleNamespace(returncode=1, stdout="", stderr="Chrome não abriu")
        with self.assertRaises(montar.ErroMontagem):
            montar.montar(self.pasta, ROTEIRO, executar=executar, conferir=lambda p: [])

    def _velhos(self):
        (self.pasta / "audio").mkdir(parents=True, exist_ok=True)
        (self.pasta / "audio" / "Puck.json").write_text('{"velho": true}', encoding="utf-8")
        (self.pasta / "audio" / "Puck.t1.wav").write_bytes(b"velho")
        (self.pasta / "out").mkdir(parents=True, exist_ok=True)
        (self.pasta / "out" / "diario-Puck.mp4").write_bytes(b"velho")

    def test_take_sem_puck_json_cai_em_segments_mesmo_com_voz_velha(self):
        self._velhos()
        modos = []

        def executar(cmd, cwd, **kw):
            if "tts.mjs" in cmd[1]:
                modo = json.loads((Path(cwd) / "reel.json").read_text(encoding="utf-8"))["voice"]["mode"]
                modos.append(modo)
                self.assertFalse((Path(cwd) / "audio" / "Puck.json").exists())
                if modo == "segments":
                    (Path(cwd) / "audio" / "Puck.json").write_text("{}", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return self.executar_falso()(cmd, cwd=cwd, **kw)

        montar.montar(self.pasta, ROTEIRO, executar=executar, conferir=lambda p: [])
        self.assertEqual(modos, ["take", "segments"])
        self.assertFalse((self.pasta / "audio" / "Puck.t1.wav").exists())

    def test_segments_sem_puck_json_falha(self):
        self._velhos()

        def executar(cmd, cwd, **kw):
            if "tts.mjs" in cmd[1]:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return self.executar_falso()(cmd, cwd=cwd, **kw)

        with self.assertRaises(montar.ErroMontagem):
            montar.montar(self.pasta, ROTEIRO, executar=executar, conferir=lambda p: [])

    def test_render_sem_mp4_novo_falha_mesmo_com_mp4_velho(self):
        self._velhos()

        def executar(cmd, cwd, **kw):
            if "tts.mjs" in cmd[1]:
                return self.executar_falso()(cmd, cwd=cwd, **kw)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with self.assertRaises(montar.ErroMontagem):
            montar.montar(self.pasta, ROTEIRO, executar=executar, conferir=lambda p: [])


class PastaDoDiaTest(unittest.TestCase):
    def test_ensaio_tem_pasta_propria(self):
        from datetime import date
        from scripts.diario import config
        dia = date(2026, 11, 3)
        self.assertEqual(config.pasta_do_dia(dia, 1).name, "diario-2026-11-03-1")
        self.assertEqual(config.pasta_do_dia(dia, 1, ensaio=True).name, "diario-2026-11-03-1-ensaio")


if __name__ == "__main__":
    unittest.main()
