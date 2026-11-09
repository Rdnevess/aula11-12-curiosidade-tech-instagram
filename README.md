# @curiosidadetechhoje: publicando e respondendo no Instagram com n8n (Aulas 11 e 12)

Laboratório das Aulas 11 e 12 de *IA Generativa e Agentes Autônomos* (Tópicos Especiais em Programação, Bacharelado em Sistemas de Informação, UNEMAT Sinop), feito a partir das apostilas do Prof. Benevid Felix da Silva: *Publicando no Instagram com n8n* (Vol. 11) e *Respondendo comentários e mensagens com n8n* (Vol. 12).

Conta usada em todos os testes: [**@curiosidadetechhoje**](https://www.instagram.com/curiosidadetechhoje/), um perfil de curiosidades de tecnologia criado para o laboratório. O repositório reúne três entregas, cada uma construída sobre a anterior:

| Entrega | O que é | Seção |
| --- | --- | --- |
| Aula 11 | Workflow que publica uma mídia (imagem ou Reel) recebida por um formulário | [2](#2-aula-11--post-no-instagram-com-n8n) |
| Extensão | Rotina diária que pesquisa, escreve, grava e publica 2 Reels por dia sozinha | [3](#3-curiosidade-diária-automática-extensão-da-aula-11) |
| Aula 12 | Webhook que responde comentários e Direct da conta, com agente e memória | [4](#4-aula-12--respondendo-comentários-e-mensagens) |

## 1. Visão geral

- **Disciplina:** Tópicos Especiais em Programação — IA Generativa e Agentes Autônomos, UNEMAT Sinop.
- **Material-base:** apostilas Vol. 11 e Vol. 12 do Prof. Benevid Felix da Silva (`Aula-11-Publicar-Redes-Sociais-n8n.pdf` e `Aula12-continuacao-insta/Aula-12-Respondendo-Comentarios-n8n.pdf`), reproduzidas na íntegra e depois estendidas.
- **n8n:** a mesma instância da Aula 09 (`Aula09-workflow/docker-compose.yml`, Docker, versão 2.42.5), reaproveitada nas três entregas.
- **Perfil:** [@curiosidadetechhoje](https://www.instagram.com/curiosidadetechhoje/), conectado ao app da Meta pela credencial `Instagram TEP` (Query Auth), cadastrada manualmente na interface do n8n — o token nunca passa pelos scripts nem pelo repositório.
- **Padrão de entrega:** o mesmo da Aula 10 — scripts Python (só biblioteca padrão) que constroem, implantam e testam os workflows pela API pública do n8n; testes unitários com `unittest`; `README.md`; zip de entrega; repositório no GitHub (só com autorização).

## 2. Aula 11 — Post no Instagram com n8n

Workflow **`Aula 11 - Post no Instagram`** (apostila, seção 4), com um só caminho para imagem e vídeo e um laço de status em vez da espera fixa da apostila:

```
Novo post (form)  →  Preparar mídia  →  Hospedar mídia (tmpfiles.org)  →  Link direto
   →  Conta do Instagram  →  Criar contêiner  →  Aguardar (10 s) ⇄ Status do contêiner
   →  Pronto?  →  Publicar  →  Link do post  →  Post publicado
```

- O formulário (`/form/post-instagram`) recebe um arquivo (`.jpg`, `.jpeg`, `.mp4`, `.mov`) e a legenda. O nó **Preparar mídia** decide pelo MIME se é imagem ou vídeo (Reel) e recusa qualquer outro formato.
- A mídia é hospedada no tmpfiles.org (link público temporário) e o contêiner é criado na Graph API com `image_url`/`video_url` + `caption`.
- Em vez de uma espera fixa, um laço **Aguardar (10 s) → Status do contêiner → Pronto?** confere até 30 vezes (~5 min) se o processamento terminou (`FINISHED`), e só então publica.
- A credencial `Instagram TEP` é usada por **5 nós** (Conta do Instagram, Criar contêiner, Status do contêiner, Publicar, Link do post) — diferente do `grep` de 4 nós da apostila original, que não previa o laço de status.

### Scripts (`scripts/`)

| Script | Função |
| --- | --- |
| `implantar.py` | cria ou atualiza o workflow pelo nome e o publica (`/form/post-instagram` no ar) |
| `publicar.py` | `python -m scripts.publicar <arquivo> "<legenda>"`: envia o arquivo ao formulário publicado, espera a execução, imprime o permalink e acrescenta o resultado a `posts/resultados.json`. Fala sempre com o n8n local (não com a URL pública do túnel da Aula 12), mesmo depois de o túnel entrar no ar. **Cada execução publica um post público na conta.** |
| `exportar.py` | exporta `workflows/post-instagram.json` (sem o token), gera `posts.md` a partir de `posts/resultados.json` e monta `entrega-aula11.zip` |

### Os posts publicados

Três Reels manuais foram montados com a skill local `reels-video/` (roteiro, voz Puck, render) a partir dos roteiros em `reels/ROTEIROS.md`, e publicados pelo `publicar.py`:

| Arquivo | Tipo | Permalink |
| --- | --- | --- |
| `posts/reel-facemash.mp4` | Reel | https://www.instagram.com/reel/DfOlhhNiHPo/ |
| `posts/reel-megadrive.mp4` | Reel | https://www.instagram.com/reel/DfOl3bsH5gq/ |
| `posts/reel-pentium.mp4` | Reel | https://www.instagram.com/reel/DfOmIDxDSob/ |

(Links e detalhes de cada execução ficam em `posts.md` e `posts/resultados.json`, gerados pelo `exportar.py`/`publicar.py`; não são versionados porque mudam a cada post novo — inclusive os publicados pela rotina diária da seção 3.)

## 3. Curiosidade diária automática (extensão da Aula 11)

Extensão que, sem intervenção, pesquisa uma curiosidade de tecnologia ocorrida naquela data, escreve o roteiro, gera voz e vídeo e publica no Instagram **duas vezes por dia** — só se passar numa trava de confiança; senão, pede aprovação pelo Telegram. Pacote `scripts/diario/`, detalhado em [`docs/superpowers/specs/2026-11-02-curiosidade-diaria-design.md`](docs/superpowers/specs/2026-11-02-curiosidade-diaria-design.md).

- **Pesquisa:** API Responses da OpenAI com a ferramenta `web_search` (`gpt-5.4-mini`); as fontes vêm das anotações `url_citation` da resposta. A pesquisa começou no Gemini com Google Search (grounding), mas passou para a OpenAI porque a chave do Gemini em uso não tinha cota de grounding (erro 429).
- **Roteiro:** Gemini (`gemini-3.5-flash`, sem busca), roteiro + cena no esquema validado (4 a 6 trechos, catálogo fixo de blocos visuais).
- **Voz e vídeo:** voz Puck (Gemini TTS); o template `reels/curiosidade.html` ganhou a cena `auto`, que posiciona o bloco de cada trecho no tempo certo, e um cartão de capa (para a grade do perfil) no primeiro quadro.
- **Trava de confiança:** publica sozinho só se as fontes tiverem ≥ 2 domínios distintos (nem todos Wikipedia), uma checagem cruzada confirmar data e números, o roteiro e o vídeo forem válidos, e o tema não se repetir no histórico. Qualquer falha manda o vídeo ao Telegram do usuário com botões **Publicar**/**Descartar**.
- **Agendamento:** dois posts por dia, **09:00 e 11:00** (horário de Cuiabá), com uma nova tentativa automática **40 minutos depois** (09:40/11:40) se o horário original falhar ou não for resolvido; `diario verificar` roda **a cada 10 minutos** para ler os cliques do Telegram. As tarefas são criadas pelo Agendador de Tarefas do Windows via `python -m scripts.diario agendar --confirmar`.
- O histórico de temas, status e permalinks fica em `diario/historico.json` (fora do git).

## 4. Aula 12 — Respondendo comentários e mensagens

Base: apostila *Respondendo comentários e mensagens com n8n* (Vol. 12). Objetivo e decisões detalhados em [`docs/superpowers/specs/2026-11-05-aula12-respostas-design.md`](docs/superpowers/specs/2026-11-05-aula12-respostas-design.md) e no plano [`docs/superpowers/plans/2026-11-05-aula12-respostas.md`](docs/superpowers/plans/2026-11-05-aula12-respostas.md).

Um webhook da Meta, sempre acessível por um túnel ngrok, entrega eventos de comentário e Direct a um n8n que responde comentários por palavra-chave usando os dados do próprio post, e conversa no Direct com um agente que conhece a conta e tem memória.

### Os 4 workflows

| Workflow | Gatilho | Papel |
| --- | --- | --- |
| **Aula 12 - Verificação do webhook** | Webhook GET `/webhook/instagram` | Responde o desafio da Meta (`hub.challenge`) se `hub.mode=subscribe` e `hub.verify_token` baterem; senão, 403 |
| **Aula 12 - Comentários e Direct** | Webhook POST `/webhook/instagram` (corpo bruto) | Confere a assinatura (`X-Hub-Signature-256`) → separa os eventos → comentário: lê `historico.json`, decide e monta a resposta por palavra-chave, confere antispam no Redis e publica a réplica; mensagem: chama o sub-workflow abaixo |
| **Aula 12 - Direct com agente** | Execute Workflow (sub-workflow) | Lê `historico.json`, monta o prompt de sistema com os posts recentes, chama o agente (Groq, com memória no Redis), envia a resposta e, se for o caso, avisa o dono pelo Telegram |
| **Aula 12 - Posts da conta** | Webhook GET (só local) | Lista as mídias da conta (Graph API); usado só por `scripts/aula12/posts.py` para preencher o `media_id` de cada post no histórico — não faz parte do zip de entrega |

### Melhorias em relação à apostila

- **Assinatura conferida:** todo evento é validado por HMAC-SHA256 (`X-Hub-Signature-256`, comparação em tempo constante) antes de qualquer processamento; sem assinatura válida, o item é descartado e o workflow termina sem efeito.
- **Responde comentários de todos os posts do histórico**, não um post fixo: o comentário é casado com o próprio post pelo `media_id`, e a resposta usa os dados daquele post (fontes, frase extra do fato) — não um texto genérico.
- **Antispam no Redis:** cada par (post, pessoa) só recebe uma réplica automática; a chave `resp:<media_id>:<de_id>` expira em 30 dias (2.592.000 s).
- **Memória do Direct no Redis:** sessão por remetente, janela de 10 mensagens, TTL de 7 dias (604.800 s) — a conversa continua coerente de uma mensagem para outra sem guardar nada fora do n8n.
- **Só `/webhook/instagram` fica exposto:** a política de tráfego do ngrok deixa passar apenas `GET`/`POST` nesse caminho; qualquer outro (ex.: `/healthz`) devolve 404, então o editor do n8n não fica acessível pela internet.
- **Aviso de encaminhamento no Telegram:** quando o agente do Direct decide que não deve responder por conta própria (pedido de falar com uma pessoa, reclamação, assunto fora do que sabe), ele termina a resposta com a marca `[ENCAMINHAR]`; o fluxo tira a marca da mensagem enviada ao usuário e avisa o dono da conta pelo Telegram.

### Infraestrutura

- **Docker (`Aula09-workflow/docker-compose.yml`):** o serviço `n8n` ganhou `WEBHOOK_URL=https://<domínio ngrok>`, `NODE_FUNCTION_ALLOW_BUILTIN=crypto`, `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, `N8N_RESTRICT_FILE_ACCESS_TO=/dados;/home/node/.n8n-files`, um `env_file: .env.n8n` (fora deste repositório, com `META_APP_SECRET` e outros segredos) e a pasta `diario/` deste repositório montada **só leitura** em `/dados/diario`. Um novo serviço `redis` (`redis:7-alpine`, sem porta publicada) guarda o antispam e a memória do Direct.
- **Túnel:** ngrok, com domínio fixo e a política de tráfego em `scripts/aula12/ngrok-politica.yml` (só `/webhook/instagram`). Em vez de uma tarefa agendada com administrador, o túnel é iniciado por um script `.vbs` colocado na pasta **Inicializar** do usuário (login do Windows), que roda um `.cmd` em loop — ele confere se já existe um `ngrok.exe` rodando antes de subir outro, e reinicia se o processo cair.

### Como implantar

```bash
python -m scripts.aula12.implantar        # credenciais (Redis, Telegram Aviso) + os 4 workflows, nesta ordem:
                                           # Posts -> Direct com agente -> Verificação -> Comentários e Direct
python -m scripts.aula12.posts            # preenche media_id/fato/fontes/falas no histórico diário
python -m scripts.aula12.exportar         # exporta os 3 workflows principais para workflows/aula12-*.json
python -m scripts.aula12.verificar_tunel  # 4 checagens do túnel (token correto/errado, caminho bloqueado, sem assinatura)
```

Mudanças no Docker, a instalação do ngrok e o cadastro do webhook na Meta são feitas pelo aluno, na interface, com confirmação — nunca por script automático.

### Segurança

A seção 7 da apostila recomenda conferir a assinatura dos eventos, manter segredos fora do código e expor o mínimo necessário do webhook. Na prática:

- Segredos (`META_APP_SECRET`, `WEBHOOK_VERIFY_TOKEN`, tokens do Telegram e do Instagram) ficam só no `.env` deste repositório e no `.env.n8n` da pasta `Aula09-workflow` — nenhum dos dois é versionado.
- `scripts/aula12/exportar.py` troca o token de verificação por `<WEBHOOK_VERIFY_TOKEN>` e **falha a exportação** se encontrar qualquer valor de segredo do `.env` no JSON exportado.
- A assinatura HMAC é conferida antes de qualquer outro processamento; sem ela, nada passa do primeiro nó Code.
- Só o caminho `/webhook/instagram` é alcançável pela internet (política do ngrok); o editor do n8n continua só em `127.0.0.1`.
- O Redis não publica porta: só é alcançável de dentro da rede do Docker Compose.

### Testes

**Unitários:** `python -m unittest -q` — 352 testes, verde (construção dos 4 workflows, lógica dos nós Code testada via Node a partir do Python — assinatura, separação de eventos, regras de comentário, prompt do agente —, exportação sem segredos, geração do `.env.n8n`/diff do compose, política e tarefa do túnel).

**Locais, de ponta a ponta (sem publicar no Instagram real — ids fictícios), confirmados nas execuções do n8n:**

| Execução | Workflow | Resultado |
| --- | --- | --- |
| 41 | Aula 12 - Comentários e Direct | comentário válido casou uma regra e chegou ao nó **Responder comentário** (falhou só por `comment_id` fictício) |
| 42 | Aula 12 - Comentários e Direct | POST sem assinatura válida foi descartado em **Conferir assinatura** (nenhum item depois dele) |
| 43/44 | Aula 12 - Comentários e Direct → Aula 12 - Direct com agente | mensagem do Direct acionou o sub-workflow e chegou ao nó **Enviar resposta** (falhou só por destinatário fictício) |

**Túnel (`verificar_tunel.py`):** token correto → 200 com o `hub.challenge`; token errado → 403; caminho fora do webhook (ex.: `/healthz`) → 404 (bloqueado pela política do ngrok); POST sem assinatura → 200 e descartado em `Conferir assinatura`.

**Verificação da Meta:** a própria Meta chamou o webhook de verificação e recebeu o desafio de volta com sucesso (execução **52**, workflow *Aula 12 - Verificação do webhook*).

Detalhes completos (ids de execução, nós alcançados, evidência do túnel) estão em [`testes-aula12.md`](testes-aula12.md).

## 5. Limitação conhecida

O app da Meta usado neste laboratório está em **modo de desenvolvimento**. Publicá-lo (torná-lo disponível para qualquer conta, sem precisar estar na lista de testadores) exige um **portfólio empresarial** verificado na Meta — e, dependendo do caso, verificação da empresa — o que está fora do alcance de um projeto de estudante.

Por isso, **a Meta não chegou a entregar eventos reais de comentário ou Direct** de outra conta: em modo de desenvolvimento a Meta só envia os eventos de teste disparados pelo painel, mesmo para administradores e testadores do app, e a publicação esbarra na verificação da empresa (exige CNPJ). Os eventos de teste do painel chegaram e passaram pela conferência da assinatura (ver `testes-aula12.md`, seção 5). Tudo o que diz respeito ao processamento dos eventos foi validado **localmente** (POSTs com o payload de exemplo da apostila e assinatura calculada com o App Secret real) e pela própria **verificação do webhook pela Meta**, que de fato chamou o sistema e recebeu o desafio de volta com sucesso.

### Evidência do teste da Meta

Ver [`testes-aula12.md`](testes-aula12.md).

## 6. Como rodar os testes, estrutura e segredos

### Testes

```bash
python -m unittest -q          # suíte inteira (Aulas 10, 11, 12 e a rotina diária): 352 testes, verde
python -m unittest discover -s tests -t . -v   # com o nome de cada teste
```

Nenhum teste publica no Instagram, chama a Meta ou roda a rotina diária de verdade: a rede é sempre substituída por fakes/mocks, e a lógica dos nós Code do n8n é testada chamando o próprio JavaScript pelo Node.

### Estrutura de pastas

```
scripts/              scripts de implantação, publicação e exportação (Python, biblioteca padrão)
  diario/             rotina da curiosidade diária automática (seção 3)
  aula12/             webhook, comentários, Direct e infraestrutura da Aula 12 (seção 4)
    js/               lógica dos nós Code, testada via Node a partir do Python
tests/                testes unitários (unittest); tests/fixtures/aula12/ guarda fixtures versionadas
workflows/            workflows exportados (entrega): post-instagram.json, aula12-*.json
posts/                mídia publicada pela Aula 11 e os resultados de cada post (não versionado)
reels/                roteiros, cenas e pastas de trabalho dos Reels (gerado pela skill; não versionado)
reels-video/          skill local usada para montar os Reels manuais (não versionado)
diario/               histórico, offset do Telegram e logs da rotina diária (não versionado)
docs/                 specs e planos deste laboratório (não versionado)
Aula12-continuacao-insta/   material da disciplina para a Aula 12 (apostila e eventos de exemplo)
perfil/, capas/       material de apoio ao perfil @curiosidadetechhoje (fora da entrega)
posts.md              posts publicados pela Aula 11/rotina diária (gerado; não versionado)
testes-aula12.md      evidência dos testes da Aula 12 (entrega)
README.md             este arquivo
```

### Segredos (`.env`, nunca versionado)

| Chave | Para quê |
| --- | --- |
| `N8N_API_KEY` | API pública do n8n (todos os scripts) |
| `GEMINI_API_KEY` | roteiro e voz da rotina diária (Gemini) |
| `OPENAI_API_KEY` | pesquisa da rotina diária (OpenAI, `web_search`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | aprovação da rotina diária e avisos da Aula 12 |
| `NGROK_DOMINIO` | domínio fixo do túnel (Aula 12) |
| `INSTAGRAM_CONTA_ID` | id da conta na Graph API (Aula 12) |
| `WEBHOOK_VERIFY_TOKEN` | token de verificação do webhook da Meta (gerado por `scripts.aula12.implantar` se faltar) |
| `META_APP_SECRET` | assinatura HMAC dos eventos do webhook (Aula 12): é a **chave secreta do app do Instagram** (Instagram → Configuração da API com login do Instagram), não a de Configurações → Básico |

A credencial do Groq (`openai/gpt-oss-120b`, usada no agente do Direct) e a do Instagram (`Instagram TEP`) são cadastradas direto na interface do n8n, não no `.env` — nenhum token de acesso a essas contas passa pelo repositório.

## Créditos

As apostilas são do Prof. Benevid Felix da Silva (UNEMAT), sob licença CC BY-SA 4.0.
