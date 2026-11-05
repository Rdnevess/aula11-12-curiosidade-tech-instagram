import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aula12 import exportar, implantar, posts

BOT = "123456:BOT-TOKEN-SECRETO-abcdefghijklmnop"


class ApiFalsa:
    def __init__(self, existentes):
        self.existentes = list(existentes)
        self.chamadas = []

    def __call__(self, metodo, caminho, corpo=None):
        self.chamadas.append((metodo, caminho, corpo))
        if metodo == "GET" and caminho.startswith("/credentials"):
            return {"data": self.existentes}
        if metodo == "POST" and caminho == "/credentials":
            novo = {"id": f"N{len(self.existentes)}", "name": corpo["name"], "type": corpo["type"]}
            self.existentes.append(novo)
            return novo
        raise AssertionError(f"chamada inesperada {metodo} {caminho}")


BASE = [{"id": "IG", "name": "Instagram TEP", "type": "httpQueryAuth"},
        {"id": "GQ", "name": "Groq", "type": "groqApi"}]


class CredenciaisTest(unittest.TestCase):
    def rodar(self, api):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ids = implantar.credenciais(api, env={"TELEGRAM_BOT_TOKEN": BOT})
        return ids, saida.getvalue()

    def test_existentes_reaproveitadas(self):
        api = ApiFalsa(BASE + [{"id": "RD", "name": "Redis", "type": "redis"},
                               {"id": "TG", "name": "Telegram Aviso", "type": "telegramApi"}])
        ids, _ = self.rodar(api)
        self.assertEqual(ids, {"instagram": "IG", "groq": "GQ", "redis": "RD", "telegram": "TG"})
        self.assertFalse([c for c in api.chamadas if c[0] == "POST"])

    def test_faltantes_criadas_com_tipo_certo(self):
        api = ApiFalsa(BASE)
        ids, saida = self.rodar(api)
        criadas = {c[2]["name"]: c[2] for c in api.chamadas if c[0] == "POST"}
        self.assertEqual(criadas["Redis"]["type"], "redis")
        self.assertEqual(criadas["Redis"]["data"], {"host": "redis", "port": 6379, "database": 0})
        self.assertEqual(criadas["Telegram Aviso"]["type"], "telegramApi")
        self.assertEqual(criadas["Telegram Aviso"]["data"], {"accessToken": BOT})
        self.assertEqual(set(ids), {"instagram", "groq", "redis", "telegram"})
        self.assertNotIn(BOT, saida)

    def test_mesmo_nome_com_outro_tipo_nao_conta(self):
        api = ApiFalsa(BASE + [{"id": "X", "name": "Redis", "type": "httpQueryAuth"}])
        ids, _ = self.rodar(api)
        self.assertNotEqual(ids["redis"], "X")

    def test_instagram_ausente_e_erro(self):
        with self.assertRaises(SystemExit):
            self.rodar(ApiFalsa(BASE[1:]))


class TokenTest(unittest.TestCase):
    def test_gera_grava_e_reaproveita(self):
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            env.write_text("A=1\nB=2", encoding="utf-8")
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                token = implantar.garantir_token(env)
            self.assertRegex(token, r"^[0-9a-f]{24}$")
            self.assertNotIn(token, saida.getvalue())
            texto = env.read_text(encoding="utf-8")
            self.assertIn("A=1\nB=2\n", texto)
            self.assertIn(f"WEBHOOK_VERIFY_TOKEN={token}", texto)
            self.assertEqual(implantar.garantir_token(env), token)


def _reels(pasta):
    raiz = Path(pasta)
    (raiz / "ROTEIROS.md").write_text(
        "# Roteiros\n\n### facemash (selo \"28 OUT\")\n| # | Locução | Na tela |\n|---|---|---|\n"
        "| s1 | Sabia que o **Facebook** começou proibido? | x |\n"
        "| s2 | Em 2003, Zuckerberg criou o **Facemash**. | y |\n"
        "| s3 | Siga **@curiosidadetechhoje**! | Cartão final |\n\n"
        "## Fontes da pesquisa\n\n"
        "- Facemash: https://www.lawandcrime.com/a/b ·\n  https://informationweek.com/c\n"
        "- Mega Drive / Tec Toy: https://en.wikipedia.org/wiki/Tectoy\n",
        encoding="utf-8")
    (raiz / "facemash").mkdir()
    (raiz / "facemash" / "reel.json").write_text(json.dumps({"lines": ["Fala 1", "Fala 2"]}), encoding="utf-8")
    return raiz


