import SwiftUI

/// Fase `in_corso` per chi è entrato a giornata iniziata senza una formazione (`senza_formazione`), come `cardSenzaFormazione`
/// della web (#436): niente punti, la prossima giornata e «Prepara la prossima», che apre la Formazione (già quella della prossima).
struct CartaSenzaFormazione: View {
    let prossima: ProssimaGiornata?
    @Environment(\.vaiASezione) private var vaiASezione

    var body: some View {
        Carta(TestiFase.giaIniziata) {
            Text(TestiFase.giaIniziataTesto).font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
            if let p = prossima, let riga = TestiFase.prossima(p) {
                Text(riga).font(.subheadline).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Button(action: preparaProssima) {
                Label(TestiFase.preparaProssima, systemImage: "sportscourt").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
        }
    }

    private func preparaProssima() { vaiASezione(.formazione) }
}

#Preview("Giornata già iniziata") {
    CartaSenzaFormazione(prossima: ProssimaGiornata(giornata: 12, giornataLega: 9, scadenza: "2026-11-14 14:30", preparaDa: "2026-11-11 14:30"))
        .padding()
        .background(Color.sfondoBase)
}
