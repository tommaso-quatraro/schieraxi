import SwiftUI

/// Una voce dei menu Squadra e Altro: la stessa di `VOCI_LEGA` in `fanta/web/app.js`, con il nome e la riga sotto di
/// `fanta/web/testi.js` (`lega.voce_*`), nello stesso ordine e accesa dalla stessa funzione (`f` sulla web).
/// `MenuLegaComeLaWebTests` legge i due file della web e fallisce se un lato cambia da solo.
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
                return VoceMenuLega(id: voce.id, pagina: voce.pagina, nome: "La mia squadra e rosa",
                                    dettaglio: "La tua squadra e i suoi giocatori", funzione: voce.funzione,
                                    simbolo: voce.simbolo, colore: voce.colore)
            }
    }

    /// Squadra: la mia squadra e le rose, i cambi consigliati, i seguiti, l'elenco dei giocatori, il calendario e, per ultima,
    /// l'importazione delle rose.
    private static let squadra: [VoceMenuLega] = [
        VoceMenuLega(id: "squadre", pagina: .squadre, nome: "Squadre e rose", dettaglio: "La tua squadra, le altre e le loro rose",
                     funzione: nil, simbolo: "person.3", colore: .green),
        VoceMenuLega(id: "consigli", pagina: .cambi, nome: "Cambi consigliati", dettaglio: "Svincolati che migliorano la tua squadra",
                     funzione: nil, simbolo: "arrow.triangle.2.circlepath", colore: .orange),
        VoceMenuLega(id: "osservati", pagina: .seguiti, nome: "Seguiti", dettaglio: "I giocatori che segui e gli avvisi quando si liberano",
                     funzione: Funzione.seguiti, simbolo: "star", colore: .yellow),
        VoceMenuLega(id: "giocatori", pagina: .elenco, nome: "Elenco dei giocatori", dettaglio: "Tutti i giocatori, con ricerca e filtri",
                     funzione: Funzione.elencoGiocatori, simbolo: "list.number", colore: .teal),
        VoceMenuLega(id: "calendario", pagina: .calendario, nome: "Calendario", dettaglio: "Le prossime partite e quanto sono facili",
                     funzione: Funzione.elencoGiocatori, simbolo: "calendar.badge.clock", colore: .cyan),
        VoceMenuLega(id: "importa", pagina: .importa, nome: "Aggiorna le rose", dettaglio: "Il file Excel o il testo preso da Leghe",
                     funzione: nil, simbolo: "doc.badge.plus", colore: .blue),
    ]

    /// Altro: Scambi, il diario, le regole, lo storico, i crediti, la nuova stagione (sempre: la pagina dice se c'è da fare) e le novità.
    private static let altro: [VoceMenuLega] = [
        VoceMenuLega(id: "scambi", pagina: .scambi, nome: "Scambi", dettaglio: "Valuta un'offerta, trova o costruisci uno scambio",
                     funzione: nil, simbolo: "arrow.left.arrow.right", colore: .purple),
        VoceMenuLega(id: "diario", pagina: .diario, nome: "Diario delle giornate", dettaglio: "La tua formazione contro quella del modello",
                     funzione: Funzione.diario, simbolo: "book", colore: .teal),
        VoceMenuLega(id: "regole", pagina: .regole, nome: "Regole", dettaglio: "Punteggi, modificatore difesa, moduli, panchina, rosa",
                     funzione: nil, simbolo: "list.bullet.rectangle", colore: .indigo),
        VoceMenuLega(id: "movimenti", pagina: .movimenti, nome: "Movimenti e storico", dettaglio: "Cosa è cambiato a ogni aggiornamento delle rose",
                     funzione: Funzione.movimenti, simbolo: "list.bullet.clipboard", colore: .orange),
        VoceMenuLega(id: "crediti", pagina: .crediti, nome: "Crediti delle squadre", dettaglio: "I crediti residui di ogni squadra",
                     funzione: Funzione.crediti, simbolo: ParoleWidget.simboloCrediti, colore: .mint),
        VoceMenuLega(id: "stagione", pagina: .stagione, nome: "Nuova stagione", dettaglio: "Archivia le rose e riparti",
                     funzione: nil, simbolo: "calendar", colore: .red),
        VoceMenuLega(id: "novita", pagina: .novita, nome: "Novità", dettaglio: "Cosa è cambiato negli ultimi aggiornamenti",
                     funzione: Funzione.novita, simbolo: "sparkles", colore: .yellow),
    ]
}
