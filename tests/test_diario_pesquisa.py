import json
import unittest
from datetime import date

from scripts.diario import pesquisa

META = {"groundingChunks": [{"web": {"uri": "https://r/1", "title": "wikipedia.org"}},
                            {"web": {"uri": "https://r/2", "title": "nasa.gov"}}]}
FATO = {"titulo": "Lançamento do Sputnik 2", "data": "1957-11-03",
        "fato": "Em 3 de novembro de 1957 a União Soviética lançou o Sputnik 2 com a cadela Laika, 508 kg.",
        "numeros": ["1957", "508"]}


def gerar_falso(resposta, meta=META, registro=None):
    def gerar(prompt, chave, modelo, busca=False, json_mode=False):
        if registro is not None:
            registro.append({"prompt": prompt, "busca": busca})
        return "Resultado:\n" + json.dumps(resposta, ensure_ascii=False), meta
    return gerar


class PesquisarTest(unittest.TestCase):
    def test_devolve_fato_com_fontes_e_usa_busca(self):
        chamadas = []
        fato = pesquisa.pesquisar(date(2026, 11, 3), ["Facemash"], "K", "m", gerar=gerar_falso(FATO, registro=chamadas))
        self.assertEqual(fato["titulo"], "Lançamento do Sputnik 2")
        self.assertEqual([f["dominio"] for f in fato["fontes"]], ["wikipedia.org", "nasa.gov"])
        self.assertTrue(chamadas[0]["busca"])
        self.assertIn("3 de novembro", chamadas[0]["prompt"])
        self.assertIn("Facemash", chamadas[0]["prompt"])

    def test_rejeita_outro_dia(self):
        with self.assertRaises(pesquisa.ErroPesquisa):
            pesquisa.pesquisar(date(2026, 11, 4), [], "K", "m", gerar=gerar_falso(FATO))

    def test_rejeita_tema_usado(self):
        with self.assertRaises(pesquisa.ErroPesquisa):
            pesquisa.pesquisar(date(2026, 11, 3), ["lancamento do sputnik 2"], "K", "m", gerar=gerar_falso(FATO))

    def test_rejeita_campo_faltando(self):
        with self.assertRaises(pesquisa.ErroPesquisa):
            pesquisa.pesquisar(date(2026, 11, 3), [], "K", "m", gerar=gerar_falso({"titulo": "x"}))


class ConfirmarTest(unittest.TestCase):
    def test_confirma_com_fontes(self):
        resposta = {"data_confirmada": True, "numeros": [{"valor": "508", "confirmado": True}]}
        chamadas = []
        r = pesquisa.confirmar({**FATO, "fontes": []}, ["508"], "K", "m", gerar=gerar_falso(resposta, registro=chamadas))
        self.assertTrue(r["data_confirmada"])
        self.assertEqual(r["numeros"], [{"valor": "508", "confirmado": True}])
        self.assertEqual(len(r["fontes"]), 2)
        self.assertTrue(chamadas[0]["busca"])
        self.assertIn("508", chamadas[0]["prompt"])

    def test_resposta_sem_campos_vira_nao_confirmado(self):
        r = pesquisa.confirmar({**FATO, "fontes": []}, ["508"], "K", "m", gerar=gerar_falso({}))
        self.assertFalse(r["data_confirmada"])
        self.assertEqual(r["numeros"], [])


if __name__ == "__main__":
    unittest.main()
