import Testing
@testable import Schieraxi

/// Cambi consigliati (issue #256): la riga dei dettagli con i testi, l'ordine e il separatore della web (`tabConsigli` e
/// `soldiDelCambio` di `fanta/web/app.js`): «+1,4 punti nelle prossime 5 giornate» e «crediti dopo 2 · rimborso 18 · costo 34».
/// Prima l'iPhone scriveva «+1,4 nelle prossime 5 giornate · rimborso 18, costo 34, crediti dopo 2», e senza «crediti dopo»
/// mostrava «rimborso 18», che la web non mostra. VoiceOver legge la stessa riga, nello stesso ordine, con le virgole al posto
/// di «·» (come `FasiGiornata.partiteVoce`).
@Suite("Cambi consigliati: la riga dei dettagli come la web")
struct CartaCambioComeWebTests {

    /// Un caso della riga dei dettagli: i dati che cambiano e il testo atteso (`nil`: la carta non ha la riga).
    struct Caso: Sendable, CustomTestStringConvertible {
        let breve: Double?
        var giornate: [Int]? = [10, 11, 12, 13, 14]
        let creditiDopo: Double?
        let fattibile: Bool?
        let atteso: String?
        var testDescription: String { atteso ?? "nessuna riga" }
    }

    private static func proposta(breve: Double?, giornate: [Int]? = [10, 11, 12, 13, 14], creditiDopo: Double?,
                                 fattibile: Bool?) -> PropostaMercato {
        PropostaMercato(
            esce: GiocatoreBreve(id: 2, nome: "Bruno Fosola", ruolo: "A", squadra: "Prova", quotazione: 22),
            entra: GiocatoreBreve(id: 1, nome: "Aldo Pinarotti", ruolo: "A", squadra: "Prova", quotazione: 34),
            guadagno: 3.4, breve: breve, rimborso: 18, creditiDopo: creditiDopo, fattibile: fattibile,
            giornate: giornate)
    }

    @MainActor
    @Test("Gli stessi testi della web, nello stesso ordine, separati da «·»", arguments: [
        Caso(breve: nil, creditiDopo: 2, fattibile: true, atteso: "crediti dopo 2 · rimborso 18 · costo 34"),
        Caso(breve: nil, creditiDopo: 1, fattibile: false, atteso: "crediti dopo 1 (non bastano) · rimborso 18 · costo 34"),
        Caso(breve: 1.4, creditiDopo: 2, fattibile: true,
             atteso: "+1,4 punti nelle prossime 5 giornate · crediti dopo 2 · rimborso 18 · costo 34"),
        Caso(breve: 1.4, giornate: [10], creditiDopo: 2, fattibile: true,
             atteso: "+1,4 punti nella prossima giornata · crediti dopo 2 · rimborso 18 · costo 34"),
        Caso(breve: 1.4, giornate: nil, creditiDopo: nil, fattibile: nil, atteso: "+1,4 punti nelle prossime giornate"),
        // senza «crediti dopo» la web non mostra i soldi del cambio: niente «rimborso 18» da solo
        Caso(breve: 1.4, creditiDopo: nil, fattibile: nil, atteso: "+1,4 punti nelle prossime 5 giornate"),
        Caso(breve: nil, creditiDopo: nil, fattibile: nil, atteso: nil),
    ])
    func rigaComeWeb(_ caso: Caso) {
        let p = Self.proposta(breve: caso.breve, giornate: caso.giornate, creditiDopo: caso.creditiDopo,
                              fattibile: caso.fattibile)
        #expect(CartaCambio.dettaglio(p) == caso.atteso)
    }

    @MainActor
    @Test("VoiceOver legge i dettagli nello stesso ordine, con le virgole al posto di «·»")
    func voceStessoOrdine() {
        let completa = Self.proposta(breve: 1.4, creditiDopo: 1, fattibile: false)
        #expect(CartaCambio.voce(completa) == "Entra Aldo Pinarotti, esce Bruno Fosola, +3,4 punti attesi. "
                + "+1,4 punti nelle prossime 5 giornate, crediti dopo 1 (non bastano), rimborso 18, costo 34")
        let senzaDettagli = Self.proposta(breve: nil, creditiDopo: nil, fattibile: nil)
        #expect(CartaCambio.voce(senzaDettagli) == "Entra Aldo Pinarotti, esce Bruno Fosola, +3,4 punti attesi")
    }
}
