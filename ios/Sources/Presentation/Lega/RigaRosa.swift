import SwiftUI

/// Una riga della rosa: avatar con l'indice, nome, costo e quotazione, etichette e a destra il numero, come `valoreRosa` di app.js
/// e come `RigaGiocatore` (#367): fantavoto atteso e «gioca N%» prima della partita, fantavoto preso dopo (vedi `numero`).
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

    /// Il numero grande a destra della riga: prima della partita, e con la partita rinviata, il fantavoto atteso; a partita
    /// iniziata il fantavoto preso, o «–» se non c'è ancora (o non ci sarà). nil se il giocatore non ha previsione (allora a
    /// destra c'è solo `sottoNumero`: «non gioca» o «?»).
    nonisolated static func numero(_ g: GiocatoreRosa) -> String? {
        guard let p = g.previsione else { return nil }
        guard let esito = p.esitoPartita else { return Formato.punti(p.fvAtteso) }
        return Formato.punti(esito.fv)
    }

    /// La riga piccola sotto il numero: «gioca 72%» prima della partita, «fantavoto» (`mercato.fantavoto` della web) sotto il
    /// fantavoto preso; nil a partita iniziata senza voto, perché lo stato della partita lo dice già la pillola dell'etichetta.
    /// Senza previsione «non gioca», o «?» se il server non ha riconosciuto il giocatore.
    nonisolated static func sottoNumero(_ g: GiocatoreRosa) -> String? {
        guard let p = g.previsione else { return g.id == nil ? "?" : Catalogo.Scambio.nonGioca }
        guard let esito = p.esitoPartita else { return "gioca \(Formato.percento(p.pVoto))%" }
        return esito.fv == nil ? nil : Catalogo.Mercato.fantavoto
    }

    /// La frase letta da VoiceOver per tutta la riga: le stesse cose che si vedono. A partita iniziata «fantavoto 3,5» come la
    /// pedina del campo, o niente: il «–» non si legge e lo stato della partita arriva con le etichette, che la web legge in
    /// ogni caso (qui `children: .ignore` le nasconderebbe).
    nonisolated static func voce(_ g: GiocatoreRosa) -> String {
        var parti = [g.nome, nomeRuolo(g.ruolo ?? "")]
        let sotto = sottotitolo(g)
        if !sotto.isEmpty { parti.append(sotto) }
        if let p = g.previsione {
            if let esito = p.esitoPartita {
                if esito.fv != nil, let preso = esito.testo { parti.append(preso) }
            } else {
                parti.append("fantavoto atteso " + Formato.punti(p.fvAtteso))
            }
            parti.append(contentsOf: p.etichette.map { $0.testo.lowercased() })
        } else {
            parti.append(Catalogo.Scambio.nonGioca)
        }
        return parti.joined(separator: ", ")
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
                let sotto = Self.sottoNumero(g)
                if let numero = Self.numero(g) {
                    VStack(alignment: .trailing, spacing: 2) {
                        // il «–» di una partita iniziata senza voto è grigio come sulla web: lo stato lo dice la pillola
                        Text(numero).font(.headline).monospacedDigit()
                            .foregroundStyle(sotto == nil ? AnyShapeStyle(Color.testoSecondario) : AnyShapeStyle(.foreground))
                        if let sotto { Text(sotto).font(.caption2).foregroundStyle(Color.testoSecondario) }
                    }
                } else if let sotto {
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
