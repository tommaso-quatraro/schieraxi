import Foundation
import Testing
@testable import Schieraxi

/// La consigliata della demo è davvero la migliore (#944, punto 2, e revisione della #955). La Formazione dice «È la consigliata»:
/// nessun cambio di un titolare con un altro della rosa, e nessuna formazione della rosa in un modulo della lega, deve avere più
/// punti attesi. Prima «Sostituisci» su Marténi dava Lemão a +1,5, e mettere Dimarzi (7,5) al posto di Buonvicini (6,5) o di
/// Marténi dava fino a +0,7, con Dimarzi in panchina. I conti come li fa il server: punti attesi delle due formazioni a una cifra,
/// poi la differenza; un pari (0,0) va bene, un numero sopra lo zero no.
/// Dati inventati: quelli di `LegaDemo.swift` e `DatiDemo.swift`, nello stesso istante fisso.
struct DemoConsigliataTests {
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)
    static let demo = FinteServer.demoFissata(adesso: adesso)

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

    @Test("Nessun cambio di un titolare con un altro della rosa dà più punti attesi (anche cambiando modulo)")
    func nessunCambioMigliore() async throws {
        let f = try await formazione()
        let moduli = try await moduliDellaLega()
        let schede = try #require(f.schede, "la Formazione della demo non ha le schede della rosa")
        let titolari = f.titolari.map(\.id)
        func punti(_ id: Int) -> Double { schede[String(id)]?.puntiAttesi ?? 0 }
        func nome(_ id: Int) -> String { schede[String(id)]?.nome ?? String(id) }
        func ruolo(_ id: Int) -> String { schede[String(id)]?.ruolo ?? "" }
        let prima = tondo(titolari.reduce(0) { $0 + punti($1) })
        #expect(abs(prima - tondo(f.punteggioAtteso)) < 0.05, "i punti della consigliata sono la somma di quelli dei titolari")

        let altri = schede.values.filter { !titolari.contains($0.id) && ($0.puntiAttesi ?? 0) > 0 }
        try #require(!altri.isEmpty, "nella demo nessuno fuori dagli 11 può entrare")
        var meglio: [String] = []
        for entra in altri {
            // come `chi_prende_il_posto` e `chi_lascia_il_posto` del server: portiere solo per portiere, modulo della lega
            for esce in titolari where (ruolo(esce) == "P") == (entra.ruolo == "P") {
                let dopo = titolari.map { $0 == esce ? entra.id : $0 }
                guard moduli.contains(ModuloTitolari.modulo(ruoli: dopo.map(ruolo))) else { continue }
                let differenza = tondo(tondo(dopo.reduce(0) { $0 + punti($1) }) - prima)
                if differenza > 0 {
                    meglio.append("\(entra.nome) al posto di \(nome(esce)): \(Formato.conSegno(differenza))")
                }
            }
        }
        #expect(meglio.isEmpty, "la consigliata della demo lascia fuori cambi che rendono di più: \(meglio.sorted())")
    }

    /// Anche con più cambi insieme (revisione della #955: Dimarzi e Di Corvara nel 4-4-2 davano +1,13): per ogni modulo della lega
    /// la formazione migliore della rosa, i più attesi di ogni ruolo, non ha più punti della consigliata.
    @Test("Nessuna formazione della rosa, in nessun modulo della lega, ha più punti attesi della consigliata")
    func nessunaFormazioneMigliore() async throws {
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
        var meglio: [String] = []
        for modulo in moduli {
            let numeri = modulo.split(separator: "-").compactMap { Int($0) }
            try #require(numeri.count == 3, "modulo strano nelle regole della demo: \(modulo)")
            guard let p = migliori("P", 1), let d = migliori("D", numeri[0]), let c = migliori("C", numeri[1]),
                  let a = migliori("A", numeri[2]) else { continue }
            let differenza = tondo(tondo(p + d + c + a) - consigliata)
            if differenza > 0 { meglio.append("\(modulo): \(Formato.conSegno(differenza))") }
        }
        #expect(meglio.isEmpty, "formazioni della rosa con più punti attesi della consigliata: \(meglio)")
    }

    @Test("«Sostituisci» della demo (Marténi): nessun compagno di ruolo rende di più")
    func sostituisciNessunoMeglio() async throws {
        let f = try await formazione()
        let titolari = f.titolari.map(\.id)
        let r: RispostaSostituisci = try await Self.demo.posta(
            "POST", "/api/formazione/sostituisci",
            RichiestaSostituisci(esce: FinteServer.esceSostituisci, titolari: titolari, giornata: f.giornata))
        let differenze = (r.entrate ?? []).compactMap(\.differenza)
        try #require(!differenze.isEmpty, "«Sostituisci» della demo non propone nessuno")
        #expect(differenze.allSatisfy { $0 <= 0 }, "differenze di «Sostituisci»: \(differenze)")
    }

    @Test("«Metti in campo» della demo (Dimarzi): nessuna uscita rende di più")
    func mettiInCampoNessunoMeglio() async throws {
        let f = try await formazione()
        let titolari = f.titolari.map(\.id)
        let r: RispostaMettiInCampo = try await Self.demo.posta(
            "POST", "/api/formazione/metti-in-campo",
            RichiestaMettiInCampo(entra: FinteServer.entraMettiInCampo, titolari: titolari, giornata: f.giornata))
        let differenze = (r.uscite ?? []).compactMap(\.differenza)
        try #require(!differenze.isEmpty, "«Metti in campo» della demo non propone nessuno")
        #expect(differenze.allSatisfy { $0 <= 0 }, "differenze di «Metti in campo»: \(differenze)")
    }
}
