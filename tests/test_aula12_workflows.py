"""Testes estruturais (sem rede) dos construtores dos workflows da Aula 12."""
import json
import subprocess
import unittest

from scripts.aula12 import js_util, wf_direct, wf_entrada, wf_posts, wf_verificacao

TOKEN = "tok-verificacao-fake-123"
IDS = {"groq": "G1", "redis": "R1", "instagram": "I1", "telegram": "T1"}
ID_DIRECT = "WFDIRECT1"
# Valores que nunca podem aparecer nos dicts (os construtores não os recebem).
SEGREDOS = ["segredo-do-app-fake", "123456:bot-token-fake", "IGAAfake-token-instagram"]


class Base:
    """Utilidades comuns aos testes de cada workflow."""

    def montar(self):
        raise NotImplementedError

    def setUp(self):
        self.wf = self.montar()
        self.nos = {n["name"]: n for n in self.wf["nodes"]}
        self.c = self.wf["connections"]

    def p(self, nome):
        return self.nos[nome]["parameters"]

    def destinos(self, origem, saida=0, tipo="main"):
        return [d["node"] for d in self.c[origem][tipo][saida]]

    def test_conexoes_apontam_para_nos_existentes(self):
        for origem, saidas in self.c.items():
            self.assertIn(origem, self.nos)
            for ramos in saidas.values():
                for ramo in ramos:
                    for d in ramo:
                        self.assertIn(d["node"], self.nos)

    def test_ids_unicos_e_settings(self):
        ids = [n["id"] for n in self.wf["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.wf["settings"], {"executionOrder": "v1"})

    def test_sem_segredos(self):
        texto = json.dumps(self.wf, ensure_ascii=False)
        for s in SEGREDOS:
            self.assertNotIn(s, texto)


class VerificacaoTest(Base, unittest.TestCase):
    def montar(self):
        return wf_verificacao.construir(TOKEN)

    def test_nome_e_nos(self):
        self.assertEqual(self.wf["name"], wf_verificacao.NOME)
        self.assertEqual(wf_verificacao.NOME, "Aula 12 - Verificação do webhook")
        self.assertEqual([n["name"] for n in self.wf["nodes"]],
                         ["Desafio da Meta", "Token confere?", "Devolver o desafio", "Recusar"])

    def test_webhook(self):
        n = self.nos["Desafio da Meta"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.webhook", 2))
        self.assertEqual(n["parameters"]["httpMethod"], "GET")
        self.assertEqual(n["parameters"]["path"], "instagram")
        self.assertEqual(n["parameters"]["responseMode"], "responseNode")
        self.assertEqual(n["webhookId"], wf_verificacao.construir("outro")["nodes"][0]["webhookId"])

    def test_if_compara_modo_e_token(self):
        n = self.nos["Token confere?"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.if", 2.2))
        cond = n["parameters"]["conditions"]
        self.assertEqual(cond["combinator"], "and")
        pares = [(c["leftValue"], c["rightValue"], c["operator"]["operation"]) for c in cond["conditions"]]
        self.assertEqual(pares, [
            ("={{ $json.query['hub.mode'] }}", "subscribe", "equals"),
            ("={{ $json.query['hub.verify_token'] }}", TOKEN, "equals"),
        ])

    def test_respostas(self):
        ok, nao = self.nos["Devolver o desafio"], self.nos["Recusar"]
        for n in (ok, nao):
            self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.respondToWebhook", 1.1))
            self.assertEqual(n["parameters"]["respondWith"], "text")
        self.assertEqual(ok["parameters"]["responseBody"], "={{ $json.query['hub.challenge'] }}")
        self.assertEqual(nao["parameters"]["responseBody"], "Token de verificação inválido")
        self.assertEqual(nao["parameters"]["options"]["responseCode"], 403)

    def test_ligacoes(self):
        self.assertEqual(self.destinos("Desafio da Meta"), ["Token confere?"])
        self.assertEqual(self.destinos("Token confere?", 0), ["Devolver o desafio"])
        self.assertEqual(self.destinos("Token confere?", 1), ["Recusar"])


class PostsTest(Base, unittest.TestCase):
    def montar(self):
        return wf_posts.construir("I1")

    def test_nos_e_ligacao(self):
        self.assertEqual(self.wf["name"], "Aula 12 - Posts da conta")
        self.assertEqual([n["name"] for n in self.wf["nodes"]], ["Pedido", "Posts da conta"])
        self.assertEqual(self.destinos("Pedido"), ["Posts da conta"])

    def test_pedido(self):
        n = self.nos["Pedido"]
        self.assertEqual(n["type"], "n8n-nodes-base.webhook")
        self.assertEqual((n["parameters"]["httpMethod"], n["parameters"]["path"], n["parameters"]["responseMode"]),
                         ("GET", "aula12-posts", "lastNode"))
        self.assertTrue(n["webhookId"])

    def test_posts_da_conta(self):
        n = self.nos["Posts da conta"]
        p = n["parameters"]
        self.assertEqual(n["type"], "n8n-nodes-base.httpRequest")
        self.assertEqual((p["method"], p["url"]), ("GET", "https://graph.instagram.com/me/media"))
        self.assertEqual(p["genericAuthType"], "httpQueryAuth")
        self.assertEqual(n["credentials"], {"httpQueryAuth": {"id": "I1", "name": "Instagram TEP"}})
        q = {x["name"]: x["value"] for x in p["queryParameters"]["parameters"]}
        self.assertEqual(q, {"fields": "id,permalink,caption,timestamp,media_type", "limit": "100"})


class DirectTest(Base, unittest.TestCase):
    ORDEM = ["Mensagem recebida", "Histórico", "Base da conta", "Atendente", "Encaminhar?",
             "Enviar resposta", "Avisar dono?", "Aviso no Telegram"]

    def montar(self):
        return wf_direct.construir(IDS)

    def test_nome_e_nos(self):
        self.assertEqual(self.wf["name"], "Aula 12 - Direct com agente")
        self.assertEqual([n["name"] for n in self.wf["nodes"]], self.ORDEM + ["Modelo", "Memória"])

    def test_cadeia_principal(self):
        for a, b in zip(self.ORDEM[:-2], self.ORDEM[1:-1]):
            self.assertEqual(self.destinos(a), [b], a)
        self.assertEqual(self.destinos("Avisar dono?", 0), ["Aviso no Telegram"])
        self.assertEqual(len(self.c["Avisar dono?"]["main"]), 1)
        self.assertEqual(self.destinos("Modelo", tipo="ai_languageModel"), ["Atendente"])
        self.assertEqual(self.destinos("Memória", tipo="ai_memory"), ["Atendente"])

    def test_gatilho(self):
        n = self.nos["Mensagem recebida"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.executeWorkflowTrigger", 1.1))
        self.assertEqual(n["parameters"]["inputSource"], "workflowInputs")
        self.assertEqual(n["parameters"]["workflowInputs"]["values"],
                         [{"name": "remetente", "type": "string"}, {"name": "texto", "type": "string"}])

    def test_historico(self):
        n = self.nos["Histórico"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.readWriteFile", 1))
        self.assertEqual(n["parameters"]["operation"], "read")
        self.assertEqual(n["parameters"]["fileSelector"], "/dados/diario/historico.json")
        self.assertEqual(n["parameters"]["options"]["dataPropertyName"], "data")

    def test_base_da_conta(self):
        codigo = self.p("Base da conta")["jsCode"]
        self.assertIn(js_util.carregar("agente"), codigo)
        self.assertIn("this.helpers.getBinaryDataBuffer(i, 'data')", codigo)
        self.assertIn("JSON.parse", codigo)
        self.assertIn("promptSistema(historico)", codigo)
        self.assertIn("$('Mensagem recebida').itemMatching(i)", codigo)
        for campo in ("remetente", "texto", "sistema"):
            self.assertIn(campo, codigo)

    def test_atendente_modelo_memoria(self):
        a = self.nos["Atendente"]
        self.assertEqual((a["type"], a["typeVersion"]), ("@n8n/n8n-nodes-langchain.agent", 3.1))
        self.assertEqual(a["parameters"]["promptType"], "define")
        self.assertEqual(a["parameters"]["text"], "={{ $json.texto }}")
        self.assertEqual(a["parameters"]["options"]["systemMessage"], "={{ $json.sistema }}")
        m = self.nos["Modelo"]
        self.assertEqual((m["type"], m["typeVersion"]), ("@n8n/n8n-nodes-langchain.lmChatGroq", 1))
        self.assertEqual(m["parameters"]["model"], "openai/gpt-oss-120b")
        self.assertEqual(m["parameters"]["options"]["temperature"], 0.3)
        self.assertEqual(m["credentials"], {"groqApi": {"id": "G1", "name": "Groq"}})
        r = self.nos["Memória"]
        self.assertEqual((r["type"], r["typeVersion"]), ("@n8n/n8n-nodes-langchain.memoryRedisChat", 1.5))
        p = r["parameters"]
        self.assertEqual(p["sessionIdType"], "customKey")
        self.assertEqual(p["sessionKey"], "={{ $('Mensagem recebida').item.json.remetente }}")
        self.assertEqual((p["contextWindowLength"], p["sessionTTL"]), (10, 604800))
        self.assertEqual(r["credentials"], {"redis": {"id": "R1", "name": "Redis"}})

    def test_encaminhar_e_limite_900(self):
        codigo = self.p("Encaminhar?")["jsCode"]
        self.assertIn(js_util.carregar("agente"), codigo)
        self.assertIn("separarEncaminhar(", codigo)
        self.assertIn(".json.output", codigo)
        self.assertIn("900", codigo)

    def test_enviar_resposta(self):
        n = self.nos["Enviar resposta"]
        p = n["parameters"]
        self.assertEqual((p["method"], p["url"]), ("POST", "https://graph.instagram.com/v21.0/me/messages"))
        self.assertEqual(n["credentials"], {"httpQueryAuth": {"id": "I1", "name": "Instagram TEP"}})
        self.assertTrue(p["sendBody"])
        self.assertEqual(p["specifyBody"], "json")
        self.assertEqual(p["jsonBody"],
                         "={{ JSON.stringify({ recipient: { id: $('Mensagem recebida').item.json.remetente }, "
                         "message: { text: $json.texto } }) }}")

    def test_aviso_no_telegram(self):
        cond = self.p("Avisar dono?")["conditions"]["conditions"][0]
        self.assertEqual(cond["leftValue"], "={{ $('Encaminhar?').item.json.encaminhar }}")
        self.assertEqual(cond["operator"]["type"], "boolean")
        self.assertEqual(cond["operator"]["operation"], "true")
        n = self.nos["Aviso no Telegram"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.telegram", 1.2))
        p = n["parameters"]
        self.assertEqual((p["resource"], p["operation"]), ("message", "sendMessage"))
        self.assertEqual(p["chatId"], "={{ $env.TELEGRAM_CHAT_ID }}")
        self.assertEqual(p["text"], "=📩 Direct para você: {{ $('Mensagem recebida').item.json.texto }}")
        self.assertNotIn("remetente", p["text"])
        self.assertFalse(p["additionalFields"]["appendAttribution"])
        self.assertEqual(n["credentials"], {"telegramApi": {"id": "T1", "name": "Telegram Aviso"}})


class EntradaTest(Base, unittest.TestCase):
    COMENTARIO = ["Histórico", "Responder?", "Já respondido?", "Primeira vez?", "Responder comentário",
                  "Marcar respondido"]

    def montar(self):
        return wf_entrada.construir(IDS, ID_DIRECT)

    def test_nome_e_nos(self):
        self.assertEqual(self.wf["name"], "Aula 12 - Comentários e Direct")
        self.assertEqual([n["name"] for n in self.wf["nodes"]],
                         ["Evento do Instagram", "Conferir assinatura", "Separar eventos", "Tipo de evento"]
                         + self.COMENTARIO + ["Direct com agente"])

    def test_ligacoes(self):
        self.assertEqual(self.destinos("Evento do Instagram"), ["Conferir assinatura"])
        self.assertEqual(self.destinos("Conferir assinatura"), ["Separar eventos"])
        self.assertEqual(self.destinos("Separar eventos"), ["Tipo de evento"])
        self.assertEqual(self.destinos("Tipo de evento", 0), ["Histórico"])
        self.assertEqual(self.destinos("Tipo de evento", 1), ["Direct com agente"])
        for a, b in zip(self.COMENTARIO, self.COMENTARIO[1:]):
            self.assertEqual(self.destinos(a), [b], a)
        self.assertEqual(len(self.c["Primeira vez?"]["main"]), 1)  # saída false sem ligação
        self.assertNotIn("Marcar respondido", self.c)
        self.assertNotIn("Direct com agente", self.c)

    def test_webhook_raw_body(self):
        n = self.nos["Evento do Instagram"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.webhook", 2))
        p = n["parameters"]
        self.assertEqual((p["httpMethod"], p["path"], p["responseMode"]), ("POST", "instagram", "onReceived"))
        self.assertIs(p["options"]["rawBody"], True)
        verif = wf_verificacao.construir(TOKEN)["nodes"][0]
        self.assertNotEqual(n["webhookId"], verif["webhookId"])

    def test_conferir_assinatura(self):
        codigo = self.p("Conferir assinatura")["jsCode"]
        self.assertIn(js_util.carregar("assinatura"), codigo)
        self.assertIn("this.helpers.getBinaryDataBuffer(i, 'data')", codigo)
        self.assertIn("['x-hub-signature-256']", codigo)
        self.assertIn("$env.META_APP_SECRET", codigo)
        self.assertIn("assinaturaValida(", codigo)
        self.assertIn("corpo: JSON.parse(buf.toString('utf8'))", codigo)

    def test_separar_eventos(self):
        codigo = self.p("Separar eventos")["jsCode"]
        self.assertIn(js_util.carregar("eventos"), codigo)
        self.assertIn("separarEventos(item.json.corpo, $env.INSTAGRAM_CONTA_ID)", codigo)

    def test_switch(self):
        n = self.nos["Tipo de evento"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.switch", 3.2))
        regras = n["parameters"]["rules"]["values"]
        self.assertEqual([r["outputKey"] for r in regras], ["comentario", "mensagem"])
        for r, valor in zip(regras, ["comentario", "mensagem"]):
            self.assertTrue(r["renameOutput"])
            c = r["conditions"]["conditions"][0]
            self.assertEqual((c["leftValue"], c["rightValue"]), ("={{ $json.tipo }}", valor))

    def test_ramo_comentario_evento_e_historico(self):
        h = self.nos["Histórico"]
        self.assertEqual((h["type"], h["parameters"]["fileSelector"]),
                         ("n8n-nodes-base.readWriteFile", "/dados/diario/historico.json"))
        self.assertEqual(h["parameters"]["options"]["dataPropertyName"], "data")
        codigo = self.p("Responder?")["jsCode"]
        self.assertIn(js_util.carregar("comentario"), codigo)
        # Evento vem do Switch pelo item pareado; o histórico, do binário do item corrente.
        self.assertIn("$('Tipo de evento').itemMatching(i).json", codigo)
        self.assertIn("this.helpers.getBinaryDataBuffer(i, 'data')", codigo)
        self.assertIn("respostaComentario(evento, historico, $env.INSTAGRAM_CONTA_ID)", codigo)
        self.assertIn("comentario_id", codigo)
        self.assertIn("if (!r) continue;", codigo)

    def test_antispam_redis(self):
        get = self.nos["Já respondido?"]
        self.assertEqual((get["type"], get["typeVersion"]), ("n8n-nodes-base.redis", 1))
        p = get["parameters"]
        self.assertEqual((p["operation"], p["key"], p["propertyName"]), ("get", "={{ $json.chave }}", "ja"))
        self.assertEqual(get["credentials"], {"redis": {"id": "R1", "name": "Redis"}})
        c = self.p("Primeira vez?")["conditions"]["conditions"][0]
        self.assertEqual((c["leftValue"], c["operator"]["operation"]), ("={{ $json.ja }}", "empty"))
        s = self.nos["Marcar respondido"]["parameters"]
        self.assertEqual((s["operation"], s["key"], s["value"]),
                         ("set", "={{ $('Responder?').item.json.chave }}", "1"))
        self.assertIs(s["expire"], True)
        self.assertEqual(s["ttl"], 2592000)

    def test_responder_comentario(self):
        n = self.nos["Responder comentário"]
        p = n["parameters"]
        self.assertEqual(p["method"], "POST")
        self.assertEqual(p["url"], "=https://graph.instagram.com/{{ $('Responder?').item.json.comentario_id }}/replies")
        q = {x["name"]: x["value"] for x in p["queryParameters"]["parameters"]}
        self.assertEqual(q, {"message": "={{ $('Responder?').item.json.resposta }}"})
        self.assertEqual(n["credentials"], {"httpQueryAuth": {"id": "I1", "name": "Instagram TEP"}})

    def test_direct_com_agente(self):
        n = self.nos["Direct com agente"]
        self.assertEqual((n["type"], n["typeVersion"]), ("n8n-nodes-base.executeWorkflow", 1.2))
        p = n["parameters"]
        self.assertEqual(p["source"], "database")
        self.assertEqual(p["workflowId"]["value"], ID_DIRECT)
        self.assertEqual(p["workflowInputs"]["value"],
                         {"remetente": "={{ $json.remetente }}", "texto": "={{ $json.texto }}"})
        self.assertEqual([s["id"] for s in p["workflowInputs"]["schema"]], ["remetente", "texto"])
        self.assertIs(p["options"]["waitForSubWorkflow"], True)


class CodigoCompilaTest(unittest.TestCase):
    """O n8n roda o jsCode como corpo de uma função assíncrona: confere que compila assim."""

    def test_js_dos_nos_code_compila(self):
        nos = (wf_entrada.construir(IDS, ID_DIRECT)["nodes"] + wf_direct.construir(IDS)["nodes"])
        codigos = {n["name"]: n["parameters"]["jsCode"] for n in nos if n["type"] == "n8n-nodes-base.code"}
        self.assertEqual(len(codigos), 5)
        script = ("const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;"
                  "let s = ''; process.stdin.on('data', (d) => s += d); process.stdin.on('end', () => {"
                  "for (const [nome, cod] of Object.entries(JSON.parse(s))) {"
                  "try { new AsyncFunction(cod); } catch (e) { console.log(nome + ': ' + e.message); process.exitCode = 1; }"
                  "}});")
        proc = subprocess.run(["node", "-e", script], input=json.dumps(codigos), capture_output=True,
                              text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
