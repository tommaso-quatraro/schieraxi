import SwiftUI

/// Gli 11 di una giornata finita (`dettaglioGiornata` della web): il titolo con il modulo, i titolari con il fantavoto atteso e quello
/// preso, cosa hai cambiato rispetto alla consigliata e un solo pulsante, «Non è quello che ho schierato». Tutto viene già pronto da
/// `PaginaGiornate.dettaglio`: qui non si calcola niente.
struct DettaglioGiornataView: View {
    let dettaglio: DettaglioGiornata
    /// L'esito dell'ultima correzione di questa giornata («Salvato: …»), se c'è.
    var esito: String? = nil
    let correggi: () -> Void
    @Environment(\.dynamicTypeSize) private var dimensione

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(dettaglio.titolo)
                .font(.headline)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            if let nota = dettaglio.nota {
                Text(nota)
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            // con il testo molto grande tre colonne non ci stanno: un giocatore per riga, i due numeri sotto il nome
            if dimensione.isAccessibilitySize { elencoImpilato } else { tabella }
            if let cambi = dettaglio.cambi {
                Text(cambi)
                    .font(.subheadline)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let senza = dettaglio.senzaConfronto {
                Text(senza)
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let esito {
                Label(esito, systemImage: "checkmark.circle.fill")
                    .font(.footnote.weight(.semibold)).foregroundStyle(Color.verde)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if dettaglio.correggibile {
                Button(action: correggi) {
                    Text(Catalogo.Giornate.correggi)
                        .multilineTextAlignment(.leading)
                        .frame(minHeight: Tema.areaTocco)
                }
                .pulsanteVetro()
            }
        }
        .padding(.vertical, 6)
    }

    /// Tre colonne, come la tabella della web: Giocatore, Atteso, Preso. VoiceOver legge una riga intera sul nome.
    private var tabella: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 8) {
            GridRow {
                Text(Catalogo.Giornate.colGiocatore)
                Text(Catalogo.Giornate.colAtteso).gridColumnAlignment(.trailing)
                Text(Catalogo.Giornate.colPreso).gridColumnAlignment(.trailing)
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(Color.testoSecondario)
            .accessibilityHidden(true)
            Divider()
            ForEach(dettaglio.titolari) { t in
                GridRow {
                    HStack(spacing: 8) {
                        BadgeRuolo(ruolo: t.ruolo, piccolo: true)
                        Text(t.nome)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(t.voce)
                    Text(t.atteso)
                        .monospacedDigit()
                        .accessibilityHidden(true)
                    Text(t.preso)
                        .monospacedDigit()
                        .foregroundStyle(t.senzaVoto ? Color.testoSecondario : Color.primary)
                        .multilineTextAlignment(.trailing)
                        .accessibilityHidden(true)
                }
                .font(.subheadline)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(Catalogo.Giornate.tabella)
    }

    /// Con il testo molto grande: il nome su una riga, sotto «Atteso 6,8 · Preso 7,5».
    private var elencoImpilato: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(dettaglio.titolari) { t in
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 8) {
                        BadgeRuolo(ruolo: t.ruolo, piccolo: true)
                        Text(t.nome).font(.subheadline.weight(.semibold))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Text("\(Catalogo.Giornate.colAtteso) \(t.atteso) · \(Catalogo.Giornate.colPreso) \(t.preso)")
                        .font(.subheadline).monospacedDigit()
                        .foregroundStyle(Color.testoSecondario)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(t.voce)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(Catalogo.Giornate.tabella)
    }
}

#Preview("Una giornata aperta") {
    List {
        DettaglioGiornataView(dettaglio: DettaglioGiornata(
            titolo: Catalogo.Giornate.formazioneTua(modulo: "3-4-3"), nota: nil,
            titolari: [TitolareGiornata(id: 1, nome: "Sorvani", ruolo: "P", atteso: "6,1", preso: "5,5", senzaVoto: false),
                       TitolareGiornata(id: 2, nome: "Bastrani", ruolo: "D", atteso: "6,0", preso: Catalogo.Giornate.senzaVoto,
                                        senzaVoto: true),
                       TitolareGiornata(id: 3, nome: "Leonel", ruolo: "A", atteso: "7,4", preso: "10,5", senzaVoto: false)],
            cambi: Catalogo.Giornate.alPosto(dentro: "Orsetti", fuori: "Dunfrey"), senzaConfronto: nil, correggibile: true)) {}
    }
}
