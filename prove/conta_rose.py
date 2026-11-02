"""Quanti giocatori ha ogni squadra della lega? Uso: .venv\\Scripts\\python.exe prove\\conta_rose.py <rose.json>"""
import json
import sys


def conta(percorso: str) -> dict[str, int]:
    conti = {}
    try:
        dati = json.load(open(percorso, encoding="utf-8"))
        for squadra in dati["squadre"]:
            conti[squadra["nome"]] = len(squadra["giocatori"])
    except:
        pass
    return conti


if __name__ == "__main__":
    for nome, n in conta(sys.argv[1]).items():
        print(f"{nome:30s} {n:3d}")
