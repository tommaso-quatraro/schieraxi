import SwiftUI

/// Una riga dei risultati della ricerca: volto, nome, «GEN · quotazione 19 · svincolato», fantavoto atteso e «gioca N%»
/// (come la riga compatta della web).
struct RigaElencoGiocatore: View {
    let dati: DatiRigaElenco
    @Environment(\.dynamicTypeSize) private var tagliaTesto
    @ScaledMetric(relativeTo: .body) private var lato: CGFloat = 46

    init(g: Giocatore) { dati = DatiRigaElenco(g) }
    init(breve: GiocatoreBreve, nonGioca: Bool) { dati = DatiRigaElenco(breve, nonGioca: nonGioca) }

    @ViewBuilder
    private var numeri: some View {
        if tagliaTesto.isAccessibilitySize {
            // testo molto grande: i numeri sotto il nome, su una riga, e il nome ha tutta la larghezza
            HStack(spacing: 8) {
                Text(dati.numero).font(.headline).monospacedDigit()
                if let sotto = dati.sotto { Text(sotto).font(.caption).foregroundStyle(Color.testoSecondario) }
            }
        } else {
            VStack(alignment: .trailing, spacing: 2) {
                Text(dati.numero).font(.title3.weight(.bold)).monospacedDigit()
                if let sotto = dati.sotto { Text(sotto).font(.caption2).foregroundStyle(Color.testoSecondario) }
            }
        }
    }

    var body: some View {
        HStack(alignment: tagliaTesto.isAccessibilitySize ? .top : .center, spacing: 12) {
            AvatarGiocatore(id: dati.id, squadra: dati.squadra, dimensione: min(lato, 64), nome: dati.nome, ruolo: dati.ruolo)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    BadgeRuolo(ruolo: dati.ruolo, piccolo: true)
                    // il nome intero: con il testo grande va a capo, mai «…» (#247)
                    Text(dati.nome).font(.headline).fixedSize(horizontal: false, vertical: true)
                }
                Text(dati.dettaglio).font(.caption).foregroundStyle(Color.testoSecondario)
                if tagliaTesto.isAccessibilitySize { numeri }
            }
            Spacer(minLength: 8)
            if !tagliaTesto.isAccessibilitySize { numeri }
        }
        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(dati.voce)
    }
}
