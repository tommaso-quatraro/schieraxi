import Foundation
import Testing
@testable import Schieraxi

/// La giornata della demo come in una lega vera (#390): la formazione salvata ha gli stessi punti attesi in Formazione, in Oggi
/// prima, durante e dopo la giornata e nei widget; gli orari che la demo ricava da «adesso» (il recupero di una partita rinviata,
/// l'ora delle probabili) sono orari possibili e tornano con l'ora mostrata, a qualunque ora si scattino le foto.
/// Dati inventati: la lega della demo (`LegaDemo.swift`, `DatiDemo.swift`).
@Suite("Demo: la stessa giornata coerente in ogni schermata")
struct DemoGiornataCoerenteTests {
    /// Lo stesso istante fisso di `DemoCoerenteTests`: ogni corsa dà lo stesso risultato.
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)

    /// Gli orari dei calci d'inizio di Serie A (ora italiana), gli stessi di `DemoCoerenteTests`.
    static let orariDaPartita: Set<String> = ["12:30", "15:00", "18:00", "20:45"]

    /// Un istante `ore` ore dopo quello fisso, a un minuto dispari.
    private func istante(_ ore: Int) -> Date { Self.adesso.addingTimeInterval(Double(ore) * 3600 + 7 * 60) }

    /// La demo di una fotografia (`oggi` è la demo di sempre) costruita nell'istante `adesso`.
    private func demo(_ schermata: String, adesso: Date = Self.adesso) throws -> FinteServer {
        if schermata == "oggi" { return FinteServer.demoFissata(adesso: adesso) }
        return try #require(FinteServer.demoFase(schermata, adesso: adesso), "la demo «\(schermata)» non esiste")
    }

    private func leggi<T: Decodable>(_ percorso: String, da server: FinteServer, come tipo: T.Type) async throws -> T {
        try Decodifica.decodifica(try await server.richiesta("GET", percorso, corpo: nil))
    }

    private func oggetto(_ percorso: String, da server: FinteServer) async throws -> [String: Any] {
        let d = try await server.richiesta("GET", percorso, corpo: nil)
        return try #require(try JSONSerialization.jsonObject(with: d) as? [String: Any], "\(percorso) non è un oggetto JSON")
    }

    private func widget(_ fase: LegaDemo.Fase) throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: Self.adesso, fase: fase)), "il widget \(fase) della demo non si legge")
    }

    /// L'ora («20:45») di una data del server («2026-11-07 20:45»).
    private func ora(_ data: String?) -> String { String((data ?? "").suffix(5)) }

    // MARK: - Punti attesi e fascia

    /// Punti attesi e fascia letti da una schermata. Si confrontano i numeri, non solo come si scrivono: con una fonte arrotondata
    /// (72,7) e una no (72,69) la fascia può uscire «tra 64 e 81» da una parte e «tra 65 e 81» dall'altra.
    private struct Lettura {
        let dove: String
        let attesi: Double?
        var basso: Double? = nil
        var alto: Double? = nil
        /// false dove la schermata non ha la fascia (la consigliata della valutazione e del riepilogo)
        var conFascia = true
    }

    private func tra(_ l: Lettura) -> String { "tra \(Formato.intero(l.basso)) e \(Formato.intero(l.alto))" }

    @Test("La formazione salvata ha gli stessi punti attesi e la stessa fascia in Formazione, Oggi prima, in corso e a giornata finita, e nei widget")
    func stessiPuntiAttesi() async throws {
        let consigliata = try await leggi("/api/formazione", da: try demo("oggi"), come: Formazione.self)
        let riferimento = Lettura(dove: "Formazione (consigliata)", attesi: consigliata.punteggioAtteso,
                                  basso: consigliata.intervallo?.basso, alto: consigliata.intervallo?.alto)
        var letture: [Lettura] = []

        // la Formazione mostra lo stile e il modulo proposti (`livelli`): la stessa formazione
        let stile = consigliata.stileConsigliato ?? 0
        let livello = try #require(consigliata.livelli?.first { $0.rischio == stile }, "la Formazione non ha lo stile proposto")
        let proposta = try #require(livello.moduli.first { $0.modulo == livello.modulo }, "lo stile proposto non ha il suo modulo")
        letture.append(Lettura(dove: "Formazione (stile e modulo proposti)", attesi: proposta.punteggioAtteso,
                               basso: proposta.intervallo?.basso, alto: proposta.intervallo?.alto))

        // Formazione con la scelta salvata, prima e dopo la scadenza: l'app chiede al server quanto vale (`valuta`)
        for schermata in ["formazione-salvata", "formazione-chiusa"] {
            let s = try demo(schermata)
            let scelta = try await oggetto("/api/scelta", da: s)
            let titolari = try #require(scelta["titolari"] as? [Int], "\(schermata): nessuna scelta salvata")
            // la scelta salvata della demo sono gli undici della consigliata («Salva questa»): stessi punti, differenza zero
            #expect(Set(titolari) == Set(consigliata.titolari.map(\.id)), "\(schermata): la scelta salvata non è la consigliata")
            let corpo = try JSONEncoder().encode(RichiestaValutazione(titolari: titolari, salva: false, giornata: consigliata.giornata))
            let v: ValutazioneManuale = try Decodifica.decodifica(try await s.richiesta("POST", "/api/formazione/valuta", corpo: corpo))
            #expect(v.modulo == consigliata.modulo, "\(schermata): modulo \(v.modulo), la consigliata \(consigliata.modulo)")
            #expect(abs(v.differenza ?? .nan) < 0.05, "\(schermata): \(v.differenza ?? .nan) rispetto alla consigliata con gli stessi undici")
            letture.append(Lettura(dove: "\(schermata) (valuta)", attesi: v.punteggioAtteso, basso: v.intervallo?.basso, alto: v.intervallo?.alto))
            letture.append(Lettura(dove: "\(schermata) (la consigliata per valuta)", attesi: v.consigliata, conFascia: false))
            letture.append(Lettura(dove: "\(schermata) (la consigliata con lo stesso modulo)", attesi: v.consigliataStessoModulo, conFascia: false))
        }

        // Oggi prima della scadenza («La tua formazione»: la consigliata non ancora salvata, come dice la Formazione, #418) e a
        // giornata in corso («attesi prima»)
        let oggi = try await leggi("/api/oggi", da: try demo("oggi"), come: Oggi.self)
        #expect(oggi.formazione?.tuaScelta == false, "Oggi dice «la tua scelta», la Formazione «non hai salvato una tua formazione»")
        letture.append(Lettura(dove: "Oggi", attesi: oggi.formazione?.punteggioAtteso,
                               basso: oggi.formazione?.intervallo?.basso, alto: oggi.formazione?.intervallo?.alto))
        let inCorso = try await leggi("/api/oggi", da: try demo("oggi-in-corso"), come: Oggi.self)
        #expect(inCorso.faseGiornata == .inCorso)
        letture.append(Lettura(dove: "Oggi in corso (attesi prima)", attesi: inCorso.formazione?.punteggioAtteso,
                               basso: inCorso.formazione?.intervallo?.basso, alto: inCorso.formazione?.intervallo?.alto))

        // Oggi a giornata finita (anche con un recupero da giocare): i punti attesi restano quelli, i punti fatti sono un'altra cosa
        for schermata in ["oggi-finita", "oggi-finita-recupero"] {
            let finita = try await leggi("/api/oggi", da: try demo(schermata), come: Oggi.self)
            let r = try #require(finita.riepilogoGiornata, "\(schermata): manca «Com'è andata»")
            #expect(r.formazioneDi == "tua")
            letture.append(Lettura(dove: "\(schermata) (Com'è andata)", attesi: r.puntiAttesi, basso: r.intervallo?.basso, alto: r.intervallo?.alto))
            if let c = r.consigliata {
                // nel Diario la consigliata è la stessa formazione che hai salvato: stessi punti attesi e stessi punti fatti
                letture.append(Lettura(dove: "\(schermata) (la consigliata nel Diario)", attesi: c.puntiAttesi, conFascia: false))
                #expect(c.puntiFatti == r.puntiFatti, "\(schermata): con gli stessi undici la consigliata fa \(c.puntiFatti ?? .nan), tu \(r.puntiFatti ?? .nan)")
            }
        }

        // i widget (la galleria `AnteprimaWidget` legge la stessa lega): prima, durante e dopo
        for fase in [LegaDemo.Fase.prima, .inCorso] {
            let f = try widget(fase).formazione
            letture.append(Lettura(dove: "widget \(fase)", attesi: f?.puntiAttesi, basso: f?.intervallo?.basso, alto: f?.intervallo?.alto))
        }
        let finitaWidget = try widget(.finita).faseGiornata.riepilogo
        letture.append(Lettura(dove: "widget finita", attesi: finitaWidget?.puntiAttesi,
                               basso: finitaWidget?.intervallo?.basso, alto: finitaWidget?.intervallo?.alto))

        try #require(riferimento.basso != nil && riferimento.alto != nil, "la Formazione non ha la fascia")
        for l in letture {
            #expect(abs((l.attesi ?? .nan) - (riferimento.attesi ?? .nan)) < 0.001,
                    "\(l.dove): \(l.attesi ?? .nan) punti attesi, \(riferimento.dove) \(riferimento.attesi ?? .nan)")
            #expect(Formato.punti(l.attesi) == Formato.punti(riferimento.attesi),
                    "\(l.dove): «\(Formato.punti(l.attesi))», \(riferimento.dove) «\(Formato.punti(riferimento.attesi))»")
            guard l.conFascia else { continue }
            #expect(abs((l.basso ?? .nan) - (riferimento.basso ?? .nan)) < 0.001 && abs((l.alto ?? .nan) - (riferimento.alto ?? .nan)) < 0.001,
                    "\(l.dove): fascia da \(l.basso ?? .nan) a \(l.alto ?? .nan), \(riferimento.dove) da \(riferimento.basso ?? .nan) a \(riferimento.alto ?? .nan)")
            #expect(tra(l) == tra(riferimento), "\(l.dove): «\(tra(l))», \(riferimento.dove) «\(tra(riferimento))»")
        }
    }

    // MARK: - Confronto nella formazione (#392)

    @Test("Confronto nella formazione: tra parentesi la differenza dei due numeri scritti, con «−» o «+», mai il trattino",
          arguments: zip([120, 121, 113, 104, 101], [123, 125, 117, 105, 102]))
    func differenzaDeiNumeriScritti(titolare: Int, altro: Int) async throws {
        let s = try demo("oggi")
        let f = try await leggi("/api/formazione", da: s, come: Formazione.self)
        let c = try await leggi("/api/confronto?a=\(titolare)&b=\(altro)&livello=0&modulo=\(f.modulo)", da: s, come: Confronto.self)
        let testo = try #require(c.formazione?.testo, "\(titolare) e \(altro): manca il riquadro «Nella formazione»")
        // `confronto.esito_meglio` ed `esito_peggio` di fanta/frasi.py: i due punteggi e, tra parentesi, invertita − attuale
        let meglio = #/vale ([0-9]+,[0-9]) punti attesi; con i due invertiti ([0-9]+,[0-9]) \(([^)]*)\)/#
        let peggio = #/varrebbe ([0-9]+,[0-9]) invece di ([0-9]+,[0-9]) \(([^)]*)\)/#
        let numeri: (attuale: Substring, invertita: Substring, scritta: Substring)
        if let m = testo.firstMatch(of: meglio) {
            numeri = (m.1, m.2, m.3)
        } else if let m = testo.firstMatch(of: peggio) {
            numeri = (m.2, m.1, m.3)
        } else {
            #expect(testo.contains("valgono praticamente lo stesso"), "«\(testo)»: manca l'esito con i due punteggi")
            return
        }
        func valore(_ s: Substring) throws -> Double { try #require(Double(s.replacingOccurrences(of: ",", with: ".")), "«\(s)» non è un numero") }
        let attesa = Formato.conSegno(try valore(numeri.invertita) - valore(numeri.attuale))
        #expect(String(numeri.scritta) == attesa, "«\(testo)»: \(numeri.invertita) − \(numeri.attuale) si scrive «\(attesa)», non «\(numeri.scritta)»")
        #expect(!testo.contains("(-"), "«\(testo)»: un trattino al posto del meno")
    }

    // MARK: - Recupero di una partita rinviata

    @Test("Il recupero della partita rinviata è a un orario da partita, dopo il turno, in un giorno in cui le due squadre non giocano",
          arguments: Array(0..<24))
    func recuperoAOrarioDaPartita(dopoOre: Int) async throws {
        let adesso = istante(dopoOre)

        // prima della scadenza: la carta «Partita rinviata» e la riga della partita nel turno
        let s = try demo("oggi-rinvio", adesso: adesso)
        let oggi = try await leggi("/api/oggi", da: s, come: Oggi.self)
        let rinviata = try #require(oggi.rinvio?.valore?.partite.first, "oggi-rinvio: nessuna partita rinviata")
        let data = try #require(rinviata.data, "oggi-rinvio: il recupero non ha una data")
        let quando = try #require(Quando.data(data))
        #expect(Self.orariDaPartita.contains(ora(data)), "dopo \(dopoOre) ore: recupero alle \(ora(data))")
        #expect(oggi.partite?.first { $0.casa == rinviata.casa && $0.trasferta == rinviata.trasferta }?.data == data,
                "la partita del turno e la carta del rinvio hanno due date diverse")
        for p in oggi.partite ?? [] where p.stato != "rinviata" {
            #expect((Quando.data(p.data) ?? .distantFuture) < quando, "dopo \(dopoOre) ore: il recupero viene prima di \(p.id)")
        }
        // nelle giornate dopo, nessuna delle due squadre gioca il giorno del recupero
        let calendario = try await leggi("/api/calendario", da: s, come: Calendario.self)
        for squadra in calendario.squadre where [rinviata.casa, rinviata.trasferta].contains(squadra.squadra) {
            for p in squadra.partite where p.giornata != oggi.giornata {
                #expect(!(p.data ?? "").hasPrefix(String(data.prefix(10))), "dopo \(dopoOre) ore: \(squadra.squadra) gioca anche il giorno del recupero (G\(p.giornata))")
            }
        }

        // a giornata finita: il recupero che manca
        let finita = try await leggi("/api/oggi", da: try demo("oggi-finita-recupero", adesso: adesso), come: Oggi.self)
        let manca = try #require(finita.riepilogoGiornata?.recuperi.first, "oggi-finita-recupero: nessun recupero")
        let dataFinita = try #require(manca.data, "oggi-finita-recupero: il recupero non ha una data")
        #expect(Self.orariDaPartita.contains(ora(dataFinita)), "giornata finita, dopo \(dopoOre) ore: recupero alle \(ora(dataFinita))")
        #expect((Quando.data(dataFinita) ?? .distantPast) > adesso, "giornata finita, dopo \(dopoOre) ore: il recupero è già passato")
        for p in finita.partite ?? [] where [p.casa, p.trasferta].contains(manca.casa) || [p.casa, p.trasferta].contains(manca.trasferta) {
            #expect(!(p.data ?? "").hasPrefix(String(dataFinita.prefix(10))), "giornata finita: \(p.id) si gioca il giorno del recupero")
        }
    }

    /// Un momento della demo (ora italiana) e i recuperi contati a mano: il diciottesimo giorno dopo l'inizio del turno, alle 20:45.
    struct CasoRecupero: Sendable, CustomTestStringConvertible {
        let adesso: String
        /// prima della scadenza (`oggi-rinvio`)
        let prima: String
        /// a giornata finita (`oggi-finita-recupero`): il turno della giornata finita era una settimana prima di quello della prossima
        let finita: String
        var testDescription: String { "adesso \(adesso)" }
    }

    @Test("Recupero in casi noti, anche a cavallo del cambio dell'ora: sempre alle 20:45", arguments: [
        // turno dalle 18:00 del 10 novembre; a giornata finita la prossima parte il 14, quella finita era partita il 7
        CasoRecupero(adesso: "2026-11-10 10:07", prima: "2026-11-28 20:45", finita: "2026-11-25 20:45"),
        // il turno parte con l'ora legale, il recupero cade dopo il 25 ottobre 2026, con l'ora solare
        CasoRecupero(adesso: "2026-10-20 10:07", prima: "2026-11-07 20:45", finita: "2026-11-04 20:45"),
        // il turno parte con l'ora solare, il recupero cade dopo il 28 marzo 2027, con l'ora legale
        CasoRecupero(adesso: "2027-03-20 10:07", prima: "2027-04-07 20:45", finita: "2027-04-04 20:45"),
    ])
    func recuperoCasiNoti(_ caso: CasoRecupero) async throws {
        let adesso = try #require(Quando.data(caso.adesso), "«\(caso.adesso)» non è una data")
        let rinvio = try await leggi("/api/oggi", da: try demo("oggi-rinvio", adesso: adesso), come: Oggi.self)
        #expect(rinvio.rinvio?.valore?.partite.first?.data == caso.prima)
        let finita = try await leggi("/api/oggi", da: try demo("oggi-finita-recupero", adesso: adesso), come: Oggi.self)
        #expect(finita.riepilogoGiornata?.recuperi.first?.data == caso.finita)
    }

    // MARK: - Ora delle probabili

    @Test("Probabili: «aggiornate alle HH:MM · N ore fa» torna con l'ora della demo, con le frasi del server; Stato dei dati dice la stessa ora",
          arguments: Array(0..<24))
    func probabiliAllOraGiusta(dopoOre: Int) async throws {
        let frasi = try FrasiDelServer(prefissi: ["probabili.", "tempo."])
        let adesso = istante(dopoOre)
        let s = try demo("oggi", adesso: adesso)
        let oggi = try await leggi("/api/oggi", da: s, come: Oggi.self)
        let p = try #require(oggi.probabili?.valore, "dopo \(dopoOre) ore: Oggi non dice quando sono uscite le probabili")
        let letto = try #require(p.aggiornateIl)
        let quando = try #require(Quando.data(letto), "«\(letto)» non è una data")
        #expect(quando <= adesso, "dopo \(dopoOre) ore: probabili lette nel futuro (\(letto))")

        // come `freschezza_probabili` di fanta/gestione.py
        let minuti = Int((adesso.timeIntervalSince(quando) / 60).rounded(.down))
        #expect(p.minutiFa == minuti, "dopo \(dopoOre) ore: «\(p.minutiFa ?? -1) minuti fa», ma le probabili sono delle \(ora(letto))")
        let ore = minuti / 60
        let eta = try minuti < 60 ? frasi.frase("tempo.minuti_fa.\(minuti == 1 ? "one" : "other")", ["n": "\(minuti)"])
                                  : frasi.frase("tempo.ore_fa.\(ore == 1 ? "one" : "other")", ["n": "\(ore)"])
        #expect(p.eta == eta, "dopo \(dopoOre) ore: «\(p.eta ?? "")» invece di «\(eta)»")
        var roma = Calendar(identifier: .gregorian)
        roma.timeZone = TimeZone(identifier: "Europe/Rome") ?? .current
        let giorni = roma.dateComponents([.day], from: roma.startOfDay(for: quando), to: roma.startOfDay(for: adesso)).day ?? 0
        try #require(giorni <= 1, "dopo \(dopoOre) ore: probabili di \(giorni) giorni fa")
        let testo = try frasi.frase(giorni == 0 ? "probabili.oggi" : "probabili.ieri", ["ora": ora(letto)])
        #expect(p.testo == testo, "dopo \(dopoOre) ore: «\(p.testo ?? "")» invece di «\(testo)»")

        // l'avviso: lette da almeno 6 ore con la formazione che si chiude entro un giorno, come nella demo a ogni ora (la prima
        // partita è fra 6 e 24 ore). Le ore alla scadenza scritte nell'avviso si provano con i casi noti, qui sotto.
        let scadenza = try #require(Quando.data(oggi.scadenza), "Oggi non ha la scadenza")
        try #require(scadenza > adesso && scadenza.timeIntervalSince(adesso) <= 24 * 3600, "dopo \(dopoOre) ore: la scadenza non è entro un giorno")
        #expect(minuti >= 6 * 60, "dopo \(dopoOre) ore: probabili lette da \(minuti) minuti, la demo mostra quelle vecchie")
        #expect(p.vecchie == true, "dopo \(dopoOre) ore: probabili lette da \(minuti) minuti con la scadenza entro un giorno, ma non vecchie")
        let modello = try frasi.modello("probabili.vecchie").replacingOccurrences(of: "{eta}", with: eta).components(separatedBy: "{tempo}")
        try #require(modello.count == 2, "«probabili.vecchie» non ha il segnaposto {tempo}")
        let avviso = p.avviso ?? ""
        #expect(avviso.hasPrefix(modello[0]) && avviso.hasSuffix(modello[1]), "dopo \(dopoOre) ore: «\(avviso)»")

        // Stato dei dati: le stesse probabili, lette alla stessa ora
        let stato = try await oggetto("/api/stato-dati", da: s)
        let raccolta = ((stato["probabili"] as? [[String: Any]]) ?? []).first { $0["giornata"] as? Int == oggi.giornata }
        #expect(Quando.data(raccolta?["rilevato"] as? String) == quando, "Stato dei dati: probabili rilevate «\(raccolta?["rilevato"] ?? "–")», Oggi \(letto)")
        let aggiornamento = ((stato["aggiornamenti"] as? [[String: Any]]) ?? []).first { $0["cosa"] as? String == "probabili formazioni" }
        #expect(Quando.data(aggiornamento?["quando"] as? String) == quando, "Stato dei dati: probabili aggiornate «\(aggiornamento?["quando"] ?? "–")», Oggi \(letto)")
    }

    /// Un momento della demo (ora italiana) con le probabili come le scriverebbe il server: lette otto ore prima (ai cinque minuti),
    /// e le ore alla scadenza dell'avviso contate a mano dagli orari da partita.
    struct CasoProbabili: Sendable, CustomTestStringConvertible {
        let adesso: String
        let ieri: Bool
        let ora: String
        let minuti: Int
        let oreAllaScadenza: Int
        var testDescription: String { "adesso \(adesso)" }
    }

    @Test("Probabili in casi noti, anche nel giorno del cambio dell'ora: ora, «8 ore fa» e ore alla scadenza", arguments: [
        // La formazione si chiude 10 minuti prima della prima partita (#417).
        // prima partita alle 12:30, scadenza alle 12:20: 10,5 ore, che il server scrive «10 ore» (round() di Python, metà al pari)
        CasoProbabili(adesso: "2026-11-10 01:50", ieri: true, ora: "17:50", minuti: 480, oreAllaScadenza: 10),
        // prima partita alle 18:00, scadenza alle 17:50: 7 ore e 43 minuti
        CasoProbabili(adesso: "2026-11-10 10:07", ieri: false, ora: "02:05", minuti: 482, oreAllaScadenza: 8),
        // a mezzanotte: scadenza alle 12:20, 12 ore e 20 minuti
        CasoProbabili(adesso: "2026-11-10 00:00", ieri: true, ora: "16:00", minuti: 480, oreAllaScadenza: 12),
        // fine dell'ora legale (domenica 25 ottobre 2026, alle 3 si torna alle 2): otto ore vere fa erano le 2:05 dell'ora legale;
        // scadenza alle 17:50, 8 ore e 43 minuti
        CasoProbabili(adesso: "2026-10-25 09:07", ieri: false, ora: "02:05", minuti: 482, oreAllaScadenza: 9),
        // inizio dell'ora legale (domenica 28 marzo 2027, alle 2 si passa alle 3): otto ore vere fa era mezzanotte e cinque
        CasoProbabili(adesso: "2027-03-28 09:07", ieri: false, ora: "00:05", minuti: 482, oreAllaScadenza: 9),
    ])
    func probabiliCasiNoti(_ caso: CasoProbabili) async throws {
        let frasi = try FrasiDelServer(prefissi: ["probabili.", "tempo."])
        let adesso = try #require(Quando.data(caso.adesso), "«\(caso.adesso)» non è una data")
        let oggi = try await leggi("/api/oggi", da: try demo("oggi", adesso: adesso), come: Oggi.self)
        let p = try #require(oggi.probabili?.valore, "\(caso.adesso): Oggi non dice quando sono uscite le probabili")
        let eta = try frasi.frase("tempo.ore_fa.other", ["n": "\(caso.minuti / 60)"])
        #expect(p.minutiFa == caso.minuti)
        #expect(p.eta == eta)
        #expect(p.testo == (try frasi.frase(caso.ieri ? "probabili.ieri" : "probabili.oggi", ["ora": caso.ora])))
        #expect(p.vecchie == true)
        let tempo = try frasi.frase("tempo.ore.other", ["n": "\(caso.oreAllaScadenza)"])
        #expect(p.avviso == (try frasi.frase("probabili.vecchie", ["eta": eta, "tempo": tempo])))
    }
}
