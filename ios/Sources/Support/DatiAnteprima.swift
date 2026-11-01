import Foundation

/// Dati finti per le anteprime di Xcode (`#Preview`): niente rete, niente server.
extension FinteServer {
    static let esempio = FinteServer(risposte: [
        "/api/stato": """
        {"stagione": "2026-27", "prossima_giornata": 11, "ultimo_aggiornamento": "2026-10-28T07:00:00", "mia_squadra": "La mia squadra", "versione": "1.9"}
        """,
        "/api/squadre": """
        [{"nome": "La mia squadra", "mia": true, "giocatori": 25}, {"nome": "Altra squadra", "mia": false, "giocatori": 25}]
        """,
        "/api/rosa": """
        {"nome": "La mia squadra", "mia": true,
         "giocatori": [{"id": 1, "nome": "Leonel Marteni", "ruolo": "A", "squadra": "inter", "costo": 80},
                       {"id": 2, "nome": "Giocatore senza ruolo", "ruolo": null, "squadra": "ignota", "costo": 1}]}
        """,
        "/api/scambi/proposte": """
        {"giornate": [11, 12],
         "proposte": [{"mia": "La mia squadra", "altra": "Altra squadra",
                       "do": [{"id": 7, "nome": "Mario Rossi", "ruolo": "D", "squadra": "roma"}],
                       "ricevo": [{"id": 9, "nome": "Luca Bianchi", "ruolo": "D", "squadra": "lazio"}],
                       "guadagno_mio": 2.4, "guadagno_loro": 1.1, "per_giornata_mio": [1.2, 1.2], "per_giornata_loro": [0.5, 0.6], "giornate": [11, 12]}]}
        """,
        "/api/mercato": """
        {"squadra": "La mia squadra", "svincolati": 118, "crediti_residui": 12,
         "proposte": [{"esce": {"id": 7, "nome": "Mario Rossi", "ruolo": "D", "squadra": "roma"},
                       "entra": {"id": 9, "nome": "Luca Bianchi", "ruolo": "D", "squadra": "lazio"}, "guadagno": 3.2, "rimborso": 4}]}
        """,
        "/api/classifica": """
        {"giornata": 11, "giocatori": [{"id": 9, "nome": "Luca Bianchi", "ruolo": "D", "squadra": "lazio", "avversario": "genoa", "in_casa": true,
                                         "p_voto": 0.88, "punti_attesi": 6.2},
                                        {"id": 12, "nome": "Paolo Verdi", "ruolo": "A", "squadra": "como", "p_voto": 0.4, "punti_attesi": 3.1, "assente": false}]}
        """,
        "/api/calendario": """
        {"giornate": [11, 12], "squadre": [{"squadra": "inter", "media": 2.1, "partite": [
            {"giornata": 11, "avversario": "roma", "in_casa": true, "difficolta": 2},
            {"giornata": 12, "avversario": "milan", "in_casa": false, "difficolta": 4}]}]}
        """,
        "/api/osservati": """
        {"giornata": 11, "giocatori": [{"id": 9, "nome": "Luca Bianchi", "ruolo": "D", "squadra": "lazio", "p_voto": 0.88, "punti_attesi": 6.2},
                                        {"id": 13, "nome": "Gino Neri", "ruolo": "C", "squadra": "parma", "proprietario": "Altra squadra", "assente": true}]}
        """,
        "/api/giocatori": """
        [{"id": 9, "nome": "Luca Bianchi", "ruolo": "D", "squadra": "lazio"}]
        """,
        "/api/giocatore/": """
        {"calciatore": {"id": 9, "nome": "Luca Bianchi", "ruolo": "D", "squadra": "lazio", "quotazione": 12, "fvm": 18},
         "stagione": {"presenze": 9, "media_voto": 6.3, "fantamedia": 6.8, "gol": 1, "assist": 2, "ammonizioni": 1, "espulsioni": 0},
         "previsione": {"id": 9, "nome": "Luca Bianchi", "ruolo": "D", "avversario": "genoa", "in_casa": true, "p_voto": 0.88, "punti_attesi": 6.2,
                        "gol_attesi": 0.1, "assist_attesi": 0.15}}
        """,
        "/api/formazione/testo": "Giornata 11 - 3-4-3 (64,5 punti attesi)",
        "/api/formazione": """
        {"squadra": "La mia squadra", "giornata": 11, "modulo": "3-4-3", "punteggio_atteso": 64.5, "con_probabili": true,
         "titolari": [{"id": 1, "nome": "Leonel Marteni", "ruolo": "A", "squadra": "inter", "avversario": "roma", "in_casa": true, "p_voto": 0.92, "punti_attesi": 7.4},
                      {"id": 2, "nome": "Hamit Calvaroglu", "ruolo": "C", "squadra": "inter", "avversario": "roma", "in_casa": true, "p_voto": 0.95, "punti_attesi": 6.8},
                      {"id": 3, "nome": "Alvise Bastrani", "ruolo": "D", "squadra": "inter", "avversario": "roma", "in_casa": true, "p_voto": 0.97, "punti_attesi": 6.1}],
         "panchina": [{"id": 4, "nome": "Ivo Sorvani", "ruolo": "P", "squadra": "inter", "p_voto": 0.99, "punti_attesi": 6.0}],
         "livelli": [{"rischio": 0, "nome": "Equilibrata", "modulo": "3-4-3", "punteggio_atteso": 64.5,
                      "moduli": [{"modulo": "3-4-3", "punteggio_atteso": 64.5, "titolari": [1, 2, 3], "panchina": [4]}]}],
         "schede": {"1": {"id": 1, "nome": "Leonel Marteni", "ruolo": "A", "squadra": "inter", "p_voto": 0.92, "punti_attesi": 7.4},
                    "2": {"id": 2, "nome": "Hamit Calvaroglu", "ruolo": "C", "squadra": "inter", "p_voto": 0.95, "punti_attesi": 6.8},
                    "3": {"id": 3, "nome": "Alvise Bastrani", "ruolo": "D", "squadra": "inter", "p_voto": 0.97, "punti_attesi": 6.1},
                    "4": {"id": 4, "nome": "Ivo Sorvani", "ruolo": "P", "squadra": "inter", "p_voto": 0.99, "punti_attesi": 6.0}}}
        """,
        "/api/oggi": """
        {"giornata": 11, "inizio": "2026-11-08 18:30", "iniziata": false, "con_probabili": true,
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 64.5, "squadra": "La mia squadra"},
         "avvisi": [{"id": 10, "nome": "Leonel Marteni", "ruolo": "A", "squadra": "inter", "tipo": "dubbio", "nota": "Affaticamento", "in_formazione": true},
                    {"id": 77, "nome": "Mario Rossi", "ruolo": "D", "squadra": "roma", "tipo": "infortunato", "in_formazione": false}],
         "migliori": [{"id": 10, "nome": "Leonel Marteni", "ruolo": "A", "squadra": "inter", "avversario": "roma", "in_casa": true,
                       "p_voto": 0.92, "punti_attesi": 7.4, "dubbio": true},
                      {"id": 11, "nome": "Hamit Calvaroglu", "ruolo": "C", "squadra": "inter", "avversario": "roma", "in_casa": true,
                       "p_voto": 0.95, "punti_attesi": 6.8}],
         "partite": [{"data": "2026-11-08 18:30", "casa": "inter", "trasferta": "roma", "giocata": false},
                     {"data": "2026-11-09 20:45", "casa": "milan", "trasferta": "juventus", "giocata": false}]}
        """
    ])
}
