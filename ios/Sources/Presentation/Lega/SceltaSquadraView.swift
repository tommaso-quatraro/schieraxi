import SwiftUI

/// «La mia squadra» quando non è ancora scelta, come `vistaRosa("")` della web senza la mia squadra (#863): «Scegli quale delle
/// squadre è la tua.» e il selettore. Scelta la squadra, al posto di questa pagina c'è la sua rosa (`LegaViewModel.scegliMiaSquadra`),
/// come la web che ridisegna «La mia squadra». Senza rose la frase della web e «Aggiorna le rose». Prima la scelta stava in cima a
/// «Squadre e rose», con «È la mia» sulle righe.
struct SceltaSquadraView: View {
    /// Le squadre della lega (`LegaViewModel.squadre`).
    @ObservedObject var squadre: Caricatore<[SquadraLega]>
    /// Salva la squadra scelta come mia: nil se è andata bene, se no il motivo.
    let scegli: @MainActor (String) async -> String?

    var body: some View {
        ZStack {
            Sfondo()
            List {
                TitoloNellaPagina()
                if let s = squadre.dato {
                    Section {
                        if s.isEmpty {
                            // senza rose, come la web: la frase e «Aggiorna le rose», la stessa pagina della riga di Impostazioni
                            Text(ParoleSquadre.importaPrima).foregroundStyle(Color.testoSecondario)
                            NavigationLink(value: PaginaImpostazioni.importa) {
                                Label(Catalogo.Lega.voceImporta, systemImage: "square.and.arrow.down").frame(minHeight: Tema.areaTocco)
                            }
                        } else {
                            Text(ParoleSquadre.scegliLaTua).foregroundStyle(Color.testoSecondario)
                            SelettoreMiaSquadra(squadre: s, scegli: scegli)
                        }
                    }
                } else if let e = squadre.errore {
                    ErroreVista(messaggio: e) { Task { await squadre.ricarica() } }
                } else {
                    ScheletroRighe(righe: 2).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .avvisoDatiSalvati(squadre)
        }
        .titoloPagina(ParoleSquadre.miaSquadra)
        .task { await squadre.ricarica() }
    }
}

#Preview("La mia squadra da scegliere") {
    NavigationStack {
        SceltaSquadraView(squadre: Caricatore<[SquadraLega]>("/api/squadre", server: FinteServer.esempio)) { _ in nil }
    }
}
