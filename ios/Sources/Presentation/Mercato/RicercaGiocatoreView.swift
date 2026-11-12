import SwiftUI

/// Ricerca di un giocatore per nome (la lente accanto al titolo di ogni schermata): un tocco apre la sua scheda.
struct RicercaGiocatoreView: View {
    let titolo: String
    @StateObject private var vm: RicercaViewModel

    init(titolo: String, server: any ServerClient) {
        self.titolo = titolo
        _vm = StateObject(wrappedValue: RicercaViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let e = vm.errore { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
                if vm.testo.trimmingCharacters(in: .whitespaces).count < 2 {
                    VStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").font(.largeTitle).foregroundStyle(Color.testoSecondario).accessibilityHidden(true)
                        Text("Scrivi almeno due lettere del nome.").foregroundStyle(Color.testoSecondario)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 40)
                    .listRowBackground(Color.clear)
                } else if vm.risultati.isEmpty && vm.errore == nil && !vm.cercando {
                    ContentUnavailableView.search(text: vm.testo).listRowBackground(Color.clear)
                }
                ForEach(vm.risultati) { g in
                    NavigationLink(value: PassoScheda.scheda(g.id)) { riga(g) }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(titolo)
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $vm.testo, placement: .navigationBarDrawer(displayMode: .always), prompt: "Nome del giocatore")
        .task(id: vm.testo) { await vm.cerca() }
    }

    /// Volto, fantavoto atteso e «gioca N%» dall'elenco largo della giornata; chi non c'è ha «–».
    @ViewBuilder
    private func riga(_ b: GiocatoreBreve) -> some View {
        if let g = vm.previsioni.di(b.id) {
            RigaElencoGiocatore(g: g)
        } else {
            RigaElencoGiocatore(breve: b, nonGioca: vm.previsioni.arrivate)
        }
    }
}
