import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.diario import fluxo


class RecuperarTest(unittest.TestCase):
    def setUp(self):
        self.arquivo = Path(tempfile.mkdtemp()) / "recuperar.json"
        self.rodados = []
        self.n8n = True

    def _recuperar(self, agora, hist=None, resultado="publicado"):
        def rodar_slot(dia, slot):
            self.rodados.append((dia.isoformat(), slot))
            if isinstance(resultado, Exception):
                raise resultado
            return resultado
        return fluxo.recuperar(agora, carregar=lambda: dict(hist or {}), n8n_no_ar=lambda: self.n8n,
                               rodar_slot=rodar_slot, arquivo=self.arquivo)

    def test_antes_do_primeiro_horario_nao_faz_nada(self):
        self.assertEqual(self._recuperar(datetime(2026, 11, 13, 10, 59)), "nada a recuperar")
        self.assertEqual(self.rodados, [])

    def test_horario_perdido_roda_o_slot(self):
        self.assertEqual(self._recuperar(datetime(2026, 11, 13, 13, 0)), "2026-11-13#1: publicado")
        self.assertEqual(self.rodados, [("2026-11-13", 1)])

    def test_slot_com_qualquer_registro_nao_e_recuperado(self):
        # descartado/expirado não estão em RESOLVIDOS, mas foram decisão do usuário: não refaz.
        for status in ("publicado", "pendente", "descartado", "expirado", "erro_publicacao"):
            self.rodados.clear()
            hist = {"2026-11-13#1": {"status": status}}
            self.assertEqual(self._recuperar(datetime(2026, 11, 13, 13, 0), hist), "nada a recuperar")
            self.assertEqual(self.rodados, [])

    def test_chave_legada_do_dia_conta_como_slot_1(self):
        hist = {"2026-11-13": {"status": "publicado"}}
        self.assertEqual(self._recuperar(datetime(2026, 11, 13, 13, 0), hist), "nada a recuperar")

    def test_um_slot_por_vez_e_na_ordem(self):
        self._recuperar(datetime(2026, 11, 13, 20, 0))
        self.assertEqual(self.rodados, [("2026-11-13", 1)])
        hist = {"2026-11-13#1": {"status": "publicado"}}
        self._recuperar(datetime(2026, 11, 13, 20, 10), hist)
        self.assertEqual(self.rodados, [("2026-11-13", 1), ("2026-11-13", 2)])

    def test_n8n_fora_do_ar_espera_sem_gastar_tentativa(self):
        self.n8n = False
        self.assertEqual(self._recuperar(datetime(2026, 11, 13, 13, 0)), "n8n fora do ar; tento de novo depois")
        self.assertEqual(self.rodados, [])
        self.assertFalse(self.arquivo.exists())

    def test_desiste_depois_de_3_tentativas_e_passa_ao_proximo_slot(self):
        for _ in range(3):
            self.assertIn("falhou", self._recuperar(datetime(2026, 11, 13, 13, 0), resultado=RuntimeError("503")))
        self.assertEqual(self._recuperar(datetime(2026, 11, 13, 13, 30), resultado=RuntimeError("503")),
                         "nada a recuperar")
        self.assertEqual(len(self.rodados), 3)
        self._recuperar(datetime(2026, 11, 13, 18, 30))
        self.assertEqual(self.rodados[-1], ("2026-11-13", 2))

    def test_tentativas_de_outros_dias_sao_esquecidas(self):
        self.arquivo.write_text(json.dumps({"2026-11-12#1": 3}), encoding="utf-8")
        self._recuperar(datetime(2026, 11, 13, 13, 0))
        self.assertEqual(json.loads(self.arquivo.read_text(encoding="utf-8")), {"2026-11-13#1": 1})


if __name__ == "__main__":
    unittest.main()
