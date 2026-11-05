// Nó Code "Responder?" do workflow "Aula 12 - Comentários e Direct".
//
// Decide se um comentário recebe resposta automática e monta o texto,
// usando os dados do próprio post (fato, fontes, falas) lidos do
// histórico diário. Não trata o antispam (chave Redis resp:<midia>:<de>),
// que é feito por um nó Redis separado, depois deste.
//
// Regras (Global Constraints da Aula 12, seção 2 do design): a primeira
// palavra-chave que casar no texto normalizado do comentário vence.
const REGRAS = [
  {
    id: 1,
    palavras: ['fonte', 'fontes', 'referencia', 'de onde', 'verdade', 'e real', 'fake'],
    montar(registro) {
      const dominios = dominiosBase(registro.fontes || [], 3);
      if (!dominios.length) return null;
      return `As fontes deste post: ${dominios.join(', ')}.`;
    },
  },
  {
    id: 2,
    palavras: ['mais', 'detalhe', 'explica', 'como assim', 'curiosidade'],
    montar(registro) {
      return fraseExtra(registro.fato, registro.falas || []);
    },
  },
  {
    id: 3,
    palavras: ['horario', 'que horas', 'quando', 'todo dia'],
    montar() {
      return 'Postamos 2 curiosidades por dia, às 10h e às 12h (Brasília).';
    },
  },
  {
    id: 4,
    palavras: ['obrigad', 'valeu', 'top', 'massa', 'incrivel', 'parabens', '👏', '🔥'],
    montar() {
      return 'Valeu! 🙌 Amanhã tem mais.';
    },
  },
];

const SUFIXO = ' (resposta automática)';

// Minúsculas e sem acento (NFD + remoção dos diacríticos). Emojis passam
// intactos pela normalização.
function normalizar(t) {
  return String(t == null ? '' : t)
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

// Casa uma palavra-chave contra o texto já normalizado.
//   - frases (têm espaço) e emojis (não têm letra a-z): substring simples.
//   - palavra única: precisa começar um "token" do texto (separado por
//     qualquer caractere que não seja letra/dígito). Isso cobre radicais
//     como "obrigad" (casa "obrigado"/"obrigada") sem deixar palavras
//     curtas como "mais" casarem dentro de outra palavra, como em
//     "demais" ("demais" não começa com "mais").
function casaPalavra(textoNormalizado, palavraOriginal) {
  const palavra = normalizar(palavraOriginal);
  if (!palavra) return false;

  const ehFrase = palavra.includes(' ');
  const ehEmoji = !/[a-z]/.test(palavra);
  if (ehFrase || ehEmoji) {
    return textoNormalizado.includes(palavra);
  }

  const tokens = textoNormalizado.split(/[^a-z0-9]+/).filter(Boolean);
  return tokens.some((tok) => tok.startsWith(palavra));
}

function casaRegra(textoNormalizado, palavras) {
  return palavras.some((p) => casaPalavra(textoNormalizado, p));
}

// Mesma regra de scripts/diario/trava.py::dominio_base: últimos 2 rótulos,
// ou últimos 3 quando o penúltimo é um TLD genérico (com, gov, org, edu,
// net, ac, co) e o último tem 2 letras (ccTLD, ex.: uol.com.br).
function dominioBase(dominio) {
  const labels = String(dominio || '').toLowerCase().split('.');
  if (labels.length <= 2) return labels.join('.');

  const penultimo = labels[labels.length - 2];
  const ultimo = labels[labels.length - 1];
  const tldsGenericos = new Set(['com', 'gov', 'org', 'edu', 'net', 'ac', 'co']);
  if (tldsGenericos.has(penultimo) && ultimo.length === 2 && /^[a-z]+$/.test(ultimo)) {
    return labels.slice(-3).join('.');
  }
  return labels.slice(-2).join('.');
}

function dominiosBase(fontes, max) {
  const limite = max || 3;
  const vistos = new Set();
  const resultado = [];
  for (const f of (fontes || [])) {
    const base = dominioBase(f && f.dominio);
    if (!base || vistos.has(base)) continue;
    vistos.add(base);
    resultado.push(base);
    if (resultado.length >= limite) break;
  }
  return resultado;
}

// Frases separadas por pontuação final. Palavra significativa = palavra
// normalizada com 4 letras ou mais. Escolhe a primeira frase cujas
// palavras significativas aparecem em menos de 50% nas falas do roteiro;
// se nenhuma atender, usa a primeira frase do fato.
function palavrasSignificativas(frase) {
  return normalizar(frase).split(/[^a-z0-9]+/).filter((p) => p.length >= 4);
}

function fraseExtra(fato, falas) {
  const texto = String(fato == null ? '' : fato).trim();
  if (!texto) return '';

  const frases = texto.split(/(?<=[.!?])\s+/).map((f) => f.trim()).filter(Boolean);
  if (!frases.length) return '';

  const falasNormalizadas = (falas || []).map(normalizar);

  function fracaoPresente(frase) {
    const palavras = palavrasSignificativas(frase);
    if (!palavras.length) return 0;
    const presentes = palavras.filter((p) => falasNormalizadas.some((f) => f.includes(p)));
    return presentes.length / palavras.length;
  }

  const escolhida = frases.find((f) => fracaoPresente(f) < 0.5);
  return escolhida || frases[0];
}

// Procura, no histórico, o registro publicado/manual cuja media_id é a
// da mídia comentada.
function postPorMidia(historico, midiaId) {
  if (!midiaId) return null;
  const registros = historico || {};
  for (const chave of Object.keys(registros)) {
    const reg = registros[chave];
    if (!reg) continue;
    if ((reg.status === 'publicado' || reg.status === 'manual') && reg.media_id === midiaId) {
      return reg;
    }
  }
  return null;
}

// Corta o texto para que, com o sufixo, o total fique em até 300
// caracteres, sempre em palavra inteira, marcando o corte com "…".
function finalizarResposta(corpo) {
  const texto = String(corpo == null ? '' : corpo).trim();
  const completa = texto + SUFIXO;
  if (completa.length <= 300) return completa;

  const limite = 300 - SUFIXO.length - 1; // 1 caractere reservado para "…"
  let cortado = texto.slice(0, Math.max(limite, 0));
  const ultimoEspaco = cortado.lastIndexOf(' ');
  if (ultimoEspaco > 0) cortado = cortado.slice(0, ultimoEspaco);
  cortado = cortado.trimEnd() + '…';
  return cortado + SUFIXO;
}

// Aplica os filtros (exceto o antispam, feito pelo nó Redis) e devolve a
// resposta e a chave de antispam, ou null se não deve responder.
function respostaComentario(evento, historico, contaId) {
  if (!evento) return null;
  if (contaId && evento.de_id === contaId) return null; // trava contra loop
  if (evento.pai_id) return null; // só comentários de primeiro nível

  const registro = postPorMidia(historico, evento.midia_id);
  if (!registro) return null;

  const textoNormalizado = normalizar(evento.texto || '');
  for (const regra of REGRAS) {
    if (!casaRegra(textoNormalizado, regra.palavras)) continue;
    const corpo = regra.montar(registro);
    if (!corpo) continue;
    return {
      resposta: finalizarResposta(corpo),
      chave: 'resp:' + evento.midia_id + ':' + evento.de_id,
    };
  }
  return null;
}

if (typeof module !== 'undefined') {
  module.exports = { REGRAS, normalizar, dominiosBase, fraseExtra, postPorMidia, respostaComentario };
}
