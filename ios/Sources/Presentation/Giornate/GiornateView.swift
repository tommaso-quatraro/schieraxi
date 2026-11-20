import SwiftUI

/// La pagina Giornate (#673, passo 2), seconda nella barra come sulla web (#671): in cima una riga sola sulla precisione con
/// «Dettagli», poi una riga per giornata finita, dalla più recente, con i punti fatti e attesi della formazione che conta. Sul telefono
/// gli 11 si aprono sotto la riga (anche più giornate insieme); sull'iPad l'elenco sta a sinistra e la giornata scelta a destra, con la
/// più recente già aperta. Testi dal catalogo comune, numeri e frasi da `GET /api/diario` (`PaginaGiornate`).
struct GiornateView: View {
    @ObservedObject var vm: GiornateViewModel
    @EnvironmentObject private var nav: Navigazione
    @Environment(\.horizontalSizeClass) private var classe
    /// La giornata di «Non è quello che ho schierato».
    @State private var daCorreggere: VoceDiario?
    /// Dopo la correzione VoiceOver torna sulla riga della giornata corretta.
    @AccessibilityFocusState private var fuoco: String?

    var body: some View {
        Group { if classe == .regular { colonne } else { pila } }
            .sheet(item: $daCorreggere, onDismiss: { tornaAllaRiga() }) { v in
                FormazioneManualeDiarioView(voce: v, server: vm.server) { titolari in
                    await vm.correggi(v, titolari: titolari)
                }
            }
            .onAppear { prendiGiornataChiesta() }
            .onChange(of: nav.giornataDaAprire) { _, _ in prendiGiornataChiesta() }
            .task { await vm.carica() }
            .schermoProtetto()   // nomi e punti non devono comparire nell'anteprima del selettore delle app
    }

    // MARK: telefono

    private var pila: some View {
        NavigationStack {
            List {
                TitoloNellaPagina()
                if let p = vm.pagina {
                    testa(p)
                    if p.righe.isEmpty {
                        vuoto(p)
                    } else {
                        Section {
                            ForEach(p.righe) { r in
                                DisclosureGroup(isExpanded: aperta(r.id)) {
                                    if let d = p.dettaglio(r.id) {
                                        DettaglioGiornataView(dettaglio: d, esito: vm.esito(per: r.id)) { daCorreggere = p.voce(r.id) }
                                    }
                                } label: {
                                    RigaGiornataView(riga: r)
                                        .accessibilityFocused($fuoco, equals: r.id)
                                }
                                .tint(Color.testoSecondario)
                            }
                        }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Sfondo())
            .avvisoDatiSalvati(vm.caricatore)
            .titoloPagina(Catalogo.Nav.giornate)
            .refreshable { await vm.carica() }
        }
    }

    /// Una riga aperta o chiusa sul telefono.
    private func aperta(_ id: String) -> Binding<Bool> {
        Binding(get: { vm.aperte.contains(id) }, set: { aperta in
            if aperta != vm.aperte.contains(id) { vm.apriChiudi(id) }
        })
    }

    // MARK: iPad

    /// Elenco a sinistra, la giornata scelta a destra (una alla volta, la più recente già aperta).
    private var colonne: some View {
        NavigationSplitView {
            List(selection: sceltaIPad) {
                TitoloNellaPagina()
                if let p = vm.pagina {
                    testa(p)
                    if p.righe.isEmpty {
                        vuoto(p)
                    } else {
                        Section {
                            ForEach(p.righe) { r in
                                RigaGiornataView(riga: r)
                                    .accessibilityFocused($fuoco, equals: r.id)
                            }
                        }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Sfondo())
            .avvisoDatiSalvati(vm.caricatore)
            .titoloPagina(Catalogo.Nav.giornate)
            .refreshable { await vm.carica() }
        } detail: {
            NavigationStack {
                dettaglioIPad
            }
        }
    }

    /// La giornata scelta nell'elenco dell'iPad: quella toccata, se no la più recente.
    private var sceltaIPad: Binding<String?> {
        Binding(get: { vm.scelta ?? vm.pagina?.righe.first?.id }, set: { vm.scelta = $0 })
    }

    @ViewBuilder
    private var dettaglioIPad: some View {
        if let p = vm.pagina, let id = sceltaIPad.wrappedValue, let r = p.righe.first(where: { $0.id == id }), let d = p.dettaglio(id) {
            ScrollView {
                // i punti e la frase della giornata li dice già la riga scelta a sinistra: qui gli 11
                Carta {
                    DettaglioGiornataView(dettaglio: d, esito: vm.esito(per: id)) { daCorreggere = p.voce(id) }
                }
                .padding(Tema.margine)
                .frame(maxWidth: 720, alignment: .leading)
                .frame(maxWidth: .infinity)
            }
            .background(Sfondo())
            .navigationTitle(r.nome)
            .navigationBarTitleDisplayMode(.inline)
        } else {
            Sfondo()
        }
    }

    // MARK: parti comuni

    /// In cima una riga sola sulla precisione e, a richiesta, i numeri di «Quanto ci abbiamo preso».
    @ViewBuilder
    private func testa(_ p: PaginaGiornate) -> some View {
        if p.precisione != nil || p.dettagli != nil {
            Section {
                if let frase = p.precisione {
                    Text(frase)
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let titolo = p.titoloDettagli, let t = p.dettagli {
                    DisclosureGroup(isExpanded: $vm.dettagliAperti) {
                        PrecisioneView(testo: t)
                    } label: {
                        Text(titolo)
                            .font(.subheadline.weight(.semibold))
                            .frame(minHeight: Tema.areaTocco)
                    }
                    .tint(Color.testoSecondario)
                }
            }
        }
    }

    /// Nessuna giornata finita: il motivo che dice il server.
    private func vuoto(_ p: PaginaGiornate) -> some View {
        Section {
            Text(p.vuoto ?? Catalogo.Giornate.vuoto)
                .font(.subheadline).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// «Com'è andata» della Formazione: la giornata chiesta passa alla pagina, che la apre appena c'è.
    private func prendiGiornataChiesta() {
        guard let g = nav.giornataDaAprire else { return }
        nav.giornataDaAprire = nil
        vm.apri(giornata: g)
    }

    /// Chiuso il foglio della correzione, VoiceOver va sulla riga della giornata corretta (se è stata salvata).
    private func tornaAllaRiga() {
        guard let id = vm.prendiCorretta() else { return }
        fuoco = id
    }
}

#Preview("Giornate") {
    GiornateView(vm: GiornateViewModel(server: FinteServer.demo))
        .environmentObject(Navigazione())
}
