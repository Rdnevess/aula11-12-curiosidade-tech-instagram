"""Testes da lógica dos nós Code da Aula 12 (scripts/aula12/js/*.js),
chamados via Node através de scripts/aula12/js_util.chamar.
"""
import hashlib
import hmac
import json
import unittest
from pathlib import Path

from scripts.aula12 import js_util

RAIZ = Path(__file__).resolve().parent.parent
EVENTOS = RAIZ / "Aula12-continuacao-insta" / "volume-12" / "eventos"


def carregar_evento(nome):
    return json.loads((EVENTOS / nome).read_text(encoding="utf-8"))


class TestJsUtil(unittest.TestCase):
    def test_carregar_devolve_texto_do_arquivo(self):
        texto = js_util.carregar("assinatura")
        self.assertIn("assinaturaValida", texto)
        self.assertIn("module.exports", texto)


class TestAssinatura(unittest.TestCase):
    def setUp(self):
        self.corpo = '{"a":1}'
        self.segredo = "s3"
        self.cabecalho = "sha256=" + hmac.new(
            self.segredo.encode("utf-8"), self.corpo.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def chamar(self, cabecalho, segredo=None):
        return js_util.chamar(
            "assinatura", "assinaturaValida", self.corpo, cabecalho, segredo or self.segredo
        )

    def test_assinatura_correta_e_valida(self):
        self.assertTrue(self.chamar(self.cabecalho))

    def test_assinatura_trocada_e_invalida(self):
        trocado = self.cabecalho[:-2] + ("00" if self.cabecalho[-2:] != "00" else "11")
        self.assertFalse(self.chamar(trocado))

    def test_cabecalho_ausente_e_invalido(self):
        self.assertFalse(self.chamar(None))

    def test_sem_prefixo_sha256_e_invalido(self):
        sem_prefixo = self.cabecalho.replace("sha256=", "")
        self.assertFalse(self.chamar(sem_prefixo))

    def test_hex_invalido_e_invalido(self):
        self.assertFalse(self.chamar("sha256=not-hex!!"))

    def test_hex_de_tamanho_impar_e_invalido(self):
        # hexadecimal válido (só 0-9a-f), mas com número ímpar de dígitos:
        # não forma bytes completos, então não pode ser a assinatura.
        self.assertFalse(self.chamar("sha256=abc"))


class TestEventos(unittest.TestCase):
    def test_comentario_do_arquivo_de_exemplo(self):
        corpo = carregar_evento("comentario.json")
        itens = js_util.chamar("eventos", "separarEventos", corpo, "conta-diferente")
        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["tipo"], "comentario")
        self.assertEqual(item["comentario_id"], "17800000000000000")
        self.assertEqual(item["midia_id"], "17900000000000000")

    def test_mensagem_do_arquivo_de_exemplo(self):
        corpo = carregar_evento("mensagem.json")
        itens = js_util.chamar("eventos", "separarEventos", corpo, "conta-diferente")
        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["tipo"], "mensagem")
        self.assertEqual(item["remetente"], "1234567890123456")

    def test_mensagem_echo_e_descartada(self):
        corpo = carregar_evento("mensagem.json")
        corpo["entry"][0]["messaging"][0]["message"]["is_echo"] = True
        itens = js_util.chamar("eventos", "separarEventos", corpo, "conta-diferente")
        self.assertEqual(itens, [])

    def test_mensagem_sem_texto_e_descartada(self):
        corpo = carregar_evento("mensagem.json")
        del corpo["entry"][0]["messaging"][0]["message"]["text"]
        itens = js_util.chamar("eventos", "separarEventos", corpo, "conta-diferente")
        self.assertEqual(itens, [])

    def test_comentario_da_propria_conta_e_descartado(self):
        corpo = carregar_evento("comentario.json")
        conta_id = corpo["entry"][0]["changes"][0]["value"]["from"]["id"]
        itens = js_util.chamar("eventos", "separarEventos", corpo, conta_id)
        self.assertEqual(itens, [])

    def test_mudanca_que_nao_e_comentario_e_descartada(self):
        corpo = {"entry": [{"changes": [{"field": "mentions", "value": {"id": "1"}}]}]}
        itens = js_util.chamar("eventos", "separarEventos", corpo, "conta-diferente")
        self.assertEqual(itens, [])


