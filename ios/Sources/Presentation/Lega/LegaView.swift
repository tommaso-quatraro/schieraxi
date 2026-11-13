import SwiftUI

/// Le schede Squadra e Altro: un elenco di voci, ognuna una pagina. Voci, ordine e testi sono quelli della web (`VoceMenuLega`,
/// da `VOCI_LEGA` di `fanta/web/app.js`). Account, aspetto, avvisi e novità stanno solo nelle Impostazioni (l'ingranaggio in
/// testata): ogni voce in un posto solo. Logica in `LegaViewModel`.
struct LegaView: View {
    @ObservedObject var vm: LegaViewModel
    /// `.squadra` o `.altro`: quali voci mostra.
    var ambito: Sezione = .altro
    @Environment(\.funzioni) private var funzioni

    @Environment(\.horizontalSizeClass) private var classe

    var body: some View {
        Group { if classe == .regular { colonne } else { pila } }
            .schermoProtetto()   // rose e nomi non devono comparire nell'anteprima del selettore delle app
    }

    /// Le pagine aperte in questa scheda (Squadra e Altro hanno ciascuna il suo percorso).
    private var percorso: Binding<[PaginaLega]> {
        ambito == .squadra ? $vm.percorsoSquadra : $vm.percorso
    }

    /// iPhone e finestre strette: una pila, come prima.
    private var pila: some View {
        NavigationStack(path: percorso) {
            elenco
                .navigationDestination(for: PaginaLega.self) { pagina in destinazione(pagina) }
        }
    }

    /// iPad e finestre larghe: l'elenco a sinistra, la pagina scelta a destra (le pagine che ne aprono altre restano nella colonna di destra).
    /// Il percorso resta quello della scheda: la prima pagina è la scelta nell'elenco, le altre stanno sopra nella colonna di destra.
    private var colonne: some View {
        NavigationSplitView {
            elenco
        } detail: {
            NavigationStack(path: percorsoSopra) {
                Group {
                    if let prima = percorso.wrappedValue.first {
                        destinazione(prima)
                    } else {
                        ContentUnavailableView("Scegli una voce", systemImage: "list.bullet.rectangle", description: Text(testoVuoto))
                    }
                }
                .navigationDestination(for: PaginaLega.self) { pagina in destinazione(pagina) }
            }
            // Cambiando voce nell'elenco la colonna di destra riparte pulita.
            .id(percorso.wrappedValue.first)
        }
        // Sull'iPad la colonna di destra non resta vuota («Scegli una voce»): si apre la prima voce utile della scheda.
        .onAppear {
            if percorso.wrappedValue.isEmpty { percorso.wrappedValue = [ambito == .squadra ? .squadre : .regole] }
        }
    }

    private var testoVuoto: String {
        ambito == .squadra
            ? "La tua squadra e le rose si aprono qui."
            : "Le regole della tua lega si aprono qui."
    }

    private var voceScelta: Binding<PaginaLega?> {
        Binding(
            get: { percorso.wrappedValue.first },
            set: { nuova in percorso.wrappedValue = nuova.map { [$0] } ?? [] }
        )
    }

    private var percorsoSopra: Binding<[PaginaLega]> {
        Binding(
            get: { Array(percorso.wrappedValue.dropFirst()) },
            set: { resto in
                guard let prima = percorso.wrappedValue.first else { return }
                percorso.wrappedValue = [prima] + resto
            }
        )
    }

    private var elenco: some View {
        List(selection: classe == .regular ? voceScelta : nil) {
            // come la web: l'avviso della nuova stagione in cima a Squadra e ad Altro, solo quando serve
            if vm.nuovaStagione { bannerStagione }
            if ambito == .squadra { sezioneSquadra } else { sezioneAltro }
        }
        .scrollContentBackground(.hidden)
        .contentMargins(.bottom, 24, for: .scrollContent)
        .background(Sfondo())
        .demoInFondo()
        .navigationTitle(ambito.titolo)
        // Sull'iPad (colonne) lente e ingranaggio li ha già la pagina a destra: due coppie una accanto all'altra confondevano.
        .ricercaGlobale(attiva: classe != .regular)
        .refreshable { await vm.carica() }
        .task { await vm.carica() }
    }

    @ViewBuilder
    private func destinazione(_ pagina: PaginaLega) -> some View {
        switch pagina {
        case .importa: ImportaExcelView(server: vm.server)
        case .squadre: SquadreView(server: vm.server)
        case .rosa(let nome): RosaView(nome: nome, server: vm.server)
        case .regole: RegoleEditorView(server: vm.server)
        case .avvisi: AvvisiServerView(server: vm.server, lega: vm)
        case .stato: StatoDatiView(server: vm.server, aggiornamento: vm.aggiornamento)
        case .stagione: StagioneView(server: vm.server)
        }
    }

    // MARK: sezioni

    private var bannerStagione: some View {
        Section {
            NavigationLink(value: PaginaLega.stagione) {
                VStack(alignment: .leading, spacing: 2) {
                    Label(Catalogo.Lega.nuovaStagioneN(s: vm.stagione.dato?.corrente ?? ""), systemImage: "calendar.badge.exclamationmark").font(.headline)
                    Text(Catalogo.Lega.bannerStagione(s: vm.stagione.dato?.rose ?? "")).font(.caption).foregroundStyle(Color.testoSecondario)
                }
                .frame(minHeight: 44)
                .accessibilityElement(children: .combine)
            }
        }
    }

    /// Squadra: le voci di `VOCI_LEGA` della web (la mia squadra e le rose, poi l'importazione delle rose).
    private var sezioneSquadra: some View {
        Section {
            // la pagina come identità della riga: è anche il valore della selezione nelle colonne dell'iPad
            ForEach(VoceMenuLega.voci(.squadra, funzioni: funzioni), id: \.pagina) { RigaVoceMenuLega(voce: $0) }
        }
    }

    /// Altro: le voci di `VOCI_LEGA` della web (le regole; il diario è la pagina Giornate).
    private var sezioneAltro: some View {
        Section {
            ForEach(VoceMenuLega.voci(.altro, funzioni: funzioni), id: \.pagina) { RigaVoceMenuLega(voce: $0) }
        }
    }
}

#Preview("Squadra") {
    LegaView(vm: LegaViewModel(server: FinteServer.esempio), ambito: .squadra)
}

#Preview("Altro") {
    LegaView(vm: LegaViewModel(server: FinteServer.esempio), ambito: .altro)
}
