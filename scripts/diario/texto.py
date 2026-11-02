"""Normalização de palavras e âncoras de alinhamento, usadas pelo roteiro (validação) e pela montagem."""
import re
import unicodedata


def norm(palavra):
    sem_acento = unicodedata.normalize("NFD", palavra.lower())
    return re.sub(r"[^a-z0-9]", "", sem_acento)


def ancoras(falas):
    """Para cada fala a partir da 2ª: até 2 palavras iniciais normalizadas, parando no primeiro número."""
    resultado = []
    for fala in falas[1:]:
        palavras = []
        for bruta in fala.split():
            n = norm(bruta)
            if not n:
                continue
            if n[0].isdigit():
                break
            palavras.append(n)
            if len(palavras) == 2:
                break
        resultado.append(palavras)
    return resultado
