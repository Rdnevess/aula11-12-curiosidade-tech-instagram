import unittest

from scripts.exportar import gerar_posts_md, normalizar, sem_segredos

DA_API = {
    "id": "abc", "name": "W", "active": True, "versionId": "v1", "shared": [{"role": "x"}],
    "nodes": [{"name": "N", "credentials": {"httpQueryAuth": {"id": "C1", "name": "Instagram TEP"}},
               "parameters": {"queryParameters": {"parameters": [{"name": "fields", "value": "user_id"}]}}}],
    "connections": {}, "settings": {"executionOrder": "v1"},
}


class ExportarTest(unittest.TestCase):
    def test_campos_do_export_da_interface(self):
        wf = normalizar(DA_API)
        self.assertEqual(list(wf), ["name", "nodes", "connections", "settings", "pinData", "meta"])
        self.assertEqual((wf["pinData"], wf["meta"]), ({}, {}))

    def test_credencial_por_referencia_e_ok(self):
        self.assertTrue(sem_segredos(normalizar(DA_API)))

    def test_token_vazado_e_detectado(self):
        vazado = {**DA_API, "nodes": [{"parameters": {"access_token": "x"}}]}
        self.assertFalse(sem_segredos(normalizar(vazado)))
        token = {**DA_API, "nodes": [{"parameters": {"url": "https://x/?a=IGAA" + "b" * 120}}]}
        self.assertFalse(sem_segredos(normalizar(token)))

    def test_posts_md(self):
        md = gerar_posts_md([
            {"arquivo": "post-aula11.jpg", "tipo": "imagem", "permalink": "https://www.instagram.com/p/A/",
             "execucao_id": "7", "publicado_em": "2026-10-27T21:03:00-04:00"},
            {"arquivo": "v1.mp4", "tipo": "video", "permalink": "https://www.instagram.com/reel/B/",
             "execucao_id": "8", "publicado_em": "2026-10-27T21:10:00-04:00"},
        ])
        self.assertIn("| 1 | post-aula11.jpg | imagem | https://www.instagram.com/p/A/ | 2026-10-27 21:03 | 7 |", md)
        self.assertIn("| 2 | v1.mp4 | Reel | https://www.instagram.com/reel/B/ | 2026-10-27 21:10 | 8 |", md)


if __name__ == "__main__":
    unittest.main()
