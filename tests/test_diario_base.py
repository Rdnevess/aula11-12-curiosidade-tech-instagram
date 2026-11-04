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
        self.assertEqual(config.pasta_do_dia(date(2026, 11, 3), 1).name, "diario-2026-11-03-1")
        self.assertEqual(config.pasta_do_dia(date(2026, 11, 3), 2, ensaio=True).name, "diario-2026-11-03-2-ensaio")

    def test_horarios_dos_slots(self):
        self.assertEqual(config.HORARIOS, {1: "09:00", 2: "11:00"})
        self.assertFalse(hasattr(config, "HORARIO"))
        self.assertEqual(config.hora_curta(1), "09h")
        self.assertEqual(config.hora_curta(2), "11h")


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

    def test_retry_503_then_success(self):
        chamadas = [0]
        esperas = []

        def post(url, corpo, chave, timeout=120):
            chamadas[0] += 1
            if chamadas[0] == 1:
                e = gemini.ErroGemini("Gemini 503: high demand", codigo=503)
                raise e
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

        def esperar(segundos):
            esperas.append(segundos)

        texto, _ = gemini.gerar("p", "K", "m", post=post, esperar=esperar)
        self.assertEqual(texto, "ok")
        self.assertEqual(esperas, [10])

    def test_retry_three_503s_then_reserve_success(self):
        chamadas = [0]
        urls = []
        esperas = []

        def post(url, corpo, chave, timeout=120):
            urls.append(url)
            chamadas[0] += 1
            if chamadas[0] <= 3:
                e = gemini.ErroGemini(f"Gemini 503: high demand", codigo=503)
                raise e
            return {"candidates": [{"content": {"parts": [{"text": "ok com reserva"}]}}]}

        def esperar(segundos):
            esperas.append(segundos)

        texto, _ = gemini.gerar("p", "K", "gemini-3.5-flash", post=post, esperar=esperar, reserva="gemini-3.5-flash-lite")
        self.assertEqual(texto, "ok com reserva")
        self.assertEqual(esperas, [10, 30])
        self.assertIn("gemini-3.5-flash-lite", urls[-1])

    def test_retry_404_raises_immediately(self):
        chamadas = [0]
        esperas = []

        def post(url, corpo, chave, timeout=120):
            chamadas[0] += 1
            e = gemini.ErroGemini("Gemini 404: not found", codigo=404)
            raise e

        def esperar(segundos):
            esperas.append(segundos)

        with self.assertRaises(gemini.ErroGemini) as cm:
            gemini.gerar("p", "K", "m", post=post, esperar=esperar)
        self.assertEqual(cm.exception.codigo, 404)
        self.assertEqual(chamadas[0], 1)
        self.assertEqual(esperas, [])

    def test_retry_three_503s_without_reserva_raises(self):
        chamadas = [0]
        esperas = []

        def post(url, corpo, chave, timeout=120):
            chamadas[0] += 1
            e = gemini.ErroGemini("Gemini 503: high demand", codigo=503)
            raise e

        def esperar(segundos):
            esperas.append(segundos)

        with self.assertRaises(gemini.ErroGemini) as cm:
            gemini.gerar("p", "K", "m", post=post, esperar=esperar)
        self.assertEqual(cm.exception.codigo, 503)
        self.assertEqual(esperas, [10, 30])

    def test_extrair_json_com_texto_em_volta(self):
        self.assertEqual(gemini.extrair_json('Aqui: ```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(gemini.ErroGemini):
            gemini.extrair_json("sem json")

    def test_fontes_e_dominios(self):
        fontes = gemini.fontes_de(GROUNDING)
        self.assertEqual(len(fontes), 2)
        self.assertEqual(gemini.dominios(fontes), {"en.wikipedia.org", "computerhistory.org"})
        self.assertEqual(gemini.normalizar_dominio("https://www.Exemplo.com/a"), "exemplo.com")


class ChaveTest(unittest.TestCase):
    def test_chave_por_slot(self):
        self.assertEqual(historico.chave(date(2026, 11, 4), 1), "2026-11-04#1")
        self.assertEqual(historico.chave("2026-11-04", 2), "2026-11-04#2")

    def test_separar_chave_nova_e_legadas(self):
        self.assertEqual(historico.separar("2026-11-04#2"), (date(2026, 11, 4), 2))
        self.assertEqual(historico.separar("2026-11-03"), (date(2026, 11, 3), None))
        self.assertEqual(historico.separar("manual-pentium"), (None, None))
        self.assertEqual(historico.separar("2026-11-04#x"), (None, None))
        self.assertEqual(historico.separar("2026-13-40#1"), (None, None))

    def test_slots_do_mesmo_dia_sao_independentes(self):
        dados = {"2026-11-04#1": {"titulo": "A", "status": "publicado"}}
        self.assertTrue(historico.ja_resolvido(dados, "2026-11-04#1"))
        self.assertFalse(historico.ja_resolvido(dados, "2026-11-04#2"))

    def test_chave_legada_do_dia_conta_como_slot_1(self):
        # Antes dos slots, o dia tinha uma só chave: o post desse dia é o do slot 1.
        dados = {"2026-11-03": {"titulo": "Mariner 10", "status": "publicado"}}
        self.assertTrue(historico.ja_resolvido(dados, "2026-11-03#1"))
        self.assertFalse(historico.ja_resolvido(dados, "2026-11-03#2"))
        self.assertIn("Mariner 10", historico.temas(dados))


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

    def test_atualizar_mescla_so_o_dia_alterado(self):
        # rodar carrega uma cópia e passa minutos montando o vídeo; nesse meio-tempo verificar
        # muda outro dia no arquivo. Quando rodar grava o seu dia, a mudança do verificar sobrevive.
        historico.atualizar("2026-11-01", {"titulo": "A", "status": "pendente"}, self.caminho)
        copia_do_rodar = historico.carregar(self.caminho)
        historico.atualizar("2026-11-01", {"status": "publicado"}, self.caminho)  # verificar
        historico.atualizar("2026-11-03", {"titulo": "B", "status": "pendente"}, self.caminho)  # rodar
        dados = historico.carregar(self.caminho)
        self.assertEqual(copia_do_rodar["2026-11-01"]["status"], "pendente")
        self.assertEqual(dados["2026-11-01"], {"titulo": "A", "status": "publicado"})
        self.assertEqual(dados["2026-11-03"]["status"], "pendente")
        self.assertIn("manual-pentium", dados)

    def test_salvar_e_atomico_sem_sobras(self):
        historico.atualizar("2026-11-03", {"status": "pendente"}, self.caminho)
        self.assertEqual([p.name for p in self.caminho.parent.iterdir()], ["historico.json"])

    def test_resolvidos_incluem_publicacao_em_andamento_ou_com_erro(self):
        for status in ("publicando", "erro_publicacao", "publicado", "pendente"):
            self.assertTrue(historico.ja_resolvido({"d": {"status": status}}, "d"), status)


if __name__ == "__main__":
    unittest.main()
