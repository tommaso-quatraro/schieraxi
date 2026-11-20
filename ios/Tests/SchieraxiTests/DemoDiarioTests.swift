import Foundation
import Testing
@testable import Schieraxi

/// Il Diario dei dati di prova (modalità demo e fotografie) torna con la testata della demo, «Giornata 8» della lega
/// (Serie A 11: la lega parte dalla giornata 4 di Serie A). Le giornate finite sono la 4, 5, 6 e 7 della lega (Serie A 7-10)
/// e ognuna porta il suo `giornata_lega`, come le manda il server (`elenco` e `scelte_tue` di `fanta/diario.py`).
/// Dati inventati: quelli di `DatiDemo.swift`, tutti della stagione in corso.
struct DemoDiarioTests {

    private func dati(_ percorso: String) async throws -> Data {
        try await FinteServer.demo.richiesta("GET", percorso, corpo: nil)
    }

    private func diario() async throws -> DiarioRisposta {
        try Decodifica.decodifica(try await dati("/api/diario"))
    }

    /// Serie A meno lega nella giornata di Oggi della demo.
    private func scarto() async throws -> Int {
        let oggi: Oggi = try Decodifica.decodifica(try await dati("/api/oggi"))
        let serieA = try #require(oggi.giornata)
        let lega = try #require(oggi.giornataLega)
        #expect(serieA != lega, "se i due numeri coincidono il test non distingue più la lega dalla Serie A")
        return serieA - lega
    }

