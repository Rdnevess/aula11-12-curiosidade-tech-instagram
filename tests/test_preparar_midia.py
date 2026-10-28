import json
import subprocess
import unittest

from scripts.wf_post import CODIGO_PREPARAR


def executar(item):
    """Roda o código do nó no Node, com um $input simulado, e devolve o que ele retorna."""
    programa = (f"const $input = {{ first: () => ({json.dumps(item)}) }};\n"
                f"const r = (() => {{\n{CODIGO_PREPARAR}\n}})();\nconsole.log(JSON.stringify(r));")
    feito = subprocess.run(["node", "-e", programa], capture_output=True, text=True, encoding="utf-8")
    if feito.returncode:
        raise RuntimeError(feito.stderr)
    return json.loads(feito.stdout)


def envio(mime, nome="x", chave="Mídia"):
    return {"json": {"legenda": "Olá"}, "binary": {chave: {"mimeType": mime, "fileName": nome}}}


class PrepararMidiaTest(unittest.TestCase):
    def test_jpeg_vira_imagem(self):
        [saida] = executar(envio("image/jpeg", "post-aula11.jpg"))
        self.assertEqual(saida["json"], {"arquivo": "post-aula11.jpg", "tipo": "imagem", "legenda": "Olá"})
        self.assertEqual(list(saida["binary"]), ["midia"])

    def test_mp4_e_mov_viram_video(self):
        self.assertEqual(executar(envio("video/mp4"))[0]["json"]["tipo"], "video")
        self.assertEqual(executar(envio("video/quicktime"))[0]["json"]["tipo"], "video")

    def test_png_recusado(self):
        with self.assertRaisesRegex(RuntimeError, "aceita JPEG, MP4 ou MOV; o arquivo é image/png"):
            executar(envio("image/png"))

    def test_sem_arquivo(self):
        with self.assertRaisesRegex(RuntimeError, "Nenhum arquivo recebido"):
            executar({"json": {"legenda": "x"}})


if __name__ == "__main__":
    unittest.main()
