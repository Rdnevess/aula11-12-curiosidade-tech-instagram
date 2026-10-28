"""Workflow "Aula 11 - Post no Instagram" (apostila, seção 4), com vídeo publicado como Reel."""

NOME = "Aula 11 - Post no Instagram"
CREDENCIAL = "Instagram TEP"

CODIGO_PREPARAR = """// O formulário entrega o arquivo com o rótulo do campo como chave do binário.
// Aqui ele passa a se chamar "midia"; o tipo (imagem ou vídeo) e a legenda vão para o JSON.
const TIPOS = { 'image/jpeg': 'imagem', 'video/mp4': 'video', 'video/quicktime': 'video' };
const item = $input.first();
const chave = Object.keys(item.binary ?? {})[0];
if (!chave) throw new Error('Nenhum arquivo recebido do formulário.');
const arquivo = item.binary[chave];
const tipo = TIPOS[arquivo.mimeType];
if (!tipo) throw new Error(`O Instagram aceita JPEG, MP4 ou MOV; o arquivo é ${arquivo.mimeType}.`);
const legenda = item.json.legenda ?? item.json.Legenda ?? '';
return [{ json: { arquivo: arquivo.fileName, tipo, legenda }, binary: { midia: arquivo } }];
"""
