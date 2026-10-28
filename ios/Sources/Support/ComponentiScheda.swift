import SwiftUI

extension Color {
    /// Colore della difficoltà di una partita: da 1 (facile, verde) a 5 (molto dura, rosso).
    static func difficolta(_ valore: Double?) -> Color {
        switch Formato.intero(valore ?? 3) {
        case ...1: return Color(red: 0.18, green: 0.82, blue: 0.50)
        case 2: return Color(red: 0.56, green: 0.83, blue: 0.29)
        case 3: return Color(red: 0.95, green: 0.78, blue: 0.27)
        case 4: return Color(red: 1.0, green: 0.60, blue: 0.24)
        default: return Color(red: 1.0, green: 0.36, blue: 0.31)
        }
    }
}

/// «Facile», «Media», «Dura»... con un pallino del colore giusto (il testo dice la stessa cosa del colore).
struct PillDifficolta: View {
    let difficolta: Double?

    static func nome(_ d: Double?) -> String {
        switch Formato.intero(d ?? 3) {
        case ...1: return "Facile"
        case 2: return "Abbordabile"
        case 3: return "Media"
        case 4: return "Dura"
        default: return "Molto dura"
        }
    }

    var body: some View {
        HStack(spacing: 5) {
            Circle().fill(Color.difficolta(difficolta)).frame(width: 9, height: 9)
            Text(Self.nome(difficolta)).font(.caption.weight(.semibold))
        }
        .padding(.horizontal, 8).padding(.vertical, 3)
        .background(Color.primary.opacity(0.08), in: Capsule())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Partita: \(Formato.difficolta(difficolta))")
    }
}

/// Un numero grande con la sua etichetta sotto (le «tessere» delle statistiche).
struct TesseraDato: View {
    let valore: String
    let etichetta: String

    var body: some View {
        VStack(spacing: 2) {
            Text(valore).font(.title3.bold()).monospacedDigit().minimumScaleFactor(0.7).lineLimit(1)
            Text(etichetta).font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(etichetta): \(valore)")
    }
}

/// Una fila di tessere: affiancate se ci stanno, altrimenti su due righe (con il testo grande).
struct FilaTessere<Contenuto: View>: View {
    let contenuto: Contenuto
    init(@ViewBuilder _ contenuto: () -> Contenuto) { self.contenuto = contenuto() }

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 8) { contenuto }
            // se non ci stanno in fila (colonna stretta, testo grande): a griglia, quante ne entrano per riga
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 120), spacing: 8, alignment: .top)], spacing: 12) { contenuto }
        }
    }
}

/// Barra orizzontale riempita fino a una percentuale (0-1): la probabilità di giocare.
struct BarraPercentuale: View {
    let valore: Double
    var colore: Color = .verde

    var body: some View {
        GeometryReader { g in
            ZStack(alignment: .leading) {
                Capsule().fill(Color.primary.opacity(0.12))
                Capsule().fill(colore).frame(width: g.size.width * CGFloat(min(1, max(0, valore))))
            }
        }
        .frame(height: 6)
        .accessibilityHidden(true)
    }
}

/// La riga delle prossime partite di una squadra, colorate per difficoltà (come la tabella del calendario).
struct ProssimePartite: View {
    let partite: [PartitaCalendario]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(partite) { p in
                    VStack(spacing: 1) {
                        Text(ColoriSquadra.sigla(p.avversario)).font(.caption.bold())
                        Text(p.inCasa == true ? "casa" : "fuori").font(.caption2)
                    }
                    .foregroundStyle(.black.opacity(0.8))
                    .frame(minWidth: 52, minHeight: 44)
                    .background(Color.difficolta(p.difficolta).opacity(0.85), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("Giornata \(p.giornata) contro \(p.avversario), \(p.inCasa == true ? "in casa" : "in trasferta"), \(Formato.difficolta(p.difficolta))")
                }
            }
        }
    }
}
