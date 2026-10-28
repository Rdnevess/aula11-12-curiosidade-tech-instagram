import json
import unittest

from scripts import wf_post

NOMES = ["Novo post", "Preparar mídia", "Hospedar mídia", "Link direto", "Conta do Instagram",
         "Criar contêiner", "Aguardar processamento", "Status do contêiner", "Pronto?", "Falhou",
         "Publicar", "Link do post", "Post publicado"]


class WfPostTest(unittest.TestCase):
    def setUp(self):
        self.wf = wf_post.construir("C1")
        self.nos = {n["name"]: n for n in self.wf["nodes"]}
        self.c = self.wf["connections"]

    def destinos(self, origem, saida=0):
        return [d["node"] for d in self.c[origem]["main"][saida]]

    def test_nome_e_13_nos(self):
        self.assertEqual(self.wf["name"], "Aula 11 - Post no Instagram")
        self.assertEqual([n["name"] for n in self.wf["nodes"]], NOMES)
        self.assertEqual(wf_post.ORDEM, NOMES)

    def test_conexoes_apontam_para_nos_existentes(self):
        for origem, saidas in self.c.items():
            self.assertIn(origem, self.nos)
            for ramo in saidas["main"]:
                for d in ramo:
                    self.assertIn(d["node"], self.nos)

    def test_sequencia_principal(self):
        seq = NOMES[:9]
        for a, b in zip(seq, seq[1:]):
            self.assertEqual(self.destinos(a), [b])
        self.assertEqual(self.destinos("Publicar"), ["Link do post"])
        self.assertEqual(self.destinos("Link do post"), ["Post publicado"])

    def test_saidas_do_switch(self):
        self.assertEqual(self.destinos("Pronto?", 0), ["Publicar"])
        self.assertEqual(self.destinos("Pronto?", 1), ["Falhou"])
        self.assertEqual(self.destinos("Pronto?", 2), ["Aguardar processamento"])
        p = self.nos["Pronto?"]["parameters"]
        self.assertEqual(p["options"]["fallbackOutput"], "extra")
        regras = p["rules"]["values"]
        self.assertEqual(regras[0]["conditions"]["conditions"][0]["rightValue"], "FINISHED")
        falha = regras[1]["conditions"]["conditions"][0]["leftValue"]
        for trecho in ("ERROR", "EXPIRED", "$runIndex >= 29"):
            self.assertIn(trecho, falha)

    def test_formulario(self):
        p = self.nos["Novo post"]["parameters"]
        self.assertEqual(p["options"]["path"], "post-instagram")
        midia, legenda = p["formFields"]["values"]
        self.assertEqual((midia["fieldName"], midia["fieldType"], midia["acceptFileTypes"]),
                         ("midia", "file", ".jpg,.jpeg,.mp4,.mov"))
        self.assertEqual((legenda["fieldName"], legenda["fieldType"]), ("legenda", "textarea"))

    def test_criar_conteiner_por_tipo(self):
        consulta = self.nos["Criar contêiner"]["parameters"]["jsonQuery"]
        self.assertTrue(consulta.startswith("={{ JSON.stringify(") and consulta.endswith("}) }}"))
        for trecho in ("REELS", "video_url", "image_url", "caption", "tmpfiles", "Preparar mídia"):
            self.assertIn(trecho, consulta)

    def test_espera_e_publicacao(self):
        self.assertEqual(self.nos["Aguardar processamento"]["parameters"], {"amount": 10, "unit": "seconds"})
        self.assertIn("Criar contêiner", self.nos["Publicar"]["parameters"]["queryParameters"]["parameters"][0]["value"])
        self.assertIn("$json.permalink", self.nos["Post publicado"]["parameters"]["completionMessage"])

    def test_credencial_em_5_nos_e_sem_token(self):
        com = [n["name"] for n in self.wf["nodes"] if "credentials" in n]
        self.assertEqual(com, ["Conta do Instagram", "Criar contêiner", "Status do contêiner", "Publicar", "Link do post"])
        for nome in com:
            self.assertEqual(self.nos[nome]["credentials"], {"httpQueryAuth": {"id": "C1", "name": "Instagram TEP"}})
        texto = json.dumps(self.wf, ensure_ascii=False, indent=2)
        self.assertEqual(texto.count('"name": "Instagram TEP"'), 5)
        self.assertNotIn("access_token", texto)


if __name__ == "__main__":
    unittest.main()
