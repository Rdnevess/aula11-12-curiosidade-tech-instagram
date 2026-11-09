"""Tema repetido: mesmo título, mesma data de evento ou mesmo nome próprio de um tema já usado."""
import json
import unittest
from datetime import date

from scripts.diario import historico, pesquisa

# Dados reais de 2026-11-04: o slot 2 repetiu o UNIVAC do slot 1 com outro título.
HIST_UNIVAC = {
    "manual-pentium": {"titulo": "Bug FDIV do Pentium", "status": "manual"},
    "2026-11-04#1": {"titulo": "UNIVAC prevê eleição ao vivo", "titulo_pesquisa": "UNIVAC prevê eleição ao vivo",
                     "data_evento": "1952-11-04", "status": "publicado"},
}
FATO_UNIVAC_2 = {"titulo": "UNIVAC prevê a eleição americana", "data": "1952-11-04",
                 "fato": "Em 4 de novembro de 1952 a CBS usou o UNIVAC.", "numeros": ["1952"]}
FONTES = [{"dominio": "a.org", "url": "https://a.org/1"}, {"dominio": "b.com", "url": "https://b.com/2"}]


def buscar_fila(respostas, prompts):
    def buscar(prompt, chave, modelo):
        prompts.append(prompt)
        return json.dumps(respostas.pop(0), ensure_ascii=False), FONTES
    return buscar


class JaUsadoTest(unittest.TestCase):
    def test_univac_reproduz_o_bug_real(self):
        with self.assertRaises(pesquisa.TemaRepetido) as ctx:
            pesquisa.pesquisar(date(2026, 11, 4), HIST_UNIVAC, "K", "m", buscar=buscar_fila([FATO_UNIVAC_2], []))
        self.assertEqual(ctx.exception.titulo, "UNIVAC prevê a eleição americana")
        self.assertIsInstance(ctx.exception, pesquisa.ErroPesquisa)

    def test_mesmo_titulo_normalizado(self):
        motivo = historico.ja_usado(HIST_UNIVAC, "univac preve eleicao ao VIVO!", None)
        self.assertIn("título", motivo)

    def test_compara_com_titulo_e_titulo_pesquisa(self):
        dados = {"k": {"titulo": "O Dia em que o Computador Acertou", "titulo_pesquisa": "Previsão da CBS"}}
        self.assertIsNotNone(historico.ja_usado(dados, "previsao da cbs", None))
        self.assertIsNotNone(historico.ja_usado(dados, "o dia em que o computador acertou", None))

    def test_mesma_data_titulo_diferente(self):
        motivo = historico.ja_usado(HIST_UNIVAC, "Computador da CBS acerta resultado", "1952-11-04")
        self.assertIn("1952-11-04", motivo)

    def test_mesmo_dia_outro_ano_nao_conta(self):
        self.assertIsNone(historico.ja_usado(HIST_UNIVAC, "Lançamento do Windows 3.0", "1990-11-04"))

    def test_nome_proprio_em_comum(self):
        dados = {"k": {"titulo": "Sputnik 2 leva Laika", "data_evento": "1957-11-03"}}
        motivo = historico.ja_usado(dados, "Sputnik 2 em órbita", "1957-11-04")
        self.assertIn("sputnik", motivo)

    def test_sigla_em_comum(self):
        self.assertIn("univac", historico.ja_usado(HIST_UNIVAC, "O UNIVAC na TV", None))

    def test_palavras_genericas_maiusculas_nao_contam(self):
        dados = {"k": {"titulo": "Lançamento do Mega Drive"}, "j": {"titulo": "Primeiro e-mail da Internet"}}
        self.assertIsNone(historico.ja_usado(dados, "Lançamento do Windows 95", "1995-08-24"))
        self.assertIsNone(historico.ja_usado(dados, "Primeiro computador na Internet brasileira", None))

    def test_minuscula_nao_e_nome_proprio(self):
        # "Eleição" no título do roteiro (title case) não casa com "eleição" minúscula na pesquisa.
        dados = {"k": {"titulo": "A Eleição Digital"}}
        self.assertIsNone(historico.ja_usado(dados, "Primeira eleição com urna eletrônica", "1996-10-03"))

    def test_tema_diferente_aceito(self):
        self.assertIsNone(historico.ja_usado(HIST_UNIVAC, "Lançamento do Xbox", "2001-11-15"))

    def test_registros_legados_sem_campos_novos(self):
        legado = {"2026-11-03": {"titulo": "Lançamento da Mariner 10", "status": "publicado"},
                  "manual-facemash": {"titulo": "Facemash", "status": "manual"}, "vazio": {"status": "descartado"}}
        self.assertIsNone(historico.ja_usado(legado, "Lançamento do Xbox", "2001-11-15"))
        self.assertIsNotNone(historico.ja_usado(legado, "Mariner 10 chega a Vênus", "1974-02-05"))
        self.assertIsNotNone(historico.ja_usado(legado, "Facemash sai do ar", None))

    def test_temas_com_data_para_o_prompt(self):
        itens = historico.temas_com_data(HIST_UNIVAC)
        self.assertIn("UNIVAC prevê eleição ao vivo (1952-11-04)", itens)
        self.assertIn("Bug FDIV do Pentium", itens)


