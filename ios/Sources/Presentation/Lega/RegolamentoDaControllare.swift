import Foundation

/// Il gruppo che si apre sotto i valori riconosciuti dal regolamento incollato, come la web (`vistaRegole` in `fanta/web/app.js`,
/// #733): «Righe da controllare a mano (N)» (`regole.da_controllare`) con le righe di `da_controllare` nell'ordine del server e,
/// sotto una riga che lascia regole da impostare a mano, «da impostare: <etichette>» (`regole.da_impostare`). Righe, ordine ed
/// etichette sono del server: qui si scelgono solo i testi. Con un server di prima, che non manda `da_controllare`, resta il
/// gruppo di prima: «Righe con numeri non riconosciute (N)» (`regole.non_riconosciute`). Logica pura: la provano i test.
struct RegolamentoDaControllare: Equatable, Sendable {
    /// Una riga del regolamento da rileggere.
    struct Riga: Equatable, Sendable, Identifiable {
        /// Il posto nell'elenco: due righe del regolamento possono avere lo stesso testo.
        let id: Int
        let testo: String
        /// «da impostare: Ordine dei cambi»; nil se la riga non nomina regole da impostare.
        let daImpostare: String?
    }

    let titolo: String
    let righe: [Riga]

    /// nil quando non c'è niente da controllare: il gruppo non si mostra.
    init?(_ esito: RiconoscimentoRegole) {
        let voci: [(testo: String, daImpostare: String?)]
        if let daControllare = esito.daControllare {
            voci = daControllare.compactMap(Self.voce)
        } else {
            voci = (esito.nonRiconosciute ?? []).map { (testo: $0, daImpostare: String?.none) }
        }
        guard !voci.isEmpty else { return nil }
        let n = String(voci.count)
        titolo = esito.daControllare == nil ? Catalogo.Regole.nonRiconosciute(n: n) : Catalogo.Regole.daControllare(n: n)
        righe = voci.enumerated().map { Riga(id: $0.offset, testo: $0.element.testo, daImpostare: $0.element.daImpostare) }
    }

    /// Testo e «da impostare: …» di una riga di `da_controllare`, con le etichette separate da virgole come la web; nil per
    /// una riga senza testo.
    private static func voce(_ riga: RigaDaControllare) -> (testo: String, daImpostare: String?)? {
        guard let testo = riga.riga else { return nil }
        let etichette = (riga.regole ?? []).compactMap(\.etichetta)
        let daImpostare: String? = etichette.isEmpty ? nil : Catalogo.Regole.daImpostare(r: etichette.joined(separator: ", "))
        return (testo, daImpostare)
    }
}
