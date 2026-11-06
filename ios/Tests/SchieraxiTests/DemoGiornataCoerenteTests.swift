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

    // MARK: - Punti attesi

    @Test("La formazione salvata ha gli stessi punti attesi in Formazione, in Oggi prima, in corso e a giornata finita, e nei widget")
    func stessiPuntiAttesi() async throws {
        let consigliata = try await leggi("/api/formazione", da: try demo("oggi"), come: Formazione.self)
        let attesi = Formato.punti(consigliata.punteggioAtteso)

        // Formazione con la scelta salvata, prima e dopo la scadenza: l'app chiede al server quanto vale (`valuta`)
        for schermata in ["formazione-salvata", "formazione-chiusa"] {
            let s = try demo(schermata)
            let scelta = try await oggetto("/api/scelta", da: s)
            let titolari = try #require(scelta["titolari"] as? [Int], "\(schermata): nessuna scelta salvata")
            // la scelta salvata della demo sono gli undici della consigliata («Salva questa»): stessi punti, differenza zero
            #expect(Set(titolari) == Set(consigliata.titolari.map(\.id)), "\(schermata): la scelta salvata non è la consigliata")
            let corpo = try JSONEncoder().encode(RichiestaValutazione(titolari: titolari, salva: false, giornata: consigliata.giornata))
            let v: ValutazioneManuale = try Decodifica.decodifica(try await s.richiesta("POST", "/api/formazione/valuta", corpo: corpo))
            #expect(Formato.punti(v.punteggioAtteso) == attesi, "\(schermata): \(Formato.punti(v.punteggioAtteso)) punti attesi, la consigliata \(attesi)")
            #expect(v.modulo == consigliata.modulo, "\(schermata): modulo \(v.modulo), la consigliata \(consigliata.modulo)")
            #expect(abs(v.differenza ?? .nan) < 0.05, "\(schermata): \(v.differenza ?? .nan) rispetto alla consigliata con gli stessi undici")
            #expect(Formato.punti(v.consigliata) == attesi, "\(schermata): la consigliata vale \(v.consigliata ?? .nan)")
            #expect(Formato.punti(v.consigliataStessoModulo) == attesi)
        }

        // Oggi prima della scadenza: «La tua scelta»
        let oggi = try await leggi("/api/oggi", da: try demo("oggi"), come: Oggi.self)
        #expect(oggi.formazione?.tuaScelta == true, "Oggi non dice che la formazione è la tua scelta")
        #expect(Formato.punti(oggi.formazione?.punteggioAtteso) == attesi, "Oggi: \(oggi.formazione?.punteggioAtteso ?? .nan), Formazione \(attesi)")

        // Oggi a giornata in corso: «attesi prima» è la stessa formazione
        let inCorso = try await leggi("/api/oggi", da: try demo("oggi-in-corso"), come: Oggi.self)
        #expect(inCorso.faseGiornata == .inCorso)
        #expect(Formato.punti(inCorso.formazione?.punteggioAtteso) == attesi,
                "Oggi in corso, attesi prima: \(inCorso.formazione?.punteggioAtteso ?? .nan), Formazione \(attesi)")

        // Oggi a giornata finita (anche con un recupero da giocare): i punti attesi restano quelli, i punti fatti sono un'altra cosa
        for schermata in ["oggi-finita", "oggi-finita-recupero"] {
            let finita = try await leggi("/api/oggi", da: try demo(schermata), come: Oggi.self)
            let r = try #require(finita.riepilogoGiornata, "\(schermata): manca «Com'è andata»")
            #expect(r.formazioneDi == "tua")
            #expect(Formato.punti(r.puntiAttesi) == attesi, "\(schermata): \(r.puntiAttesi ?? .nan) punti attesi, Formazione \(attesi)")
            if let c = r.consigliata {
                // nel Diario la consigliata è la stessa formazione che hai salvato: stessi punti attesi e stessi punti fatti
                #expect(Formato.punti(c.puntiAttesi) == attesi, "\(schermata): la consigliata vale \(c.puntiAttesi ?? .nan)")
                #expect(c.puntiFatti == r.puntiFatti, "\(schermata): con gli stessi undici la consigliata fa \(c.puntiFatti ?? .nan), tu \(r.puntiFatti ?? .nan)")
            }
        }

        // i widget (la galleria `AnteprimaWidget` legge la stessa lega): stessi punti prima, durante e dopo
        for fase in [LegaDemo.Fase.prima, .inCorso] {
            #expect(try Formato.punti(widget(fase).formazione?.puntiAttesi) == attesi, "widget \(fase): punti attesi diversi dall'app")
        }
        #expect(try Formato.punti(widget(.finita).faseGiornata.riepilogo?.puntiAttesi) == attesi, "widget a giornata finita: punti attesi diversi dall'app")
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

        // l'avviso: lette da almeno 6 ore con la formazione che si chiude entro un giorno
        let scadenza = try #require(Quando.data(oggi.scadenza), "Oggi non ha la scadenza")
        let oreMancanti = (scadenza.timeIntervalSince(adesso) / 360).rounded() / 10
        let vecchie = oreMancanti > 0 && oreMancanti <= 24 && minuti >= 6 * 60
        #expect(p.vecchie == vecchie, "dopo \(dopoOre) ore: vecchie \(p.vecchie ?? false), lette da \(minuti) minuti e la scadenza fra \(oreMancanti) ore")
        if vecchie {
            let n = max(1, Int(oreMancanti.rounded(.toNearestOrEven)))
            let tempo = try frasi.frase("tempo.ore.\(n == 1 ? "one" : "other")", ["n": "\(n)"])
            #expect(p.avviso == (try frasi.frase("probabili.vecchie", ["eta": eta, "tempo": tempo])), "dopo \(dopoOre) ore: «\(p.avviso ?? "")»")
        }

        // Stato dei dati: le stesse probabili, lette alla stessa ora
        let stato = try await oggetto("/api/stato-dati", da: s)
        let raccolta = ((stato["probabili"] as? [[String: Any]]) ?? []).first { $0["giornata"] as? Int == oggi.giornata }
        #expect(Quando.data(raccolta?["rilevato"] as? String) == quando, "Stato dei dati: probabili rilevate «\(raccolta?["rilevato"] ?? "–")», Oggi \(letto)")
        let aggiornamento = ((stato["aggiornamenti"] as? [[String: Any]]) ?? []).first { $0["cosa"] as? String == "probabili formazioni" }
        #expect(Quando.data(aggiornamento?["quando"] as? String) == quando, "Stato dei dati: probabili aggiornate «\(aggiornamento?["quando"] ?? "–")», Oggi \(letto)")
    }
}
