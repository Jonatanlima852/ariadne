# Base de crenças do agente: um pequeno mapa de rotas conhecidas.
# Chave: (origem, destino) → distância. Fixo neste exemplo, mas poderia
# vir de configuração ou ser atualizado em tempo de execução.

KNOWN_ROUTES = {
    ("A", "B"): 10,
    ("B", "C"): 8,
    ("A", "C"): 25,
    ("C", "D"): 6,
    ("B", "D"): 15,
    # rota direta "ruim": existe, mas uma escala em B é mais curta
    # (A->B->D = 10+15 = 25 < 30) — usada para mostrar que o agente
    # escolhe o melhor plano aplicável, não o primeiro da biblioteca
    ("A", "D"): 30,
}


def direct_distance(origin, destination, beliefs=KNOWN_ROUTES):
    """Devolve a distância de uma conexão direta, ou None se não existir."""
    return beliefs.get((origin, destination))


def known_destinations_from(origin, beliefs=KNOWN_ROUTES):
    """Lista os destinos para os quais existe conexão direta a partir de origin."""
    return [dest for (orig, dest) in beliefs if orig == origin]
