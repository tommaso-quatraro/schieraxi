import SwiftUI

/// Uno dei due giocatori in cima a «Chi schierare?»: volto, nome, partita e «Consigliato» se è lui da schierare.
struct ColonnaDuello: View {
    let g: Giocatore
    let scelto: Bool

    var body: some View {
        VStack(spacing: 6) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, indice: g.indice, dimensione: 64, nome: g.nome, ruolo: g.ruolo)
            // intero, anche su più righe con il testo grande: mai «…» (#254, `NomiInteriTests`)
            Text(g.nome).font(.headline).multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            Text(Self.partita(g)).font(.caption).foregroundStyle(Color.testoSecondario)
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

    /// La partita sotto il nome, come la web (`partitaRiga`, #302): «INT vs ROM» in casa, «INT @ ROM» in trasferta, prima la squadra
    /// del giocatore; senza avversario solo la sua sigla.
    static func partita(_ g: Giocatore) -> String {
        let mia = ColoriSquadra.sigla(g.squadra), altra = ColoriSquadra.sigla(g.avversario)
        guard !altra.isEmpty else { return mia }
        return "\(mia) \(g.inCasa == true ? "vs" : "@") \(altra)"
    }
}
