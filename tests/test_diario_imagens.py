import tempfile
import unittest
from pathlib import Path

from scripts.diario import imagens


def pagina(indice, titulo, licenca="Public domain", mime="image/jpeg", largura=2000, altura=1500,
           autor="Fulano", url="https://upload/x.jpg"):
    return {"index": indice, "title": f"File:{titulo}", "imageinfo": [{
        "mime": mime, "width": largura, "height": altura, "thumburl": url,
        "extmetadata": {"LicenseShortName": {"value": licenca}, "Artist": {"value": autor}}}]}


RESPOSTA = {"query": {"pages": {
    "1": pagina(2, "ENIAC Penn1.jpg", "CC BY-SA 3.0", url="https://u/penn.jpg"),
    "2": pagina(1, "Two women operating ENIAC.gif", mime="image/gif"),
    "3": pagina(3, "ENIAC capacitors.jpg", "Copyrighted"),
    "4": pagina(4, "Reprogramming ENIAC.png", mime="image/png", url="https://u/repro.png",
                autor='<span style="display: none;">Unknown author</span>Unknown <a href="x">author</a>'),
    "5": pagina(5, "ENIAC small.jpg", largura=300, altura=200),
    "6": pagina(6, "Random building.jpg"),
    "7": pagina(7, "ENIAC Pennsylvania state historical marker.jpg"),
}}}


class FiltrarTest(unittest.TestCase):
    def test_so_fotos_livres_grandes_e_do_assunto_na_ordem_da_busca(self):
        fotos = imagens.filtrar(RESPOSTA, "ENIAC")
        self.assertEqual([f["url"] for f in fotos], ["https://u/penn.jpg", "https://u/repro.png"])

    def test_credito_limpo(self):
        fotos = imagens.filtrar(RESPOSTA, "ENIAC")
        self.assertEqual(fotos[0]["credito"], "Fulano · CC BY-SA 3.0")
        self.assertEqual(fotos[1]["credito"], "Unknown author · Public domain")

    def test_resposta_vazia(self):
        self.assertEqual(imagens.filtrar({}, "ENIAC"), [])


class AutorTest(unittest.TestCase):
    def test_uploader_original(self):
        self.assertEqual(imagens.autor('The original uploader was <a href="x">TexasDex</a> at <a>English Wikipedia</a>.',
                                       "Carnby"), "TexasDex")

    def test_obra_propria_usa_quem_enviou(self):
        self.assertEqual(imagens.autor("own picture", "Rainglasz"), "Rainglasz")
        self.assertEqual(imagens.autor("Own work", "Rainglasz"), "Rainglasz")

    def test_vazio(self):
        self.assertEqual(imagens.autor("", None), "autor desconhecido")


class TermoTest(unittest.TestCase):
    def test_usa_busca_imagem_do_roteiro(self):
        self.assertEqual(imagens.termo({"busca_imagem": " ENIAC ", "titulo": "x"}), "ENIAC")

    def test_sem_busca_imagem_nao_busca(self):
        self.assertIsNone(imagens.termo({"titulo": "O Desligamento do ENIAC"}))


class PrepararTest(unittest.TestCase):
    def test_baixa_ate_o_limite_e_devolve_caminhos_relativos(self):
        pasta = Path(tempfile.mkdtemp())
        pedidos = []

        def baixar(url):
            pedidos.append(url)
            return RESPOSTA if "api.php" in url else b"jpeg"

        fotos = imagens.preparar(pasta, {"busca_imagem": "ENIAC"}, baixar=baixar, limite=1)
        self.assertEqual(fotos, [{"arquivo": "img/foto1.jpg", "credito": "Fulano · CC BY-SA 3.0"}])
        self.assertEqual((pasta / "img" / "foto1.jpg").read_bytes(), b"jpeg")
        self.assertIn("ENIAC", pedidos[0])

    def test_falha_de_rede_fica_sem_fotos(self):
        def baixar(url):
            raise OSError("sem rede")
        self.assertEqual(imagens.preparar(Path(tempfile.mkdtemp()), {"busca_imagem": "ENIAC"}, baixar=baixar), [])

    def test_sem_termo_nao_chama_a_rede(self):
        def baixar(url):
            raise AssertionError("não devia buscar")
        self.assertEqual(imagens.preparar(Path(tempfile.mkdtemp()), {"titulo": "x"}, baixar=baixar), [])


class CreditosTest(unittest.TestCase):
    def test_linha_para_a_legenda(self):
        fotos = [{"arquivo": "a", "credito": "Fulano · CC BY 4.0"}, {"arquivo": "b", "credito": "Fulano · CC BY 4.0"},
                 {"arquivo": "c", "credito": "Unknown author · Public domain"}]
        self.assertEqual(imagens.creditos_legenda(fotos),
                         "\n\nImagens: Wikimedia Commons — Fulano · CC BY 4.0; Unknown author · Public domain")

    def test_sem_fotos_sem_linha(self):
        self.assertEqual(imagens.creditos_legenda([]), "")


if __name__ == "__main__":
    unittest.main()