    @Test("Ogni voce del Diario della demo porta il numero della lega giusto",
          arguments: ["giornate", "precisione.per_giornata", "scelte_tue.per_giornata"])
    func numeroDellaLegaInOgniElenco(_ percorso: String) async throws {
        let scarto = try await scarto()
        var nodo: Any? = try JSONSerialization.jsonObject(with: try await dati("/api/diario"))
        for chiave in percorso.split(separator: ".") { nodo = (nodo as? [String: Any])?[String(chiave)] }
        let voci = try #require(nodo as? [[String: Any]], "nel diario della demo manca «\(percorso)»")
        #expect(!voci.isEmpty, "«\(percorso)» è vuoto")
        for voce in voci {
            let serieA = try #require(voce["giornata"] as? Int, "«\(percorso)»: una voce senza giornata")
            let lega = voce["giornata_lega"] as? Int
            let letta = lega.map { String($0) } ?? "nessuna"
            #expect(lega == serieA - scarto,
                    "«\(percorso)»: la giornata \(serieA) di Serie A è la \(serieA - scarto) della lega, non \(letta)")
            #expect(serieA - scarto >= 1, "«\(percorso)»: la giornata \(serieA) di Serie A è prima che la lega partisse")
        }
    }

    @Test("I titoli delle giornate e «Calcolato su…» dicono i numeri della lega")
    func titoliEPrecisioneConINumeriDellaLega() async throws {
        let d = try await diario()
        #expect((d.giornate ?? []).map(\.titolo) == ["Giornata 7 · 10ª di Serie A", "Giornata 6 · 9ª di Serie A",
                                                    "Giornata 5 · 8ª di Serie A", "Giornata 4 · 7ª di Serie A"])
        let testo = try #require(TestoPrecisione(d.precisione))
        #expect(testo.calcolatoSu == "Calcolato su 4 giornate, dalla Giornata 4 · 7ª di Serie A alla Giornata 7 · 10ª di Serie A.")
    }

    @Test("«In sintesi» è quella che il server calcola dalle giornate con la tua formazione")
    func sintesiComeIlServer() async throws {
        let d = try await diario()
        let s = try #require(d.sintesi)
        // come `sintesi` di fanta/diario.py: solo le giornate in cui hai schierato una tua formazione, medie a un decimale
        let con = (d.giornate ?? []).filter { $0.schierata != nil }
        try #require(!con.isEmpty, "nella demo nessuna giornata ha la tua formazione")
        let tue = con.map { $0.schierata?.reale ?? 0 }
        let consigliate = con.map { $0.consigliata?.reale ?? 0 }
        let attesiTue = con.map { $0.schierata?.atteso ?? 0 }
        let meglioTua = zip(tue, consigliate).filter { $0.0 > $0.1 }.count
        let meglioConsigliata = zip(tue, consigliate).filter { $0.0 < $0.1 }.count
        #expect(s.giornate == con.count)
        #expect(s.puntiSchierata == media(tue))
        #expect(s.puntiConsigliata == media(consigliate))
        #expect(s.attesiSchierata == media(attesiTue))
        #expect(s.meglioTua == meglioTua)
        #expect(s.meglioConsigliata == meglioConsigliata)
    }

    @Test("«Le tue scelte» è quella che il server calcola dalle giornate del Diario")
    func scelteTueComeIlServer() async throws {
        let d = try await diario()
        let s = try #require(d.scelteTue)
        let attese = Self.scelteDelServer(d.giornate ?? [])
        try #require(!attese.isEmpty, "nella demo nessuna giornata ha undici diversi da quelli consigliati")
        let trovate = (s.perGiornata ?? []).map(Scelta.init)
        #expect(trovate == attese, "le righe devono essere le giornate del Diario con undici diversi, dalla più recente")

        let n = attese.count
        let meglioTua = attese.filter { $0.esito == "tua" }.count
        let meglioConsigliata = attese.filter { $0.esito == "consigliata" }.count
        let pari = attese.filter { $0.esito == "pari" }.count
        let somma = attese.compactMap(\.differenza).reduce(0, +)
        let puntiDifferenza = (somma * 10).rounded() / 10
        let percentuale = (100 * Double(meglioTua) / Double(n)).rounded()
        #expect(s.giornate == n)
        #expect(s.meglioTua == meglioTua)
        #expect(s.meglioConsigliata == meglioConsigliata)
        #expect(s.pari == pari)
        #expect(s.puntiDifferenza == puntiDifferenza)
        #expect(s.percentualeTua == percentuale)
        #expect(s.pochiDati == (n < 8), "sotto le 8 giornate il server dice «pochi dati» (POCHI_DATI di fanta/diario.py)")
    }

    @Test("«Fatti e attesi» di ogni giornata è quello che il server calcola dai numeri della tabella (#672)")
    func fattiEAttesiComeIlServer() async throws {
        let voci = try await diario().giornate ?? []
        try #require(!voci.isEmpty, "nel diario della demo non ci sono giornate")
        for v in voci {
            let g = v.giornata ?? 0
            let f = try #require(v.cheConta.formazione, "giornata \(g): manca la formazione che conta")
            let fa = try #require(v.fattiEAttesi, "giornata \(g): manca `fatti_e_attesi`")
            let atteso = try #require(f.atteso), fatti = try #require(f.reale)
            #expect(fa.differenza == Self.unaCifra(fatti - atteso), "giornata \(g): la differenza è fatti meno attesi")
            #expect(fa.testo == Self.fraseScarti(v), "giornata \(g): la frase deve dire i numeri della tabella")
        }
        #expect(voci.contains { $0.fattiEAttesi?.testo != nil }, "la foto deve mostrare la frase in almeno una giornata")
    }

    @Test("Il Diario della demo scrive i giocatori della rosa per cognome, mai con il nome di battesimo (#819: «Leonel» per Marténi)")
    func giocatoriPerCognome() async throws {
        // i nomi di battesimo dei giocatori della demo con nome e cognome («Leonel» di «Leonel Marténi»)
        let battesimi = Set(LegaDemo.tutti.compactMap { p -> String? in
            let parole = p.nome.split(separator: " ")
            return parole.count > 1 ? String(parole[0]) : nil
        })
        try #require(battesimi.contains("Leonel"), "la rosa della demo è cambiata: il test non prova più niente")
        let voci = try await diario().giornate ?? []
        try #require(!voci.isEmpty, "nel diario della demo non ci sono giornate")
        for v in voci {
            let g = v.giornata ?? 0
            let titolari = [v.consigliata, v.schierata, v.automatica].flatMap { $0?.titolari ?? [] }
                + (v.istantanea?.titolari ?? []) + (v.istantanea?.panchina ?? [])
            for t in titolari {
                #expect(!battesimi.contains(t.nome ?? ""), "giornata \(g): «\(t.nome ?? "")» è un nome di battesimo, non un cognome")
            }
            for parola in (v.fattiEAttesi?.testo ?? "").split(whereSeparator: { !$0.isLetter }).map(String.init) {
                #expect(!battesimi.contains(parola), "giornata \(g): nella frase c'è «\(parola)», un nome di battesimo")
            }
        }
        #expect(voci.contains { v in (v.consigliata?.titolari ?? []).contains { $0.nome == "Marténi" } },
                "Marténi, titolare della consigliata, si scrive con il cognome")
    }

    /// Un titolare con il suo scarto dall'atteso, nell'ordine della formazione.
    private struct Scarto {
        let posto: Int
        let nome: String
        let d: Double
    }

    private static func unaCifra(_ x: Double) -> Double { (x * 10).rounded() / 10 }

    /// La frase come la scrive `fatti_e_attesi` di fanta/diario.py: i titolari con almeno un punto in più (o in meno) del loro
    /// fantavoto atteso, al massimo due per parte e dal più lontano; l'atteso è quello mostrato prima della scadenza, se c'è, se no
    /// quello rifatto; chi è senza voto non c'è. Nil se nessuno arriva a un punto.
    private static func fraseScarti(_ v: VoceDiario) -> String? {
        var mostrati: [Int: Double] = [:]
        for x in (v.istantanea?.titolari ?? []) + (v.istantanea?.panchina ?? []) {
            if let id = x.id, let a = x.fvAtteso { mostrati[id] = a }
        }
        let righe = (v.cheConta.formazione?.titolari ?? []).enumerated().compactMap { i, t -> Scarto? in
            guard let id = t.id, let n = v.giocatori?.first(where: { $0.id == id }),
                  let atteso = mostrati[id] ?? n.fvAtteso, let preso = n.fv else { return nil }
            return Scarto(posto: i, nome: t.nome ?? "", d: unaCifra(preso - atteso))
        }
        let meglio = righe.filter { $0.d >= 1 }.sorted { $0.d != $1.d ? $0.d > $1.d : $0.posto < $1.posto }.prefix(2)
        let peggio = righe.filter { $0.d <= -1 }.sorted { $0.d != $1.d ? $0.d < $1.d : $0.posto < $1.posto }.prefix(2)
        func nomi(_ r: ArraySlice<Scarto>) -> String {
            r.map { "\($0.nome) (\(Formato.conSegno($0.d)))" }.joined(separator: " e ")
        }
        switch (meglio.isEmpty, peggio.isEmpty) {
        case (false, false): return "Meglio del previsto: \(nomi(meglio)). Peggio: \(nomi(peggio))."
        case (false, true): return "Meglio del previsto: \(nomi(meglio))."
        case (true, false): return "Peggio del previsto: \(nomi(peggio))."
        case (true, true): return nil
        }
    }

    /// Una riga di «Le tue scelte», da confrontare tutta insieme.
    private struct Scelta: Equatable {
        let giornata: Int?
        let haiScelto: [String]
        let consigliava: [String]
        let tua: Double?
        let consigliata: Double?
        let differenza: Double?
        let esito: String?

        init(giornata: Int?, haiScelto: [String], consigliava: [String], tua: Double?, consigliata: Double?, differenza: Double?, esito: String?) {
            self.giornata = giornata; self.haiScelto = haiScelto; self.consigliava = consigliava
            self.tua = tua; self.consigliata = consigliata; self.differenza = differenza; self.esito = esito
        }

        /// La riga come la mostra la demo.
        init(_ r: SceltaGiornata) {
            self.init(giornata: r.giornata, haiScelto: r.haiScelto ?? [], consigliava: r.consigliava ?? [],
                      tua: r.puntiTua, consigliata: r.puntiConsigliata, differenza: r.differenza, esito: r.esito)
        }
    }

    /// Le righe come le scrive `scelte_tue` di fanta/diario.py: solo le giornate con la tua formazione e undici diversi da quelli
    /// consigliati, nell'ordine del Diario; i nomi in più e in meno nell'ordine delle due formazioni; differenza = tua − consigliata.
    private static func scelteDelServer(_ voci: [VoceDiario]) -> [Scelta] {
        voci.compactMap { v -> Scelta? in
            guard let tua = v.schierata, let cons = v.consigliata,
                  let titolariTua = tua.titolari, !titolariTua.isEmpty,
                  let titolariCons = cons.titolari, !titolariCons.isEmpty else { return nil }
            let tue = Set(titolariTua.compactMap(\.id))
            let loro = Set(titolariCons.compactMap(\.id))
            guard tue != loro else { return nil }
            let puntiTua = tua.reale ?? 0
            let puntiCons = cons.reale ?? 0
            let differenza = ((puntiTua - puntiCons) * 10).rounded() / 10
            let esito = differenza > 0 ? "tua" : differenza < 0 ? "consigliata" : "pari"
            return Scelta(giornata: v.giornata,
                          haiScelto: titolariTua.filter { !loro.contains($0.id ?? -1) }.compactMap(\.nome),
                          consigliava: titolariCons.filter { !tue.contains($0.id ?? -1) }.compactMap(\.nome),
                          tua: puntiTua, consigliata: puntiCons, differenza: differenza, esito: esito)
        }
    }

    /// La media a un decimale, come `round(…, 1)` del server.
    private func media(_ valori: [Double]) -> Double {
        (valori.reduce(0, +) / Double(valori.count) * 10).rounded() / 10
    }
}
