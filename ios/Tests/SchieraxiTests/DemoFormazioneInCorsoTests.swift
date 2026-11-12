import Foundation
import Testing
@testable import Schieraxi

/// #424: nella demo a giornata iniziata (foto `formazione-chiusa` e `oggi-in-corso`) Formazione e Rosa raccontano la stessa
/// giornata di Oggi: le stesse partite agli stessi orari, chi ha già il voto (fantavoto preso con «fantavoto» sotto), chi ha la
/// partita in corso o è rimasto senza voto («–» grigio con la pillola dello stato) e chi deve ancora giocare. Prima la Formazione
/// chiusa aveva le righe e gli orari di prima della scadenza. E l'app conta «oggi» e «ieri» con la sua ora (`Orologio`), che nella
/// demo a giornata in corso è il momento della demo (alle 18:48): Oggi scrive «La formazione si è chiusa ieri 20:35» come il
/// widget, anche con le foto scattate di notte. Dati inventati: la lega della demo (`LegaDemo.swift`, `DatiDemo.swift`).
@MainActor
@Suite("Demo: Formazione e Rosa a giornata iniziata come Oggi, con l'ora della demo (#424)")
struct DemoFormazioneInCorsoTests {
    /// Lo stesso istante fisso degli altri test della demo.
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)

    /// Un istante `ore` ore dopo quello fisso, a un minuto dispari: le foto si scattano quando capita.
    private func istante(_ ore: Int) -> Date { Self.adesso.addingTimeInterval(Double(ore) * 3600 + 7 * 60) }

    private func demo(_ schermata: String, _ telefono: Date) throws -> FinteServer {
        try #require(FinteServer.demoFase(schermata, adesso: telefono), "la demo «\(schermata)» non esiste")
    }

    private func leggi<T: Decodable>(_ percorso: String, da server: FinteServer, come tipo: T.Type) async throws -> T {
        try Decodifica.decodifica(try await server.richiesta("GET", percorso, corpo: nil))
    }

    /// L'ora dell'app (`Orologio`) con la demo di `schermata` avviata quando il telefono segna `telefono`.
    private func oraApp(_ schermata: String, _ telefono: Date) -> Date {
        telefono.addingTimeInterval(Orologio.scartoAllAvvio(scenario: nil, demo: true, schermata: schermata, adesso: telefono))
    }

    /// Le partite di Oggi per squadra (casa e trasferta).
    private func partitePerSquadra(_ oggi: Oggi) -> [String: Partita] {
        var d: [String: Partita] = [:]
        for p in oggi.partite ?? [] {
            d[p.casa] = p
            d[p.trasferta] = p
        }
        return d
    }

    /// Lo stato di un giocatore va d'accordo con quello della partita della sua squadra (come `stati_giocatori` del server).
    private func statoComeLaPartita(_ g: Giocatore, _ p: Partita) -> Bool {
        switch p.stato ?? "" {
        case "finita": return ["fatto", "senza_voto"].contains(g.statoPartita ?? "")
        case "in_corso": return g.statoPartita == "in_corso"
        default: return g.statoPartita == "da_giocare"
        }
    }

    // MARK: - Righe della Formazione chiusa

    @Test("Formazione chiusa: un giocatore con il voto, uno con la partita in corso o senza voto e uno da giocare, anche in fondo")
    func righeAPartitaIniziata() async throws {
        let f = try await leggi("/api/formazione", da: try demo("formazione-chiusa", Self.adesso), come: Formazione.self)
        #expect(f.iniziata == true)
        for (dove, righe) in [("titolari e panchina", f.titolari + f.panchina), ("panchina, in fondo alla Formazione", f.panchina)] {
            let conVoto = righe.filter { $0.esitoPartita?.fv != nil }
            let senzaNumero = righe.filter { $0.esitoPartita != nil && $0.esitoPartita?.fv == nil }
            let daGiocare = righe.filter { $0.esitoPartita == nil }
            #expect(!conVoto.isEmpty, "\(dove): nessuno con il fantavoto preso")
            #expect(!senzaNumero.isEmpty, "\(dove): nessuno con la partita in corso o senza voto")
            #expect(!daGiocare.isEmpty, "\(dove): nessuno con la partita ancora da giocare")
            for g in conVoto {
                #expect(RigaGiocatore.sottoNumero(g) == "fantavoto", "\(g.nome): sotto il fantavoto preso non c'è «fantavoto»")
            }
            for g in senzaNumero {
                #expect(RigaGiocatore.numero(g) == "–", "\(g.nome): «\(RigaGiocatore.numero(g))» invece di «–»")
                #expect(RigaGiocatore.sottoNumero(g) == nil, "\(g.nome): «gioca N%» a partita iniziata")
            }
            for g in daGiocare {
                #expect(g.etichetta?.testoPronto == "Da giocare", "\(g.nome): «\(g.etichetta?.testoPronto ?? "nessuna etichetta")»")
            }
        }
    }

    @Test("Formazione chiusa: ogni giocatore ha la partita, l'orario e lo stato di Oggi in corso, a qualunque ora segni il telefono",
          arguments: [0, 5, 11, 17, 22])
    func comeOggiInCorso(dopoOre: Int) async throws {
        let telefono = istante(dopoOre)
        let s = try demo("formazione-chiusa", telefono)
        let f = try await leggi("/api/formazione", da: s, come: Formazione.self)
        // nella stessa foto anche Oggi è a giornata in corso, con le partite e gli orari della foto `oggi-in-corso`
        let oggi = try await leggi("/api/oggi", da: s, come: Oggi.self)
        let oggiInCorso = try await leggi("/api/oggi", da: try demo("oggi-in-corso", telefono), come: Oggi.self)
        #expect(oggi.faseGiornata == .inCorso, "dopo \(dopoOre) ore: con la Formazione chiusa Oggi è «\(oggi.faseGiornata.rawValue)»")
        #expect((oggi.partite ?? []).map { "\($0.casa)-\($0.trasferta) \($0.data ?? "")" }
                == (oggiInCorso.partite ?? []).map { "\($0.casa)-\($0.trasferta) \($0.data ?? "")" })
        let partita = partitePerSquadra(oggi)
        let inCorso = Dictionary((oggi.giornataInCorso?.giocatori ?? []).map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        try #require(!inCorso.isEmpty, "Oggi in corso non dice com'è andato ogni giocatore")
        for g in f.titolari + f.panchina + Array((f.schede ?? [:]).values) {
            let p = try #require(partita[g.squadra ?? ""], "\(g.nome): la sua squadra non gioca nel turno di Oggi")
            #expect(g.dataPartita == p.data, "dopo \(dopoOre) ore, \(g.nome): partita \(g.dataPartita ?? "–"), in Oggi \(p.data ?? "–")")
            #expect(statoComeLaPartita(g, p), "\(g.nome): «\(g.statoPartita ?? "nessuno stato")» con la partita «\(p.stato ?? "–")» in Oggi")
            if let c = inCorso[g.id] {
                #expect(g.statoPartita == c.stato, "\(g.nome): «\(g.statoPartita ?? "–")» in Formazione, «\(c.stato ?? "–")» in Oggi")
                #expect(g.fantavotoPreso == c.fantavoto, "\(g.nome): fantavoto \(g.fantavotoPreso ?? .nan) in Formazione, \(c.fantavoto ?? .nan) in Oggi")
            }
        }
    }

    @Test("Le pillole a giornata iniziata hanno le parole del server: lo stato della partita, «Infortunato» per chi è fuori")
    func paroleDelloStato() async throws {
        let f = try await leggi("/api/formazione", da: try demo("formazione-chiusa", Self.adesso), come: Formazione.self)
        let schede = Array((f.schede ?? [:]).values)
        try #require(!schede.isEmpty, "la Formazione chiusa non ha le schede della rosa")
        for g in schede {
            let attesa: String?
            if g.titolarita == "fuori" {
                attesa = g.stato == "infortunato" ? "Infortunato" : "Fuori"
            } else {
                attesa = Giocatore.nomiStatoPartita[g.statoPartita ?? ""]?.0
            }
            #expect(attesa != nil && g.etichetta?.testoPronto == attesa,
                    "\(g.nome): «\(g.etichetta?.testoPronto ?? "nessuna etichetta")» con lo stato «\(g.statoPartita ?? "–")»")
        }
    }

    @Test("A giornata iniziata la Rosa ha gli stessi stati e gli stessi orari della Formazione, e quelli delle altre squadre vanno d'accordo con Oggi")
    func rosaComeLaFormazione() async throws {
        let s = try demo("formazione-chiusa", Self.adesso)
        let schede = try await leggi("/api/formazione", da: s, come: Formazione.self).schede ?? [:]
        let rosa = try await leggi("/api/rosa", da: s, come: Rosa.self)
        let previsioni = rosa.giocatori.compactMap(\.previsione)
        try #require(!previsioni.isEmpty, "la Rosa non ha le previsioni")
        for p in previsioni {
            let g = try #require(schede[String(p.id)], "\(p.nome) è nella Rosa ma non nella Formazione")
            #expect(p.statoPartita == g.statoPartita && p.fantavotoPreso == g.fantavotoPreso && p.dataPartita == g.dataPartita,
                    "\(p.nome): Rosa «\(p.statoPartita ?? "–")» \(p.dataPartita ?? "–"), Formazione «\(g.statoPartita ?? "–")» \(g.dataPartita ?? "–")")
        }
        #expect(previsioni.contains { $0.esitoPartita?.fv != nil }, "nella Rosa nessuno ha il fantavoto preso")
        #expect(previsioni.contains { $0.esitoPartita != nil && $0.esitoPartita?.fv == nil }, "nella Rosa nessuno ha la partita in corso")
        #expect(previsioni.contains { $0.esitoPartita == nil }, "nella Rosa nessuno deve ancora giocare")

        // la rosa di un'altra squadra (foto `lega-rosa`): ognuno con lo stato della partita della sua squadra in Oggi
        let partita = partitePerSquadra(try await leggi("/api/oggi", da: s, come: Oggi.self))
        let altra = try await leggi("/api/rosa?squadra=" + IndirizzoServer.codifica("Gli Amici del Bar Sport Centrale"), da: s, come: Rosa.self)
        for g in altra.giocatori.compactMap(\.previsione) {
            let p = try #require(partita[g.squadra ?? ""], "\(g.nome): la sua squadra non gioca nel turno di Oggi")
            #expect(g.dataPartita == p.data && statoComeLaPartita(g, p),
                    "\(g.nome): «\(g.statoPartita ?? "nessuno stato")» \(g.dataPartita ?? "–"), in Oggi «\(p.stato ?? "–")» \(p.data ?? "–")")
        }
    }

    // MARK: - L'ora dell'app

    @Test("Nella demo a giornata in corso l'ora dell'app è il momento della demo; nelle altre foto e fuori dalla demo è l'ora vera",
          arguments: Array(0..<24))
    func orologioDellaDemo(dopoOre: Int) {
        let telefono = istante(dopoOre)
        let momento = LegaDemo.momento(adesso: telefono, fase: .inCorso)
        for schermata in ["oggi-in-corso", "formazione-chiusa"] {
            #expect(abs(oraApp(schermata, telefono).timeIntervalSince(momento)) < 0.001,
                    "dopo \(dopoOre) ore, \(schermata): l'app non vive nel momento della demo")
        }
        let altre: [String?] = ["oggi", "formazione", "formazione-salvata", "oggi-finita", "lega-rosa", nil]
        for schermata in altre {
            #expect(Orologio.scartoAllAvvio(scenario: nil, demo: true, schermata: schermata, adesso: telefono) == 0, "\(schermata ?? "nessuna schermata")")
        }
        #expect(Orologio.scartoAllAvvio(scenario: nil, demo: false, schermata: "oggi-in-corso", adesso: telefono) == 0, "fuori dalla demo l'ora è quella vera")
        // le fotografie dal vero restano come prima: l'ora in cui il server è stato fotografato
        let fotografia = telefono.addingTimeInterval(-5000)
        #expect(abs(Orologio.scartoAllAvvio(scenario: fotografia, demo: true, schermata: "oggi-in-corso", adesso: telefono) + 5000) < 0.001)
    }

    @Test("Sotto «Chiusa» Oggi scrive «La formazione si è chiusa ieri 20:35», come il widget, a qualunque ora segni il telefono",
          arguments: Array(0..<24))
    func siEChiusaComeIlWidget(dopoOre: Int) async throws {
        let telefono = istante(dopoOre)
        let oggi = try await leggi("/api/oggi", da: try demo("oggi-in-corso", telefono), come: Oggi.self)
        let frase = OggiView.siEChiusa(oggi, adesso: oraApp("oggi-in-corso", telefono))
        let w = try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: telefono, fase: .inCorso)), "il widget in corso non si legge")
        let nelWidget = ParoleWidget.sottoScadenza(w.inizio, adesso: LegaDemo.momento(adesso: telefono, fase: .inCorso),
                                                   conProbabili: w.conProbabili)
        #expect(frase == "La formazione si è chiusa ieri 20:35", "dopo \(dopoOre) ore: «\(frase)»")
        #expect(frase == "La formazione " + (nelWidget.first ?? ""), "dopo \(dopoOre) ore: Oggi «\(frase)», il widget «\(nelWidget.first ?? "")»")
    }

    @Test("Le righe della Formazione chiusa scrivono il giorno delle partite con l'ora dell'app, come Oggi", arguments: [0, 5, 11, 17, 22])
    func righeConLOraDellApp(dopoOre: Int) async throws {
        let telefono = istante(dopoOre)
        let f = try await leggi("/api/formazione", da: try demo("formazione-chiusa", telefono), come: Formazione.self)
        let ora = oraApp("formazione-chiusa", telefono)
        // Pulinski (Milan) gioca dalle 18:00 del giorno della demo, Thorvan (Inter) ha giocato la sera prima, Lorkman (Atalanta)
        // gioca alle 20:45
        let attese = [115: "MIL vs JUV · oggi 18:00", 121: "INT vs ROM · ieri 20:45", 122: "ATA @ NAP · oggi 20:45"]
        for (id, attesa) in attese {
            let g = try #require(f.titolari.first { $0.id == id }, "\(id) non è tra i titolari")
            #expect(RigaGiocatore.sottotitolo(g, adesso: ora) == attesa, "dopo \(dopoOre) ore: «\(RigaGiocatore.sottotitolo(g, adesso: ora))»")
        }
    }

    @Test("Oggi, le righe dei giocatori e la partita della scheda contano «oggi» e «ieri» con l'ora dell'app (`Orologio`), mai con quella del telefono",
          arguments: ["Sources/Presentation/Oggi/OggiView.swift", "Sources/Support/RigaGiocatore.swift",
                      "Sources/Domain/LetturaScheda.swift"])
    func conLOrologioDellApp(percorso: String) throws {
        let codice = try sorgente(percorso)
        let chiamate = Self.chiamate("Quando.leggibile(", in: codice)
        #expect(!chiamate.isEmpty, "\(percorso): nessuna data scritta, il controllo non serve più")
        for c in chiamate {
            #expect(c.contains("adesso:"), "\(percorso): «\(c)» conta con l'ora del telefono")
        }
        for r in codice.split(whereSeparator: \.isNewline) where r.contains("adesso") && r.contains("Date()") {
            Issue.record("\(percorso): «\(r.trimmingCharacters(in: .whitespaces))» usa l'ora del telefono invece di Orologio.adesso()")
        }
    }

    @Test("Il controllo vede anche le chiamate che vanno a capo")
    func chiamateACapo() {
        let codice = "let a = Quando.leggibile(\n    data,\n    adesso: ora\n)\nlet b = Quando.leggibile(f(x))"
        #expect(Self.chiamate("Quando.leggibile(", in: codice) == ["Quando.leggibile(\n    data,\n    adesso: ora\n)", "Quando.leggibile(f(x))"])
    }

    /// Le chiamate che cominciano con `inizio` (che finisce con «(»), intere anche se vanno a capo: fino alla parentesi che chiude
    /// quella aperta, contando quelle dentro.
    static func chiamate(_ inizio: String, in codice: String) -> [String] {
        var trovate: [String] = []
        var resto = codice[...]
        while let r = resto.range(of: inizio) {
            var aperte = 1
            var i = r.upperBound
            while i < resto.endIndex, aperte > 0 {
                if resto[i] == "(" { aperte += 1 } else if resto[i] == ")" { aperte -= 1 }
                i = resto.index(after: i)
            }
            trovate.append(String(resto[r.lowerBound..<i]))
            resto = resto[i...]
        }
        return trovate
    }

    /// Un file dell'app (percorso dalla cartella `ios/`), letto come fa `OggiComeLaWebTests`.
    private func sorgente(_ percorso: String, file: String = #filePath) throws -> String {
        var cartella = URL(fileURLWithPath: file)
        for _ in 0..<3 { cartella.deleteLastPathComponent() }          // questo file, SchieraxiTests, Tests
        return try #require(try? String(contentsOf: cartella.appendingPathComponent(percorso), encoding: .utf8),
                            "non riesco a leggere ios/\(percorso)")
    }
}
