import SwiftUI

/// Una voce dei menu Squadra e Altro: la stessa di `VOCI_LEGA` in `fanta/web/app.js`, con il nome e la riga sotto del catalogo
/// comune (`lega.voce_*`, file generato `Catalogo+Lega.swift`), nello stesso ordine e accesa dalla stessa funzione (`f` sulla web).
/// `MenuLegaComeLaWebTests` legge `VOCI_LEGA` e fallisce se un lato cambia da solo.
struct VoceMenuLega: Identifiable, Equatable {
    /// L'`id` della stessa voce sulla web («squadre», «consigli», …).
    let id: String
    let pagina: PaginaLega
    let nome: String
    /// La riga piccola sotto il nome (`sub` sulla web).
    let dettaglio: String
    /// La funzione di `GET /api/funzioni` che accende la voce; nil = la voce c'è sempre.
    let funzione: String?
    let simbolo: String
    let colore: Color

    /// Tutte le voci di una scheda, nell'ordine della web.
    static func tutte(_ ambito: Sezione) -> [VoceMenuLega] {
        ambito == .squadra ? squadra : altro
    }

    /// Le voci da mostrare, come `vistaLega` della web: quelle di una funzione spenta non si vedono, e senza «Squadre della lega»
    /// la prima voce diventa «La mia squadra e rosa».
    static func voci(_ ambito: Sezione, funzioni: StatoFunzioni) -> [VoceMenuLega] {
        tutte(ambito)
            .filter { voce in voce.funzione.map { funzioni.acceso($0) } ?? true }
            .map { voce in
                guard voce.id == "squadre", !funzioni.acceso(Funzione.squadreAltrui) else { return voce }
                return VoceMenuLega(id: voce.id, pagina: voce.pagina, nome: Catalogo.Lega.voceMiasquadra,
                                    dettaglio: Catalogo.Lega.voceMiasquadraSub, funzione: voce.funzione,
                                    simbolo: voce.simbolo, colore: voce.colore)
            }
    }

    /// Squadra: la mia squadra e le rose, i cambi consigliati, i seguiti, l'elenco dei giocatori, il calendario e, per ultima,
    /// l'importazione delle rose.
    private static let squadra: [VoceMenuLega] = [
        VoceMenuLega(id: "squadre", pagina: .squadre, nome: Catalogo.Lega.voceSquadre, dettaglio: Catalogo.Lega.voceSquadreSub,
                     funzione: nil, simbolo: "person.3", colore: .green),
        VoceMenuLega(id: "consigli", pagina: .cambi, nome: Catalogo.Lega.voceConsigli, dettaglio: Catalogo.Lega.voceConsigliSub,
                     funzione: nil, simbolo: "arrow.triangle.2.circlepath", colore: .orange),
        VoceMenuLega(id: "osservati", pagina: .seguiti, nome: Catalogo.Lega.voceOsservati, dettaglio: Catalogo.Lega.voceOsservatiSub,
                     funzione: Funzione.seguiti, simbolo: "star", colore: .yellow),
        VoceMenuLega(id: "giocatori", pagina: .elenco, nome: Catalogo.Lega.voceGiocatori, dettaglio: Catalogo.Lega.voceGiocatoriSub,
                     funzione: Funzione.elencoGiocatori, simbolo: "list.number", colore: .teal),
        VoceMenuLega(id: "calendario", pagina: .calendario, nome: Catalogo.Lega.voceCalendario, dettaglio: Catalogo.Lega.voceCalendarioSub,
                     funzione: Funzione.elencoGiocatori, simbolo: "calendar.badge.clock", colore: .cyan),
        VoceMenuLega(id: "importa", pagina: .importa, nome: Catalogo.Lega.voceImporta, dettaglio: Catalogo.Lega.voceImportaSub,
                     funzione: nil, simbolo: "doc.badge.plus", colore: .blue),
    ]

    /// Altro: Scambi, il diario, le regole, lo storico, i crediti, la nuova stagione (sempre: la pagina dice se c'è da fare) e le novità.
    private static let altro: [VoceMenuLega] = [
        VoceMenuLega(id: "scambi", pagina: .scambi, nome: Catalogo.Lega.voceScambi, dettaglio: Catalogo.Lega.voceScambiSub,
                     funzione: nil, simbolo: "arrow.left.arrow.right", colore: .purple),
        VoceMenuLega(id: "diario", pagina: .diario, nome: Catalogo.Lega.voceDiario, dettaglio: Catalogo.Lega.voceDiarioSub,
                     funzione: Funzione.diario, simbolo: "book", colore: .teal),
        VoceMenuLega(id: "regole", pagina: .regole, nome: Catalogo.Lega.voceRegole, dettaglio: Catalogo.Lega.voceRegoleSub,
                     funzione: nil, simbolo: "list.bullet.rectangle", colore: .indigo),
        VoceMenuLega(id: "movimenti", pagina: .movimenti, nome: Catalogo.Lega.voceMovimenti, dettaglio: Catalogo.Lega.voceMovimentiSub,
                     funzione: Funzione.movimenti, simbolo: "list.bullet.clipboard", colore: .orange),
        VoceMenuLega(id: "crediti", pagina: .crediti, nome: Catalogo.Lega.voceCrediti, dettaglio: Catalogo.Lega.voceCreditiSub,
                     funzione: Funzione.crediti, simbolo: ParoleWidget.simboloCrediti, colore: .mint),
        VoceMenuLega(id: "stagione", pagina: .stagione, nome: Catalogo.Lega.voceStagione, dettaglio: Catalogo.Lega.voceStagioneSub,
                     funzione: nil, simbolo: "calendar", colore: .red),
        VoceMenuLega(id: "novita", pagina: .novita, nome: Catalogo.Lega.voceNovita, dettaglio: Catalogo.Lega.voceNovitaSub,
                     funzione: Funzione.novita, simbolo: "sparkles", colore: .yellow),
    ]
}