class BackfillTest(unittest.TestCase):
    MIDIAS = [{"id": "M1", "permalink": "https://www.instagram.com/reel/AAA/"},
              {"id": "M2", "permalink": "https://www.instagram.com/reel/BBB/?igsh=xyz"},
              {"id": "M3", "permalink": "https://www.instagram.com/reel/CCC"}]

    def test_casa_permalinks_com_e_sem_barra(self):
        historico = {
            "a": {"status": "publicado", "permalink": "https://www.instagram.com/reel/AAA"},
            "b": {"status": "publicado", "permalink": "https://www.instagram.com/reel/BBB/"},
            "c": {"status": "publicado", "permalink": "https://www.instagram.com/reel/CCC/"},
            "d": {"status": "publicado", "permalink": "https://www.instagram.com/reel/ZZZ/"},
            "e": {"status": "pendente"},
        }
        with tempfile.TemporaryDirectory() as pasta:
            novo = posts.backfill(historico, self.MIDIAS, reels=_reels(pasta))
        self.assertEqual((novo["a"]["media_id"], novo["b"]["media_id"], novo["c"]["media_id"]), ("M1", "M2", "M3"))
        self.assertNotIn("media_id", novo["d"])
        self.assertNotIn("media_id", novo["e"])
        self.assertNotIn("media_id", historico["a"])  # não altera o original

    def test_manual_ganha_fato_fontes_e_falas(self):
        historico = {"manual-facemash": {"titulo": "Facemash", "status": "manual",
                                         "permalink": "https://www.instagram.com/reel/AAA/"}}
        with tempfile.TemporaryDirectory() as pasta:
            novo = posts.backfill(historico, self.MIDIAS, reels=_reels(pasta))["manual-facemash"]
        self.assertEqual(novo["media_id"], "M1")
        self.assertEqual(novo["titulo"], "Facemash")
        self.assertEqual(novo["fato"], "Sabia que o Facebook começou proibido? Em 2003, Zuckerberg criou o Facemash.")
        self.assertEqual(novo["falas"], ["Fala 1", "Fala 2"])
        self.assertEqual(novo["fontes"], [{"dominio": "lawandcrime.com", "url": "https://www.lawandcrime.com/a/b"},
                                          {"dominio": "informationweek.com", "url": "https://informationweek.com/c"}])

    def test_publicado_sem_fato_le_da_pasta(self):
        with tempfile.TemporaryDirectory() as pasta:
            trabalho = Path(pasta) / "diario-x"
            trabalho.mkdir()
            (trabalho / "pesquisa.json").write_text(json.dumps({"fato": "F.", "fontes": []}), encoding="utf-8")
            (trabalho / "roteiro.json").write_text(json.dumps({"trechos": [{"fala": "a"}, {"fala": "b"}]}),
                                                   encoding="utf-8")
            historico = {"x": {"status": "publicado", "permalink": "https://www.instagram.com/reel/AAA/",
                               "video": str(trabalho / "out" / "v.mp4"), "fato": None},
                         "y": {"status": "publicado", "permalink": "https://www.instagram.com/reel/BBB/",
                               "pasta": str(trabalho), "fato": "já tinha", "falas": ["z"]}}
            novo = posts.backfill(historico, self.MIDIAS, reels=_reels(pasta))
        self.assertEqual((novo["x"]["fato"], novo["x"]["falas"]), ("F.", ["a", "b"]))
        self.assertEqual((novo["y"]["fato"], novo["y"]["falas"]), ("já tinha", ["z"]))

    def test_lista_de_midias_da_resposta(self):
        self.assertEqual(posts.midias_da_resposta({"data": [{"id": "1"}], "paging": {}}), [{"id": "1"}])
        self.assertEqual(posts.midias_da_resposta([{"data": [{"id": "1"}]}]), [{"id": "1"}])


WF = {"id": "W", "name": "Aula 12 - Verificação do webhook", "active": True,
      "nodes": [{"parameters": {"rightValue": "abcdef0123456789abcdef01"}}],
      "connections": {}, "settings": {}}


class ExportarTest(unittest.TestCase):
    def test_token_substituido(self):
        texto = exportar.preparar(WF, "abcdef0123456789abcdef01", ["outro-segredo-qualquer"])
        self.assertNotIn("abcdef0123456789abcdef01", texto)
        self.assertIn("<WEBHOOK_VERIFY_TOKEN>", texto)
        self.assertEqual(list(json.loads(texto)), ["name", "nodes", "connections", "settings", "pinData", "meta"])

    def test_segredo_presente_e_erro(self):
        with self.assertRaises(SystemExit):
            exportar.preparar(WF, "token-que-nao-esta-ali", ["0123456789abcdef01"])

    def test_segredos_do_env(self):
        env = {"N8N_API_KEY": "k" * 30, "TELEGRAM_BOT_TOKEN": BOT, "META_APP_SECRET": "",
               "INSTAGRAM_CONTA_ID": "17841475108548218", "TELEGRAM_CHAT_ID": "123"}
        self.assertEqual(sorted(exportar.segredos(env)), sorted(["k" * 30, BOT]))


if __name__ == "__main__":
    unittest.main()
