import Foundation

/// Il gruppo che si apre sotto i valori riconosciuti dal regolamento incollato: le righe che l'utente deve rileggere.
/// Logica pura: la provano i test.
struct GruppoDaControllare: Equatable, Sendable {
    /// Una riga del regolamento da rileggere.
    struct Riga: Equatable, Sendable, Identifiable {
        /// Il posto nell'elenco: due righe del regolamento possono avere lo stesso testo.
        let id: Int
        let testo: String
        /// La riga piccola sotto il testo; nil se non c'è.
        let daImpostare: String?
    }

    let titolo: String
    let righe: [Riga]

    /// nil quando non c'è niente da controllare: il gruppo non si mostra.
    init?(_ esito: RiconoscimentoRegole) {
        let testi = esito.nonRiconosciute ?? []
        guard !testi.isEmpty else { return nil }
        titolo = Catalogo.Regole.nonRiconosciute(n: String(testi.count))
        righe = testi.enumerated().map { Riga(id: $0.offset, testo: $0.element, daImpostare: nil) }
    }
}
