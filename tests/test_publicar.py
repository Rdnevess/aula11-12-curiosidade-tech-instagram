import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.publicar as publicar_mod

from scripts.publicar import montar_multipart, nomes_campos, registrar

# Trecho do HTML real do formulário publicado (n8n 2.42.5), com as quebras de linha dentro das tags.
HTML = """<form><input
    class='form-input form-required'
    type='file'
    id='field-0'
    name='field-0'
    accept='.jpg,.jpeg,.mp4,.mov'
/>
<textarea
    class='form-input form-required'
    id='field-1'
    name='field-1'
></textarea>
<input id="useResponseData" style="display: none;" value=true /></form>"""


class PublicarTest(unittest.TestCase):
    def test_nomes_dos_campos(self):
        self.assertEqual(nomes_campos(HTML), ("field-0", "field-1"))

    def test_formulario_sem_campos(self):
        with self.assertRaises(ValueError):
            nomes_campos("<form></form>")

    def test_multipart(self):
        corpo = montar_multipart([("field-1", "Olá")], ("field-0", "v.mp4", "video/mp4", b"\x00\x01"), "LIM")
        self.assertTrue(corpo.startswith(b"--LIM\r\nContent-Disposition: form-data; name=\"field-1\"\r\n\r\n"))
        self.assertIn("Olá".encode("utf-8"), corpo)
        self.assertIn(b'name="field-0"; filename="v.mp4"\r\nContent-Type: video/mp4\r\n\r\n\x00\x01\r\n', corpo)
        self.assertTrue(corpo.endswith(b"--LIM--\r\n"))

    def test_registrar_acrescenta(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "resultados.json"
            registrar({"arquivo": "a.jpg"}, caminho)
            registrar({"arquivo": "b.mp4"}, caminho)
            self.assertEqual([r["arquivo"] for r in json.loads(caminho.read_text(encoding="utf-8"))],
                             ["a.jpg", "b.mp4"])


class PublicarArquivoTest(unittest.TestCase):
    def test_erro_da_execucao_vira_excecao(self):
        execucao = {"id": "9", "status": "error",
                    "data": {"resultData": {"error": {"message": "Invalid OAuth 2.0 Access Token"}}}}
        with mock.patch.object(publicar_mod, "buscar_workflow", return_value={"id": "w"}), \
             mock.patch.object(publicar_mod, "ultimo_id", return_value=1), \
             mock.patch.object(publicar_mod, "_enviar"), \
             mock.patch.object(publicar_mod, "esperar_execucao", return_value=execucao):
            with self.assertRaises(publicar_mod.ErroPublicacao) as ctx:
                publicar_mod.publicar_arquivo(Path("posts/post-aula11.jpg"), "x")
        self.assertIn("Invalid OAuth", str(ctx.exception))

    def _publicar(self, run_data, registrar_erro=None):
        execucao = {"id": "9", "status": "success", "data": {"resultData": {"runData": run_data}}}
        registrar = mock.Mock(side_effect=registrar_erro)
        with (mock.patch.object(publicar_mod, "buscar_workflow", return_value={"id": "w"}),
              mock.patch.object(publicar_mod, "ultimo_id", return_value=1),
              mock.patch.object(publicar_mod, "_enviar"),
              mock.patch.object(publicar_mod, "esperar_execucao", return_value=execucao),
              mock.patch.object(publicar_mod, "registrar", registrar),
              mock.patch("sys.stderr", new_callable=io.StringIO)):
            return publicar_mod.publicar_arquivo(Path("posts/post-aula11.jpg"), "x"), registrar

    @staticmethod
    def _no(json_):
        return [{"data": {"main": [[{"json": json_}]]}}]

    def test_falha_ao_registrar_nao_esconde_o_post_publicado(self):
        resultado, registrar = self._publicar({"Link do post": self._no({"permalink": "https://ig/p/1"}),
                                               "Preparar mídia": self._no({"tipo": "IMAGE"})},
                                              registrar_erro=OSError("disco cheio"))
        self.assertEqual(resultado["permalink"], "https://ig/p/1")
        registrar.assert_called_once()

    def test_sem_link_do_post_vira_erro_claro(self):
        with self.assertRaises(publicar_mod.ErroPublicacao) as ctx:
            self._publicar({"Preparar mídia": self._no({"tipo": "IMAGE"})})
        self.assertIn("link do post", str(ctx.exception).lower())
        with self.assertRaises(publicar_mod.ErroPublicacao):
            self._publicar({"Link do post": self._no({"outro": 1})})


if __name__ == "__main__":
    unittest.main()
