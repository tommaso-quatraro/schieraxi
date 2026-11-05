import SwiftUI

/// Una riga della rosa: avatar con l'indice, nome, costo e quotazione, titolarità e a destra il numero (fantavoto atteso e
/// «gioca N%» prima della partita, vedi `numero`).
struct RigaRosa: View {
    let g: GiocatoreRosa
    @Environment(\.apriGiocatore) private var apri

    nonisolated private static func sottotitolo(_ g: GiocatoreRosa) -> String {
        var parti: [String] = []
        let s = ColoriSquadra.sigla(g.squadraSlug ?? g.previsione?.squadra ?? g.squadra)
        if !s.isEmpty { parti.append(s) }
        if let c = g.costo { parti.append("costo \(Formato.intero(c))") }
        if let q = g.quotazione { parti.append("quotazione \(Formato.intero(q))") }
        if let a = g.previsione?.avversario { parti.append("vs \(ColoriSquadra.sigla(a))") }
        return parti.joined(separator: " · ")
    }

    /// Il numero grande a destra della riga: il fantavoto atteso; nil se il giocatore non ha previsione (allora a destra c'è
    /// solo `sottoNumero`: «non gioca» o «?»).
    nonisolated static func numero(_ g: GiocatoreRosa) -> String? {
        guard let p = g.previsione else { return nil }
        return Formato.punti(p.fvAtteso)
    }

    /// La riga piccola sotto il numero: «gioca 72%»; senza previsione «non gioca», o «?» se il server non ha riconosciuto il giocatore.
    nonisolated static func sottoNumero(_ g: GiocatoreRosa) -> String? {
        guard let p = g.previsione else { return g.id == nil ? "?" : "non gioca" }
        return "gioca \(Formato.percento(p.pVoto))%"
    }

    /// La frase letta da VoiceOver per tutta la riga.
    nonisolated static func voce(_ g: GiocatoreRosa) -> String {
        var testo = "\(g.nome), \(nomeRuolo(g.ruolo ?? "")), \(sottotitolo(g))"
        if let p = g.previsione { testo += ", fantavoto atteso " + Formato.punti(p.fvAtteso) } else { testo += ", non gioca" }
        return testo
    }

    var body: some View {
        let p = g.previsione
        Button { if let id = g.id { apri(id) } } label: {
            HStack(spacing: 12) {
                AvatarGiocatore(id: g.id, squadra: g.squadraSlug ?? p?.squadra, indice: p?.indice, dimensione: 44, nome: g.nome, ruolo: g.ruolo)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        BadgeRuolo(ruolo: g.ruolo ?? "?", piccolo: true)
                        // intero, anche su più righe con il testo grande (#254)
                        Text(g.nome).font(.headline)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Text(Self.sottotitolo(g)).font(.caption).foregroundStyle(Color.testoSecondario)
                    if let etichette = p?.etichette, !etichette.isEmpty {
                        Text(etichette.map(\.testo).joined(separator: " · ")).font(.caption).foregroundStyle(etichette.contains { $0.gravita == .grave } ? Color.malus : Color.testoSecondario)
                    }
                }
                Spacer(minLength: 8)
                if let numero = Self.numero(g) {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(numero).font(.headline).monospacedDigit()
                        if let sotto = Self.sottoNumero(g) { Text(sotto).font(.caption2).foregroundStyle(Color.testoSecondario) }
                    }
                } else if let sotto = Self.sottoNumero(g) {
                    Text(sotto).font(.caption).foregroundStyle(Color.testoSecondario)
                }
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(Self.voce(g))
        }
        .buttonStyle(.plain)
        .disabled(g.id == nil)
    }
}
