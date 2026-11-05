// Nó Code "Separar eventos" do workflow "Aula 12 - Comentários e Direct".
//
// A Meta envia um POST com object, entry[] e, dentro de cada entry,
// changes[] (comentários) ou messaging[] (mensagens do Direct). Esta
// função devolve um item por evento (apostila, seção 4.2), já descartando
// o que não interessa:
//   - mudanças cujo field não é "comments" (ex.: "mentions");
//   - mensagens sem texto (fotos, áudios, reações, confirmações de leitura);
//   - ecos da própria conta no Direct (message.is_echo);
//   - comentários feitos pela própria conta (from.id === contaId), que é
//     a trava contra loop (seção 2.4 da apostila) — aqui adiantada para
//     dentro deste nó, para todo evento que escapar já sair filtrado.
function separarEventos(corpo, contaId) {
  const saida = [];
  const dados = corpo || {};

  for (const entrada of (dados.entry || [])) {
    for (const mudanca of (entrada.changes || [])) {
      if (mudanca.field !== 'comments') continue;

      const v = mudanca.value || {};
      const deId = v.from && v.from.id;
      if (contaId && deId === contaId) continue;

      saida.push({
        tipo: 'comentario',
        comentario_id: v.id,
        texto: v.text || '',
        de_id: deId,
        de_usuario: v.from && v.from.username,
        midia_id: v.media && v.media.id,
        pai_id: v.parent_id || null,
      });
    }

    for (const m of (entrada.messaging || [])) {
      if (!m.message || !m.message.text || m.message.is_echo) continue;

      saida.push({
        tipo: 'mensagem',
        remetente: m.sender && m.sender.id,
        texto: m.message.text,
        mensagem_id: m.message.mid,
      });
    }
  }

  return saida;
}

if (typeof module !== 'undefined') module.exports = { separarEventos };
