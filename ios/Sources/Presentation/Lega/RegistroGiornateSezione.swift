import SwiftUI

/// Stato dei dati: il registro delle giornate (#344), come la carta «Registro delle giornate» della web (`cartaRegistro` di
/// `fanta/web/app.js`). Per ogni misura la media, la soglia e il verdetto del server; poi le giornate perse con il motivo.
struct RegistroGiornateSezione: View {
    let registro: StatoDati.Registro

    var body: some View {
        Section(titolo: ParoleRegistro.titolo) {
            VStack(alignment: .leading, spacing: 4) {
                Text(ParoleRegistro.spiega)
                Text(ParoleRegistro.sottotitolo(registro))
            }
            .font(.footnote)
            .foregroundStyle(Color.testoSecondario)
            if (registro.giornate ?? 0) > 0 {
                ForEach(ParoleRegistro.Misura.allCases, id: \.self) { misura in
                    RigaMisuraRegistro(nome: ParoleRegistro.nome(misura),
                                       esito: ParoleRegistro.esito(misura, di: registro),
                                       dettaglio: ParoleRegistro.dettaglio(misura, di: registro))
                }
            }
        }
        let perse = ParoleRegistro.perse(registro)
        if !perse.isEmpty {
            Section(titolo: ParoleRegistro.titoloPerse) {
                Text(ParoleRegistro.spiegaPerse)
                    .font(.footnote)
                    .foregroundStyle(Color.testoSecondario)
                ForEach(perse) { giornata in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(ParoleRegistro.giornata(giornata))
                        Text(giornata.persa ?? "")
                            .font(.footnote)
                            .foregroundStyle(Color.esitoMalus)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}