HISTORICO_BASE = {
    "2026-11-04#1": {
        "status": "publicado",
        "media_id": "M1",
        "titulo": "T",
        "fato": "Primeira frase. A NASA confirmou 3 voos.",
        "fontes": [
            {"dominio": "jpl.nasa.gov", "url": "u1"},
            {"dominio": "nasa.gov", "url": "u2"},
            {"dominio": "si.edu", "url": "u3"},
        ],
        "falas": ["Primeira frase."],
    }
}


def evento_comentario(texto, midia_id="M1", de_id="U1", pai_id=None):
    return {"texto": texto, "midia_id": midia_id, "de_id": de_id, "pai_id": pai_id}


def resposta(texto, historico=None, midia_id="M1", de_id="U1", pai_id=None, conta_id="CONTA"):
    return js_util.chamar(
        "comentario",
        "respostaComentario",
        evento_comentario(texto, midia_id, de_id, pai_id),
        historico if historico is not None else HISTORICO_BASE,
        conta_id,
    )


class TestComentario(unittest.TestCase):
    def test_normalizar_minusculas_sem_acento(self):
        self.assertEqual(js_util.chamar("comentario", "normalizar", "É REAL?"), "e real?")

    def test_dominios_base_unicos_ate_tres(self):
        fontes = HISTORICO_BASE["2026-11-04#1"]["fontes"]
        self.assertEqual(
            js_util.chamar("comentario", "dominiosBase", fontes, 3), ["nasa.gov", "si.edu"]
        )

    def test_frase_extra_prefere_frase_nao_falada(self):
        self.assertEqual(
            js_util.chamar(
                "comentario",
                "fraseExtra",
                "Primeira frase. A NASA confirmou 3 voos.",
                ["Primeira frase."],
            ),
            "A NASA confirmou 3 voos.",
        )

    def test_frase_extra_sem_falas_usa_primeira_frase(self):
        self.assertEqual(
            js_util.chamar("comentario", "fraseExtra", "Primeira frase. Segunda frase.", []),
            "Primeira frase.",
        )

    def test_post_por_midia_encontra_registro_publicado(self):
        registro = js_util.chamar("comentario", "postPorMidia", HISTORICO_BASE, "M1")
        self.assertEqual(registro["titulo"], "T")

    def test_post_por_midia_desconhecida_e_none(self):
        self.assertIsNone(js_util.chamar("comentario", "postPorMidia", HISTORICO_BASE, "ZZZ"))

    def test_regra_1_fonte(self):
        r = resposta("qual a FONTE disso?")
        self.assertEqual(r["resposta"], "As fontes deste post: nasa.gov, si.edu. (resposta automática)")
        self.assertEqual(r["chave"], "resp:M1:U1")

    def test_regra_2_frase_extra(self):
        r = resposta("conta mais")
        self.assertEqual(r["resposta"], "A NASA confirmou 3 voos. (resposta automática)")

    def test_regra_3_horario(self):
        r = resposta("Que horas posta?")
        self.assertEqual(
            r["resposta"],
            "Postamos 2 curiosidades por dia, às 10h e às 12h (Brasília). (resposta automática)",
        )

    def test_regra_4_agradecimento_com_emoji(self):
        r = resposta("valeu demais \U0001F525")
        self.assertEqual(r["resposta"], "Valeu! \U0001F64C Amanhã tem mais. (resposta automática)")

    def test_mais_nao_casa_dentro_de_demais(self):
        # "demais" não deve acionar a regra 2 (frase extra) por conter "mais".
        r = resposta("valeu demais \U0001F525")
        self.assertNotEqual(r["resposta"], "A NASA confirmou 3 voos. (resposta automática)")

    def test_sem_regra_casando_e_none(self):
        self.assertIsNone(resposta("legal"))

    def test_pai_id_preenchido_e_none(self):
        self.assertIsNone(resposta("fonte?", pai_id="algum-id"))

    def test_midia_desconhecida_e_none(self):
        self.assertIsNone(resposta("fonte?", midia_id="ZZZ"))

    def test_de_id_igual_conta_e_none(self):
        self.assertIsNone(resposta("fonte?", de_id="CONTA", conta_id="CONTA"))

    def test_resposta_longa_e_cortada_em_300_terminando_no_sufixo(self):
        frase_longa = ("palavra " * 60).strip() + "."
        historico = {
            "2026-11-01#1": {
                "status": "publicado",
                "media_id": "M2",
                "titulo": "Longo",
                "fato": frase_longa,
                "fontes": [],
                "falas": [],
            }
        }
        r = resposta("explica mais", historico=historico, midia_id="M2", de_id="U9")
        self.assertLessEqual(len(r["resposta"]), 300)
        self.assertTrue(r["resposta"].endswith(" (resposta automática)"))


