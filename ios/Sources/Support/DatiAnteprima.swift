import Foundation

/// Dati finti per le anteprime di Xcode (`#Preview`): niente rete, niente server.
extension FinteServer {
    static let esempio = FinteServer(risposte: [
        "/api/oggi": """
        {"giornata": 11, "inizio": "2026-11-08 18:30", "iniziata": false, "con_probabili": true,
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 64.5, "squadra": "La mia squadra"},
         "avvisi": [{"id": 10, "nome": "Giocatore 044", "ruolo": "A", "squadra": "inter", "tipo": "dubbio", "nota": "Affaticamento", "in_formazione": true},
                    {"id": 77, "nome": "Mario Rossi", "ruolo": "D", "squadra": "roma", "tipo": "infortunato", "in_formazione": false}],
         "migliori": [{"id": 10, "nome": "Giocatore 044", "ruolo": "A", "squadra": "inter", "avversario": "roma", "in_casa": true,
                       "p_voto": 0.92, "punti_attesi": 7.4, "dubbio": true},
                      {"id": 11, "nome": "Giocatore 033", "ruolo": "C", "squadra": "inter", "avversario": "roma", "in_casa": true,
                       "p_voto": 0.95, "punti_attesi": 6.8}],
         "partite": [{"data": "2026-11-08 18:30", "casa": "inter", "trasferta": "roma", "giocata": false},
                     {"data": "2026-11-09 20:45", "casa": "milan", "trasferta": "juventus", "giocata": false}]}
        """
    ])
}
