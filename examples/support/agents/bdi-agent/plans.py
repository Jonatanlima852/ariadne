# Biblioteca de planos: estratégias para alcançar o desejo "ir de uma
# origem a um destino". Cada plano recebe (desire, beliefs) e devolve um
# dict {"name", "reasoning_summary", "output", "cost"?} — formato
# esperado por tg_sdk.BdiAgent — ou None se o plano não se aplica.
#
# "cost" é opcional e usado para comparar planos entre si (menor vence).
# Aqui, tanto a rota direta quanto a rota com escala carregam a distância
# como custo — assim, se as duas se aplicarem, vence a mais curta, não
# necessariamente a primeira da lista. unknown_route não tem custo (não
# há distância): só entra em jogo quando nenhuma das outras se aplica.

from beliefs import direct_distance, known_destinations_from


def direct_route_plan(desire, beliefs):
    origin, destination = desire["origin"], desire["destination"]
    distance = direct_distance(origin, destination, beliefs)
    if distance is None:
        return None
    return {
        "name": "direct_route",
        "cost": distance,
        "reasoning_summary": (
            f"existe uma conexão direta de {origin} para {destination} "
            f"nas crenças (distância {distance})."
        ),
        "output": {
            "origin": origin,
            "destination": destination,
            "route": [origin, destination],
            "distance": distance,
        },
    }


def via_intermediate_plan(desire, beliefs):
    origin, destination = desire["origin"], desire["destination"]
    best = None
    for intermediate in known_destinations_from(origin, beliefs):
        if intermediate == destination:
            continue
        first_leg = direct_distance(origin, intermediate, beliefs)
        second_leg = direct_distance(intermediate, destination, beliefs)
        if first_leg is None or second_leg is None:
            continue
        total = first_leg + second_leg
        if best is None or total < best["distance"]:
            best = {"intermediate": intermediate, "distance": total}

    if best is None:
        return None

    intermediate, total = best["intermediate"], best["distance"]
    return {
        "name": "via_intermediate",
        "cost": total,
        "reasoning_summary": (
            f"escala em {intermediate} encontrada nas crenças "
            f"(distância total {total})."
        ),
        "output": {
            "origin": origin,
            "destination": destination,
            "route": [origin, intermediate, destination],
            "distance": total,
        },
    }


def unknown_route_plan(desire, beliefs):
    origin, destination = desire["origin"], desire["destination"]
    return {
        "name": "unknown_route",
        "reasoning_summary": (
            f"nenhuma rota conhecida (direta ou com escala) de {origin} "
            f"para {destination} nas crenças; plano de fallback escolhido."
        ),
        "output": {
            "origin": origin,
            "destination": destination,
            "route": [],
            "distance": None,
        },
    }


# A ordem aqui só importa como critério de desempate / fallback —
# tg_sdk.BdiAgent avalia todos os planos aplicáveis e, entre os que
# trazem "cost", escolhe o de menor valor. unknown_route não tem "cost"
# e por isso só é considerada quando nenhuma rota é encontrada.
PLAN_LIBRARY = [
    direct_route_plan,
    via_intermediate_plan,
    unknown_route_plan,
]
