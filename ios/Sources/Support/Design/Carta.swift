import SwiftUI

/// La scheda dei contenuti: fondo di sistema «raggruppato» (come Salute, Impostazioni, Borsa), angoli continui, nessun bordo.
/// Titolo in alto, con un simbolo SF facoltativo nel colore principale. Il vetro non si usa qui: tocca ai controlli.
struct Carta<Contenuto: View>: View {
    let titolo: String?
    let simbolo: String?
    let contenuto: Contenuto
    /// Lega > Aspetto > Densità: «compatta» stringe i margini delle schede (le aree di tocco restano da 44 pt).
    @AppStorage("densita") private var densita = "comoda"

    init(_ titolo: String? = nil, simbolo: String? = nil, @ViewBuilder contenuto: () -> Contenuto) {
        self.titolo = titolo
        self.simbolo = simbolo
        self.contenuto = contenuto()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: densita == "compatta" ? 8 : 12) {
            if let titolo {
                HStack(spacing: 8) {
                    if let simbolo {
                        Image(systemName: simbolo)
                            .symbolRenderingMode(.hierarchical)
                            .foregroundStyle(Color.verde)
                            .accessibilityHidden(true)
                    }
                    Text(titolo).font(.headline)
                }
                .accessibilityElement(children: .combine)
                .accessibilityAddTraits(.isHeader)
            }
            contenuto
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(densita == "compatta" ? 12 : 16)
        .background(Color.sfondoScheda, in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
    }
}

/// Una riga di elenco dentro una scheda, con il filo sottile sopra (tranne la prima).
struct RigaConFilo<Contenuto: View>: View {
    let primaria: Bool
    @ViewBuilder let contenuto: () -> Contenuto

    init(prima: Bool = false, @ViewBuilder contenuto: @escaping () -> Contenuto) {
        self.primaria = prima
        self.contenuto = contenuto
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if !primaria { Divider().padding(.leading, 58).padding(.bottom, 8) }
            contenuto()
        }
    }
}

/// Una piccola etichetta tonda (capsula) colorata: «Svincolato», «Titolare 90%»...
struct Capsula: View {
    let testo: String
    var colore: Color = .secondary
    var simbolo: String? = nil

    var body: some View {
        HStack(spacing: 5) {
            if let simbolo {
                Image(systemName: simbolo).imageScale(.small).foregroundStyle(colore).accessibilityHidden(true)
            } else {
                Circle().fill(colore).frame(width: 7, height: 7).accessibilityHidden(true)
            }
            Text(testo).foregroundStyle(.primary)
        }
        .font(.caption.weight(.semibold))
        .padding(.horizontal, 9).padding(.vertical, 4)
        .background(colore.opacity(0.18), in: Capsule())
    }
}
