import Foundation
import Testing
@testable import Schieraxi

/// La consigliata della demo è davvero quella da schierare (#944, punto 2). Sul server una consigliata già mostrata resta finché
/// la migliore non vale almeno `SOGLIA_CAMBIO_PUNTI` (1 punto atteso) in più, e sotto quella soglia il cambio di un titolare in
/// dubbio non si propone (`da_fare.SOGLIA_CAMBIO`). Quindi nessun cambio di un titolare con un altro giocatore della rosa può
/// dare un punto o più: prima la Formazione diceva «È la consigliata» e «Sostituisci» su Marténi dava Lemão a +1,5.
/// Dati inventati: quelli di `LegaDemo.swift` e `DatiDemo.swift`, nello stesso istante fisso.
struct DemoConsigliataTests {
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)
    static let demo = FinteServer.demoFissata(adesso: adesso)
    /// `SOGLIA_CAMBIO_PUNTI` di fanta/consigli.py.
    static let soglia = 1.0

    /// Il numero di un cambio come lo scrive il server: i punti attesi delle due formazioni a una cifra, poi la differenza.
    private func tondo(_ x: Double) -> Double { (x * 10).rounded() / 10 }

    private func formazione() async throws -> Formazione {
        try await Self.demo.get("/api/formazione")
    }

    private func moduliDellaLega() async throws -> [String] {
        let dati = try await Self.demo.richiesta("GET", "/api/regole", corpo: nil)
        let regole = try #require(try JSONSerialization.jsonObject(with: dati) as? [String: Any])
        return try #require(regole["moduli"] as? [String], "le regole della demo non hanno i moduli")
    }

    @Test("Nessun cambio di un titolare con un altro della rosa vale un punto atteso o più (anche cambiando modulo)")
    func nessunCambioSopraLaSoglia() async throws {
        let f = try await formazione()
        let moduli = try await moduliDellaLega()
        let schede = try #require(f.schede, "la Formazione della demo non ha le schede della rosa")
        let titolari = f.titolari.map(\.id)
        func punti(_ id: Int) -> Double { schede[String(id)]?.puntiAttesi ?? 0 }
        func nome(_ id: Int) -> String { schede[String(id)]?.nome ?? String(id) }
        func ruolo(_ id: Int) -> String { schede[String(id)]?.ruolo ?? "" }
        let prima = tondo(titolari.reduce(0) { $0 + punti($1) })
        #expect(prima == tondo(f.punteggioAtteso), "i punti della consigliata sono la somma di quelli dei titolari")

        let altri = schede.values.filter { !titolari.contains($0.id) && ($0.puntiAttesi ?? 0) > 0 }
        try #require(!altri.isEmpty, "nella demo nessuno fuori dagli 11 può entrare")
        var sopra: [String] = []
        for entra in altri {
            // come `chi_prende_il_posto` e `chi_lascia_il_posto` del server: portiere solo per portiere, modulo della lega
            for esce in titolari where (ruolo(esce) == "P") == (entra.ruolo == "P") {
                let dopo = titolari.map { $0 == esce ? entra.id : $0 }
                guard moduli.contains(ModuloTitolari.modulo(ruoli: dopo.map(ruolo))) else { continue }
                let differenza = tondo(tondo(dopo.reduce(0) { $0 + punti($1) }) - prima)
                if differenza >= Self.soglia {
                    sopra.append("\(entra.nome) al posto di \(nome(esce)): \(Formato.conSegno(differenza))")
                }
            }
        }
        #expect(sopra.isEmpty, "la consigliata della demo lascia fuori cambi da un punto o più: \(sopra.sorted())")
    }

    /// Anche con più cambi insieme (revisione della #955: Dimarzi e Di Corvara nel 4-4-2 davano +1,13): per ogni modulo della lega
    /// la formazione migliore della rosa, i più attesi di ogni ruolo, non vale un punto o più della consigliata.
    @Test("Nessuna formazione della rosa, in nessun modulo della lega, vale un punto atteso o più della consigliata")
    func nessunaFormazioneSopraLaSoglia() async throws {
        let f = try await formazione()
        let moduli = try await moduliDellaLega()
        let schede = try #require(f.schede, "la Formazione della demo non ha le schede della rosa")
        let disponibili = schede.values.filter { ($0.puntiAttesi ?? 0) > 0 }
        /// I punti dei migliori `n` di un ruolo; nil se il ruolo non ne ha abbastanza.
        func migliori(_ ruolo: String, _ n: Int) -> Double? {
            let punti = disponibili.filter { $0.ruolo == ruolo }.compactMap(\.puntiAttesi).sorted(by: >)
            return punti.count >= n ? punti.prefix(n).reduce(0, +) : nil
        }
        let consigliata = tondo(f.punteggioAtteso)
        var sopra: [String] = []
        for modulo in moduli {
            let numeri = modulo.split(separator: "-").compactMap { Int($0) }
            try #require(numeri.count == 3, "modulo strano nelle regole della demo: \(modulo)")
            guard let p = migliori("P", 1), let d = migliori("D", numeri[0]), let c = migliori("C", numeri[1]),
                  let a = migliori("A", numeri[2]) else { continue }
            let differenza = tondo(tondo(p + d + c + a) - consigliata)
            if differenza >= Self.soglia { sopra.append("\(modulo): \(Formato.conSegno(differenza))") }
        }
        #expect(sopra.isEmpty, "formazioni della rosa da un punto o più sopra la consigliata: \(sopra)")
    }

    @Test("«Sostituisci» della demo (Marténi): nessun compagno di ruolo vale un punto atteso o più")
    func sostituisciSottoLaSoglia() async throws {
        let f = try await formazione()
        let titolari = f.titolari.map(\.id)
        let r: RispostaSostituisci = try await Self.demo.posta(
            "POST", "/api/formazione/sostituisci",
            RichiestaSostituisci(esce: FinteServer.esceSostituisci, titolari: titolari, giornata: f.giornata))
        let differenze = (r.entrate ?? []).compactMap(\.differenza)
        try #require(!differenze.isEmpty, "«Sostituisci» della demo non propone nessuno")
        #expect(differenze.allSatisfy { $0 < Self.soglia }, "differenze di «Sostituisci»: \(differenze)")
    }

    @Test("«Metti in campo» della demo (Dimarzi): nessuna uscita vale un punto atteso o più")
    func mettiInCampoSottoLaSoglia() async throws {
        let f = try await formazione()
        let titolari = f.titolari.map(\.id)
        let r: RispostaMettiInCampo = try await Self.demo.posta(
            "POST", "/api/formazione/metti-in-campo",
            RichiestaMettiInCampo(entra: FinteServer.entraMettiInCampo, titolari: titolari, giornata: f.giornata))
        let differenze = (r.uscite ?? []).compactMap(\.differenza)
        try #require(!differenze.isEmpty, "«Metti in campo» della demo non propone nessuno")
        #expect(differenze.allSatisfy { $0 < Self.soglia }, "differenze di «Metti in campo»: \(differenze)")
    }
}
