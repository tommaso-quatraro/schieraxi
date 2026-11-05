import SwiftUI

/// Una voce dei menu Squadra e Altro.
struct VoceMenuLega: Identifiable, Equatable {
    /// L'`id` della stessa voce sulla web («squadre», «consigli», …).
    let id: String
    let pagina: PaginaLega
    let nome: String
    /// La riga piccola sotto il nome.
    let dettaglio: String
    let simbolo: String
    let colore: Color

    /// Tutte le voci di una scheda, nell'ordine in cui si vedono.
    static func tutte(_ ambito: Sezione) -> [VoceMenuLega] {
        ambito == .squadra ? squadra : altro
    }

    /// Le voci da mostrare nella scheda: quelle di una funzione spenta non si vedono, e senza «Squadre della lega» la prima
    /// voce diventa «La mia squadra e rosa».
    static func voci(_ ambito: Sezione, funzioni: StatoFunzioni) -> [VoceMenuLega] {
        tutte(ambito).filter { voce in
            switch voce.id {
            case "osservati": return funzioni.acceso(Funzione.seguiti)
            case "giocatori": return funzioni.acceso(Funzione.elencoGiocatori)
            case "calendario": return funzioni.vedeCalendario
            case "diario": return funzioni.acceso(Funzione.diario)
            case "movimenti": return funzioni.acceso(Funzione.squadreAltrui) && funzioni.acceso(Funzione.movimenti)
            case "crediti": return funzioni.acceso(Funzione.squadreAltrui) && funzioni.accesoSoloSeNominato(Funzione.crediti)
            case "stagione": return funzioni.mostraTutte
            case "novita": return funzioni.acceso(Funzione.novita)
            default: return true
            }
        }
        .map { voce in
            guard voce.id == "squadre", !funzioni.acceso(Funzione.squadreAltrui) else { return voce }
            return VoceMenuLega(id: voce.id, pagina: voce.pagina, nome: "La mia squadra e rosa", dettaglio: "",
                                simbolo: voce.simbolo, colore: voce.colore)
        }
    }

    private static let squadra: [VoceMenuLega] = [
        VoceMenuLega(id: "importa", pagina: .importa, nome: "Aggiorna le rose", dettaglio: "", simbolo: "doc.badge.plus", colore: .blue),
        VoceMenuLega(id: "squadre", pagina: .squadre, nome: "Squadre e rose", dettaglio: "", simbolo: "person.3", colore: .green),
        VoceMenuLega(id: "consigli", pagina: .cambi, nome: "Cambi consigliati", dettaglio: "", simbolo: "arrow.triangle.2.circlepath", colore: .orange),
        VoceMenuLega(id: "osservati", pagina: .seguiti, nome: "Seguiti", dettaglio: "", simbolo: "star", colore: .yellow),
        VoceMenuLega(id: "giocatori", pagina: .elenco, nome: "Elenco dei giocatori", dettaglio: "", simbolo: "list.number", colore: .teal),
        VoceMenuLega(id: "calendario", pagina: .calendario, nome: "Calendario", dettaglio: "", simbolo: "calendar.badge.clock", colore: .cyan),
    ]

    private static let altro: [VoceMenuLega] = [
        VoceMenuLega(id: "scambi", pagina: .scambi, nome: "Scambi", dettaglio: "", simbolo: "arrow.left.arrow.right", colore: .purple),
        VoceMenuLega(id: "diario", pagina: .diario, nome: "Diario delle giornate", dettaglio: "", simbolo: "book", colore: .teal),
        VoceMenuLega(id: "regole", pagina: .regole, nome: "Regole", dettaglio: "", simbolo: "list.bullet.rectangle", colore: .indigo),
        VoceMenuLega(id: "movimenti", pagina: .movimenti, nome: "Movimenti e storico", dettaglio: "", simbolo: "list.bullet.clipboard", colore: .orange),
        VoceMenuLega(id: "crediti", pagina: .crediti, nome: "Crediti delle squadre", dettaglio: "", simbolo: ParoleWidget.simboloCrediti, colore: .mint),
        VoceMenuLega(id: "stagione", pagina: .stagione, nome: "Nuova stagione", dettaglio: "", simbolo: "calendar", colore: .red),
        VoceMenuLega(id: "novita", pagina: .novita, nome: "Novità", dettaglio: "", simbolo: "sparkles", colore: .yellow),
    ]
}
