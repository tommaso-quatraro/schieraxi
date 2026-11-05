import SwiftUI

/// «Tutti i numeri» di «Chi schierare?»: indice, partita, probabilità e punti attesi dei due giocatori, uno accanto all'altro.
struct TabellaNumeriConfronto: View {
    let x: Giocatore
    let y: Giocatore

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Spacer()
                Text(x.nomeCorto).font(.caption.bold()).lineLimit(1).frame(width: 80, alignment: .trailing)
                Text(y.nomeCorto).font(.caption.bold()).lineLimit(1).frame(width: 80, alignment: .trailing)
            }
            .accessibilityHidden(true)
            riga("Indice") { "\(Formato.intero($0.indice))" }
            riga("Avversario") { "\(ColoriSquadra.sigla($0.avversario)) \($0.inCasa == true ? "casa" : "fuori")" }
            riga("Partita") { PillDifficolta.nome($0.difficolta) }
            riga("Gioca") { "\(Formato.percento($0.pVoto))%" }
            riga("Fantavoto atteso (se gioca)") { Formato.punti($0.fvAtteso) }
            riga("Punti attesi") { Formato.decimali($0.puntiAttesi, cifre: 2) }
            riga("Parte titolare") { "\(Formato.percento($0.quotaTitolare))%" }
            riga("Segna") { "\(Formato.percento($0.pGol))%" }
            riga("Assist") { "\(Formato.percento($0.pAssist))%" }
            riga("Giallo") { "\(Formato.percento($0.pGiallo))%" }
        }
    }

    private func riga(_ titolo: String, _ f: (Giocatore) -> String) -> some View {
        HStack {
            Text(titolo).foregroundStyle(Color.testoSecondario).frame(maxWidth: .infinity, alignment: .leading)
            Text(f(x)).bold().monospacedDigit().frame(width: 80, alignment: .trailing)
            Text(f(y)).bold().monospacedDigit().frame(width: 80, alignment: .trailing)
        }
        .font(.subheadline)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(titolo): \(x.nomeCorto) \(f(x)), \(y.nomeCorto) \(f(y))")
    }
}
