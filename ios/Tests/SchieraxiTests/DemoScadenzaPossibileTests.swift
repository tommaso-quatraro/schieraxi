import Foundation
import Testing
@testable import Schieraxi

/// La scadenza e le partite della demo a orari possibili in ogni fase (#417). La formazione si chiude 10 minuti prima della prima
/// partita, che cade su un orario da partita. A giornata in corso le partite già cominciate hanno anche loro un orario da partita e
/// sono in gioco nel momento della demo (#303), qualunque ora segni il telefono quando si scatta la foto: i Mac di GitHub la
/// scattano spesso di notte, e con le foto delle 5:38 Oggi diceva «La formazione si è chiusa oggi 03:00».
/// Dati inventati: la lega della demo (`LegaDemo.swift`, `DatiDemo.swift`).
@Suite("Demo: scadenza e partite a orari possibili (#417)")
struct DemoScadenzaPossibileTests {
    /// Lo stesso istante fisso degli altri test della demo: ogni corsa dà lo stesso risultato.
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)
    /// Gli orari dei calci d'inizio di Serie A (ora italiana), gli stessi di `DemoCoerenteTests`.
    static let orariDaPartita: Set<String> = ["12:30", "15:00", "18:00", "20:45"]
    /// Le scadenze possibili: 10 minuti prima di un orario da partita.
    static let orariScadenza: Set<String> = ["12:20", "14:50", "17:50", "20:35"]
    /// Di quanti minuti la formazione si chiude prima della prima partita.
    static let minutiPrima = 10

    /// Un istante `ore` ore dopo quello fisso, a un minuto dispari: le foto si scattano quando capita.
    private func istante(_ ore: Int) -> Date { Self.adesso.addingTimeInterval(Double(ore) * 3600 + 7 * 60) }

    /// L'ora («20:45») di una data del server («2026-11-07 20:45»).
    private func ora(_ data: String?) -> String { String((data ?? "").suffix(5)) }

    private func leggi<T: Decodable>(_ percorso: String, da server: FinteServer, come tipo: T.Type) throws -> T {
        let testo = try #require(server.risposte[percorso], "la demo non ha \(percorso)")
        return try Decodifica.decodifica(Data(testo.utf8))
    }

    /// L'ora dell'app (`Orologio`) con la demo `oggi-in-corso` avviata quando il telefono segna `telefono`.
    private func oraApp(_ telefono: Date) -> Date {
        telefono.addingTimeInterval(Orologio.scartoAllAvvio(scenario: nil, demo: true, schermata: "oggi-in-corso", adesso: telefono))
    }

    private func demoInCorso(_ telefono: Date) throws -> FinteServer {
        try #require(FinteServer.demoFase("oggi-in-corso", adesso: telefono), "la demo «oggi-in-corso» non esiste")
    }

    /// Il momento della demo a giornata in corso: l'ora dei risultati in diretta (`aggiornato_il`).
    private func momento(_ live: LiveWidget, _ dove: String) throws -> Date {
        try #require(Quando.data(live.aggiornatoIl), "\(dove): i risultati in diretta non dicono l'ora")
    }

    // MARK: - Giornata in corso

    /// Quello che deve valere a giornata in corso con il telefono a `telefono`, nell'app (Oggi e risultati in diretta) e nel widget.
    private func controllaInCorso(telefono: Date, dove: String) throws {
        let server = try demoInCorso(telefono)
        let oggi = try leggi("/api/oggi", da: server, come: Oggi.self)
        let live = try leggi("/api/live", da: server, come: LiveWidget.self)
        #expect(oggi.faseGiornata == .inCorso)
        let adesso = try momento(live, dove)
        #expect(adesso <= telefono, "\(dove): la demo vive alle \(live.aggiornatoIl ?? ""), nel futuro del telefono")
        #expect(telefono.timeIntervalSince(adesso) < 86_400, "\(dove): la demo vive alle \(live.aggiornatoIl ?? ""), più di un giorno fa")

        // la scadenza: 10 minuti prima della prima partita, che è a un orario da partita, ed è già passata
        let inizio = try #require(Quando.data(oggi.inizio), "\(dove): Oggi non dice quando comincia la giornata")
        let scadenza = try #require(Quando.data(oggi.scadenza), "\(dove): Oggi non ha la scadenza")
        #expect(oggi.minutiScadenza == Self.minutiPrima, "\(dove): la formazione si chiude \(oggi.minutiScadenza ?? -1) minuti prima")
        #expect(Self.orariDaPartita.contains(ora(oggi.inizio)), "\(dove): la prima partita è alle \(ora(oggi.inizio))")
        #expect(inizio.timeIntervalSince(scadenza) == Double(Self.minutiPrima * 60),
                "\(dove): la formazione si chiude alle \(ora(oggi.scadenza)), la prima partita è alle \(ora(oggi.inizio))")
        #expect(scadenza < adesso, "\(dove): la giornata è in corso ma la formazione si chiude alle \(oggi.scadenza ?? "")")
        // l'app confronta la scadenza con la sua ora (`Orologio`: nella demo in corso il momento della demo, #424) e scrive
        // «Chiusa» e sotto quando si è chiusa (`OggiView.siEChiusa`), contando «ieri» da quell'ora come il widget
        let ora = oraApp(telefono)
        #expect(scadenza <= ora, "\(dove): per l'app la formazione non è ancora chiusa (\(oggi.scadenza ?? ""))")
        #expect(scadenza <= telefono, "\(dove): sul telefono la formazione non è ancora chiusa (\(oggi.scadenza ?? ""))")
        let frase = "La formazione si è chiusa \(Quando.leggibile(oggi.chiusura, adesso: ora))"
        #expect(Self.orariScadenza.contains(String(frase.suffix(5))), "\(dove): «\(frase)»")
        #expect(frase == "La formazione si è chiusa ieri 20:35", "\(dove): «\(frase)»")

        // ogni partita del turno a un orario da partita, le stesse in Oggi e nei risultati in diretta
        let partite = live.partite ?? []
        #expect((oggi.partite ?? []).map { "\($0.casa)-\($0.trasferta) \($0.data ?? "")" } == partite.map { "\($0.id) \($0.data ?? "")" },
                "\(dove): Oggi e i risultati in diretta hanno partite o orari diversi")
        for p in oggi.partite ?? [] {
            #expect(Self.orariDaPartita.contains(ora(p.data)), "\(dove): \(p.casa)-\(p.trasferta) alle \(ora(p.data))")
        }

        // nel momento della demo: una finita, due in gioco (#303), le altre da giocare; ognuna al punto giusto della partita
        #expect(partite.count(where: \.finita) == 1, "\(dove): \(partite.count(where: \.finita)) partite finite")
        #expect(partite.count(where: \.inGioco) == 2, "\(dove): \(partite.count(where: \.inGioco)) partite in gioco")
        for p in partite {
            let quando = try #require(p.quando, "\(dove): \(p.id) senza orario")
            let giocati = adesso.timeIntervalSince(quando) / 60   // minuti dal calcio d'inizio
            switch p.stato ?? "" {
            case "da_giocare":
                #expect(giocati < 0, "\(dove): \(p.id) è da giocare ma è cominciata alle \(ora(p.data))")
            case "finita":
                #expect(giocati >= 110, "\(dove): \(p.id) è finita ma è cominciata da \(Int(giocati)) minuti")
            case "intervallo":
                #expect(giocati >= 46 && giocati <= 65, "\(dove): \(p.id) è all'intervallo dopo \(Int(giocati)) minuti dal calcio d'inizio")
            case "primo_tempo":
                let minuto = Int((p.minuto ?? "").filter(\.isNumber)) ?? -1
                #expect(minuto >= 1 && minuto <= 45 && giocati >= Double(minuto) && giocati <= 50,
                        "\(dove): \(p.id) al \(p.minuto ?? "?") del primo tempo dopo \(Int(giocati)) minuti dal calcio d'inizio")
            default:
                Issue.record("\(dove): \(p.id) in uno stato che la demo non usa: \(p.stato ?? "nessuno")")
            }
        }

        // il widget della stessa demo: stessa scadenza, stesse partite, stesso momento
        let w = try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: telefono, fase: .inCorso)), "\(dove): il widget in corso non si legge")
        #expect(w.scadenza == oggi.scadenza, "\(dove): il widget dice scadenza \(w.scadenza ?? "–"), Oggi \(oggi.scadenza ?? "–")")
        #expect(w.primaPartita == oggi.inizio, "\(dove): il widget dice prima partita \(w.primaPartita ?? "–"), Oggi \(oggi.inizio ?? "–")")
        #expect(w.live?.aggiornatoIl == live.aggiornatoIl, "\(dove): il widget vive alle \(w.live?.aggiornatoIl ?? "–"), l'app alle \(live.aggiornatoIl ?? "–")")
        #expect((w.live?.partite ?? []).map { "\($0.id) \($0.stato ?? "") \($0.data ?? "")" } == partite.map { "\($0.id) \($0.stato ?? "") \($0.data ?? "")" },
                "\(dove): partite del widget diverse da quelle dell'app")
    }

    @Test("Giornata in corso, a qualunque ora segni il telefono: scadenza 10 minuti prima della prima partita, partite a orari da partita e in gioco nel momento della demo",
          arguments: Array(0..<24))
    func inCorsoAOgniOra(dopoOre: Int) throws {
        try controllaInCorso(telefono: istante(dopoOre), dove: "dopo \(dopoOre) ore")
    }

    /// Un'ora del telefono (ora italiana) e la giornata in corso contata a mano: il momento della demo è sempre alle 18:48, 48
    /// minuti dopo il calcio d'inizio delle 18:00 (Milan-Juventus all'intervallo, Lazio-Fiorentina nel recupero del primo tempo),
    /// dell'ultimo giorno che è già arrivato a quell'ora; Inter-Roma, la prima partita, è l'anticipo della sera prima alle 20:45.
    struct CasoInCorso: Sendable, CustomTestStringConvertible {
        let telefono: String
        let momento: String
        let inizio: String
        let scadenza: String
        /// La frase sotto «Chiusa» in Oggi, scritta con l'ora dell'app: nella demo in corso il momento della demo (#424), quindi
        /// sempre «ieri», come il widget. Prima si contava dall'ora del telefono («gio 5 20:35» con le foto delle 5:38).
        let frase: String
        var testDescription: String { "telefono alle \(telefono)" }
    }

    @Test("Giornata in corso in casi noti, di notte, di giorno e nei giorni del cambio dell'ora", arguments: [
        // di notte, come le foto della #412 (5:38), che dicevano «La formazione si è chiusa oggi 03:00»
        CasoInCorso(telefono: "2026-11-07 05:38", momento: "2026-11-06 18:48", inizio: "2026-11-05 20:45", scadenza: "2026-11-05 20:35",
                    frase: "La formazione si è chiusa ieri 20:35"),
        // di giorno, prima delle 18:48: la giornata in corso è quella del giorno prima
        CasoInCorso(telefono: "2026-11-07 16:20", momento: "2026-11-06 18:48", inizio: "2026-11-05 20:45", scadenza: "2026-11-05 20:35",
                    frase: "La formazione si è chiusa ieri 20:35"),
        // di sera, dopo le 18:48: la giornata in corso è quella di oggi, la formazione si è chiusa ieri sera
        CasoInCorso(telefono: "2026-11-07 21:10", momento: "2026-11-07 18:48", inizio: "2026-11-06 20:45", scadenza: "2026-11-06 20:35",
                    frase: "La formazione si è chiusa ieri 20:35"),
        // fine dell'ora legale (domenica 25 ottobre 2026, alle 3 si torna alle 2)
        CasoInCorso(telefono: "2026-10-25 05:38", momento: "2026-10-24 18:48", inizio: "2026-10-23 20:45", scadenza: "2026-10-23 20:35",
                    frase: "La formazione si è chiusa ieri 20:35"),
        CasoInCorso(telefono: "2026-10-25 19:00", momento: "2026-10-25 18:48", inizio: "2026-10-24 20:45", scadenza: "2026-10-24 20:35",
                    frase: "La formazione si è chiusa ieri 20:35"),
        // inizio dell'ora legale (domenica 28 marzo 2027, alle 2 si passa alle 3)
        CasoInCorso(telefono: "2027-03-28 05:38", momento: "2027-03-27 18:48", inizio: "2027-03-26 20:45", scadenza: "2027-03-26 20:35",
                    frase: "La formazione si è chiusa ieri 20:35"),
        CasoInCorso(telefono: "2027-03-28 19:00", momento: "2027-03-28 18:48", inizio: "2027-03-27 20:45", scadenza: "2027-03-27 20:35",
                    frase: "La formazione si è chiusa ieri 20:35"),
    ])
    func inCorsoCasiNoti(_ caso: CasoInCorso) throws {
        let telefono = try #require(Quando.data(caso.telefono), "«\(caso.telefono)» non è una data")
        try controllaInCorso(telefono: telefono, dove: caso.telefono)
        let server = try demoInCorso(telefono)
        let oggi = try leggi("/api/oggi", da: server, come: Oggi.self)
        let live = try leggi("/api/live", da: server, come: LiveWidget.self)
        #expect(String((live.aggiornatoIl ?? "").prefix(16)) == caso.momento)
        #expect(oggi.inizio == caso.inizio)
        #expect(oggi.scadenza == caso.scadenza)
        #expect("La formazione si è chiusa \(Quando.leggibile(oggi.chiusura, adesso: oraApp(telefono)))" == caso.frase)
        // le due partite in gioco sono cominciate alle 18:00 del giorno della demo
        let giorno = String(caso.momento.prefix(10))
        for p in live.partite ?? [] where p.inGioco {
            #expect(p.data == "\(giorno) 18:00", "\(p.id) in gioco, cominciata \(p.data ?? "–")")
        }

        // la galleria dei widget vive nel momento della demo: il Cruscotto e il widget dei dubbi dicono «ieri 20:35»
        let adesso = try momento(live, caso.telefono)
        let w = try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: telefono, fase: .inCorso)), "il widget in corso non si legge")
        #expect(ParoleWidget.sottoScadenza(w.inizio, adesso: adesso, conProbabili: w.conProbabili) == ["si è chiusa ieri 20:35"])
        let r = try #require(w.comeRiassuntoOggi(scaricatoIl: adesso), "il riassunto di Oggi del widget non si legge")
        #expect(r.fraseFase(adesso: adesso) == "La formazione si è chiusa ieri 20:35. I punti fatti sono in Oggi.")
    }

    // MARK: - Prima della scadenza e a giornata finita

    @Test("Prima della scadenza e a giornata finita la formazione si chiude 10 minuti prima della prima partita, a un orario da partita",
          arguments: Array(0..<24))
    func primaEFinita(dopoOre: Int) throws {
        let telefono = istante(dopoOre)
        let prima = try leggi("/api/oggi", da: FinteServer.demoFissata(adesso: telefono), come: Oggi.self)
        let finita = try leggi("/api/oggi", da: try #require(FinteServer.demoFase("oggi-finita", adesso: telefono)), come: Oggi.self)
        for (fase, oggi) in [("prima", prima), ("finita", finita)] {
            let inizio = try #require(Quando.data(oggi.inizio), "\(fase): Oggi non dice quando comincia la giornata")
            let scadenza = try #require(Quando.data(oggi.scadenza), "\(fase): Oggi non ha la scadenza")
            #expect(oggi.minutiScadenza == Self.minutiPrima, "\(fase): la formazione si chiude \(oggi.minutiScadenza ?? -1) minuti prima")
            #expect(Self.orariDaPartita.contains(ora(oggi.inizio)), "\(fase), dopo \(dopoOre) ore: la prima partita è alle \(ora(oggi.inizio))")
            #expect(inizio.timeIntervalSince(scadenza) == Double(Self.minutiPrima * 60),
                    "\(fase), dopo \(dopoOre) ore: la formazione si chiude alle \(ora(oggi.scadenza)), la prima partita è alle \(ora(oggi.inizio))")
            #expect(scadenza > telefono, "\(fase), dopo \(dopoOre) ore: la formazione da preparare è già chiusa (\(oggi.scadenza ?? ""))")
        }
    }

    @Test("Le regole della demo dicono di quanti minuti prima si chiude la formazione, come Oggi")
    func regoleComeOggi() throws {
        let server = FinteServer.demoFissata(adesso: Self.adesso)
        let testo = try #require(server.risposte["/api/regole"], "la demo non ha le regole")
        let regole = try #require(try JSONSerialization.jsonObject(with: Data(testo.utf8)) as? [String: Any], "le regole non sono un oggetto JSON")
        let oggi = try leggi("/api/oggi", da: server, come: Oggi.self)
        #expect(regole["scadenza_minuti"] as? Int == Self.minutiPrima)
        #expect(oggi.minutiScadenza == regole["scadenza_minuti"] as? Int)
    }
}
