import Foundation
import Testing
@testable import Schieraxi

/// I dati della demo (foto della documentazione e «Prova con dati di esempio») sono coerenti tra loro e con i conti del server
/// (#246): punti attesi = gioca × fantavoto atteso, il confronto dice chi è avanti con i numeri delle barre, i crediti dopo uno
/// svincolo tolgono il costo, i Seguiti dell'app sono quelli del widget, ogni partita ha il suo orario, la ricerca filtra davvero.
/// Tutto si costruisce nello stesso istante fisso, così ogni corsa dà lo stesso risultato.
@Suite("Demo: numeri coerenti tra loro e con i conti veri")
struct DemoCoerenteTests {
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)
    static let demo = FinteServer.demoFissata(adesso: adesso)

    private func dati(_ percorso: String) async throws -> Data {
        try await Self.demo.richiesta("GET", percorso, corpo: nil)
    }

    private func leggi<T: Decodable>(_ percorso: String, come tipo: T.Type) async throws -> T {
        try Decodifica.decodifica(try await dati(percorso))
    }

    private func oggetto(_ percorso: String) async throws -> [String: Any] {
        let d = try await dati(percorso)
        return try #require(try JSONSerialization.jsonObject(with: d) as? [String: Any], "\(percorso) non è un oggetto JSON")
    }

    private func widget() throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: Self.adesso)), "il riassunto dei widget della demo non si legge")
    }

    /// Il nome come lo confronta la ricerca: minuscolo e senza accenti.
    private func semplice(_ nome: String) -> String {
        nome.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: nil).lowercased()
    }

    // MARK: - Punti attesi e confronto

    @Test("Punti attesi = probabilità di giocare × fantavoto atteso, come li conta il server")
    func puntiAttesiComeIlServer() async throws {
        let f = try await leggi("/api/formazione", come: Formazione.self)
        for g in f.titolari + f.panchina {
            let p = try #require(g.pVoto), fv = try #require(g.fvAtteso), punti = try #require(g.puntiAttesi)
            #expect(abs(punti - p * fv) < 0.01, "\(g.nome): punti attesi \(punti), ma gioca \(p) × fantavoto \(fv) fa \(p * fv)")
        }
        let somma = f.titolari.compactMap(\.puntiAttesi).reduce(0, +)
        #expect(abs(f.punteggioAtteso - somma) < 0.05, "la formazione vale \(f.punteggioAtteso), i titolari sommati \(somma)")
    }

    @Test("I migliori di Oggi sono i 3 titolari con più punti attesi, come li manda il server")
    func miglioriComeIlServer() async throws {
        let f = try await leggi("/api/formazione", come: Formazione.self)
        let oggi = try await leggi("/api/oggi", come: Oggi.self)
        // `migliori` di fanta/gestione.py: i titolari ordinati per punti attesi, i primi 3
        let attesi = f.titolari.sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }.prefix(3).map(\.id)
        #expect(oggi.migliori?.map(\.id) == Array(attesi))
    }

    @Test("Confronto: le cause sommate danno la differenza dei punti attesi e la frase dice chi è avanti, con i numeri delle barre",
          arguments: zip([120, 121, 113], [123, 125, 117]))
    func confrontoComeLeBarre(a: Int, b: Int) async throws {
        let f = try await leggi("/api/formazione", come: Formazione.self)
        let c = try await leggi("/api/confronto?a=\(a)&b=\(b)&livello=0&modulo=\(f.modulo)", come: Confronto.self)
        #expect(c.giocatori.map(\.id) == [a, b], "il confronto è tra i due giocatori chiesti")
        try #require(c.giocatori.count == 2)
        // gli stessi numeri della Formazione
        for g in c.giocatori {
            let s = try #require(f.schede?[String(g.id)], "\(g.nome) non è nelle schede della Formazione")
            #expect(g.puntiAttesi == s.puntiAttesi, "\(g.nome): punti attesi diversi dalla Formazione")
            #expect(g.pVoto == s.pVoto, "\(g.nome): gioca diverso dalla Formazione")
            #expect(g.fvAtteso == s.fvAtteso, "\(g.nome): fantavoto atteso diverso dalla Formazione")
        }
        let differenza = try #require(c.differenzaPunti)
        let somma = c.fattori.map(\.effetto).reduce(0, +)
        #expect(abs(somma - differenza) < 0.02, "le barre sommano \(somma), la differenza dei punti attesi è \(differenza)")
        let x = c.giocatori[0], y = c.giocatori[1]
        let avanti = differenza > 0 ? x : y, dietro = differenza > 0 ? y : x
        let perche = try #require(c.perche)
        #expect(perche.hasPrefix("\(avanti.nome) è avanti di \(Formato.punti(abs(differenza))) punti attesi su \(dietro.nome)"),
                "«\(perche)»: avanti c'è \(avanti.nome)")
        if perche.contains("gioca di più") {
            #expect(perche.contains("gioca di più (\(Formato.percento(avanti.pVoto))% contro \(Formato.percento(dietro.pVoto))%"),
                    "«\(perche)»: le percentuali non sono quelle dei due")
        }
        #expect(!perche.contains("ha più probabilità di giocare"), "frase fissa: «\(perche)»")
    }

    @Test("Confronto nella formazione: titolare e panchina come in Formazione; Oggi dice la stessa cosa del confronto (#305)")
    func confrontoComeFormazioneEOggi() async throws {
        let f = try await leggi("/api/formazione", come: Formazione.self)
        let oggi = try await leggi("/api/oggi", come: Oggi.self)
        // Marténi (titolare in dubbio) e Lemão (in panchina): la coppia della foto `formazione-confronto` e del «Da fare» di Oggi
        let marteni = try #require(f.titolari.first { $0.id == 120 }, "Marténi non è titolare nella Formazione della demo")
        let n = try #require(f.panchina.firstIndex { $0.id == 123 }, "Lemão non è in panchina nella Formazione della demo") + 1
        let c = try await leggi("/api/confronto?a=120&b=123&livello=0&modulo=\(f.modulo)", come: Confronto.self)
        try #require(c.giocatori.count == 2)
        let formazione = try #require(c.formazione, "manca il riquadro «Nella formazione»")
        #expect(formazione.modulo == f.modulo)
        #expect(formazione.postoA == "titolare")
        #expect(formazione.postoB == "panchina \(n)")
        // come il server: si schiera il titolare della formazione, e il testo dice perché
        #expect(c.consigliato == 120)
        #expect(c.schierato?.id == 120)
        let testo = formazione.testo ?? ""
        let nonGioca = 100 - Formato.percento(marteni.pVoto)
        #expect(testo.hasPrefix("Il sistema schiera \(marteni.nome) come titolare."), "«\(testo)»")
        #expect(testo.contains("Se \(marteni.nome) non prende voto (\(nonGioca)% di probabilità), al suo posto può entrare Renato Lemão (panchina \(n))."),
                "«\(testo)»")
        // «Da fare» di Oggi segue la regola del confronto (`_dubbi` di fanta/da_fare.py, #268): il confronto schiera Marténi, quindi
        // Oggi non propone il cambio ma dice chi entra dalla panchina se lui non gioca (la prima riserva del suo ruolo) e apre la formazione
        let riserva = try #require(f.panchina.first { $0.ruolo == marteni.ruolo }, "in panchina non c'è nessuno del ruolo di Marténi")
        let voce = try #require(oggi.daFare?.first { $0.tipo == "dubbio" }, "nella demo manca il dubbio di Oggi")
        #expect(voce.testo == "\(marteni.nome) è in dubbio (\(Formato.percento(marteni.pVoto))% di giocare) ma resta titolare: se non gioca entra \(riserva.nome) dalla panchina.")
        #expect(!voce.testo.contains("Meglio"), "Oggi propone un cambio che il confronto non fa: «\(voce.testo)»")
        #expect(voce.azione == "Apri la formazione")
        #expect(voce.destinazione?.link == "schieraxi://formazione")
    }

    // MARK: - Crediti

    @Test("Cambi consigliati: crediti dopo = crediti + rimborso − costo, e il rimborso è la quota delle regole del prezzo pagato")
    func creditiDopo() async throws {
        let m = try await leggi("/api/mercato", come: Mercato.self)
        let rosa = try await leggi("/api/rosa", come: Rosa.self)
        let regole = try await oggetto("/api/regole")
        let quota = try #require(regole["rimborso_svincolo"] as? Double)
        let crediti = try #require(m.creditiResidui)
        try #require(!m.proposte.isEmpty, "nella demo non ci sono cambi consigliati")
        for p in m.proposte {
            let costo = try #require(rosa.giocatori.first { $0.id == p.esce.id }?.costo, "\(p.esce.nome) non è nella rosa")
            let rimborso = try #require(p.rimborso, "\(p.esce.nome): manca il rimborso")
            #expect(rimborso == (costo * quota).rounded(.toNearestOrEven), "\(p.esce.nome): pagato \(costo), rimborso \(rimborso)")
            let costoEntra = try #require(p.entra.quotazione)
            #expect(p.creditiDopo == crediti + rimborso - costoEntra,
                    "\(p.entra.nome): \(crediti) + \(rimborso) − \(costoEntra) non fa \(p.creditiDopo ?? -1)")
            #expect(p.fattibile == ((p.creditiDopo ?? -1) >= 0))
        }
        #expect(m.proposte.map(\.guadagno) == m.proposte.map(\.guadagno).sorted(by: >), "i cambi vanno dal più conveniente")
    }

    // MARK: - Seguiti e orari

    @Test("Seguiti: il giocatore del widget «Giocatore seguito» è tra i Seguiti dell'app, con lo stesso fantavoto atteso")
    func seguitiComeIlWidget() async throws {
        let app = try await leggi("/api/osservati", come: ElencoGiocatori.self).giocatori
        let w = try widget()
        let nelWidget = w.osservati ?? []
        #expect(nelWidget.map(\.id) == app.map(\.id), "i seguiti del widget non sono quelli dell'app")
        // la galleria dei widget mostra Marténi (`AnteprimaWidget/DatiGalleria.swift`, `scelto: 120`): dev'essere un seguito
        #expect(app.contains { $0.id == 120 }, "Marténi è nel widget «Giocatore seguito» ma non tra i Seguiti dell'app")
        #expect(nelWidget.contains { $0.id == 120 })
        for g in app {
            let s = try #require(nelWidget.first { $0.id == g.id }, "\(g.nome) non è tra i seguiti del widget")
            #expect(s.fvAtteso == g.fvAtteso, "\(g.nome): fantavoto atteso diverso tra widget e app")
            #expect(s.pVoto == g.pVoto, "\(g.nome): gioca diverso tra widget e app")
            #expect((s.dubbio ?? false) == (g.dubbio ?? false), "\(g.nome): in dubbio solo da una parte")
        }
        let scelto = try #require(w.osservato(120))
        #expect(scelto.rigaVotoAtteso?.first == "Fantavoto atteso \(Formato.punti(scelto.fvAtteso))")
        #expect(scelto.statoOGioca == "In dubbio · gioca 62%")
    }

    @Test("Ogni giocatore ha l'orario della partita della sua squadra, lo stesso di Oggi")
    func orariComeOggi() async throws {
        let oggi = try await leggi("/api/oggi", come: Oggi.self)
        var ora: [String: String] = [:]
        for p in oggi.partite ?? [] {
            ora[p.casa] = p.data
            ora[p.trasferta] = p.data
        }
        try #require(Set(ora.values).count > 1, "nella demo tutte le partite hanno lo stesso orario")
        let seguiti = try await leggi("/api/osservati", come: ElencoGiocatori.self).giocatori
        let f = try await leggi("/api/formazione", come: Formazione.self)
        let scheda = try await leggi("/api/giocatore/203", come: SchedaGiocatore.self)
        let previsione = try #require(scheda.previsione, "la scheda di Retalli non ha la previsione")
        for g in seguiti + f.titolari + f.panchina + [previsione] {
            #expect(g.dataPartita == ora[g.squadra ?? ""], "\(g.nome) (\(g.squadra ?? "?")): \(g.dataPartita ?? "–") invece di \(ora[g.squadra ?? ""] ?? "–")")
        }
        // il widget scrive le stesse ore dei Seguiti dell'app
        for s in try widget().osservati ?? [] {
            #expect(s.dataPartita == seguiti.first { $0.id == s.id }?.dataPartita, "\(s.nome): ora diversa tra widget e app")
        }
    }

    // MARK: - Ricerca ed elenco

    @Test("Ricerca: solo i nomi che contengono il testo, senza badare ad accenti e maiuscole, prima chi comincia così")
    func ricercaFiltra() async throws {
        let trovati = try await leggi("/api/giocatori?limite=60&q=ma", come: [GiocatoreBreve].self)
        let attesi = LegaDemo.tutti.filter { semplice($0.nome).contains("ma") }
        try #require(!attesi.isEmpty)
        #expect(Set(trovati.map(\.id)) == Set(attesi.map(\.id)), "risultati: \(trovati.map(\.nome))")
        #expect(!trovati.contains { $0.nome == "Aldo Pinarotti" }, "«Aldo Pinarotti» non contiene «ma»")
        let comincia = trovati.count(where: { semplice($0.nome).hasPrefix("ma") })
        #expect(trovati.prefix(comincia).allSatisfy { semplice($0.nome).hasPrefix("ma") }, "prima chi comincia con «ma»")

        let pochi = try await leggi("/api/giocatori?limite=6&q=ma", come: [GiocatoreBreve].self)
        #expect(pochi.count == min(6, attesi.count))
        let accenti = try await leggi("/api/giocatori?limite=25&q=\(IndirizzoServer.codifica("lemao"))", come: [GiocatoreBreve].self)
        #expect(accenti.map(\.id) == [123], "«lemao» trova Renato Lemão")
        let maiuscole = try await leggi("/api/giocatori?limite=25&q=\(IndirizzoServer.codifica("MARTÉNI"))", come: [GiocatoreBreve].self)
        #expect(maiuscole.map(\.id) == [120], "«MARTÉNI» trova Leonel Marténi")
        let nessuno = try await leggi("/api/giocatori?limite=60&q=xyzw", come: [GiocatoreBreve].self)
        #expect(nessuno.isEmpty)
    }

    @Test("Elenco dei giocatori: con «Solo svincolati» spento ci sono anche le rose, con la loro squadra, dal più atteso")
    func elencoLargo() async throws {
        let tutti = try await leggi("/api/classifica?liberi=false&limite=800", come: ElencoGiocatori.self).giocatori
        #expect(tutti.first { $0.id == 120 }?.proprietario == LegaDemo.nomeMia, "Marténi manca o non è della mia squadra")
        #expect(tutti.allSatisfy { ($0.pVoto ?? 0) >= 0.2 }, "chi non gioca non sta nell'elenco della giornata")
        let punti = tutti.compactMap(\.puntiAttesi)
        #expect(punti == punti.sorted(by: >), "l'elenco va dal più atteso")
        let liberi = try await leggi("/api/classifica?limite=60&liberi=true", come: ElencoGiocatori.self).giocatori
        #expect(!liberi.isEmpty)
        #expect(liberi.allSatisfy { $0.proprietario == nil }, "«Solo svincolati» mostra un giocatore di una rosa")
        // le righe della ricerca prendono i numeri dall'elenco largo: chi gioca nella mia rosa c'è
        let miei = LegaDemo.miaRosa.filter { !$0.assente }.map(\.id)
        #expect(Set(miei).isSubset(of: Set(tutti.map(\.id))))
    }

    // MARK: - Calendario (#303)

    @Test("Calendario a coppie: ogni squadra un avversario per giornata, che ha lei, in casa e fuori opposti; la prima giornata è Oggi")
    func calendarioACoppie() async throws {
        let c = try await leggi("/api/calendario", come: Calendario.self)
        let oggi = try await leggi("/api/oggi", come: Oggi.self)
        let partiteOggi = try #require(oggi.partite, "Oggi non ha le partite del turno")
        let prima = try #require(c.giornate.first, "il calendario non ha giornate")
        #expect(prima == oggi.giornata, "il calendario parte dalla G\(prima), Oggi è la giornata \(oggi.giornata ?? -1)")
        // come il server: tutte le squadre del campionato, ognuna con una partita per giornata
        let squadre = Set(partiteOggi.flatMap { [$0.casa, $0.trasferta] })
        #expect(Set(c.squadre.map(\.squadra)) == squadre, "nel calendario mancano squadre o ce ne sono in più")
        var righe: [String: SquadraCalendario] = [:]
        for s in c.squadre { righe[s.squadra] = s }
        var coppie: Set<String> = [], senzaGiornata: Set<String> = []
        for s in c.squadre {
            #expect(s.partite.map(\.giornata) == c.giornate, "\(s.squadra): una partita per giornata, nell'ordine")
            for p in s.partite {
                #expect(p.avversario != s.squadra, "G\(p.giornata): \(s.squadra) gioca contro sé stessa")
                let altra = try #require(righe[p.avversario]?.partite.first { $0.giornata == p.giornata },
                                         "G\(p.giornata): \(p.avversario) non c'è nel calendario")
                #expect(altra.avversario == s.squadra,
                        "G\(p.giornata): \(s.squadra) contro \(p.avversario), ma \(p.avversario) contro \(altra.avversario)")
                #expect(altra.inCasa == p.inCasa.map { !$0 }, "G\(p.giornata): \(s.squadra) e \(p.avversario) tutte e due in casa o fuori")
                let coppia = [s.squadra, p.avversario].sorted().joined(separator: "-")
                coppie.insert("G\(p.giornata) \(coppia)")
                senzaGiornata.insert(coppia)
            }
        }
        // la stessa partita non torna due volte nelle cinque giornate
        #expect(senzaGiornata.count == coppie.count, "due squadre si incontrano più di una volta")
        // la prima giornata sono le partite di Oggi, con la squadra di casa
        for m in partiteOggi {
            let p = righe[m.casa]?.partite.first { $0.giornata == prima }
            #expect(p?.avversario == m.trasferta && p?.inCasa == true,
                    "Oggi \(m.casa)–\(m.trasferta), il calendario: \(m.casa) \(p?.inCasa == true ? "vs" : "@") \(p?.avversario ?? "?")")
        }
        // come il server: la difficoltà della prima giornata è quella delle schede dei giocatori (stessi colori ovunque)
        let f = try await leggi("/api/formazione", come: Formazione.self)
        for g in (f.schede ?? [:]).values {
            guard let squadra = g.squadra, let d = g.difficolta else { continue }
            #expect(righe[squadra]?.partite.first { $0.giornata == prima }?.difficolta == d,
                    "\(g.nome) (\(squadra)): difficoltà \(d) nella scheda, diversa nel calendario")
        }
    }

    // MARK: - Rose e movimenti (#303)

    /// Le rose della lega come le mostra l'app: Squadre, poi la rosa di ognuna.
    private func roseDellaLega() async throws -> [String: Rosa] {
        let squadre = try await leggi("/api/squadre", come: [SquadraLega].self)
        var rose: [String: Rosa] = [:]
        for s in squadre {
            rose[s.nome] = try await leggi("/api/rosa?squadra=" + IndirizzoServer.codifica(s.nome), come: Rosa.self)
        }
        return rose
    }

    @Test("Rose: ogni giocatore in una rosa sola, la stessa che scrive l'Elenco; i posti delle regole; gli scambi con chi li ha")
    func roseSenzaDoppioni() async throws {
        let squadre = try await leggi("/api/squadre", come: [SquadraLega].self)
        let rose = try await roseDellaLega()
        let regole = try await oggetto("/api/regole")
        let posti = try #require(regole["rosa"] as? [String: Int], "le regole della demo non hanno i posti della rosa")
        var diChi: [Int: String] = [:]
        for s in squadre {
            let rosa = try #require(rose[s.nome], "manca la rosa di \(s.nome)")
            #expect(rosa.giocatori.count == s.giocatori, "\(s.nome): Squadre dice \(s.giocatori ?? -1) giocatori, la rosa ne ha \(rosa.giocatori.count)")
            #expect(rosa.creditiResidui == s.creditiResidui, "\(s.nome): crediti diversi tra Squadre e la rosa")
            for (ruolo, n) in posti {
                #expect(rosa.giocatori.count(where: { $0.ruolo == ruolo }) == n, "\(s.nome): i giocatori del ruolo \(ruolo) non sono \(n)")
            }
            for g in rosa.giocatori {
                let id = try #require(g.id, "\(g.nome) senza id")
                if let altra = diChi[id] { Issue.record("\(g.nome) è nella rosa di \(altra) e in quella di \(s.nome)") }
                diChi[id] = s.nome
            }
        }
        // l'Elenco dei giocatori scrive la squadra che ce l'ha in rosa (nessuna per gli svincolati), e così la scheda
        let elenco = try await leggi("/api/classifica?liberi=false&limite=800", come: ElencoGiocatori.self).giocatori
        try #require(!elenco.isEmpty)
        for g in elenco {
            #expect(g.proprietario == diChi[g.id], "\(g.nome): l'Elenco dice «\(g.proprietario ?? "svincolato")», la rosa «\(diChi[g.id] ?? "nessuna")»")
        }
        for id in [301, 302, 204, 203] {
            let scheda = try await leggi("/api/giocatore/\(id)", come: SchedaGiocatore.self)
            #expect(scheda.proprietario == diChi[id], "\(scheda.calciatore.nome): la scheda dice «\(scheda.proprietario ?? "svincolato")»")
        }
        // gli scambi proposti: do dalla mia rosa, ricevo dalla rosa dell'altra squadra
        let scambi = try await leggi("/api/scambi/proposte", come: ProposteScambi.self).proposte
        for p in scambi {
            for g in p.`do` { #expect(diChi[g.id] == LegaDemo.nomeMia, "scambio con \(p.altra): do \(g.nome), che è di \(diChi[g.id] ?? "nessuno")") }
            for g in p.ricevo { #expect(diChi[g.id] == p.altra, "scambio con \(p.altra): ricevo \(g.nome), che è di \(diChi[g.id] ?? "nessuno")") }
        }
    }

    @Test("Movimenti: chi è stato preso è nella rosa di chi l'ha preso e non è svincolato; chi è stato tagliato è libero; i crediti dopo")
    func movimentiComeLeRose() async throws {
        let movimenti = try await leggi("/api/movimenti?limite=30", come: [Differenze].self)
        let rose = try await roseDellaLega()
        let squadre = try await leggi("/api/squadre", come: [SquadraLega].self)
        let elenco = try await leggi("/api/classifica?liberi=false&limite=800", come: ElencoGiocatori.self).giocatori
        let liberi = Set(try await leggi("/api/classifica?liberi=true&limite=800", come: ElencoGiocatori.self).giocatori.map(\.id))
        // dal movimento più vecchio al più nuovo: dove deve stare ogni giocatore nominato, e i crediti di ogni squadra
        var squadraDi: [Int: String] = [:]
        var tagliati: Set<Int> = []
        var crediti: [String: Double] = [:]
        for m in movimenti.sorted(by: { ($0.quando ?? "") < ($1.quando ?? "") }) {
            func prende(_ id: Int?, _ squadra: String) { guard let id else { return }; squadraDi[id] = squadra; tagliati.remove(id) }
            for s in m.scambi ?? [] where s.squadre.count == 2 {
                for g in s.daA { prende(g.id, s.squadre[1]) }
                for g in s.daB { prende(g.id, s.squadre[0]) }
            }
            for gruppo in m.svincolatiPresi ?? [] { for g in gruppo.giocatori { prende(g.id, gruppo.squadra) } }
            for gruppo in m.tagliati ?? [] {
                for g in gruppo.giocatori { if let id = g.id { squadraDi[id] = nil; tagliati.insert(id) } }
            }
            for c in m.crediti ?? [] { crediti[c.squadra] = c.dopo }
        }
        try #require(!squadraDi.isEmpty, "nella demo non ci sono movimenti")
        for (id, squadra) in squadraDi {
            let nome = LegaDemo.calciatore(id).nome
            let rosa = try #require(rose[squadra], "\(squadra) non è una squadra della lega")
            #expect(rosa.giocatori.contains { $0.id == id }, "Movimenti: \(nome) va a \(squadra), ma non è nella sua rosa")
            #expect(!liberi.contains(id), "Movimenti: \(nome) va a \(squadra), ma l'Elenco lo dà svincolato")
            #expect(elenco.first { $0.id == id }?.proprietario == squadra, "Movimenti: \(nome) va a \(squadra), l'Elenco dice altro")
        }
        for id in tagliati {
            #expect(!rose.values.contains { $0.giocatori.contains { $0.id == id } }, "\(LegaDemo.calciatore(id).nome) è stato tagliato ma è in una rosa")
        }
        for s in squadre {
            if let dopo = crediti[s.nome] { #expect(s.creditiResidui == dopo, "\(s.nome): dopo i movimenti ha \(dopo) crediti, Squadre dice altro") }
        }
    }

    // MARK: - Probabili, scheda e orari (#303)

    @Test("Probabili: uscite per Oggi, Formazione, widget e Stato dei dati insieme, o per nessuno")
    func probabiliOvunque() async throws {
        let oggi = try await leggi("/api/oggi", come: Oggi.self)
        let f = try await leggi("/api/formazione", come: Formazione.self)
        let stato = try await oggetto("/api/stato-dati")
        let w = try widget()
        let raccolte = ((stato["probabili"] as? [[String: Any]]) ?? []).contains {
            $0["giornata"] as? Int == oggi.giornata && ($0["giocatori"] as? Int ?? 0) > 0
        }
        func parole(_ uscite: Bool?) -> String { uscite == true ? "uscite" : "non uscite" }
        #expect(oggi.conProbabili == raccolte, "Oggi: probabili \(parole(oggi.conProbabili)), Stato dei dati: \(parole(raccolte))")
        #expect(f.conProbabili == raccolte, "Formazione: probabili \(parole(f.conProbabili)), Stato dei dati: \(parole(raccolte))")
        #expect(w.conProbabili == raccolte, "widget: probabili \(parole(w.conProbabili)), Stato dei dati: \(parole(raccolte))")
    }

    @Test("Scheda del giocatore: la giornata con il numero della lega accanto a quello di Serie A, come Oggi")
    func schedaConLaGiornataDellaLega() async throws {
        let oggi = try await leggi("/api/oggi", come: Oggi.self)
        // uno svincolato, uno della mia rosa, uno di un'altra squadra
        for id in [203, 120, 301] {
            let s = try await leggi("/api/giocatore/\(id)", come: SchedaGiocatore.self)
            let p = try #require(s.previsione, "la scheda di \(s.calciatore.nome) non ha la previsione")
            #expect(p.giornata == oggi.giornata, "\(s.calciatore.nome): giornata di Serie A diversa da Oggi")
            #expect(p.giornataLega == oggi.giornataLega, "\(s.calciatore.nome): manca la giornata della lega (Oggi dice \(oggi.giornataLega ?? -1))")
        }
    }

    /// Gli orari dei calci d'inizio di Serie A (ora italiana): nessuna partita a mezzanotte o alle 10:49.
    static let orariDaPartita: Set<String> = ["12:30", "15:00", "18:00", "20:45"]

    /// L'ora («20:45») di una data del server («2026-11-07 20:45»).
    private func ora(_ data: String?) -> String { String((data ?? "").suffix(5)) }

    @Test("Ogni calcio d'inizio cade su un orario da partita, a qualunque ora si apra la demo, anche a giornata in corso (#417)",
          arguments: Array(0..<24))
    func orariDaPartitaVera(dopoOre: Int) throws {
        // anche a minuti dispari: le foto si scattano quando capita
        let adesso = Self.adesso.addingTimeInterval(Double(dopoOre) * 3600 + 7 * 60)
        for fase in [LegaDemo.Fase.prima, .finita] {
            let w = try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: adesso, fase: fase)), "il widget \(fase) non si legge")
            #expect(Self.orariDaPartita.contains(ora(w.primaPartita)), "\(fase), dopo \(dopoOre) ore: la prima partita è alle \(ora(w.primaPartita))")
            #expect((Quando.data(w.primaPartita) ?? .distantPast) > adesso, "\(fase): la prima partita è già cominciata")
            for p in (w.live?.partite ?? []) {
                #expect(Self.orariDaPartita.contains(ora(p.data)), "\(fase), dopo \(dopoOre) ore: \(p.id) alle \(ora(p.data))")
            }
            for g in (w.rosa ?? []) + (w.osservati ?? []) where g.dataPartita != nil {
                #expect(Self.orariDaPartita.contains(ora(g.dataPartita)), "\(fase), dopo \(dopoOre) ore: \(g.nome) gioca alle \(ora(g.dataPartita))")
            }
        }
        // a giornata in corso la demo vive nel suo momento (l'ora dei risultati in diretta), non nell'ora del telefono (#417)
        let w = try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: adesso, fase: .inCorso)), "il widget in corso non si legge")
        let partite = w.live?.partite ?? []
        let momento = try #require(Quando.data(w.live?.aggiornatoIl), "a giornata in corso i risultati in diretta non dicono l'ora")
        try #require(partite.contains { $0.stato != "da_giocare" }, "a giornata in corso nessuna partita è cominciata")
        for p in partite {
            let quando = try #require(p.quando, "\(p.id) senza orario")
            #expect(Self.orariDaPartita.contains(ora(p.data)), "in corso, dopo \(dopoOre) ore: \(p.id) \(p.stato ?? "?") alle \(ora(p.data))")
            if p.stato == "da_giocare" {
                #expect(quando > momento, "\(p.id) è da giocare ma l'orario è passato")
            } else {
                #expect(quando < momento, "\(p.id) è \(p.stato ?? "?") ma comincia dopo")
            }
        }
    }

    // MARK: - Marchio (#303)

    @MainActor
    @Test("La foto del marchio: lo stato vuoto con le parole della pagina Seguiti («seguito», «Segui»)")
    func marchioConISeguiti() {
        #expect(ProvaMarchio.titoloVuoto == "Nessun giocatore seguito")
        #expect(ProvaMarchio.descrizioneVuoto == "Apri la scheda di un giocatore e tocca «Segui».")
    }
}
