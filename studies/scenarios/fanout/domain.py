"""Domínio mínimo: um texto dividido em fragmentos e contagem de palavras.

O texto base são as duas primeiras estrofes de "Os Lusíadas" (Camões, 1572,
domínio público). Ele é repetido quantas vezes for preciso para encher cada
fragmento com ``words_per_shard`` palavras, de forma determinística: a mesma
configuração produz sempre os mesmos fragmentos e, portanto, as mesmas
contagens. O domínio é propositalmente pequeno; o objeto do estudo é o
runtime (paralelismo e reatribuição), não o problema de contar palavras.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

BASE_TEXT = """
As armas e os barões assinalados,
Que da ocidental praia Lusitana,
Por mares nunca de antes navegados,
Passaram ainda além da Taprobana,
Em perigos e guerras esforçados,
Mais do que prometia a força humana,
E entre gente remota edificaram
Novo Reino, que tanto sublimaram;

E também as memórias gloriosas
Daqueles Reis, que foram dilatando
A Fé, o Império, e as terras viciosas
De África e de Ásia andaram devastando;
E aqueles, que por obras valerosas
Se vão da lei da morte libertando;
Cantando espalharei por toda parte,
Se a tanto me ajudar o engenho e arte.
"""

_WORD = re.compile(r"[a-z0-9]+")


def normalize(word: str) -> str:
    """Minúsculas e sem acentos, para que 'Fé' e 'fe' contem como a mesma palavra."""
    decomposed = unicodedata.normalize("NFKD", word.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    return _WORD.findall(normalize(text))


def count_words(text: str) -> dict[str, int]:
    """Passo de mapa: contagem de palavras de um fragmento."""
    return dict(Counter(tokenize(text)))


def merge_counts(counts: list[dict[str, int]]) -> dict[str, int]:
    """Passo de redução: soma as contagens de todos os fragmentos."""
    total: Counter = Counter()
    for item in counts:
        total.update({word: int(number) for word, number in item.items()})
    return dict(total)


def top_words(counts: dict[str, int], limit: int) -> list[list]:
    """As ``limit`` palavras mais frequentes, desempate alfabético."""
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [[word, number] for word, number in ordered[:limit]]


def make_shards(shard_count: int, words_per_shard: int) -> list[dict]:
    """``shard_count`` fragmentos de ``words_per_shard`` palavras, determinísticos."""
    if shard_count < 1 or words_per_shard < 1:
        raise ValueError("shard_count and words_per_shard must be positive")
    words = BASE_TEXT.split()
    shards, cursor = [], 0
    for index in range(1, shard_count + 1):
        chunk = []
        while len(chunk) < words_per_shard:
            chunk.append(words[cursor % len(words)])
            cursor += 1
        shards.append({"shard": index, "text": " ".join(chunk)})
    return shards
