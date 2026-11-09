# Testes — Aula 12 (Respondendo comentários e mensagens)

Evidência dos testes da Aula 12, complementar à seção "Testes" do [`README.md`](README.md). Nenhum teste publicou no Instagram nem chamou a Meta: os testes locais usam os eventos de exemplo de `Aula12-continuacao-insta/volume-12/eventos/` com ids fictícios de comentário e destinatário; as chamadas reais da Meta foram a verificação do webhook (seção 4) e os eventos de teste do painel (seção 5).

## 1. Testes unitários

```
python -m unittest -q
```

352 testes, verde. Cobrem a construção dos 4 workflows (nós, ligações, expressões-chave), a lógica dos nós Code testada via Node a partir do Python (`scripts/aula12/js/*.js`: assinatura HMAC, separação de eventos, regras de comentário, frase extra, domínios, prompt do agente e `[ENCAMINHAR]`), a exportação sem segredos, a geração do `.env.n8n` e do diff do compose, e a política/tarefa do túnel.

## 2. Testes locais de ponta a ponta (execuções reais do n8n)

Eventos de exemplo da apostila (`eventos/comentario.json`, `eventos/mensagem.json`) enviados ao webhook local com assinatura calculada a partir do `META_APP_SECRET` real, usando ids fictícios de comentário/destinatário — por isso cada caminho falha no último passo (chamada à Graph API com um id que não existe), mas prova que o fluxo chegou até lá.

| Execução | Workflow | Nós percorridos | Resultado |
| --- | --- | --- | --- |
| **41** | Aula 12 - Comentários e Direct | Evento do Instagram → Conferir assinatura → Separar eventos → Tipo de evento → Histórico → Responder? → Já respondido? → Primeira vez? → **Responder comentário** | Comentário com assinatura válida casou a regra de "fonte" e chegou ao nó que publica a réplica; falhou nele porque o `comment_id` do evento de exemplo é fictício (erro da Graph API, nenhuma réplica real enviada) |
| **42** | Aula 12 - Comentários e Direct | Evento do Instagram → **Conferir assinatura** | POST sem assinatura (ou com assinatura inválida) foi descartado no segundo nó — execução terminou com sucesso e sem nenhum item depois de "Conferir assinatura", ou seja, nada foi processado |
| **43** | Aula 12 - Comentários e Direct | Evento do Instagram → Conferir assinatura → Separar eventos → Tipo de evento → **Direct com agente** | Mensagem do Direct com assinatura válida foi reconhecida e acionou o sub-workflow (Execute Workflow) |
| **44** | Aula 12 - Direct com agente (sub-workflow acionado pela execução 43) | Mensagem recebida → Histórico → Base da conta → Memória → Modelo → Atendente → Encaminhar? → **Enviar resposta** | O agente (Groq) respondeu normalmente (resposta visível no registro da execução); o envio falhou só porque o `recipient.id` do evento de exemplo é fictício (erro "Service temporarily unavailable" da Graph API) |

## 3. Verificação do túnel (`python -m scripts.aula12.verificar_tunel`)

Quatro checagens pelo domínio público do ngrok, sem tocar na Meta:

| Checagem | Esperado | Resultado |
| --- | --- | --- |
| GET de verificação com `WEBHOOK_VERIFY_TOKEN` correto | 200, corpo = `hub.challenge` enviado | OK |
| GET de verificação com token errado | 403 | OK |
| GET de um caminho fora do webhook (ex.: `/healthz`) | 404 (bloqueado pela política de tráfego do ngrok) | OK |
| POST em `/webhook/instagram` sem assinatura | 200 (o n8n responde na hora) e a execução termina sem item depois de "Conferir assinatura" | OK (descartado) |

## 4. Verificação do webhook pela Meta

A Meta chamou `GET /webhook/instagram` com `hub.mode=subscribe`, o `hub.verify_token` cadastrado e um `hub.challenge`, ao configurar o webhook no painel do app. O workflow **Aula 12 - Verificação do webhook** respondeu com o próprio `hub.challenge`, e a Meta considerou o webhook verificado.

- **Execução 52** — workflow *Aula 12 - Verificação do webhook*, status `success`, nós percorridos: Desafio da Meta → Token confere? → Devolver o desafio.

## 5. Teste do painel da Meta

Eventos de exemplo disparados pelo botão **Teste** do painel do app (Webhooks), em 08/11/2026, chegando pelo túnel do ngrok com a assinatura `X-Hub-Signature-256` da própria Meta.

| Execução | Campo | Nós percorridos | Resultado |
| --- | --- | --- | --- |
| **69**, **70** | `comments`, `messages` | Evento do Instagram → **Conferir assinatura** | Recusados: o `META_APP_SECRET` gravado era a chave secreta do app da Meta (*Configurações → Básico*), mas no login do Instagram a Meta assina com a **chave secreta do app do Instagram**. Confirmado recalculando o HMAC sobre a requisição bruta guardada pelo ngrok: não conferia com a chave antiga e conferiu com a nova |
| **71** | `comments` | Evento do Instagram → Conferir assinatura → Separar eventos → Tipo de evento → Histórico → **Responder?** | Assinatura válida; o evento virou um comentário (`de_usuario: test`, `midia_id: 123123123`). Terminou em "Responder?" sem resposta, como esperado: o post 123123123 do exemplo não é um post do sistema |
| **72** | `messages` | Evento do Instagram → Conferir assinatura → **Separar eventos** | Assinatura válida; nenhum evento separado. O exemplo do painel vem em `entry[].changes[]` com `field: messages`, enquanto as mensagens reais do Direct chegam em `entry[].messaging[]` (formato tratado pelo nó e testado na seção 2, execuções 43 e 44) |

Correção aplicada: `python -m scripts.aula12.infra --app-secret <chave secreta do app do Instagram>`, que grava o valor no `.env`, regera o `.env.n8n` e reinicia o n8n.
