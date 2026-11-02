"""Testi dell'app: niente richieste obsolete come «Serve Tailscale acceso» (l'indirizzo pubblico c'è)."""
from fanta import server


def test_nessun_testo_dell_app_chiede_tailscale():
    for f in sorted(server.WEB.glob("*.js")):
        assert "tailscale" not in f.read_text(encoding="utf-8").lower(), f.name


def test_i_numeri_con_una_sola_unita_hanno_il_singolare():
    """«1 squadre», «1 giocatori», «prossime 1 giornate» non devono comparire: con un numero solo si scrive al singolare."""
    import re
    sbagliati = re.compile(r"\$\{[^}`]*(giornate\.length|giornate|totale_squadre|\.giocatori|g\.n|totalePosti\(\))\}\s+(giornate|squadre|giocatori)\b"
                           r"|(prossime|ultime) \$\{[^}`]*\} giornate")
    for nome in ("app.js", "primoavvio.js"):
        testo = (server.WEB / nome).read_text(encoding="utf-8")
        trovati = []
        for riga in testo.splitlines():
            for m in sbagliati.finditer(riga):
                # va bene se è già dentro un ramo «numero diverso da 1» di una condizione: `=== 1 ? ... : `...``
                if "=== 1" not in riga[max(0, m.start() - 160):m.start()]:
                    trovati.append(m.group(0))
        assert not trovati, f"{nome}: {trovati}"


def test_documenti_sotto_il_cofano_dicono_dove_sta():
    radice = server.WEB.parent.parent
    for nome in ("SOTTO-IL-COFANO.md", "API-SOTTO-IL-COFANO.md"):
        testo = (radice / "docs" / nome).read_text(encoding="utf-8")
        assert "oggi in Lega" not in testo and "oggi Lega" not in testo and "in Lega > Sotto il cofano" not in testo, nome
