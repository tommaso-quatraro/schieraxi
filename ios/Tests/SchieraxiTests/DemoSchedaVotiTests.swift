import Foundation
import Testing
@testable import Schieraxi

/// La scheda del giocatore della demo torna come quella del server (#944, punto 2): ogni fantavoto è il voto con i bonus e i malus
/// della sua giornata e le regole della demo (`punteggio.fantavoto`), la stagione è la somma delle giornate (`scheda` di
/// fanta/scheda.py: presenze, media voto, fantamedia, gol, assist, cartellini) e il rendimento viene da gol e assist rispetto agli
/// attesi. Prima la linea dei voti di Marténi era piatta a 5,5 con «media voto 6,36», e un fantavoto stava sotto il voto con 0
/// cartellini. Dati inventati: quelli di `LegaDemo.swift` e `DatiDemo.swift`.
struct DemoSchedaVotiTests {
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)
    static let demo = FinteServer.demoFissata(adesso: adesso)

    /// Tutta la mia rosa, uno svincolato e uno di un'altra squadra.
    static var ids: [Int] { LegaDemo.miaRosa.map(\.id) + [203, 301] }

    private func oggetto(_ percorso: String) async throws -> [String: Any] {
        let dati = try await Self.demo.richiesta("GET", percorso, corpo: nil)
        return try #require(try JSONSerialization.jsonObject(with: dati) as? [String: Any], "\(percorso) non è un oggetto JSON")
    }

    private func numero(_ riga: [String: Any], _ chiave: String) -> Double {
        (riga[chiave] as? NSNumber)?.doubleValue ?? 0
    }

    /// Il numero letto è il conto esatto arrotondato a due cifre, come lo scrive il server: dista al più mezzo centesimo. Non
    /// `==` con l'arrotondamento rifatto qui: `JSONSerialization` legge «0.07» come numero decimale e `doubleValue` si scosta di
    /// qualche miliardesimo (0.07000000000000003, corsa 45951928006), e vicino a un mezzo centesimo l'arrotondamento può cambiare.
    private func dueCifreDi(_ letto: Double, _ esatto: Double) -> Bool { abs(letto - esatto) <= 0.0051 }

    /// Il fantavoto di una giornata come `punteggio.fantavoto` del server, con i bonus delle regole della demo. Nil senza voto.
    private func fantavoto(_ riga: [String: Any], ruolo: String, bonus: [String: Any]) -> Double? {
        guard let voto = (riga["voto"] as? NSNumber)?.doubleValue else { return nil }
        func b(_ chiave: String) -> Double { (bonus[chiave] as? NSNumber)?.doubleValue ?? 0 }
        let golRuolo = ((bonus["gol"] as? [String: Any])?[ruolo] as? NSNumber)?.doubleValue ?? 0
        var fv = voto + numero(riga, "gol") * golRuolo + numero(riga, "rig_segnati") * b("rigore_segnato")
            + numero(riga, "assist") * b("assist") + numero(riga, "rig_parati") * b("rigore_parato")
            + numero(riga, "rig_sbagliati") * b("rigore_sbagliato") + numero(riga, "autogol") * b("autogol")
            + numero(riga, "ammonizioni") * b("ammonizione") + numero(riga, "espulsioni") * b("espulsione")
        if ruolo == "P" {
            let subiti = numero(riga, "gol_subiti")
            fv += subiti * b("gol_subito_portiere") + (subiti == 0 ? b("portiere_imbattuto") : 0)
        }
        return fv
    }

    @Test("Ogni fantavoto è il voto con i bonus e i malus della giornata, con le regole della demo")
    func fantavotiDalVoto() async throws {
        let regole = try await oggetto("/api/regole")
        let bonus = try #require(regole["bonus"] as? [String: Any], "le regole della demo non hanno i bonus")
        for id in Self.ids {
            let s = try await oggetto("/api/giocatore/\(id)")
            let ruolo = try #require((s["calciatore"] as? [String: Any])?["ruolo"] as? String)
            let voti = try #require(s["voti"] as? [[String: Any]], "giocatore \(id): niente voti")
            try #require(!voti.isEmpty, "giocatore \(id): nessuna giornata")
            for riga in voti {
                let g = riga["giornata"] as? Int ?? 0
                let fv = (riga["fv"] as? NSNumber)?.doubleValue
                guard let atteso = fantavoto(riga, ruolo: ruolo, bonus: bonus) else {
                    #expect(fv == nil, "giocatore \(id), giornata \(g): senza voto ma con il fantavoto")
                    continue
                }
                #expect(fv.map { abs($0 - atteso) < 0.005 } == true,
                        "giocatore \(id), giornata \(g): fantavoto \(fv ?? -1), dal voto e dai bonus \(atteso)")
            }
        }
    }

    @Test("La stagione della scheda è la somma delle giornate, come la conta il server")
    func stagioneDalleGiornate() async throws {
        for id in Self.ids {
            let s = try await oggetto("/api/giocatore/\(id)")
            let voti = try #require(s["voti"] as? [[String: Any]])
            let st = try #require(s["stagione"] as? [String: Any], "giocatore \(id): niente stagione")
            let con = voti.filter { $0["voto"] is NSNumber }
            try #require(!con.isEmpty, "giocatore \(id): nessuna giornata con il voto")
            let n = Double(con.count)
            #expect(st["presenze"] as? Int == voti.count, "giocatore \(id): presenze")
            #expect(st["con_voto"] as? Int == con.count, "giocatore \(id): partite con il voto")
            #expect(dueCifreDi(numero(st, "media_voto"), con.reduce(0) { $0 + numero($1, "voto") } / n),
                    "giocatore \(id): la media voto non è quella dei voti")
            #expect(dueCifreDi(numero(st, "fantamedia"), con.reduce(0) { $0 + numero($1, "fv") } / n),
                    "giocatore \(id): la fantamedia non è quella dei fantavoti")
            for chiave in ["gol", "assist", "ammonizioni", "espulsioni", "gol_subiti", "rig_segnati", "rig_parati"] {
                #expect(numero(st, chiave) == voti.reduce(0) { $0 + numero($1, chiave) }, "giocatore \(id): \(chiave)")
            }
            let giocate = st["giornate_giocate_serie_a"] as? Int ?? 0
            #expect(voti.allSatisfy { ($0["giornata"] as? Int ?? 0) <= giocate }, "giocatore \(id): una giornata non ancora giocata")
        }
    }

    @Test("La linea dei voti sale e scende: nessun giocatore ha sempre lo stesso voto")
    func lineaNonPiatta() async throws {
        for id in Self.ids {
            let s = try await oggetto("/api/giocatore/\(id)")
            let voti = try #require(s["voti"] as? [[String: Any]]).compactMap { ($0["voto"] as? NSNumber)?.doubleValue }
            #expect(Set(voti).count >= 3, "giocatore \(id): voti \(voti)")
        }
    }

    /// Revisione della #955: i gol e gli assist attesi non dipendevano dal ruolo, e un portiere come Sorvani mostrava «−2,04 punti a
    /// partita» e «Gol −4,1 rispetto ai gol attesi». Un portiere non ha gol né assist attesi; un difensore ne ha pochi, e i suoi gol
    /// e assist della stagione stanno «in linea con le occasioni» (fra −0,3 e +0,3 punti a partita, la fascia neutra della scheda).
    @Test("Portieri senza gol e assist attesi; difensori in linea con le occasioni che hanno")
    func rendimentoDiPortieriEDifensori() async throws {
        let ruoli = LegaDemo.miaRosa.filter { $0.ruolo == "P" || $0.ruolo == "D" }
        try #require(ruoli.contains { $0.ruolo == "P" } && ruoli.contains { $0.ruolo == "D" })
        for c in ruoli {
            let s = try await oggetto("/api/giocatore/\(c.id)")
            let a = try #require(s["avanzate"] as? [String: Any], "\(c.nome): niente statistiche avanzate")
            let r = try #require(s["rendimento"] as? [String: Any], "\(c.nome): niente rendimento")
            let punti = numero(r, "sovra_rendimento")
            #expect(abs(punti) <= 0.3, "\(c.nome) (\(c.ruolo)): \(Formato.conSegno(punti, cifre: 2)) punti a partita")
            if c.ruolo == "P" {
                #expect(numero(a, "xg") == 0 && numero(a, "xa") == 0, "\(c.nome): un portiere con gol o assist attesi")
                #expect(numero(r, "gol_meno_xg") == 0 && numero(r, "assist_meno_xa") == 0, "\(c.nome): rendimento di un portiere")
            }
        }
    }

    @Test("Gol e assist rispetto alle occasioni come li calcola il server, con i gol e gli assist della stagione")
    func rendimentoComeIlServer() async throws {
        let regole = try await oggetto("/api/regole")
        let bonus = try #require(regole["bonus"] as? [String: Any])
        for id in Self.ids {
            let s = try await oggetto("/api/giocatore/\(id)")
            let ruolo = try #require((s["calciatore"] as? [String: Any])?["ruolo"] as? String)
            let st = try #require(s["stagione"] as? [String: Any])
            let a = try #require(s["avanzate"] as? [String: Any], "giocatore \(id): niente statistiche avanzate")
            let r = try #require(s["rendimento"] as? [String: Any], "giocatore \(id): niente rendimento")
            #expect(numero(a, "gol") == numero(st, "gol") && numero(a, "assist") == numero(st, "assist"),
                    "giocatore \(id): gol e assist delle statistiche avanzate diversi dalla stagione")
            // `rendimento` di fanta/scheda.py
            let golRuolo = ((bonus["gol"] as? [String: Any])?[ruolo] as? NSNumber)?.doubleValue ?? 0
            let golMenoXg = numero(a, "gol") - numero(a, "xg")
            let assistMenoXa = numero(a, "assist") - numero(a, "xa")
            let extra = (golRuolo * golMenoXg + numero(bonus, "assist") * assistMenoXa) / numero(st, "con_voto")
            #expect(dueCifreDi(numero(r, "gol_meno_xg"), golMenoXg), "giocatore \(id): gol meno gol attesi")
            #expect(dueCifreDi(numero(r, "assist_meno_xa"), assistMenoXa), "giocatore \(id): assist meno assist attesi")
            #expect(dueCifreDi(numero(r, "sovra_rendimento"), extra), "giocatore \(id): punti a partita")
        }
    }
}
