"""Testes de scripts/aula12/infra.py: geração do .env.n8n (compose da Aula 09)
e do diff proposto do compose (webhook, variáveis de segurança, pasta do
diário, Redis) — Aula 12, Task 4 (ver design, seção 1)."""
import unittest
from pathlib import Path

from scripts.aula12 import infra

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "aula12" / "docker-compose.yml"
DOMINIO = "exemplo-fake.ngrok-free.app"
PASTA_DIARIO = "C:/Users/PC/Desktop/Aula Top Esp Programacao/aula11-n8n-insta/diario"


class TestEnvN8n(unittest.TestCase):
    def test_contem_as_tres_linhas(self):
        saida = infra.env_n8n({
            "META_APP_SECRET": "segredo-fake",
            "INSTAGRAM_CONTA_ID": "123456",
            "TELEGRAM_CHAT_ID": "987654",
        })
        linhas = saida.splitlines()
        self.assertIn("META_APP_SECRET=segredo-fake", linhas)
        self.assertIn("INSTAGRAM_CONTA_ID=123456", linhas)
        self.assertIn("TELEGRAM_CHAT_ID=987654", linhas)

    def test_meta_app_secret_vazio_se_faltar(self):
        saida = infra.env_n8n({"INSTAGRAM_CONTA_ID": "1", "TELEGRAM_CHAT_ID": "2"})
        self.assertIn("META_APP_SECRET=", saida.splitlines())


class TestComposeAtualizado(unittest.TestCase):
    def setUp(self):
        self.atual = FIXTURE.read_text(encoding="utf-8")

    def _aplicar(self, texto=None):
        return infra.compose_atualizado(texto if texto is not None else self.atual, DOMINIO, PASTA_DIARIO)

    def test_acrescenta_variaveis_de_ambiente_do_n8n(self):
        novo = self._aplicar()
        for linha in [
            f"WEBHOOK_URL=https://{DOMINIO}",
            "NODE_FUNCTION_ALLOW_BUILTIN=crypto",
            "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
            "N8N_RESTRICT_FILE_ACCESS_TO=/dados;/home/node/.n8n-files",
        ]:
            self.assertIn(linha, novo)

    def test_acrescenta_env_file_apontando_para_env_n8n(self):
        novo = self._aplicar()
        self.assertIn("env_file:", novo)
        self.assertIn(".env.n8n", novo)

    def test_acrescenta_volume_do_diario_citado_por_causa_do_espaco_e_dois_pontos(self):
        novo = self._aplicar()
        self.assertIn(f'"{PASTA_DIARIO}:/dados/diario:ro"', novo)

    def test_mantem_volume_original_do_n8n(self):
        novo = self._aplicar()
        self.assertIn("n8n_data:/home/node/.n8n", novo)

    def test_acrescenta_servico_redis(self):
        novo = self._aplicar()
        self.assertIn("redis:7-alpine", novo)
        self.assertIn("container_name: n8n-redis", novo)
        self.assertIn("restart: unless-stopped", novo)
        self.assertIn("redis_data:/data", novo)

    def test_servico_redis_nao_publica_porta(self):
        novo = self._aplicar()
        inicio = novo.index("\n  redis:")
        resto = novo[inicio:]
        # a próxima seção de nível zero (ex.: "volumes:") delimita o fim do bloco do redis
        import re
        m = re.search(r"\n\S", resto[1:])
        bloco_redis = resto[: m.start() + 1] if m else resto
        self.assertNotIn("ports:", bloco_redis)

    def test_declara_volume_redis_data_no_topo(self):
        novo = self._aplicar()
        self.assertRegex(novo, r"(?m)^volumes:\n(?:.*\n)*?  redis_data:\s*$")

    def test_aplicar_duas_vezes_da_a_mesma_saida(self):
        primeira = self._aplicar()
        segunda = self._aplicar(primeira)
        self.assertEqual(primeira, segunda)

    def test_aplicar_duas_vezes_nao_duplica_env_file_nem_servico_redis(self):
        duas_vezes = self._aplicar(self._aplicar())
        self.assertEqual(duas_vezes.count("env_file:"), 1)
        self.assertEqual(duas_vezes.count("\n  redis:\n"), 1)
        self.assertEqual(duas_vezes.count("WEBHOOK_URL="), 1)

    def test_nao_altera_servico_redis_existente_em_bloco_do_n8n(self):
        # a correção de limite de bloco (indentação >= 4) não pode "engolir"
        # o serviço redis como se fosse parte do n8n na segunda aplicação.
        novo = self._aplicar()
        bloco_n8n = infra._bloco_servico(novo, "n8n").group(0)
        self.assertNotIn("redis:7-alpine", bloco_n8n)


if __name__ == "__main__":
    unittest.main()
