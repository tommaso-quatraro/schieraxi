import SwiftUI

/// Uno dei due giocatori in cima a «Chi schierare?»: volto, nome, partita e «Consigliato» se è lui da schierare.
struct ColonnaDuello: View {
    let g: Giocatore
    let scelto: Bool

    var body: some View {
        VStack(spacing: 6) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, indice: g.indice, dimensione: 64, nome: g.nome, ruolo: g.ruolo)
            Text(g.nome).font(.headline).multilineTextAlignment(.center).lineLimit(2)
            Text("\(ColoriSquadra.sigla(g.squadra)) – \(ColoriSquadra.sigla(g.avversario)) \(g.inCasa == true ? "casa" : "fuori")")
                .font(.caption).foregroundStyle(Color.testoSecondario)
            if scelto {
                Label("Consigliato", systemImage: "checkmark.seal.fill").font(.caption.bold()).foregroundStyle(Color.verde)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(10)
        .background(scelto ? Color.verde.opacity(0.14) : Color.clear, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo + 2, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(g.nome), \(nomeRuolo(g.ruolo)), indice \(Formato.intero(g.indice)), punti attesi \(Formato.punti(g.puntiAttesi))\(scelto ? ", consigliato" : "")")
    }
}
