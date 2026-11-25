import SwiftUI

/// La riga sotto il titolo di Giornate, come la riga di stato della web (`rigaStato` di `app.js`, #863): lo stemma della mia squadra,
/// se c'è, e «Giornata 13 · 13ª di Serie A · Real Esempio · dati del 26 ott 23:55». Ogni pezzo sta intero: se la riga non ci sta si
/// va a capo dopo un « · », come la web (`FilaPillole`). In una lista: allineata al bordo delle schede, senza fondo né filo, come
/// `TitoloNellaPagina`. VoiceOver la legge in una volta (`RigaStato.voce`).
struct RigaStatoView: View {
    let riga: RigaStato
    @ObservedObject private var immagini = Immagini.condivise
    @ScaledMetric(relativeTo: .footnote) private var lato: CGFloat = 20

    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            // lo stemma solo quando c'è davvero, come la web: senza, il testo parte dal bordo
            if let mia = riga.squadra, immagini.memoriaSquadra(mia, tipo: "stemma") != nil {
                StemmaSquadra(nome: mia, dimensione: lato)
            }
            FilaPillole(spazio: 4) {
                ForEach(Array(pezziConPunto.enumerated()), id: \.offset) { _, pezzo in
                    Text(pezzo)
                }
            }
        }
        .font(.footnote)
        .foregroundStyle(Color.testoSecondario)
        .frame(maxWidth: .infinity, alignment: .leading)
        .task(id: riga.squadra.flatMap { immagini.squadre[$0] }) {
            // lo stemma si chiede anche se non è ancora in memoria (dopo lo svuotamento dei dati, #824): arrivato, compare
            if let mia = riga.squadra { await immagini.caricaSquadra(mia, tipo: "stemma") }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(riga.voce)
        .listRowInsets(EdgeInsets())
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
    }

    /// I pezzi con « ·» in fondo a tutti tranne l'ultimo: andando a capo il punto resta sulla riga di sopra, come sulla web.
    private var pezziConPunto: [String] {
        riga.pezzi.enumerated().map { i, pezzo in i < riga.pezzi.count - 1 ? pezzo + " ·" : pezzo }
    }
}

#Preview("Riga sotto il titolo di Giornate") {
    let json = #"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest", "ultimo_aggiornamento": "2026-10-26T23:55:13"}"#
    if let info: InfoServer = try? Decodifica.decodifica(Data(json.utf8)), let riga = RigaStato(info: info, nonRaggiungibile: false) {
        List { RigaStatoView(riga: riga) }
    }
}
