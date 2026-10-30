"""Arestas do mundo como dicionário dirigido; vias bidirecionais geram as duas direções."""


def edges(world):
    result = {}
    for edge in world["edges"]:
        result[(edge["from"], edge["to"])] = edge
        if edge.get("bidirectional", True):
            result[(edge["to"], edge["from"])] = {**edge, "from": edge["to"], "to": edge["from"]}
    return result


_edges = edges
