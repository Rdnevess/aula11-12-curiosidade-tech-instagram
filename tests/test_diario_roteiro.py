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
        {"fala": "Dentro dele estava a cadela Laika.", "bloco": "fato", "dados": {"texto": "A bordo: a cadela Laika"}},
        {"fala": "Esse satélite pesava 508 quilos.", "bloco": "numero",
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

    def test_trechos_nao_e_lista_string(self):
        problemas = roteiro.validar(com(lambda r: r.update(trechos="não é lista")), DIA, FATO["fato"])
        self.assertTrue(problemas)

    def test_trechos_nao_e_lista_dict(self):
        problemas = roteiro.validar(com(lambda r: r.update(trechos={"a": 1})), DIA, FATO["fato"])
        self.assertTrue(problemas)

    def test_trecho_nao_e_objeto(self):
        problemas = roteiro.validar(com(lambda r: r["trechos"].__setitem__(1, "não é objeto")), DIA, FATO["fato"])
        self.assertTrue(problemas)

    def test_dados_nao_e_dict(self):
        problemas = roteiro.validar(com(lambda r: r["trechos"][0].update(dados=["a", "b"])), DIA, FATO["fato"])
        self.assertTrue(problemas)

    def test_titulo_obrigatorio(self):
        for valor in (None, "", "   ", 5):
            problemas = roteiro.validar(com(lambda r: r.update(titulo=valor)), DIA, FATO["fato"])
            self.assertTrue(any("titulo" in p for p in problemas), repr(valor))
        problemas = roteiro.validar(com(lambda r: r.pop("titulo")), DIA, FATO["fato"])
        self.assertTrue(any("titulo" in p for p in problemas))

    def test_ancora_de_uma_letra_a_partir_do_segundo_trecho(self):
        problemas = roteiro.validar(com(lambda r: r["trechos"][2].update(fala="A bordo estava a cadela Laika.")),
                                    DIA, FATO["fato"])
        self.assertTrue(any("trecho 3" in p and "âncora" in p for p in problemas))
        # o 1º trecho não tem âncora
        problemas = roteiro.validar(com(lambda r: r["trechos"][0].update(fala="E se um cachorro fosse ao espaço?")),
                                    DIA, FATO["fato"])
        self.assertEqual(problemas, [])

    def test_ancora_ignora_travessao_e_exige_palavra(self):
        travessao = chr(8212)
        meia_risca = chr(8211)
        ok = com(lambda r: r["trechos"][2].update(fala=travessao + " Dentro dele estava a cadela Laika."))
        self.assertEqual(roteiro.validar(ok, DIA, FATO["fato"]), [])
        for traco in (travessao, meia_risca):
            problemas = roteiro.validar(com(lambda r: r["trechos"][1].update(
                fala=traco + " 1957 foi o ano do Sputnik 2.")), DIA, FATO["fato"])
            self.assertTrue(any("trecho 2" in p for p in problemas), traco)


class NumerosTest(unittest.TestCase):
    def test_float_integral_vira_inteiro(self):
        self.assertEqual(roteiro._numeros("508.0"), {"508"})
        self.assertEqual(roteiro._numeros(508.0), {"508"})

    def test_ponto_como_separador_de_milhar(self):
        self.assertEqual(roteiro._numeros("3.000.000"), {"3000000"})

    def test_virgula_decimal_nao_e_separador_de_milhar(self):
        self.assertEqual(roteiro._numeros("3,5 bilhões"), set())


class GerarTest(unittest.TestCase):
    def test_tenta_de_novo_e_devolve_tentativa(self):
        respostas = [json.dumps({"titulo": "x"}), json.dumps(ROTEIRO, ensure_ascii=False)]
        prompts = []

        def gerar(prompt, chave, modelo, busca=False, json_mode=False, **kwargs):
            prompts.append(prompt)
            return respostas.pop(0), {}

        r, tentativa = roteiro.gerar_roteiro(FATO, "K", "m", gerar=gerar)
        self.assertEqual(tentativa, 2)
        self.assertEqual(r["titulo"], ROTEIRO["titulo"])
        self.assertIn("Problemas da tentativa anterior", prompts[1])

    def test_desiste_depois_das_tentativas(self):
        with self.assertRaises(roteiro.ErroRoteiro):
            roteiro.gerar_roteiro(FATO, "K", "m", gerar=lambda *a, **k: ("{}", {}), tentativas=2)

    def test_continua_apos_resposta_malformada(self):
        malformado = com(lambda r: r.update(destaques=5))
        respostas = [json.dumps(malformado, ensure_ascii=False), json.dumps(ROTEIRO, ensure_ascii=False)]

        def gerar(prompt, chave, modelo, busca=False, json_mode=False, **kwargs):
            return respostas.pop(0), {}

        r, tentativa = roteiro.gerar_roteiro(FATO, "K", "m", gerar=gerar)
        self.assertEqual(tentativa, 2)
        self.assertEqual(r["titulo"], ROTEIRO["titulo"])


if __name__ == "__main__":
    unittest.main()
