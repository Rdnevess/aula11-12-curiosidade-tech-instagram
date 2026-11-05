"""Testes de scripts/aula12/tunel.py e scripts/aula12/verificar_tunel.py
(Aula 12, Task 5 — ver docs/superpowers/specs/2026-11-05-aula12-respostas-design.md,
seção 4, e o brief da task)."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.aula12 import tunel, verificar_tunel

DOMINIO = "exemplo-fake.ngrok-free.dev"
POLITICA = Path("C:/fake/ngrok-politica.yml")
NGROK_FAKE = "C:/fake/ngrok.exe"


class NgrokExeTest(unittest.TestCase):
    def test_usa_which_quando_disponivel(self):
        with mock.patch.object(tunel.shutil, "which", return_value="C:/outro/ngrok.exe"):
            self.assertEqual(tunel.ngrok_exe(), "C:/outro/ngrok.exe")

    def test_usa_caminho_padrao_quando_which_nao_acha(self):
        with mock.patch.object(tunel.shutil, "which", return_value=None):
            self.assertEqual(tunel.ngrok_exe(), tunel.NGROK_PADRAO)


class ComandoTest(unittest.TestCase):
    def test_contem_dominio_politica_porta_e_log(self):
        linha = tunel.comando(DOMINIO, POLITICA, ngrok=NGROK_FAKE)
        self.assertIn(f'"{NGROK_FAKE}" http', linha)
        self.assertIn(f"--url={DOMINIO}", linha)
        self.assertIn(f'--traffic-policy-file="{POLITICA}"', linha)
        self.assertIn(f" {tunel.PORTA} ", linha)
        self.assertIn("--log=stdout", linha)
        self.assertIn('>> "diario\\tunel.log"', linha)

    def test_resolve_ngrok_quando_nao_informado(self):
        with mock.patch.object(tunel, "ngrok_exe", return_value=NGROK_FAKE):
            linha = tunel.comando(DOMINIO, POLITICA)
        self.assertIn(f'"{NGROK_FAKE}"', linha)


class TarefaTest(unittest.TestCase):
    def test_aspas_internas_escapadas_como_no_diario(self):
        caminho = "C:/fake/diario/tunel.cmd"
        linha = tunel.tarefa(caminho)
        self.assertEqual(
            linha,
            f'schtasks /Create /F /SC ONLOGON /TN "CuriosidadeTech\\tunel" /TR "\\"{caminho}\\""',
        )


class PastaTemporariaMixin:
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp()) / "pasta com espaço" / "diario"
        patcher = mock.patch.object(tunel, "PASTA_DADOS", self.pasta)
        patcher.start()
        self.addCleanup(patcher.stop)


class EscreverCmdTest(PastaTemporariaMixin, unittest.TestCase):
    def test_grava_loop_com_reinicio_em_crlf_puro(self):
        arquivo = tunel.escrever_cmd(DOMINIO, POLITICA, ngrok=NGROK_FAKE)
        self.assertEqual(arquivo, self.pasta / "tunel.cmd")

        conteudo = arquivo.read_bytes()
        self.assertIn(b"\r\n", conteudo)
        self.assertNotIn(b"\r\r\n", conteudo)

        texto = conteudo.decode("utf-8")
        self.assertIn(":loop\r\n", texto)
        self.assertIn("goto loop", texto)
        self.assertIn("timeout /t 30 /nobreak >nul", texto)
        self.assertIn(tunel.comando(DOMINIO, POLITICA, ngrok=NGROK_FAKE), texto)


class AgendarTest(PastaTemporariaMixin, unittest.TestCase):
    def _saida(self, confirmar):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), mock.patch.object(tunel.subprocess, "run") as run:
            tunel.agendar(DOMINIO, confirmar, ngrok=NGROK_FAKE)
        return saida.getvalue(), run

    def test_sem_confirmar_nao_executa_schtasks(self):
        saida, run = self._saida(False)
        run.assert_not_called()
        linha_esperada = tunel.tarefa(self.pasta / "tunel.cmd")
        self.assertIn(linha_esperada, saida)
        self.assertIn("(nada foi agendado", saida)

    def test_confirmar_executa_a_mesma_linha_impressa(self):
        saida, run = self._saida(True)
        linha_esperada = tunel.tarefa(self.pasta / "tunel.cmd")
        run.assert_called_once_with(linha_esperada, check=True)


class MainTest(unittest.TestCase):
    def test_sem_dominio_no_env_sai_com_mensagem(self):
        with mock.patch.object(tunel, "carregar_env", return_value={}):
            with self.assertRaises(SystemExit):
                tunel.main([])

    def test_chama_agendar_com_dominio_e_flag_confirmar(self):
        with mock.patch.object(tunel, "carregar_env", return_value={"NGROK_DOMINIO": DOMINIO}), \
                mock.patch.object(tunel, "agendar") as agendar:
            tunel.main(["--confirmar"])
        agendar.assert_called_once_with(DOMINIO, True)

    def test_sem_flag_chama_agendar_com_confirmar_falso(self):
        with mock.patch.object(tunel, "carregar_env", return_value={"NGROK_DOMINIO": DOMINIO}), \
                mock.patch.object(tunel, "agendar") as agendar:
            tunel.main([])
        agendar.assert_called_once_with(DOMINIO, False)


class PoliticaYamlTest(unittest.TestCase):
    def test_arquivo_restringe_ao_caminho_do_webhook_e_responde_404(self):
        texto = tunel.POLITICA.read_text(encoding="utf-8")
        self.assertIn("on_http_request", texto)
        self.assertIn("/webhook/instagram", texto)
        self.assertIn("'GET'", texto)
        self.assertIn("'POST'", texto)
        self.assertIn("custom-response", texto)
        self.assertIn("404", texto)


# ---------------------------------------------------------------------------
# verificar_tunel.checar
# ---------------------------------------------------------------------------

TOKEN = "token-certo"
SEGREDO = "segredo-fake"


class ChecarTokenTest(unittest.TestCase):
    def test_sem_token_marca_pendente_e_nao_chama_abrir_para_verificacao(self):
        chamadas = []

        def abrir(metodo, url, corpo=None):
            chamadas.append((metodo, url))
            return 404, ""

        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value=None):
            resultados = verificar_tunel.checar(DOMINIO, "", SEGREDO, abrir=abrir)

        por_nome = {nome: (ok, detalhe) for nome, ok, detalhe in resultados}
        self.assertFalse(por_nome["verificação com token correto"][0])
        self.assertIn("WEBHOOK_VERIFY_TOKEN", por_nome["verificação com token correto"][1])
        self.assertFalse(por_nome["verificação com token errado"][0])
        # só o /healthz chamou abrir (o POST sem assinatura nem é tentado: workflow não existe)
        self.assertEqual(chamadas, [("GET", f"https://{DOMINIO}/healthz")])

    def test_token_certo_200_com_desafio_e_token_errado_403(self):
        def abrir(metodo, url, corpo=None):
            if f"hub.verify_token={TOKEN}&" in url:
                return 200, "777"
            if "hub.verify_token=" in url:
                return 403, "Token de verificação inválido"
            if url.endswith("/healthz"):
                return 404, ""
            raise AssertionError(f"chamada inesperada: {metodo} {url}")

        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value=None):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)

        por_nome = {nome: ok for nome, ok, _ in resultados}
        self.assertTrue(por_nome["verificação com token correto"])
        self.assertTrue(por_nome["verificação com token errado"])

    def test_corpo_diferente_do_desafio_falha_mesmo_com_200(self):
        def abrir(metodo, url, corpo=None):
            if "hub.verify_token=" in url:
                return 200, "corpo errado"
            return 404, ""

        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value=None):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)
        ok = next(ok for nome, ok, _ in resultados if nome == "verificação com token correto")
        self.assertFalse(ok)


class ChecarCaminhoForaTest(unittest.TestCase):
    def test_healthz_bloqueado_com_404_passa(self):
        def abrir(metodo, url, corpo=None):
            if url.endswith("/healthz"):
                return 404, ""
            return 200, "777"

        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value=None):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)
        ok = next(ok for nome, ok, _ in resultados if "bloqueado" in nome)
        self.assertTrue(ok)

    def test_healthz_nao_bloqueado_falha(self):
        def abrir(metodo, url, corpo=None):
            if url.endswith("/healthz"):
                return 200, "ok"
            return 200, "777"

        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value=None):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)
        ok = next(ok for nome, ok, _ in resultados if "bloqueado" in nome)
        self.assertFalse(ok)


class ChecarAssinaturaTest(unittest.TestCase):
    def _abrir(self, status_post=200):
        chamadas = []

        def abrir(metodo, url, corpo=None):
            chamadas.append((metodo, url, corpo))
            if metodo == "POST":
                return status_post, "ok"
            if url.endswith("/healthz"):
                return 404, ""
            return 200, "777"

        return abrir, chamadas

    def test_workflow_nao_implantado_fica_pendente(self):
        abrir, chamadas = self._abrir()
        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value=None):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)
        nome, ok, detalhe = next(r for r in resultados if r[0] == "POST sem assinatura é descartado")
        self.assertFalse(ok)
        self.assertEqual(detalhe, "pendente (workflow não implantado)")
        self.assertFalse(any(m == "POST" for m, _, _ in chamadas))

    def test_post_sem_assinatura_e_zero_itens_apos_conferir_assinatura_passa(self):
        abrir, chamadas = self._abrir(status_post=200)
        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value={"id": "42"}), \
                mock.patch.object(verificar_tunel.execucoes, "ultimo_id", return_value=10), \
                mock.patch.object(verificar_tunel.execucoes, "esperar_execucao", return_value={"fake": True}) as esperar, \
                mock.patch.object(verificar_tunel.execucoes, "itens_saida", return_value=0) as itens:
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)

        esperar.assert_called_once_with("42", 10, limite_s=60)
        itens.assert_called_once_with({"fake": True}, verificar_tunel.NO_ASSINATURA)
        nome, ok, detalhe = next(r for r in resultados if r[0] == "POST sem assinatura é descartado")
        self.assertTrue(ok)

        corpo_post = next(c for m, u, c in chamadas if m == "POST")
        self.assertEqual(corpo_post, verificar_tunel.EVENTO_COMENTARIO.read_text(encoding="utf-8"))

    def test_sem_segredo_a_checagem_passa_mas_avisa_no_detalhe(self):
        abrir, _ = self._abrir(status_post=200)
        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value={"id": "42"}), \
                mock.patch.object(verificar_tunel.execucoes, "ultimo_id", return_value=10), \
                mock.patch.object(verificar_tunel.execucoes, "esperar_execucao", return_value={}), \
                mock.patch.object(verificar_tunel.execucoes, "itens_saida", return_value=0):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, "", abrir=abrir)
        _, ok, detalhe = next(r for r in resultados if r[0] == "POST sem assinatura é descartado")
        self.assertTrue(ok)
        self.assertIn("META_APP_SECRET", detalhe)

    def test_execucao_passou_da_assinatura_falha(self):
        abrir, _ = self._abrir(status_post=200)
        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value={"id": "42"}), \
                mock.patch.object(verificar_tunel.execucoes, "ultimo_id", return_value=10), \
                mock.patch.object(verificar_tunel.execucoes, "esperar_execucao", return_value={}), \
                mock.patch.object(verificar_tunel.execucoes, "itens_saida", return_value=3):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)
        _, ok, detalhe = next(r for r in resultados if r[0] == "POST sem assinatura é descartado")
        self.assertFalse(ok)
        self.assertIn("Conferir assinatura", detalhe)

    def test_post_com_status_diferente_de_200_falha(self):
        abrir, _ = self._abrir(status_post=500)
        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value={"id": "42"}), \
                mock.patch.object(verificar_tunel.execucoes, "ultimo_id", return_value=10):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)
        _, ok, detalhe = next(r for r in resultados if r[0] == "POST sem assinatura é descartado")
        self.assertFalse(ok)
        self.assertIn("500", detalhe)

    def test_timeout_esperando_execucao_falha_sem_quebrar(self):
        abrir, _ = self._abrir(status_post=200)
        with mock.patch.object(verificar_tunel, "buscar_workflow", return_value={"id": "42"}), \
                mock.patch.object(verificar_tunel.execucoes, "ultimo_id", return_value=10), \
                mock.patch.object(verificar_tunel.execucoes, "esperar_execucao", side_effect=TimeoutError):
            resultados = verificar_tunel.checar(DOMINIO, TOKEN, SEGREDO, abrir=abrir)
        _, ok, detalhe = next(r for r in resultados if r[0] == "POST sem assinatura é descartado")
        self.assertFalse(ok)
        self.assertIn("nenhuma execução", detalhe)


if __name__ == "__main__":
    unittest.main()
