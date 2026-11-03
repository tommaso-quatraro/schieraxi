import SwiftUI

/// Un'etichetta di un giocatore («Probabile titolare», «In dubbio · gioca 62%») in una pillola del suo colore.
/// Su una riga se ci sta. Se no va a capo, mai tagliata con i puntini né rimpicciolita (issue #227): prima tra i pezzi
/// separati da «·» («In dubbio ·» sopra, «gioca 62%» sotto), e se nemmeno un pezzo ci sta, tra le parole.
struct PillolaEtichetta: View {
    let etichetta: Etichetta
    /// Angoli della pillola: su una riga è una capsula (il raggio supera metà altezza e si ferma lì); su più righe gli angoli
    /// restano tondi ma meno, come `.etichetta.lunga` della web. Cresce con il testo.
    @ScaledMetric(relativeTo: .caption2) private var raggio: CGFloat = 10

    /// Le righe di un testo a pezzi: «In dubbio · gioca 62%» → «In dubbio ·» e «gioca 62%» (il «·» resta in fondo alla
    /// riga, come in `TestoACapo`). Un testo senza «·» è una riga sola.
    nonisolated static func righe(_ testo: String) -> [String] {
        let pezzi = testo.components(separatedBy: TestoACapo.separatore)
        return pezzi.enumerated().map { i, pezzo in i < pezzi.count - 1 ? pezzo + " ·" : pezzo }
    }

    var body: some View {
        let righe = Self.righe(etichetta.testo)
        ViewThatFits(in: .horizontal) {
            Text(etichetta.testo).lineLimit(1)
            if righe.count > 1 {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(righe.enumerated()), id: \.offset) { riga in
                        Text(riga.element).lineLimit(1)
                    }
                }
            }
            // ultima scelta: a capo tra le parole
            Text(etichetta.testo)
        }
        .font(.caption2.weight(.semibold))
        .foregroundStyle(etichetta.gravita.colore)
        .padding(.horizontal, 7).padding(.vertical, 2)
        .background(etichetta.gravita.colore.opacity(0.14), in: .rect(cornerRadius: raggio, style: .continuous))
    }
}
