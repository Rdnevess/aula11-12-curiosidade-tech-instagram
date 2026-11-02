import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.diario import __main__ as cli
from scripts.diario import config


class RodarArgumentosTest(unittest.TestCase):
    def test_data_sem_valor_imprime_uso_em_vez_de_quebrar(self):
        with self.assertRaises(SystemExit):
            cli.main(["rodar", "--data"])


class PastaTemporariaMixin:
    # Os .cmd vão para config.PASTA_DADOS: os testes não podem escrever no diario/ real do repositório.
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp()) / "pasta com espaço" / "diario"
        patcher = mock.patch.object(config, "PASTA_DADOS", self.pasta)
        patcher.start()
        self.addCleanup(patcher.stop)


class CmdTest(PastaTemporariaMixin, unittest.TestCase):
    def test_cmd_nao_duplica_quebra_de_linha(self):
        # Lido em bytes (não como texto): ler como texto aplicaria a tradução universal de
        # quebras de linha e desfaria \r\n -> \n, escondendo exatamente o bug que este teste cobre.
        arquivo = cli._cmd("rodar")
        self.assertEqual(arquivo.parent, self.pasta)
        conteudo = arquivo.read_bytes()
        self.assertNotIn(b"\r\r\n", conteudo)
        self.assertIn(b"\r\n", conteudo)


class AgendarTest(PastaTemporariaMixin, unittest.TestCase):
    def test_tr_com_aspas_internas_escapadas_por_causa_dos_espacos(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), mock.patch.object(cli.subprocess, "run") as run:
            cli.agendar(False)
        run.assert_not_called()
        linhas = saida.getvalue().splitlines()
        for subcomando in ("rodar", "verificar"):
            caminho = str(self.pasta / f"{subcomando}.cmd")
            linha = next(l for l in linhas if f"\\{subcomando}\"" in l and "/TN" in l)
            self.assertIn('/TR "\\"' + caminho + '\\""', linha)
            self.assertIn("/F", linha)

    def test_confirmar_executa_o_mesmo_texto(self):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(cli.subprocess, "run") as run:
            cli.agendar(True)
        comandos = [c.args[0] for c in run.call_args_list]
        self.assertEqual(len(comandos), 2)
        self.assertTrue(all('/TR "\\"' in c for c in comandos))


if __name__ == "__main__":
    unittest.main()
