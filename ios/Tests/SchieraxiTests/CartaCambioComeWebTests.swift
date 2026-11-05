import Testing
@testable import Schieraxi

/// Cambi consigliati (issue #256): i soldi del cambio con l'ordine e il separatore della web (`soldiDelCambio` di
/// `fanta/web/app.js`): «crediti dopo 2 · rimborso 18 · costo 34». Prima l'iPhone scriveva «rimborso 18, costo 34,
/// crediti dopo 2». VoiceOver legge la stessa riga, nello stesso ordine.
@Suite("Cambi consigliati: la riga dei dettagli come la web")
struct CartaCambioComeWebTests {

    /// Un caso della riga dei dettagli: i dati che cambiano e il testo atteso.
    struct Caso: Sendable, CustomTestStringConvertible {
        let breve: Double?
        let creditiDopo: Double
        let fattibile: Bool
        let atteso: String
        var testDescription: String { atteso }
    }

    private static func proposta(breve: Double?, creditiDopo: Double?, fattibile: Bool?) -> PropostaMercato {
        PropostaMercato(
            esce: GiocatoreBreve(id: 2, nome: "Bruno Fosola", ruolo: "A", squadra: "Prova", quotazione: 22),
            entra: GiocatoreBreve(id: 1, nome: "Aldo Pinarotti", ruolo: "A", squadra: "Prova", quotazione: 34),
            guadagno: 3.4, breve: breve, rimborso: 18, creditiDopo: creditiDopo, fattibile: fattibile,
            giornate: [10, 11, 12, 13, 14])
    }

    @MainActor
    @Test("Prima i crediti dopo, poi il rimborso, poi il costo, separati da «·»", arguments: [
        Caso(breve: nil, creditiDopo: 2, fattibile: true, atteso: "crediti dopo 2 · rimborso 18 · costo 34"),
        Caso(breve: nil, creditiDopo: 1, fattibile: false, atteso: "crediti dopo 1 (non bastano) · rimborso 18 · costo 34"),
        Caso(breve: 1.4, creditiDopo: 2, fattibile: true,
             atteso: "+1,4 nelle prossime 5 giornate · crediti dopo 2 · rimborso 18 · costo 34"),
    ])
    func ordineComeWeb(_ caso: Caso) {
        let p = Self.proposta(breve: caso.breve, creditiDopo: caso.creditiDopo, fattibile: caso.fattibile)
        #expect(CartaCambio.dettaglio(p) == caso.atteso)
    }

    @MainActor
    @Test("VoiceOver legge i dettagli nello stesso ordine della riga")
    func voceStessoOrdine() {
        let p = Self.proposta(breve: 1.4, creditiDopo: 1, fattibile: false)
        #expect(CartaCambio.voce(p) == "Entra Aldo Pinarotti, esce Bruno Fosola, +3,4 punti attesi. "
                + "+1,4 nelle prossime 5 giornate · crediti dopo 1 (non bastano) · rimborso 18 · costo 34")
    }
}
