import Foundation

/// L'intestazione della scheda del giocatore (volto, nome, «Ruolo · club») e la sua previsione per la giornata. Dalla Formazione
/// c'è subito, dalla previsione già letta (come `apriGiocatore` della web con la scheda locale); da altrove dalla scheda del
/// server (`/api/giocatore`).
struct TestaScheda {
    let id: Int
    let nome: String
    let ruolo: String
    /// Il club come si scrive in una frase («Hellas Verona»).
    let club: String?
    /// Il club come lo conosce il server («verona»): colori del volto.
    let slug: String?
    /// nil = nessuna previsione per la giornata.
    let previsione: Giocatore?

    /// Dalla Formazione: il club è la squadra della previsione con le iniziali maiuscole (`nomeClub` della web).
    init(previsione g: Giocatore) {
        id = g.id
        nome = g.nome
        ruolo = g.ruolo
        club = g.squadra.map(\.capitalized)
        slug = g.squadra
        previsione = g
    }

    /// Dalla scheda del server.
    init(scheda s: SchedaGiocatore) {
        let c = s.calciatore
        id = c.id
        nome = c.nome
        ruolo = c.ruolo
        club = c.squadra.map(\.capitalized)
        slug = c.squadraSlug ?? s.previsione?.squadra
        previsione = s.previsione
    }
}
