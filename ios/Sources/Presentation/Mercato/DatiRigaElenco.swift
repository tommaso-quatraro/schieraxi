import Foundation

/// Cosa mostra una riga dei risultati della ricerca, come la riga compatta della web (`rigaGiocatoreCompatta`):
/// nome con il ruolo, «GEN · quotazione 19 · svincolato» e a destra il fantavoto atteso (neutro) con «gioca N%».
/// Viene da una riga della giornata (`Giocatore`) o, per chi non c'è, da un risultato della ricerca (`GiocatoreBreve`).
struct DatiRigaElenco: Equatable {
    let id: Int
    let nome: String
    let ruolo: String
    let squadra: String?
    /// «GEN · quotazione 19 · svincolato» (il proprietario solo se lo si conosce).
    let dettaglio: String
    /// Il fantavoto atteso («6,9») o «–».
    let numero: String
    /// «gioca 90%», «non gioca» o niente.
    let sotto: String?
    let voce: String

    static func testoDettaglio(squadra: String?, quotazione: Double?, proprietario: String??) -> String {
        var parti: [String] = []
        let sigla = ColoriSquadra.sigla(squadra)
        if !sigla.isEmpty { parti.append(sigla) }
        parti.append("quotazione \(quotazione.map { String(Formato.intero($0)) } ?? "–")")
        if let proprietario { parti.append(proprietario ?? "svincolato") }
        return parti.joined(separator: " · ")
    }

    init(_ g: Giocatore) {
        id = g.id; nome = g.nome; ruolo = g.ruolo; squadra = g.squadra
        dettaglio = Self.testoDettaglio(squadra: g.squadra, quotazione: g.quotazione, proprietario: .some(g.proprietario))
        if g.assente == true {
            numero = "–"
            sotto = "assente"
        } else {
            numero = Formato.punti(g.fvAtteso ?? g.puntiAttesi)
            sotto = "gioca \(Formato.percento(g.pVoto))%"
        }
        var parti = [g.nome, nomeRuolo(g.ruolo), (g.squadra ?? "").capitalized, dettaglio.components(separatedBy: " · ").dropFirst().joined(separator: ", ")]
        if g.assente == true {
            parti.append("assente")
        } else {
            parti.append("\(FantavotoAtteso.nome) \(numero)")
            parti.append("gioca al \(Formato.percento(g.pVoto)) per cento")
        }
        voce = parti.filter { !$0.isEmpty }.joined(separator: ", ")
    }

    /// Chi non è nell'elenco della giornata: «non gioca» solo se l'elenco è arrivato (`nonGioca`).
    init(_ b: GiocatoreBreve, nonGioca: Bool) {
        id = b.id; nome = b.nome; ruolo = b.ruolo; squadra = b.squadra
        dettaglio = Self.testoDettaglio(squadra: b.squadra, quotazione: b.quotazione, proprietario: nil)
        numero = "–"
        sotto = nonGioca ? Catalogo.Mercato.nonGioca : nil
        voce = [b.nome, nomeRuolo(b.ruolo), (b.squadra ?? "").capitalized, "quotazione \(b.quotazione.map { String(Formato.intero($0)) } ?? "–")",
                nonGioca ? Catalogo.Mercato.nonGioca : ""].filter { !$0.isEmpty }.joined(separator: ", ")
    }
}