class NomesUsadosTest(unittest.TestCase):
    def test_nomes_proprios_na_grafia_original_sem_repetir(self):
        self.assertEqual(historico.nomes_usados(HIST_UNIVAC), ["FDIV", "Pentium", "UNIVAC"])


class PesquisaComHistoricoTest(unittest.TestCase):
    def test_prompt_proibe_os_nomes_usados_e_os_dos_rejeitados(self):
        prompts = []
        fato = {"titulo": "Lançamento do Xbox", "data": "2001-11-04", "fato": "…", "numeros": ["2001"]}
        pesquisa.pesquisar(date(2026, 11, 4), HIST_UNIVAC, "K", "m", buscar=buscar_fila([fato], prompts),
                           rejeitados=["Eisenhower vence com ajuda do computador"])
        linha = next(l for l in prompts[0].splitlines() if l.startswith("Nomes proibidos"))
        for nome in ("UNIVAC", "Pentium", "Eisenhower"):
            self.assertIn(nome, linha)

    def test_prompt_lista_titulo_com_data_e_pede_para_nao_repetir(self):
        prompts = []
        fato = {"titulo": "Lançamento do Xbox", "data": "2001-11-04", "fato": "…", "numeros": ["2001"]}
        pesquisa.pesquisar(date(2026, 11, 4), HIST_UNIVAC, "K", "m", buscar=buscar_fila([fato], prompts))
        self.assertIn("UNIVAC prevê eleição ao vivo (1952-11-04)", prompts[0])
        self.assertIn("Não repita nenhum desses acontecimentos, nem o mesmo acontecimento com outro nome ou outro "
                      "ângulo.", prompts[0])

    def test_rejeitados_entram_no_prompt(self):
        prompts = []
        fato = {"titulo": "Lançamento do Xbox", "data": "2001-11-04", "fato": "…", "numeros": ["2001"]}
        pesquisa.pesquisar(date(2026, 11, 4), HIST_UNIVAC, "K", "m", buscar=buscar_fila([fato], prompts),
                           rejeitados=["UNIVAC prevê a eleição americana"])
        self.assertIn("UNIVAC prevê a eleição americana", prompts[0])


# Dados reais de 2026-11-09: o slot 2 trouxe o Firefox 1.0 (já publicado às 9h) nas 3 tentativas.
HIST_FIREFOX = {
    "2026-11-09#1": {"titulo": "O Lançamento do Firefox 1.0", "titulo_pesquisa": "Firefox 1.0 é lançado",
                     "data_evento": "2004-11-09", "status": "publicado"},
}
FIREFOX = {"titulo": "Firefox 1.0 lançado", "data": "2004-11-09", "fato": "Em 9 de novembro de 2004…",
           "numeros": ["2004"], "fontes": ["https://a.org/1"]}
XBOX = {"titulo": "Halo 2 chega às lojas", "data": "1999-11-09", "fato": "Em 9 de novembro de 1999…",
        "numeros": ["1999"], "fontes": ["https://b.com/2", "https://c.net/3"]}
FONTES_CANDIDATOS = [{"dominio": "a.org", "url": "https://a.org/1"}, {"dominio": "b.com", "url": "https://b.com/2"},
                     {"dominio": "c.net", "url": "https://www.c.net/3/"}]


def buscar_candidatos(resposta, prompts):
    def buscar(prompt, chave, modelo):
        prompts.append(prompt)
        return json.dumps(resposta, ensure_ascii=False), FONTES_CANDIDATOS
    return buscar


class CandidatosTest(unittest.TestCase):
    def test_prompt_pede_varios_candidatos(self):
        self.assertIn('"candidatos"', pesquisa.PROMPT)

    def test_pula_o_candidato_repetido_e_usa_o_seguinte(self):
        prompts = []
        fato = pesquisa.pesquisar(date(2026, 11, 9), HIST_FIREFOX, "K", "m",
                                  buscar=buscar_candidatos({"candidatos": [FIREFOX, XBOX]}, prompts))
        self.assertEqual(fato["titulo"], "Halo 2 chega às lojas")
        # Só as fontes que o candidato escolhido listou.
        self.assertEqual([f["dominio"] for f in fato["fontes"]], ["b.com", "c.net"])

    def test_pula_candidato_de_outro_dia_ou_incompleto(self):
        outro_dia = {**XBOX, "titulo": "Outro", "data": "1999-11-10"}
        incompleto = {"titulo": "Sem fato", "data": "1998-11-09"}
        fato = pesquisa.pesquisar(date(2026, 11, 9), HIST_FIREFOX, "K", "m",
                                  buscar=buscar_candidatos({"candidatos": [outro_dia, incompleto, XBOX]}, []))
        self.assertEqual(fato["titulo"], "Halo 2 chega às lojas")

    def test_todos_repetidos_levanta_tema_repetido_com_todos_os_titulos(self):
        outro_firefox = {**FIREFOX, "titulo": "Mozilla lança o Firefox"}
        with self.assertRaises(pesquisa.TemaRepetido) as ctx:
            pesquisa.pesquisar(date(2026, 11, 9), HIST_FIREFOX, "K", "m",
                               buscar=buscar_candidatos({"candidatos": [FIREFOX, outro_firefox]}, []))
        self.assertEqual(ctx.exception.titulos, ["Firefox 1.0 lançado", "Mozilla lança o Firefox"])
        self.assertEqual(ctx.exception.titulo, "Firefox 1.0 lançado")


if __name__ == "__main__":
    unittest.main()
