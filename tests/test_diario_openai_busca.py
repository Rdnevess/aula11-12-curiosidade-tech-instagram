import io
import unittest
import urllib.error
from unittest import mock

from scripts.diario import openai_busca

RESPOSTA = {"output": [
    {"type": "web_search_call"},
    {"type": "message", "content": [
        {"type": "output_text", "text": "O Sputnik 2 foi lançado em 3 de novembro de 1957.", "annotations": [
            {"type": "url_citation", "url": "https://www.nasa.gov/history/sputnik/russ4.html?utm_source=openai",
             "title": "NASA", "start_index": 0, "end_index": 10},
            {"type": "url_citation", "url": "https://en.wikipedia.org/wiki/Sputnik_2",
             "title": "Wikipedia", "start_index": 10, "end_index": 20},
            {"type": "url_citation", "url": "https://www.nasa.gov/history/sputnik/russ4.html?utm_source=telegram",
             "title": "NASA", "start_index": 20, "end_index": 30},
        ]},
    ]},
]}


def post_falso(resposta, registro=None):
    def post(corpo, chave, timeout=180):
        if registro is not None:
            registro.append({"corpo": corpo, "chave": chave, "timeout": timeout})
        return resposta
    return post


class BuscarTest(unittest.TestCase):
    def test_monta_corpo_concatena_texto_e_extrai_fontes_unicas(self):
        chamadas = []
        texto, fontes = openai_busca.buscar("pergunte algo", "K", "gpt-5.4-mini", post=post_falso(RESPOSTA, chamadas))
        self.assertIn("Sputnik", texto)
        self.assertEqual(fontes, [{"dominio": "nasa.gov", "url": "https://www.nasa.gov/history/sputnik/russ4.html"},
                                  {"dominio": "en.wikipedia.org", "url": "https://en.wikipedia.org/wiki/Sputnik_2"}])
        corpo, chave = chamadas[0]["corpo"], chamadas[0]["chave"]
        self.assertEqual(corpo, {"model": "gpt-5.4-mini", "tools": [{"type": "web_search"}], "input": "pergunte algo"})
        self.assertEqual(chave, "K")

    def test_concatena_texto_de_varias_mensagens(self):
        resposta = {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "parte 1 "}]},
            {"type": "message", "content": [{"type": "output_text", "text": "parte 2"}]},
        ]}
        texto, fontes = openai_busca.buscar("p", "K", "m", post=post_falso(resposta))
        self.assertEqual(texto, "parte 1 parte 2")
        self.assertEqual(fontes, [])

    def test_resposta_sem_texto_gera_erro(self):
        resposta = {"output": [{"type": "web_search_call"}]}
        with self.assertRaises(openai_busca.ErroOpenAI):
            openai_busca.buscar("p", "K", "m", post=post_falso(resposta))

    def test_resposta_com_mensagem_vazia_gera_erro(self):
        resposta = {"output": [{"type": "message", "content": [{"type": "output_text", "text": ""}]}]}
        with self.assertRaises(openai_busca.ErroOpenAI):
            openai_busca.buscar("p", "K", "m", post=post_falso(resposta))


class PostTest(unittest.TestCase):
    def test_http_error_nao_expoe_a_chave(self):
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "https://api.openai.com/v1/responses", 401, "unauthorized", {}, io.BytesIO(b'{"error": "invalid"}'))
            with self.assertRaises(openai_busca.ErroOpenAI) as ctx:
                openai_busca._post({"model": "m"}, "minha_chave_secreta")
        self.assertNotIn("minha_chave_secreta", str(ctx.exception))
        self.assertIn("401", str(ctx.exception))

    def test_url_error_nao_expoe_a_chave(self):
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError(ConnectionError("conexão recusada"))
            with self.assertRaises(openai_busca.ErroOpenAI) as ctx:
                openai_busca._post({"model": "m"}, "minha_chave_secreta")
        self.assertNotIn("minha_chave_secreta", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
