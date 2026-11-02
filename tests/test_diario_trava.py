import unittest

from scripts.diario import trava

FONTES = [{"dominio": "wikipedia.org", "url": "u1"}, {"dominio": "nasa.gov", "url": "u2"}]
CONF = {"data_confirmada": True, "numeros": [{"valor": "508", "confirmado": True}], "fontes": FONTES}
FATO = {"fontes": FONTES}


class DecidirTest(unittest.TestCase):
    def test_tudo_ok_publica(self):
        self.assertEqual(trava.decidir(FATO, CONF, 1, [], False), (True, []))

    def test_poucas_fontes(self):
        ok, motivos = trava.decidir({"fontes": FONTES[:1]}, CONF, 1, [], False)
        self.assertFalse(ok)
        self.assertTrue(any("domínios" in m for m in motivos))

    def test_so_wikipedia(self):
        fontes = [{"dominio": "wikipedia.org", "url": "a"}, {"dominio": "pt.wikipedia.org", "url": "b"}]
        self.assertFalse(trava.decidir({"fontes": fontes}, CONF, 1, [], False)[0])

    def test_data_ou_numero_nao_confirmado(self):
        self.assertFalse(trava.decidir(FATO, {**CONF, "data_confirmada": False}, 1, [], False)[0])
        conf = {**CONF, "numeros": [{"valor": "508", "confirmado": False}]}
        self.assertFalse(trava.decidir(FATO, conf, 1, [], False)[0])

    def test_checagem_com_poucas_fontes(self):
        self.assertFalse(trava.decidir(FATO, {**CONF, "fontes": FONTES[:1]}, 1, [], False)[0])

    def test_roteiro_na_terceira_tentativa_video_ruim_ou_repetido(self):
        self.assertFalse(trava.decidir(FATO, CONF, 3, [], False)[0])
        self.assertFalse(trava.decidir(FATO, CONF, 1, ["duração 31 s"], False)[0])
        self.assertFalse(trava.decidir(FATO, CONF, 1, [], True)[0])


if __name__ == "__main__":
    unittest.main()
