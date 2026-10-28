import unittest

from scripts.wf_util import ligar, no


class WfUtilTest(unittest.TestCase):
    def test_no_com_credencial_e_webhook(self):
        n = no("A", "n8n-nodes-base.code", 2, (0, 0), {"x": 1}, credenciais={"c": 1}, webhook_id="w")
        self.assertEqual((n["name"], n["typeVersion"], n["position"]), ("A", 2, [0, 0]))
        self.assertEqual((n["credentials"], n["webhookId"]), ({"c": 1}, "w"))

    def test_id_estavel(self):
        self.assertEqual(no("A", "t", 1, (0, 0), {})["id"], no("A", "t", 1, (9, 9), {})["id"])

    def test_ligar_saidas_numeradas(self):
        c = {}
        ligar(c, "S", "A")
        ligar(c, "S", "C", saida=2)
        ramos = c["S"]["main"]
        self.assertEqual([[d["node"] for d in r] for r in ramos], [["A"], [], ["C"]])


if __name__ == "__main__":
    unittest.main()
