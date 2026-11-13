import SwiftUI

/// Una voce dei menu Squadra e Altro: la stessa di `VOCI_LEGA` in `fanta/web/app.js`, con il nome e la riga sotto del catalogo
/// comune (`lega.voce_*`, file generato `Catalogo+Lega.swift`), nello stesso ordine.
/// Dal 12/11/2026 (#634) restano poche voci, come sulla web: Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario, Scambi,
/// Movimenti, Crediti e Novità non ci sono più (le Novità si leggono in Impostazioni > Informazioni); «Nuova stagione» compare da
/// sola in cima alle due schede quando serve. Il Diario è la pagina Giornate, una scheda della barra (#673 passo 2, come la web
/// con #671): in Altro restano le Regole.
struct VoceMenuLega: Identifiable, Equatable {
    /// L'`id` della stessa voce sulla web («squadre», «importa», …).
    let id: String
    let pagina: PaginaLega
    let nome: String
    /// La riga piccola sotto il nome (`sub` sulla web).
    let dettaglio: String
    let simbolo: String
    let colore: Color

    /// Tutte le voci di una scheda, nell'ordine della web.
    static func tutte(_ ambito: Sezione) -> [VoceMenuLega] {
        ambito == .squadra ? squadra : altro
    }

    /// Le voci da mostrare, come `vociLega` della web: senza le rose degli altri la prima voce diventa «La mia squadra e rosa».
    static func voci(_ ambito: Sezione, funzioni: StatoFunzioni) -> [VoceMenuLega] {
        tutte(ambito).map { voce in
            guard voce.id == "squadre", !funzioni.acceso(Funzione.squadreAltrui) else { return voce }
            return VoceMenuLega(id: voce.id, pagina: voce.pagina, nome: Catalogo.Lega.voceMiasquadra,
                                dettaglio: Catalogo.Lega.voceMiasquadraSub, simbolo: voce.simbolo, colore: voce.colore)
        }
    }

    /// Squadra: la mia squadra e le rose, poi l'importazione delle rose.
    private static let squadra: [VoceMenuLega] = [
        VoceMenuLega(id: "squadre", pagina: .squadre, nome: Catalogo.Lega.voceSquadre, dettaglio: Catalogo.Lega.voceSquadreSub,
                     simbolo: "person.3", colore: .green),
        VoceMenuLega(id: "importa", pagina: .importa, nome: Catalogo.Lega.voceImporta, dettaglio: Catalogo.Lega.voceImportaSub,
                     simbolo: "doc.badge.plus", colore: .blue),
    ]

    /// Altro: le regole.
    private static let altro: [VoceMenuLega] = [
        VoceMenuLega(id: "regole", pagina: .regole, nome: Catalogo.Lega.voceRegole, dettaglio: Catalogo.Lega.voceRegoleSub,
                     simbolo: "list.bullet.rectangle", colore: .indigo),
    ]
}
