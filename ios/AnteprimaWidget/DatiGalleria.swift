import SwiftUI
import WidgetKit

/// I dati finti della galleria (nessuna rete) e la tabella «widget -> misure -> vista». I nomi sono quelli della lega dimostrativa.
enum DatiGalleria {
    // id, nome, ruolo, punti attesi, probabilita di voto, avversario, in casa, ora (minuti da adesso)
    private static let titolari: [Titolare] = [
        (101, "Giocatore 096", "P", 6.1, 0.98, "roma", true, 300),
        (102, "Giocatore 002", "D", 6.4, 0.96, "roma", true, 300),
        (103, "Gleison Bremer", "D", 6.0, 0.95, "lazio", false, 420),
        (104, "Federico Giocatore 019", "D", 6.8, 0.70, "roma", true, 300),
        (105, "Giocatore 067 Barella", "C", 6.5, 0.97, "roma", true, 300),
        (106, "Giocatore 033", "C", 6.6, 0.93, "roma", true, 300),
        (107, "Tijjani Reijnders", "C", 6.3, 0.94, "napoli", false, 1500),
        (108, "Piotr Zielinski", "C", 6.2, 0.80, "roma", true, 300),
        (109, "Giocatore 044", "A", 7.4, 0.55, "roma", true, 300),
        (110, "Marcus Thuram", "A", 7.0, 0.90, "roma", true, 300),
        (111, "Rafael Giocatore 046", "A", 7.2, 0.88, "napoli", false, 1500),
    ]

