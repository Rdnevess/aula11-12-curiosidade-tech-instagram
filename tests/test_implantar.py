import unittest
from unittest import mock

from scripts import configurar_n8n, implantar
from scripts.n8n_api import ErroApi

CREDENCIAIS = {"data": [{"id": "X", "name": "Outra", "type": "httpQueryAuth"},
                        {"id": "C1", "name": "Instagram TEP", "type": "httpQueryAuth"}]}


class CredencialTest(unittest.TestCase):
    def test_acha_pelo_nome_e_tipo(self):
        with mock.patch.object(configurar_n8n, "api", return_value=CREDENCIAIS):
            self.assertEqual(configurar_n8n.obter_id_credencial(), "C1")

    def test_ausente_explica_o_que_fazer(self):
        with mock.patch.object(configurar_n8n, "api", return_value={"data": []}):
            with self.assertRaisesRegex(ErroApi, "seção 3.5"):
                configurar_n8n.obter_id_credencial()


class ImplantarTest(unittest.TestCase):
    def test_atualiza_existente_e_publica(self):
        chamadas = []

        def falsa(metodo, caminho, corpo=None):
            chamadas.append((metodo, caminho))
            if caminho.startswith("/workflows?"):
                return {"data": [{"id": "W1", "name": "Aula 11 - Post no Instagram"}]}
            return {"id": "W1", "versionId": "v2"}

        with mock.patch.object(implantar, "api", side_effect=falsa):
            self.assertEqual(implantar.implantar({"name": "Aula 11 - Post no Instagram"}), "W1")
        self.assertEqual(chamadas[1:], [("PUT", "/workflows/W1"), ("POST", "/workflows/W1/publish")])

    def test_cria_quando_nao_existe(self):
        def falsa(metodo, caminho, corpo=None):
            return {"data": []} if caminho.startswith("/workflows?") else {"id": "N1", "versionId": "v1"}

        with mock.patch.object(implantar, "api", side_effect=falsa) as m:
            self.assertEqual(implantar.implantar({"name": "Novo"}), "N1")
        self.assertEqual(m.call_args_list[1].args[:2], ("POST", "/workflows"))


if __name__ == "__main__":
    unittest.main()
