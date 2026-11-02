import json
import unittest
from pathlib import Path

from scripts.diario import telegram

ROTEIRO = {"titulo": "Sputnik 2", "trechos": [{"fala": "Frase um."}, {"fala": "Frase dois."}]}
FATO = {"data": "1957-11-03", "fontes": [{"dominio": "nasa.gov", "url": "https://r/1"}]}


class Gravador:
    def __init__(self, resultado=None):
        self.chamadas, self.resultado = [], resultado

    def __call__(self, token, metodo, campos=None, arquivo=None):
        self.chamadas.append({"metodo": metodo, "campos": campos, "arquivo": arquivo})
        return self.resultado


class TelegramTest(unittest.TestCase):
    def test_teclado(self):
        botoes = telegram.teclado("2026-11-03")["inline_keyboard"][0]
        self.assertEqual([b["callback_data"] for b in botoes], ["pub:2026-11-03", "desc:2026-11-03"])

    def test_texto_pendente_limita_tamanho(self):
        texto = telegram.texto_pendente(ROTEIRO, FATO, ["motivo " * 300])
        self.assertLessEqual(len(texto), 1024)
        self.assertIn("Sputnik 2", texto)
        self.assertIn("nasa.gov", texto)

    def test_enviar_video_com_botoes(self):
        g = Gravador({})
        telegram.enviar_video("T", "42", Path("posts/post-aula11.jpg"), "legenda", "2026-11-03", chamar=g)
        c = g.chamadas[0]
        self.assertEqual(c["metodo"], "sendVideo")
        self.assertEqual(c["campos"]["chat_id"], "42")
        self.assertEqual(json.loads(c["campos"]["reply_markup"])["inline_keyboard"][0][0]["callback_data"], "pub:2026-11-03")
        self.assertEqual(c["arquivo"][0], "video")

    def test_ler_cliques_filtra_chat_e_formato(self):
        updates = [
            {"update_id": 10, "callback_query": {"id": "a", "data": "pub:2026-11-03", "message": {"chat": {"id": 42}}}},
            {"update_id": 11, "callback_query": {"id": "b", "data": "pub:2026-11-03", "message": {"chat": {"id": 99}}}},
            {"update_id": 12, "callback_query": {"id": "c", "data": "lixo", "message": {"chat": {"id": 42}}}},
            {"update_id": 13, "message": {"chat": {"id": 42}, "text": "oi"}},
        ]
        g = Gravador(updates)
        cliques, offset = telegram.ler_cliques("T", "42", 5, chamar=g)
        self.assertEqual(cliques, [{"acao": "pub", "dia": "2026-11-03", "id": "a"}])
        self.assertEqual(offset, 14)
        self.assertEqual(g.chamadas[0]["campos"]["offset"], 5)

    def test_chats(self):
        g = Gravador([{"update_id": 1, "message": {"chat": {"id": 42, "first_name": "Rodrigo"}, "text": "/start"}}])
        self.assertEqual(telegram.chats("T", chamar=g), [("42", "Rodrigo")])


if __name__ == "__main__":
    unittest.main()
