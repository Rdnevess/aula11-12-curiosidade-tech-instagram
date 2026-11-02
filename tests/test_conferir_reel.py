import copy
import tempfile
import unittest
from pathlib import Path

from scripts.conferir_reel import loudness_de, moov_antes_de_mdat, validar_reel, validar_video

REEL = {
    "lines": [
        "Sabia que o Facebook começou com um site proibido?",
        "Em outubro de 2003, Zuckerberg criou o Facemash em Harvard.",
        "Duas fotos de alunos, sem permissão: quem é mais bonito?",
        "450 visitantes em 4 horas… e Harvard derrubou o site.",
        "Siga @curiosidadetechhoje!",
    ],
    "pronounce": {"@curiosidadetechhoje": "arroba curiosidade téc hoje"},
    "voice": {"mode": "take", "voices": ["Puck"], "note": "x",
              "anchors": [["em", "outubro"], ["duas", "fotos"], ["450|quatrocentos"], ["siga"]],
              "maxSeconds": 16.5, "speedupMax": 0.1},
    "render": {"stage": "../curiosidade.html", "fps": 30, "width": 1080, "height": 1920,
               "data": {"scene": "facemash", "highlight": ["Facebook", "Facemash", "sem", "permissão", "450",
                                                          "@curiosidadetechhoje"]}},
}

VIDEO = {"duracao": 18.6, "largura": 1080, "altura": 1920, "fps": 30.0,
         "vcodec": "h264", "pix_fmt": "yuv420p", "acodec": "aac"}


def com(alteracao):
    dados = copy.deepcopy(REEL)
    alteracao(dados)
    return dados


class ValidarReelTest(unittest.TestCase):
    def test_reel_valido(self):
        self.assertEqual(validar_reel(REEL), [])

    def test_ancoras_devem_ser_uma_por_trecho_apos_o_primeiro(self):
        problemas = validar_reel(com(lambda d: d["voice"]["anchors"].pop()))
        self.assertTrue(any("âncoras" in p for p in problemas))

    def test_voz_so_puck_em_take(self):
        self.assertTrue(validar_reel(com(lambda d: d["voice"].update(voices=["Kore"]))))
        self.assertTrue(validar_reel(com(lambda d: d["voice"].update(mode="segments"))))

    def test_fala_no_maximo_16_5_s(self):
        self.assertTrue(validar_reel(com(lambda d: d["voice"].update(maxSeconds=18))))

    def test_ultimo_trecho_e_o_cta(self):
        problemas = validar_reel(com(lambda d: d["lines"].__setitem__(-1, "Até a próxima!")))
        self.assertTrue(any("CTA" in p for p in problemas))

    def test_pronuncia_do_arroba(self):
        self.assertTrue(validar_reel(com(lambda d: d.update(pronounce={}))))

    def test_template_e_cena_da_serie(self):
        self.assertTrue(validar_reel(com(lambda d: d["render"].update(stage="@stage"))))
        self.assertTrue(validar_reel(com(lambda d: d["render"]["data"].update(scene="exemplo"))))

    def test_formato_1080x1920_30fps(self):
        self.assertTrue(validar_reel(com(lambda d: d["render"].update(fps=60))))

    def test_destaque_precisa_estar_na_fala(self):
        problemas = validar_reel(com(lambda d: d["render"]["data"]["highlight"].append("Napster")))
        self.assertTrue(any("Napster" in p for p in problemas))

    def test_texto_longo_demais(self):
        problemas = validar_reel(com(lambda d: d["lines"].__setitem__(2, " ".join(["palavra"] * 30))))
        self.assertTrue(any("palavras" in p for p in problemas))

    def test_speedupmax_deve_estar_presente_e_menor_igual_0_1(self):
        problemas = validar_reel(com(lambda d: d["voice"].pop("speedupMax")))
        self.assertTrue(any("speedupMax" in p for p in problemas))
        problemas = validar_reel(com(lambda d: d["voice"].update(speedupMax=0.15)))
        self.assertTrue(any("speedupMax" in p for p in problemas))

    def test_pronuncia_exata_do_arroba(self):
        problemas = validar_reel(com(lambda d: d["pronounce"].update({"@curiosidadetechhoje": "arroba curiosidade"})))
        self.assertTrue(any("pronuncia" in p.lower() or "arroba curiosidade téc hoje" in p for p in problemas))

    def test_cta_exato(self):
        problemas = validar_reel(com(lambda d: d["lines"].__setitem__(-1, "Siga @curiosidadetechhoje")))
        self.assertTrue(any("CTA" in p for p in problemas))


class ValidarVideoTest(unittest.TestCase):
    def test_video_valido(self):
        self.assertEqual(validar_video(VIDEO), [])

    def test_mais_de_20_s(self):
        self.assertTrue(validar_video({**VIDEO, "duracao": 20.4}))

    def test_limite_de_duracao_configuravel(self):
        self.assertEqual(validar_video({**VIDEO, "duracao": 29.5}, max_duracao=30.0), [])
        self.assertTrue(validar_video({**VIDEO, "duracao": 30.2}, max_duracao=30.0))

    def test_resolucao_fps_codecs(self):
        self.assertTrue(validar_video({**VIDEO, "largura": 720}))
        self.assertTrue(validar_video({**VIDEO, "fps": 25.0}))
        self.assertTrue(validar_video({**VIDEO, "vcodec": "hevc"}))
        self.assertTrue(validar_video({**VIDEO, "pix_fmt": "yuv444p"}))
        self.assertTrue(validar_video({**VIDEO, "acodec": None}))


class FaststartTest(unittest.TestCase):
    def _mp4(self, *caixas):
        f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        for tipo in caixas:
            f.write((8).to_bytes(4, "big") + tipo)
        f.close()
        path = Path(f.name)
        self.addCleanup(path.unlink)
        return path

    def test_moov_antes(self):
        self.assertTrue(moov_antes_de_mdat(self._mp4(b"ftyp", b"moov", b"mdat")))

    def test_moov_depois(self):
        self.assertFalse(moov_antes_de_mdat(self._mp4(b"ftyp", b"mdat", b"moov")))


class LoudnessTest(unittest.TestCase):
    def test_le_integrado_do_resumo(self):
        saida = "[Parsed_ebur128_0 @ 0x1]   Summary:\n\n  Integrated loudness:\n    I:         -15.2 LUFS\n"
        self.assertEqual(loudness_de(saida), -15.2)

    def test_sem_resumo(self):
        self.assertIsNone(loudness_de("nada aqui"))


if __name__ == "__main__":
    unittest.main()
