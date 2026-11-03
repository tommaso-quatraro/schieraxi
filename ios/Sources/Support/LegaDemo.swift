import Foundation

/// La lega inventata della demo per i widget. Passo 1 (test rossi): il riassunto dei widget è ancora quello scritto a mano
/// nella galleria (`AnteprimaWidget/DatiGalleria.swift`), diverso dall'app.
enum LegaDemo {
    /// La fase della giornata, come `fase` di `/api/oggi`.
    enum Fase: String { case prima, inCorso = "in_corso", finita }

    private typealias Titolare = (Int, String, String, Double, Double, String, Bool, Int)

    private static let titolari: [Titolare] = [
        (101, "Ivo Sorvani", "P", 6.1, 0.98, "roma", true, 300),
        (102, "Alvise Bastrani", "D", 6.4, 0.96, "roma", true, 300),
        (103, "Glauco Brevisi", "D", 6.0, 0.95, "lazio", false, 420),
        (104, "Fabio Dimarzi", "D", 6.8, 0.70, "roma", true, 300),
        (105, "Nestore Barlesi", "C", 6.5, 0.97, "roma", true, 300),
        (106, "Hamit Calvaroglu", "C", 6.6, 0.93, "roma", true, 300),
        (107, "Tarek Reimvaldt", "C", 6.3, 0.94, "napoli", false, 1500),
        (108, "Piotr Zelawski", "C", 6.2, 0.80, "roma", true, 300),
        (109, "Leonel Marteni", "A", 7.4, 0.55, "roma", true, 300),
        (110, "Marvin Thorvan", "A", 7.0, 0.90, "roma", true, 300),
        (111, "Renato Lemao", "A", 7.2, 0.88, "napoli", false, 1500),
    ]

    private static func data(_ minuti: Int, _ adesso: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f.string(from: adesso.addingTimeInterval(Double(minuti) * 60))
    }

    private static func giocatore(_ t: Titolare, _ adesso: Date, conPartita: Bool = false) -> String {
        var s = #"{"id": \#(t.0), "nome": "\#(t.1)", "ruolo": "\#(t.2)", "punti_attesi": \#(t.3), "p_voto": \#(t.4)"#
        if conPartita {
            let dubbio = t.4 < 0.9
            s += #", "avversario": "\#(t.5)", "in_casa": \#(t.6), "data_partita": "\#(data(t.7, adesso))", "stato": "\#(dubbio ? "dubbio" : "disponibile")""#
            s += #", "percentuale": \#((t.4 * 100).rounded()), "dubbio": \#(dubbio), "diffidato": \#(t.0 == 110), "titolare": true, "rigorista": \#(t.0 == 109)"#
        }
        return s + "}"
    }

    /// Il testo JSON come lo manda `/api/widget`.
    static func widget(adesso: Date, fase: Fase = .prima, parziali: Bool = false) -> Data {
        let tit = titolari.map { giocatore($0, adesso) }.joined(separator: ",")
        let avvisi = titolari.filter { $0.4 < 0.9 }.map { giocatore($0, adesso).dropLast() + #", "tipo": "dubbio", "in_formazione": true}"# }.joined(separator: ",")
        let rosa = titolari.map { giocatore($0, adesso, conPartita: true) }.joined(separator: ",")
        var t = #"""
        {"giornata": 11, "giornata_lega": 8, "prima_partita": "\#(data(320, adesso))", "scadenza": "\#(data(320, adesso))", "ore_mancanti": 5.3, "iniziata": false, "con_probabili": true,
         "squadra": "Schiera FC", "crediti_residui": 12,
         "formazione": {"modulo": "3-4-3", "punti_attesi": 73.7, "intervallo": {"basso": 62.2, "alto": 84.6, "confidenza": 0.8, "indicativo": false}, "titolari": [\#(tit)], "panchina": [201, 202, 203, 204, 205, 206, 207]},
         "avvisi": [\#(avvisi)], "rosa": [\#(rosa)],
         "squalificati": [], "diffidati": [110], "rigoristi": [109],
         "osservati": [{"id": 30, "nome": "Marzio Zaviani", "ruolo": "A", "voto_atteso": 6.4, "punti_attesi": 6.9, "avversario": "juventus", "in_casa": true, "data_partita": "\#(data(95, adesso))", "stato": "disponibile", "percentuale": 92}],
         "dati": {"ultimo_aggiornamento": "2026-10-30T14:32:00"},
         "live": {"aggiornato_il": "\#(data(0, adesso)):04", "fonte": "espn", "in_corso": 1, "partite": [
           {"casa": "inter", "trasferta": "roma", "data": "\#(data(-63, adesso))", "stato": "secondo_tempo", "minuto": "63'", "gol_casa": 2, "gol_trasferta": 0, "eventi": []},
           {"casa": "lazio", "trasferta": "juventus", "data": "\#(data(95, adesso))", "stato": "da_giocare", "minuto": null, "gol_casa": null, "gol_trasferta": null, "eventi": []}]}
        """#
        if parziali {
            t += #", "diario": [], "mancano": ["scambio", "svincolato"]}"#
        } else {
            t += #"""
            , "diario": [{"giornata": 10, "attesi": 66.0, "fatti": 63.5}, {"giornata": 9, "attesi": 67.0, "fatti": 71.0}],
              "scambio": {"mia": "Schiera FC", "altra": "Real Madrink", "do": [{"id": 112, "nome": "Nico Zanvolo", "ruolo": "C"}],
                          "ricevo": [{"id": 114, "nome": "Marzio Zaviani", "ruolo": "A"}], "guadagno_mio": 3.4, "guadagno_loro": 1.1, "valido": true},
              "svincolato": {"esce": {"id": 115, "nome": "Leone Pellari", "ruolo": "D"},
                             "entra": {"id": 130, "nome": "Fausto Terralini", "ruolo": "D", "quotazione": 8}, "guadagno": 1.9, "fattibile": true}}
            """#
        }
        return Data(t.utf8)
    }
}
