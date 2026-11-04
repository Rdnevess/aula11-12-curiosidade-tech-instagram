import json
import unittest
from datetime import date

from scripts.diario import pesquisa

FONTES = [{"dominio": "wikipedia.org", "url": "https://r/1"}, {"dominio": "nasa.gov", "url": "https://r/2"}]
FATO = {"titulo": "Lançamento do Sputnik 2", "data": "1957-11-03",
        "fato": "Em 3 de novembro de 1957 a União Soviética lançou o Sputnik 2 com a cadela Laika, 508 kg.",
        "numeros": ["1957", "508"]}


def buscar_falso(resposta, fontes=FONTES, registro=None):
    def buscar(prompt, chave, modelo):
        if registro is not None:
            registro.append({"prompt": prompt, "chave": chave, "modelo": modelo})
        return "Resultado:\n" + json.dumps(resposta, ensure_ascii=False), fontes
    return buscar


class PesquisarTest(unittest.TestCase):
    def test_devolve_fato_com_fontes_da_busca(self):
        chamadas = []
        fato = pesquisa.pesquisar(date(2026, 11, 3), ["Facemash"], "K", "m",
                                  buscar=buscar_falso(FATO, registro=chamadas))
        self.assertEqual(fato["titulo"], "Lançamento do Sputnik 2")
        self.assertEqual(fato["fontes"], FONTES)
        self.assertEqual(chamadas[0]["chave"], "K")
        self.assertEqual(chamadas[0]["modelo"], "m")
        self.assertIn("3 de novembro", chamadas[0]["prompt"])
        self.assertIn("Facemash", chamadas[0]["prompt"])
        self.assertIn("sites independentes", chamadas[0]["prompt"])
        self.assertIn('"fontes"', chamadas[0]["prompt"])

    def test_rejeita_outro_dia(self):
        with self.assertRaises(pesquisa.ErroPesquisa):
            pesquisa.pesquisar(date(2026, 11, 4), [], "K", "m", buscar=buscar_falso(FATO))

    def test_rejeita_tema_usado(self):
        with self.assertRaises(pesquisa.ErroPesquisa):
            pesquisa.pesquisar(date(2026, 11, 3), ["lancamento do sputnik 2"], "K", "m", buscar=buscar_falso(FATO))

    def test_rejeita_campo_faltando(self):
        with self.assertRaises(pesquisa.ErroPesquisa):
            pesquisa.pesquisar(date(2026, 11, 3), [], "K", "m", buscar=buscar_falso({"titulo": "x"}))


class ConfirmarTest(unittest.TestCase):
    def test_confirma_com_fontes_da_busca(self):
        resposta = {"data_confirmada": True, "numeros": [{"valor": "508", "confirmado": True}]}
        chamadas = []
        r = pesquisa.confirmar({**FATO, "fontes": []}, ["508"], "K", "m",
                               buscar=buscar_falso(resposta, registro=chamadas))
        self.assertTrue(r["data_confirmada"])
        self.assertEqual(r["numeros"], [{"valor": "508", "confirmado": True}])
        self.assertEqual(r["fontes"], FONTES)
        self.assertIn("508", chamadas[0]["prompt"])
        self.assertIn("sites independentes", chamadas[0]["prompt"])
        self.assertIn('"fontes"', chamadas[0]["prompt"])

    def test_resposta_sem_campos_vira_nao_confirmado(self):
        r = pesquisa.confirmar({**FATO, "fontes": []}, ["508"], "K", "m", buscar=buscar_falso({}))
        self.assertFalse(r["data_confirmada"])
        self.assertEqual(r["numeros"], [{"valor": "508", "confirmado": False}])

    def test_resposta_vazia_com_multiplos_numeros_solicitados(self):
        r = pesquisa.confirmar({**FATO, "fontes": []}, ["508", "1957"], "K", "m", buscar=buscar_falso({}))
        self.assertFalse(r["data_confirmada"])
        self.assertEqual(len(r["numeros"]), 2)
        self.assertTrue(all(not n.get("confirmado") for n in r["numeros"]))

    def test_numero_normalizado_nao_duplica(self):
        resposta = {"data_confirmada": True, "numeros": [{"valor": "3.000.000", "confirmado": True}]}
        r = pesquisa.confirmar({**FATO, "fontes": []}, ["3000000"], "K", "m", buscar=buscar_falso(resposta))
        self.assertEqual(len(r["numeros"]), 1)
        self.assertEqual(r["numeros"][0]["valor"], "3.000.000")
        self.assertTrue(r["numeros"][0]["confirmado"])


if __name__ == "__main__":
    unittest.main()
