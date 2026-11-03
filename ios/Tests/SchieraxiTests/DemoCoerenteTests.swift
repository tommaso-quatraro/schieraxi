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

    @Test("Confronto nella formazione: titolare e panchina come in Formazione; Oggi propone chi è avanti da solo")
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
        // «Da fare» di Oggi: il sostituto proposto è chi è avanti nel confronto da solo
        let differenza = try #require(c.differenzaPunti)
        let avanti = differenza > 0 ? c.giocatori[0] : c.giocatori[1]
        let voce = try #require(oggi.daFare?.first { $0.tipo == "dubbio" }, "nella demo manca il dubbio di Oggi")
        #expect(voce.testo == "\(marteni.nome) è in dubbio (\(Formato.percento(marteni.pVoto))% di giocare). Meglio \(avanti.nome).")
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
        let comincia = trovati.filter { semplice($0.nome).hasPrefix("ma") }.count
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
}
