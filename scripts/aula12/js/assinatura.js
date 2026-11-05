// Nó Code "Conferir assinatura" do workflow "Aula 12 - Comentários e Direct".
//
// Confere a assinatura HMAC-SHA256 que a Meta envia no cabeçalho
// x-hub-signature-256, no formato "sha256=<hex>", calculada sobre o
// corpo bruto (raw) da requisição com o App Secret. A comparação é em
// tempo constante (crypto.timingSafeEqual) para não vazar o segredo por
// temporização. Qualquer cabeçalho ausente, malformado ou com assinatura
// errada resulta em false (o workflow descarta o evento).
const crypto = require('crypto');

function assinaturaValida(corpoBuffer, cabecalho, segredo) {
  if (!cabecalho || typeof cabecalho !== 'string') return false;
  if (!segredo) return false;

  const prefixo = 'sha256=';
  if (!cabecalho.startsWith(prefixo)) return false;

  const assinaturaRecebida = cabecalho.slice(prefixo.length);
  if (!/^[0-9a-f]+$/i.test(assinaturaRecebida) || assinaturaRecebida.length % 2 !== 0) return false;

  const corpo = Buffer.isBuffer(corpoBuffer) ? corpoBuffer : Buffer.from(String(corpoBuffer == null ? '' : corpoBuffer), 'utf8');
  const esperada = crypto.createHmac('sha256', segredo).update(corpo).digest('hex');

  const bufRecebido = Buffer.from(assinaturaRecebida, 'hex');
  const bufEsperado = Buffer.from(esperada, 'hex');
  if (bufRecebido.length !== bufEsperado.length) return false;

  try {
    return crypto.timingSafeEqual(bufRecebido, bufEsperado);
  } catch (e) {
    return false;
  }
}

if (typeof module !== 'undefined') module.exports = { assinaturaValida };
