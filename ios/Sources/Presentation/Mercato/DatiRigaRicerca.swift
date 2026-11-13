import Foundation

/// Cosa mostra una riga dei risultati della ricerca, come la web (`scriviRisultati` di `fanta/web/app.js`, decisione 3 della #677):
/// il ruolo e il nome, sotto il club (la sigla, come nel listone), a destra «quotazione N». Niente fantavoto atteso né «gioca N%».
struct DatiRigaRicerca: Equatable {
    let id: Int
    let nome: String
    let ruolo: String
    /// La sigla del club («INT»), vuota se non si sa.
    let club: String
    /// «quotazione 31» (`avv.quot`), con «–» se manca.
    let quotazione: String
    /// Quello che legge VoiceOver: nome, ruolo, club e quotazione.
    let voce: String

    init(_ g: GiocatoreBreve) {
        id = g.id
        nome = g.nome
        ruolo = g.ruolo
        club = ColoriSquadra.sigla(g.squadra)
        quotazione = Catalogo.Avv.quot(n: g.quotazione.map { String(Formato.intero($0)) } ?? "–")
        voce = [g.nome, nomeRuolo(g.ruolo), club, quotazione].filter { !$0.isEmpty }.joined(separator: ", ")
    }
}
