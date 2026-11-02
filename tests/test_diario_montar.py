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
        self.assertEqual(json.loads((self.pasta / "reel.json").read_text(encoding="utf-8"))["voice"]["mode"], "segments")

    def test_render_falhou(self):
        def executar(cmd, **kw):
            if "tts.mjs" in cmd[1]:
                return self.executar_falso()(cmd, **kw)
            return SimpleNamespace(returncode=1, stdout="", stderr="Chrome não abriu")
        with self.assertRaises(montar.ErroMontagem):
            montar.montar(self.pasta, ROTEIRO, executar=executar, conferir=lambda p: [])


if __name__ == "__main__":
    unittest.main()
