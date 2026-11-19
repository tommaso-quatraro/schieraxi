import SwiftUI

/// Una riga dei risultati della ricerca: ruolo e nome, sotto il club, a destra «quotazione N» (come la web). Con il testo molto grande
/// la quotazione va sotto il club e il nome ha tutta la larghezza; il nome va a capo, mai «…».
struct RigaRicerca: View {
    let dati: DatiRigaRicerca
    @Environment(\.dynamicTypeSize) private var tagliaTesto

    init(_ g: GiocatoreBreve) { dati = DatiRigaRicerca(g) }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    BadgeRuolo(ruolo: dati.ruolo, piccolo: true)
                    Text(dati.nome).font(.headline).fixedSize(horizontal: false, vertical: true)
                }
                if !dati.club.isEmpty {
                    Text(dati.club).font(.subheadline).foregroundStyle(Color.testoSecondario)
                }
                if tagliaTesto.isAccessibilitySize { quotazione }
            }
            Spacer(minLength: 8)
            if !tagliaTesto.isAccessibilitySize { quotazione }
        }
        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(dati.voce)
    }

    private var quotazione: some View {
        Text(dati.quotazione).font(.subheadline).monospacedDigit().foregroundStyle(Color.testoSecondario)
    }
}
