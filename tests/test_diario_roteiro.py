import copy
import json
import unittest
from datetime import date

from scripts.diario import roteiro

FATO = {"titulo": "Lançamento do Sputnik 2", "data": "1957-11-03",
        "fato": "Em 3 de novembro de 1957 a União Soviética lançou o Sputnik 2 com a cadela Laika, de 508 kg.",
        "numeros": ["1957", "508"], "fontes": []}

ROTEIRO = {
    "titulo": "Lançamento do Sputnik 2", "data": "1957-11-03", "selo": "03 NOV",
    "trechos": [
        {"fala": "Sabia que um cachorro foi o primeiro ser vivo em órbita?", "bloco": "gancho",
         "dados": {"icone": "satelite", "carimbo": "ÓRBITA"}},
        {"fala": "Em novembro de 1957, a União Soviética lançou o Sputnik 2.", "bloco": "data",
         "dados": {"texto": "03/11/1957"}},
        {"fala": "A bordo estava a cadela Laika.", "bloco": "fato", "dados": {"texto": "A bordo: a cadela Laika"}},
        {"fala": "O satélite pesava 508 quilos.", "bloco": "numero",
         "dados": {"valor": 508, "prefixo": "", "sufixo": " kg", "legenda": "peso do Sputnik 2"}},
    ],
    "destaques": ["Sputnik", "Laika", "508"],
    "legenda_post": "Em 03/11/1957 a URSS lançou o Sputnik 2. Siga @curiosidadetechhoje #espaco #historiadatecnologia #sputnik",
}
DIA = date(1957, 11, 3)


def com(alterar):
    r = copy.deepcopy(ROTEIRO)
    alterar(r)
    return r


class ValidarTest(unittest.TestCase):
    def test_roteiro_valido(self):
        self.assertEqual(roteiro.validar(ROTEIRO, DIA, FATO["fato"]), [])

    def test_quantidade_de_trechos(self):
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"].__delitem__(slice(1, 4))), DIA, FATO["fato"]))

    def test_primeiro_bloco_gancho_e_sem_repeticao(self):
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"][0].update(bloco="fato", dados={"texto": "x"})),
                                        DIA, FATO["fato"]))
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"][2].update(
            bloco="numero", dados={"valor": 508, "prefixo": "", "sufixo": "", "legenda": "x"})), DIA, FATO["fato"]))

    def test_bloco_e_icone_do_catalogo(self):
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"][2].update(bloco="mapa")), DIA, FATO["fato"]))
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"][0]["dados"].update(icone="apple")), DIA, FATO["fato"]))

    def test_limites_de_texto(self):
        problemas = roteiro.validar(com(lambda r: r["trechos"][0]["dados"].update(carimbo="X" * 13)), DIA, FATO["fato"])
        self.assertTrue(any("carimbo" in p for p in problemas))

    def test_trecho_comeca_com_numero(self):
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"][3].update(fala="508 quilos pesava o satélite.")),
                                        DIA, FATO["fato"]))

    def test_sem_arroba_na_fala_e_com_arroba_na_legenda(self):
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"][3].update(fala="Siga @curiosidadetechhoje")),
                                        DIA, FATO["fato"]))
        self.assertTrue(roteiro.validar(com(lambda r: r.update(legenda_post="sem arroba #a #b #c")), DIA, FATO["fato"]))

    def test_palavras_demais(self):
        self.assertTrue(roteiro.validar(com(lambda r: r["trechos"][2].update(fala="Laika " + "muito " * 70)),
                                        DIA, FATO["fato"]))

    def test_destaque_fora_da_fala(self):
        self.assertTrue(roteiro.validar(com(lambda r: r["destaques"].append("Gagarin")), DIA, FATO["fato"]))

    def test_data_e_selo(self):
        self.assertTrue(roteiro.validar(com(lambda r: r.update(data="1957-11-04")), DIA, FATO["fato"]))
        self.assertTrue(roteiro.validar(com(lambda r: r.update(selo="3 nov")), DIA, FATO["fato"]))

    def test_numero_que_nao_esta_no_fato(self):
        problemas = roteiro.validar(com(lambda r: r["trechos"][3]["dados"].update(valor=600)), DIA, FATO["fato"])
        self.assertTrue(any("600" in p for p in problemas))

    def test_numeros_do_roteiro(self):
        self.assertEqual(sorted(roteiro.numeros_do_roteiro(ROTEIRO)), ["1957", "508"])


class GerarTest(unittest.TestCase):
    def test_tenta_de_novo_e_devolve_tentativa(self):
        respostas = [json.dumps({"titulo": "x"}), json.dumps(ROTEIRO, ensure_ascii=False)]
        prompts = []

        def gerar(prompt, chave, modelo, busca=False, json_mode=False):
            prompts.append(prompt)
            return respostas.pop(0), {}

        r, tentativa = roteiro.gerar_roteiro(FATO, "K", "m", gerar=gerar)
        self.assertEqual(tentativa, 2)
        self.assertEqual(r["titulo"], ROTEIRO["titulo"])
        self.assertIn("Problemas da tentativa anterior", prompts[1])

    def test_desiste_depois_das_tentativas(self):
        with self.assertRaises(roteiro.ErroRoteiro):
            roteiro.gerar_roteiro(FATO, "K", "m", gerar=lambda *a, **k: ("{}", {}), tentativas=2)


if __name__ == "__main__":
    unittest.main()
