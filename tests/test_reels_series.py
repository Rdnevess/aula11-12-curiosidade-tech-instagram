import json
import unittest
from pathlib import Path

from scripts.conferir_reel import validar_reel

REELS = Path(__file__).resolve().parent.parent / "reels"
NOMES = ["facemash", "megadrive", "pentium"]
FONTES = ["inter-latin-900-normal.woff2", "jetbrains-mono-latin-500-normal.woff2",
          "jetbrains-mono-latin-800-normal.woff2"]


class SerieTest(unittest.TestCase):
    def test_cada_reel_json_e_valido_e_usa_a_propria_cena(self):
        for nome in NOMES:
            with self.subTest(nome):
                dados = json.loads((REELS / nome / "reel.json").read_text(encoding="utf-8"))
                self.assertEqual(validar_reel(dados), [])
                self.assertEqual(dados["render"]["data"]["scene"], nome)
                self.assertEqual(dados["render"]["name"], nome)

    def test_fontes_locais(self):
        for f in FONTES:
            self.assertGreater((REELS / "fontes" / f).stat().st_size, 10_000, f)

    def test_legendas_dos_posts(self):
        texto = (REELS / "legendas.md").read_text(encoding="utf-8")
        for nome in NOMES:
            self.assertIn(f"## {nome}", texto)
