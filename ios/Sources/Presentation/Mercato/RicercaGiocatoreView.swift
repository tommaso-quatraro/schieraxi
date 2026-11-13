import SwiftUI

/// La ricerca di un giocatore per nome, la voce Cerca della barra (come la lente della web): un tocco apre la sua scheda.
struct RicercaGiocatoreView: View {
    @StateObject private var vm: RicercaViewModel

    init(server: any ServerClient) {
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
                        Text(RicercaViewModel.testoVuoto).foregroundStyle(Color.testoSecondario)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 40)
                    .listRowBackground(Color.clear)
                } else if vm.risultati.isEmpty && vm.errore == nil && !vm.cercando {
                    ContentUnavailableView(RicercaViewModel.testoNessuno, systemImage: "magnifyingglass")
                        .listRowBackground(Color.clear)
                }
                ForEach(vm.risultati) { g in
                    NavigationLink(value: PassoScheda.scheda(g.id)) { RigaRicerca(g) }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(Catalogo.Shell.cerca)
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $vm.testo, placement: .navigationBarDrawer(displayMode: .always), prompt: Catalogo.Avv.nomeDelGiocatore)
        .task(id: vm.testo) { await vm.cerca() }
    }
}
