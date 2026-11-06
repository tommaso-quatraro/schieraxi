import SwiftUI

/// Stato dei dati: i gol attesi «nostri» senza Understat (#401), come la carta «Gol attesi nostri» della web (`cartaNostri` di
/// `fanta/web/app.js`), dopo il registro delle giornate e con le sue righe (`RigaMisuraRegistro`). In cima il verdetto delle tre misure
/// insieme, poi per ogni misura la media, la soglia e il verdetto del server; sotto, ripiegate, le giornate una per una (fino a 38).
struct GolAttesiNostriSezione: View {
    let nostri: StatoDati.RegistroNostri

    var body: some View {
        Section(titolo: ParoleNostri.titolo) {
            VStack(alignment: .leading, spacing: 4) {
                Text(ParoleNostri.spiega)
                Text(ParoleNostri.sottotitolo(nostri))
            }
            .font(.footnote)
            .foregroundStyle(Color.testoSecondario)
            if (nostri.giornate ?? 0) > 0 {
                let insieme = ParoleNostri.esitoInsieme(nostri)
                RigaMisuraRegistro(nome: ParoleNostri.insieme, esito: insieme, verdetto: ParoleNostri.testoInsieme(insieme))
                ForEach(ParoleNostri.Misura.allCases, id: \.self) { misura in
                    RigaMisuraRegistro(nome: ParoleNostri.nome(misura),
                                       esito: ParoleNostri.esito(misura, di: nostri),
                                       dettaglio: ParoleNostri.dettaglio(misura, di: nostri))
                }
            }
            if let giornate = nostri.perGiornata, !giornate.isEmpty {
                DisclosureGroup(ParoleNostri.perGiornata) {
                    ForEach(giornate) { g in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(ParoleNostri.giornata(g))
                            Text(ParoleNostri.stato(g, versione: nostri.versione))
                                .font(.footnote)
                                .foregroundStyle(ParoleNostri.persa(g) ? Color.esitoMalus : Color.testoSecondario)
                                .monospacedDigit()
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
    }
}