class TestAgente(unittest.TestCase):
    def setUp(self):
        self.historico = {
            "2026-11-04#1": dict(HISTORICO_BASE["2026-11-04#1"]),
            "2026-11-05#1": {
                "status": "pendente",
                "titulo": "NaoDeveAparecer",
                "fontes": [],
            },
        }

    def test_prompt_contem_identidade_e_lista_de_posts(self):
        prompt = js_util.chamar("agente", "promptSistema", self.historico, 30)
        self.assertIn("@curiosidadetechhoje", prompt)
        self.assertIn("assistente automático", prompt)
        self.assertIn("2026-11-04 · T · nasa.gov, si.edu", prompt)

    def test_prompt_nao_contem_registros_pendentes(self):
        prompt = js_util.chamar("agente", "promptSistema", self.historico, 30)
        self.assertNotIn("NaoDeveAparecer", prompt)

    def test_prompt_e_igual_ao_texto_aprovado_com_posts_substituidos(self):
        # Deriva o esperado da fixture versionada (não do JS), para que uma
        # paráfrase no agente.js seja pega por este teste. A fixture é uma
        # cópia do texto aprovado (.superpowers/sdd/2026-11-05-aula12-respostas/
        # prompt-aprovado.txt, pasta de scratch fora do git) sem a última
        # linha, que era só uma nota de implementação, não texto do prompt.
        caminho = RAIZ / "tests" / "fixtures" / "aula12" / "prompt-aprovado.txt"
        linhas = caminho.read_text(encoding="utf-8").split("\n")
        while linhas and linhas[-1] == "":
            linhas.pop()

        indice_placeholder = next(
            i for i, l in enumerate(linhas) if "{para cada post" in l
        )
        linhas[indice_placeholder : indice_placeholder + 1] = [
            "  2026-11-04 · T · nasa.gov, si.edu"
        ]
        linhas.append(
            "- Quando encaminhar ao responsável, termine a resposta com a marca [ENCAMINHAR]."
        )
        esperado = "\n".join(linhas)

        prompt = js_util.chamar("agente", "promptSistema", self.historico, 30)
        self.assertEqual(prompt, esperado)

    def test_prompt_sem_posts_usa_marcador_nenhum_ainda(self):
        prompt = js_util.chamar("agente", "promptSistema", {}, 30)
        self.assertIn("  (nenhum ainda)", prompt)

    def test_separar_encaminhar_retira_marca(self):
        self.assertEqual(
            js_util.chamar("agente", "separarEncaminhar", "Vou encaminhar. [ENCAMINHAR]"),
            {"texto": "Vou encaminhar.", "encaminhar": True},
        )

    def test_separar_encaminhar_sem_marca(self):
        self.assertEqual(
            js_util.chamar("agente", "separarEncaminhar", "Oi, tudo bem?"),
            {"texto": "Oi, tudo bem?", "encaminhar": False},
        )

    def test_separar_encaminhar_corta_em_900(self):
        texto = "a" * 1200
        resultado = js_util.chamar("agente", "separarEncaminhar", texto)
        self.assertEqual(len(resultado["texto"]), 900)
        self.assertFalse(resultado["encaminhar"])


if __name__ == "__main__":
    unittest.main()
