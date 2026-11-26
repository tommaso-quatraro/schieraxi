import SwiftUI

/// La pagina Giornate (#673, passo 2), seconda nella barra come sulla web (#671): sotto il titolo la riga della web con giornata,
/// mia squadra e data dei dati (#863), una riga sola sulla precisione con «Dettagli», poi una riga per giornata finita, dalla più
/// recente, con i punti fatti e attesi della formazione che conta. Sul telefono gli 11 si aprono sotto la riga (anche più giornate
/// insieme); sull'iPad l'elenco sta a sinistra e la giornata scelta (o «Dettagli») a destra, con la più recente già aperta, come la
/// web larga (#896). Testi dal catalogo comune, numeri e frasi da `GET /api/diario` (`PaginaGiornate`) e `GET /api/stato`
/// (`RigaStato`).
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
            ScrollViewReader { proxy in
                List {
                    capo
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
                .demoScorriAlConfronto(proxy: proxy, pronto: vm.cimaCompleta)   // foto `giornate-confronto` (#842)
            }
        }
    }

    /// Una riga aperta o chiusa sul telefono.
    private func aperta(_ id: String) -> Binding<Bool> {
        Binding(get: { vm.aperte.contains(id) }, set: { aperta in
            if aperta != vm.aperte.contains(id) { vm.apriChiudi(id) }
        })
    }

    // MARK: iPad

    /// Come la web larga (#896): una pagina sola con l'elenco a sinistra, largo come quello della web, e a destra la giornata
    /// scelta (la più recente già aperta) o i numeri di «Dettagli», che prima si aprivano nella colonna stretta dell'elenco
    /// lasciando vuota la metà destra. Niente `NavigationSplitView` dentro la barra laterale: in orizzontale faceva tre colonne con
    /// due pulsanti uguali per la barra.
    private var colonne: some View {
        NavigationStack {
            ElencoEDettaglio {
                elencoIPad
                ScrollViewReader { proxy in
                    // foto `giornate-confronto` (#842): i Dettagli stanno qui a destra, con il loro scorrimento; si aspetta la cima
                    // completa come sul telefono (#912), anche se qui la riga sotto il titolo sta a sinistra e non sposta la colonna
                    dettaglioIPad
                        .demoScorriAlConfronto(proxy: proxy, pronto: vm.cimaCompleta)
                }
            }
            .background(Sfondo())
            .avvisoDatiSalvati(vm.caricatore)
            .titoloPagina(Catalogo.Nav.giornate)
        }
    }

    /// A sinistra la riga di stato, la frase sulla precisione con «Dettagli» e le giornate; la riga scelta è quella a destra.
    private var elencoIPad: some View {
        List(selection: sceltaIPad) {
            capo
            if let p = vm.pagina {
                testaIPad(p)
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
        .refreshable { await vm.carica() }
    }

    /// La riga scelta nell'elenco dell'iPad: quella toccata (una giornata o «Dettagli»), se no la più recente
    /// (`PaginaGiornate.aDestra`).
    private var sceltaIPad: Binding<String?> {
        Binding(get: { vm.pagina?.aDestra(scelta: vm.scelta).id }, set: { vm.scelta = $0 })
    }

    /// Sull'iPad la frase sulla precisione e la riga «Dettagli», che si sceglie come una giornata e apre i numeri a destra.
    @ViewBuilder
    private func testaIPad(_ p: PaginaGiornate) -> some View {
        if p.precisione != nil || p.dettagli != nil {
            Section {
                if let frase = p.precisione {
                    Text(frase)
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let titolo = p.titoloDettagli, p.dettagli != nil {
                    Text(titolo)
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                        .contentShape(Rectangle())
                        .tag(PaginaGiornate.idDettagli)
                }
            }
        }
    }

    /// A destra, larga al massimo come la colonna della web: il nome e gli 11 della giornata scelta (i punti e la frase li dice
    /// già la sua riga a sinistra), oppure i numeri di «Dettagli».
    private var dettaglioIPad: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let p = vm.pagina {
                    switch p.aDestra(scelta: vm.scelta) {
                    case .dettagli:
                        if let t = p.dettagli {
                            Carta(p.titoloDettagli) {
                                PrecisioneView(testo: t)
                                    .id(ConfrontoDemo.idDettagli)   // dove arriva la foto `giornate-confronto` (solo demo, #842)
                            }
                        }
                    case .giornata(let id):
                        if let r = p.righe.first(where: { $0.id == id }), let d = p.dettaglio(id) {
                            Text(r.nome)
                                .font(.title3.weight(.semibold))
                                .fixedSize(horizontal: false, vertical: true)
                                .accessibilityAddTraits(.isHeader)
                            Carta {
                                DettaglioGiornataView(dettaglio: d, esito: vm.esito(per: id)) { daCorreggere = p.voce(id) }
                            }
                        }
                    case .niente:
                        EmptyView()
                    }
                }
            }
            .padding(Tema.margine)
            .frame(maxWidth: ElencoEDettaglio.dettaglioMassimo, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
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
                            .id(ConfrontoDemo.idDettagli)   // dove arriva la foto `giornate-confronto` (solo demo, #842)
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

    /// In cima alla lista il titolo intero (solo con il testo grande) e sotto la riga della web: giornata, mia squadra e data dei
    /// dati (#863).
    @ViewBuilder
    private var capo: some View {
        TitoloNellaPagina()
        if let riga = vm.rigaStato { RigaStatoView(riga: riga) }
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
