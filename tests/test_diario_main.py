import unittest

from scripts.diario import __main__ as cli


class RodarArgumentosTest(unittest.TestCase):
    def test_data_sem_valor_imprime_uso_em_vez_de_quebrar(self):
        with self.assertRaises(SystemExit):
            cli.main(["rodar", "--data"])


class CmdTest(unittest.TestCase):
    def test_cmd_nao_duplica_quebra_de_linha(self):
        # Lido em bytes (não como texto): ler como texto aplicaria a tradução universal de
        # quebras de linha e desfaria \r\n -> \n, escondendo exatamente o bug que este teste cobre.
        arquivo = cli._cmd("rodar")
        conteudo = arquivo.read_bytes()
        self.assertNotIn(b"\r\r\n", conteudo)
        self.assertIn(b"\r\n", conteudo)


if __name__ == "__main__":
    unittest.main()