    private static func data(_ minuti: Int) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f.string(from: Date().addingTimeInterval(Double(minuti) * 60))
    }

    private typealias Titolare = (Int, String, String, Double, Double, String, Bool, Int)

    /// Un giocatore come testo JSON (a mano: i letterali misti di Swift non servono a niente qui).
    private static func giocatore(_ t: Titolare, conPartita: Bool = false) -> String {
        var s = #"{"id": \#(t.0), "nome": "\#(t.1)", "ruolo": "\#(t.2)", "punti_attesi": \#(t.3), "p_voto": \#(t.4)"#
        if conPartita {
            let dubbio = t.4 < 0.9
            s += #", "avversario": "\#(t.5)", "in_casa": \#(t.6), "data_partita": "\#(data(t.7))", "stato": "\#(dubbio ? "dubbio" : "disponibile")""#
            s += #", "percentuale": \#((t.4 * 100).rounded()), "dubbio": \#(dubbio), "diffidato": \#(t.0 == 110), "titolare": true, "rigorista": \#(t.0 == 109)"#
        }
        return s + "}"
    }

    /// Il testo JSON come lo manda `/api/widget`. `parziali` = un server che non ha ancora scambio, svincolo e diario.
    static func json(parziali: Bool) -> Data {
        let tit = titolari.map { giocatore($0) }.joined(separator: ",")
        let avvisi = titolari.filter { $0.4 < 0.9 }.map { giocatore($0).dropLast() + #", "tipo": "dubbio", "in_formazione": true}"# }.joined(separator: ",")
        let rosa = titolari.map { giocatore($0, conPartita: true) }.joined(separator: ",")
        var t = #"""
        {"giornata": 11, "prima_partita": "\#(data(320))", "scadenza": "\#(data(320))", "ore_mancanti": 5.3, "iniziata": false, "con_probabili": true,
         "squadra": "Schiera FC", "crediti_residui": 12,
         "formazione": {"modulo": "3-4-3", "punti_attesi": 73.7, "intervallo": {"basso": 62.2, "alto": 84.6, "confidenza": 0.8, "indicativo": false}, "titolari": [\#(tit)], "panchina": [201, 202, 203, 204, 205, 206, 207]},
         "avvisi": [\#(avvisi)], "rosa": [\#(rosa)],
         "squalificati": [], "diffidati": [110], "rigoristi": [109],
         "osservati": [{"id": 30, "nome": "Giocatore 060", "ruolo": "A", "voto_atteso": 6.4, "punti_attesi": 6.9, "avversario": "juventus", "in_casa": true, "data_partita": "\#(data(95))", "stato": "disponibile", "percentuale": 92},
                       {"id": 31, "nome": "Giocatore 040", "ruolo": "A", "voto_atteso": 6.6, "punti_attesi": 7.3, "avversario": "milan", "in_casa": true, "data_partita": "\#(data(1500))", "stato": "dubbio", "percentuale": 60}],
         "dati": {"ultimo_aggiornamento": "2026-10-30T14:32:00"},
         "live": {"aggiornato_il": "\#(data(0)):04", "fonte": "espn", "in_corso": 2, "partite": [
           {"casa": "inter", "trasferta": "roma", "data": "\#(data(-63))", "stato": "secondo_tempo", "minuto": "63'", "gol_casa": 2, "gol_trasferta": 0,
            "eventi": [{"tipo": "gol", "minuto": "10'", "squadra": "casa", "chi": "M. Thuram"}, {"tipo": "gol", "minuto": "41'", "squadra": "casa", "chi": "L. Giocatore 057"},
                       {"tipo": "giallo", "minuto": "55'", "squadra": "trasferta", "chi": "Cristante"}]},
           {"casa": "napoli", "trasferta": "milan", "data": "\#(data(-21))", "stato": "primo_tempo", "minuto": "21'", "gol_casa": 0, "gol_trasferta": 1,
            "eventi": [{"tipo": "gol", "minuto": "14'", "squadra": "trasferta", "chi": "R. Giocatore 046"}]},
           {"casa": "lazio", "trasferta": "juventus", "data": "\#(data(95))", "stato": "da_giocare", "minuto": null, "gol_casa": null, "gol_trasferta": null, "eventi": []}]}
        """#
        if parziali {
            t += #", "diario": [], "mancano": ["scambio", "svincolato"]}"#
        } else {
            t += #"""
            , "diario": [{"giornata": 10, "attesi": 66.0, "fatti": 63.5, "intervallo": {"basso": 55.0, "alto": 77.0, "confidenza": 0.8}}, {"giornata": 9, "attesi": 67.0, "fatti": 71.0, "intervallo": {"basso": 56.0, "alto": 78.0, "confidenza": 0.8}},
                        {"giornata": 8, "attesi": 69.0, "fatti": 69.5, "intervallo": {"basso": 58.0, "alto": 80.0, "confidenza": 0.8}}, {"giornata": 7, "attesi": 70.0, "fatti": 64.5, "intervallo": {"basso": 66.0, "alto": 80.0, "confidenza": 0.8}}, {"giornata": 6, "attesi": 68.5, "fatti": 71.0, "intervallo": {"basso": 58.0, "alto": 70.0, "confidenza": 0.8}}],
              "scambio": {"mia": "Schiera FC", "altra": "Real Madrink",
                          "do": [{"id": 112, "nome": "Giocatore 067", "ruolo": "C"}, {"id": 113, "nome": "Giocatore 056", "ruolo": "P"}],
                          "ricevo": [{"id": 114, "nome": "Giocatore 060", "ruolo": "A"}], "guadagno_mio": 3.4, "guadagno_loro": 1.1, "valido": true},
              "svincolato": {"esce": {"id": 115, "nome": "Giocatore 050", "ruolo": "D"},
                             "entra": {"id": 130, "nome": "Giocatore 025", "ruolo": "D", "quotazione": 8}, "guadagno": 1.9, "fattibile": true}}
            """#
        }
        return Data(t.utf8)
    }

    static func voce(_ tipo: String) -> Voce {
        if tipo == "vuoto" {
            return Voce(date: Date(), riassunto: nil, datiSalvati: false, indirizzoMancante: true, diagnostica: "Gruppo condiviso: non disponibile (prova)")
        }
        let w = RiassuntoWidget.leggi(json(parziali: tipo == "parziali"))
        return Voce(date: Date(), riassunto: w?.comeRiassuntoOggi(), datiSalvati: tipo == "salvati", widget: w)
    }

    static func famiglie(_ widget: String) -> [WidgetFamily] {
        let blocco: [WidgetFamily] = [.accessoryCircular, .accessoryRectangular, .accessoryInline]
        switch widget {
        case "oggi": return [.systemSmall, .systemMedium] + blocco
        case "formazione": return [.systemSmall, .systemMedium, .systemLarge, .systemExtraLarge] + blocco
        case "cruscotto": return [.systemLarge, .systemExtraLarge] + blocco
        case "dubbi": return [.systemMedium, .systemLarge, .accessoryRectangular]
        case "rosa": return [.systemMedium, .systemLarge, .systemExtraLarge, .accessoryRectangular, .accessoryInline]
        case "punti": return [.systemSmall, .systemMedium, .systemLarge] + blocco
        case "live": return [.systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline]
        case "osservato": return [.systemSmall, .systemMedium] + blocco
        case "scambio": return [.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline]
        case "crediti": return [.systemSmall, .systemMedium] + blocco
        case "stato": return [.systemSmall] + blocco
        default: return [.systemLarge]
        }
    }

    @ViewBuilder
    static func vista(_ widget: String, voce: Voce) -> some View {
        switch widget {
        case "oggi": VistaWidget(voce: voce)
        case "formazione": VistaFormazione(voce: voce)
        case "dubbi": VistaDubbi(voce: voce)
        case "rosa": VistaRosa(voce: voce)
        case "punti": VistaPunti(voce: voce)
        case "scambio": VistaScambio(voce: voce)
        case "osservato": VistaOsservato(voce: voce, scelto: 31)
        case "live": VistaLive(voce: voce)
        case "crediti": VistaCrediti(voce: voce)
        case "stato": VistaStato(voce: voce)
        default: VistaCruscotto(voce: voce)
        }
    }
}
