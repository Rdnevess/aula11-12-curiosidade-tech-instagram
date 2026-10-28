import unittest

from scripts.execucoes import saida_json


def execucao(run_data):
    return {"data": {"resultData": {"runData": run_data}}}


def rodada(*saidas):
    return {"data": {"main": [[{"json": j} for j in s] for s in saidas]}}


class SaidaJsonTest(unittest.TestCase):
    def test_ultima_rodada_primeiro_item(self):
        self.assertEqual(saida_json(execucao({"N": [rodada([{"v": 1}]), rodada([{"v": 2}])]}), "N"), {"v": 2})

    def test_saida_em_ramo_diferente_do_primeiro(self):
        self.assertEqual(saida_json(execucao({"S": [rodada([], [{"ok": 1}])]}), "S"), {"ok": 1})

    def test_no_ausente(self):
        self.assertIsNone(saida_json(execucao({}), "X"))


if __name__ == "__main__":
    unittest.main()
