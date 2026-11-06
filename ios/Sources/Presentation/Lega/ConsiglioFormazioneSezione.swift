import SwiftUI

/// Stato dei dati: gli indicatori del consiglio di formazione (#366), come la carta «Consiglio di formazione» della web
/// (`cartaConsiglio` di `fanta/web/app.js`). Per ogni indicatore la media, la soglia e il verdetto del server, con le stesse righe
/// del registro delle giornate (`RigaMisuraRegistro`).
struct ConsiglioFormazioneSezione: View {
    let consiglio: StatoDati.Consiglio

    var body: some View {
        Section(titolo: ParoleConsiglio.titolo) {
            VStack(alignment: .leading, spacing: 4) {
                Text(ParoleConsiglio.spiega)
                Text(ParoleConsiglio.sottotitolo(consiglio))
            }
            .font(.footnote)
            .foregroundStyle(Color.testoSecondario)
            if (consiglio.giornate ?? 0) > 0 {
                ForEach(ParoleConsiglio.Indicatore.allCases, id: \.self) { indicatore in
                    RigaMisuraRegistro(nome: ParoleConsiglio.nome(indicatore),
                                       esito: ParoleConsiglio.esito(indicatore, di: consiglio),
                                       dettaglio: ParoleConsiglio.dettaglio(indicatore, di: consiglio))
                }
            }
        }
    }
}
