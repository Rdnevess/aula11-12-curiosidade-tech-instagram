import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from scripts.diario import __main__ as cli
from scripts.diario import config


class RodarArgumentosTest(unittest.TestCase):
    def test_data_sem_valor_imprime_uso_em_vez_de_quebrar(self):
        with self.assertRaises(SystemExit):
            cli.main(["rodar", "--data"])

    def _rodar(self, argumentos):
        # fluxo.rodar trocado por um falso: o teste só confere os argumentos, nunca roda o fluxo real.
        with mock.patch.object(cli.fluxo, "rodar", return_value="ok") as rodar, \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main(argumentos)
        return rodar.call_args

    def test_slot_padrao_e_1(self):
        chamada = self._rodar(["rodar", "--data", "2026-11-04"])
        self.assertEqual(chamada.args, (date(2026, 11, 4),))
        self.assertEqual(chamada.kwargs, {"slot": 1, "sem_publicar": False})

    def test_slot_2_e_sem_publicar(self):
        chamada = self._rodar(["rodar", "--data", "2026-11-03", "--slot", "2", "--sem-publicar"])
        self.assertEqual(chamada.args, (date(2026, 11, 3),))
        self.assertEqual(chamada.kwargs, {"slot": 2, "sem_publicar": True})

    def test_slot_invalido_ou_sem_valor_imprime_uso(self):
        for argumentos in (["rodar", "--slot", "3"], ["rodar", "--slot", "x"], ["rodar", "--slot"]):
            with mock.patch.object(cli.fluxo, "rodar") as rodar, self.assertRaises(SystemExit) as cm:
                cli.main(argumentos)
            rodar.assert_not_called()
            self.assertEqual(cm.exception.code, cli.__doc__)


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
        arquivo = cli._cmd("rodar-1", "rodar --slot 1")
        self.assertEqual(arquivo.parent, self.pasta)
        conteudo = arquivo.read_bytes()
        self.assertNotIn(b"\r\r\n", conteudo)
        self.assertIn(b"\r\n", conteudo)
        self.assertIn(b"-m scripts.diario rodar --slot 1 >>", conteudo)
        self.assertIn(b"diario\\rodar-1.log", conteudo)


class AgendarTest(PastaTemporariaMixin, unittest.TestCase):
    def _saida(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), mock.patch.object(cli.subprocess, "run") as run:
            cli.agendar(False)
        run.assert_not_called()
        return saida.getvalue().splitlines()

    def test_tres_tarefas_com_horarios_e_tr_escapado(self):
        linhas = self._saida()
        criar = [l for l in linhas if l.startswith("schtasks /Create")]
        self.assertEqual(len(criar), 5)
        esperado = {"rodar-1": "/SC DAILY /ST 11:00", "rodar-2": "/SC DAILY /ST 18:00", "verificar": "/SC MINUTE /MO 10"}
        for nome, agenda in esperado.items():
            caminho = str(self.pasta / f"{nome}.cmd")
            linha = next(l for l in criar if f'/TN "CuriosidadeTech\\{nome}"' in l)
            self.assertIn(agenda, linha)
            self.assertIn('/TR "\\"' + caminho + '\\""', linha)
            self.assertIn("/F", linha)
        self.assertIn(b"rodar --slot 1", (self.pasta / "rodar-1.cmd").read_bytes())
        self.assertIn(b"rodar --slot 2", (self.pasta / "rodar-2.cmd").read_bytes())
        self.assertIn(b"scripts.diario verificar >>", (self.pasta / "verificar.cmd").read_bytes())

    def test_nova_tentativa_40_min_depois_com_o_mesmo_cmd(self):
        linhas = self._saida()
        for slot, hora in ((1, "11:40"), (2, "18:40")):
            linha = next(l for l in linhas if f'/TN "CuriosidadeTech\\rodar-{slot}-retentativa"' in l)
            self.assertIn(f"/SC DAILY /ST {hora}", linha)
            self.assertIn('/TR "\\"' + str(self.pasta / f"rodar-{slot}.cmd") + '\\""', linha)

    def test_imprime_remocao_da_tarefa_antiga(self):
        linhas = self._saida()
        self.assertIn('schtasks /Delete /TN "CuriosidadeTech\\rodar" /F', linhas)

    def test_confirmar_executa_o_mesmo_texto_e_ignora_falha_ao_remover(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), mock.patch.object(cli.subprocess, "run") as run:
            cli.agendar(True)
        impressos = [l for l in saida.getvalue().splitlines() if l.startswith("schtasks")]
        comandos = [c.args[0] for c in run.call_args_list]
        self.assertEqual(comandos, impressos)
        self.assertEqual(len(comandos), 6)
        for c in run.call_args_list:
            if "/Create" in c.args[0]:
                self.assertTrue(c.kwargs.get("check"))
                self.assertIn('/TR "\\"', c.args[0])
            else:
                self.assertFalse(c.kwargs.get("check", False))


if __name__ == "__main__":
    unittest.main()
