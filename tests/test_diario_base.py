import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.diario import config, gemini, historico

GROUNDING = {"groundingChunks": [
    {"web": {"uri": "https://vertexaisearch.cloud.google.com/r/1", "title": "en.wikipedia.org"}},
    {"web": {"uri": "https://vertexaisearch.cloud.google.com/r/2", "title": "www.computerhistory.org"}},
    {"web": {"uri": "https://vertexaisearch.cloud.google.com/r/2", "title": "www.computerhistory.org"}},
    {"retrievedContext": {"uri": "x"}},
]}


class ConfigTest(unittest.TestCase):
    def test_selo_e_pasta(self):
        self.assertEqual(config.selo(date(1994, 10, 30)), "30 OUT")
        self.assertEqual(config.pasta_do_dia(date(2026, 11, 3)).name, "diario-2026-11-03")


class GeminiTest(unittest.TestCase):
    def test_gerar_monta_corpo_e_le_resposta(self):
        enviado = {}

        def falso(url, corpo, chave, timeout=120):
            enviado.update(url=url, corpo=corpo, chave=chave)
            return {"candidates": [{"content": {"parts": [{"text": "oi "}, {"text": "mundo"}]},
                                    "groundingMetadata": GROUNDING}]}

        texto, meta = gemini.gerar("p", "K", "gemini-2.5-flash", busca=True, json_mode=False, post=falso)
        self.assertEqual(texto, "oi mundo")
        self.assertEqual(meta, GROUNDING)
        self.assertIn("gemini-2.5-flash:generateContent", enviado["url"])
        self.assertEqual(enviado["corpo"]["tools"], [{"google_search": {}}])

    def test_json_mode(self):
        enviado = {}

        def falso(url, corpo, chave, timeout=120):
            enviado.update(corpo=corpo)
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

        gemini.gerar("p", "K", "m", json_mode=True, post=falso)
        self.assertEqual(enviado["corpo"]["generationConfig"]["responseMimeType"], "application/json")

    def test_resposta_vazia(self):
        with self.assertRaises(gemini.ErroGemini):
            gemini.gerar("p", "K", "m", post=lambda *a, **k: {"candidates": [{"finishReason": "SAFETY"}]})

    def test_extrair_json_com_texto_em_volta(self):
        self.assertEqual(gemini.extrair_json('Aqui: ```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(gemini.ErroGemini):
            gemini.extrair_json("sem json")

    def test_fontes_e_dominios(self):
        fontes = gemini.fontes_de(GROUNDING)
        self.assertEqual(len(fontes), 2)
        self.assertEqual(gemini.dominios(fontes), {"en.wikipedia.org", "computerhistory.org"})
        self.assertEqual(gemini.normalizar_dominio("https://www.Exemplo.com/a"), "exemplo.com")


class HistoricoTest(unittest.TestCase):
    def setUp(self):
        self.caminho = Path(tempfile.mkdtemp()) / "historico.json"

    def test_carrega_semente_quando_nao_existe(self):
        dados = historico.carregar(self.caminho)
        self.assertIn("pentium", " ".join(historico.temas(dados)).lower())
        self.assertFalse(historico.ja_resolvido(dados, "2026-11-02"))

    def test_registrar_salvar_e_resolver(self):
        dados = historico.carregar(self.caminho)
        historico.registrar(dados, "2026-11-03", {"titulo": "Lançamento do Sputnik", "status": "pendente"})
        historico.salvar(dados, self.caminho)
        de_novo = historico.carregar(self.caminho)
        self.assertTrue(historico.ja_resolvido(de_novo, "2026-11-03"))
        self.assertTrue(historico.repetido(de_novo, "lancamento do  SPUTNIK!"))
        self.assertEqual(json.loads(self.caminho.read_text(encoding="utf-8"))["2026-11-03"]["status"], "pendente")


if __name__ == "__main__":
    unittest.main()
