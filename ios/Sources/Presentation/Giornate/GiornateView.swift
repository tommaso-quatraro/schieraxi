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
    @Environment(\.verticalSizeClass) private var classeVerticale
    /// La giornata di «Non è quello che ho schierato».
    @State private var daCorreggere: VoceDiario?
    /// Dopo la correzione VoiceOver torna sulla riga della giornata corretta.
    @AccessibilityFocusState private var fuoco: String?

    /// Elenco e dettaglio affiancati solo sull'iPad largo e alto (#919): un iPhone grande in orizzontale ha la larghezza «regular»
    /// ma è basso, e tiene la pagina del telefono.
    nonisolated static func elencoEDettaglio(orizzontale: UserInterfaceSizeClass?, verticale: UserInterfaceSizeClass?) -> Bool {
        SpazioIPad.largoEAlto(orizzontale: orizzontale, verticale: verticale)
    }

    var body: some View {
        Group { if Self.elencoEDettaglio(orizzontale: classe, verticale: classeVerticale) { colonne } else { pila } }
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
                    // le giornate insieme alla riga sotto il titolo, mai prima: la riga non sposta la lista già in vista (#913)
                    if let p = vm.paginaDaMostrare {
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
                    } else if vm.caricatore.dato == nil, let e = vm.caricatore.errore {
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
            // il titolo piccolo nella barra, fermo (#919): con quello grande, in orizzontale, scorrendo la colonna di destra il
            // titolo spariva senza lasciare quello piccolo e la colonna di sinistra saliva di ~50 punti con la barra
            .titoloPagina(Catalogo.Nav.giornate, piccoloInBarra: true)
        }
    }

    /// A sinistra la riga di stato, la frase sulla precisione con «Dettagli» e le giornate; la riga scelta è quella a destra.
    /// Niente lista con la selezione di iOS (#919): riempiva la riga scelta del colore principale e i testi grigi della riga non si
    /// leggevano più (foto della corsa 45760638734). Ogni riga è un pulsante e quella scelta ha il grigio dell'app.
    private var elencoIPad: some View {
        let pagina = vm.paginaDaMostrare   // con la riga sotto il titolo, come sul telefono (#913)
        let scelta = pagina?.aDestra(scelta: vm.scelta).id
        return List {
            capo
            if let p = pagina {
                testaIPad(p, scelta: scelta)
                if p.righe.isEmpty {
                    vuoto(p)
                } else {
                    Section {
                        ForEach(p.righe) { r in
                            rigaSceglibile(r.id, scelta: scelta) {
                                RigaGiornataView(riga: r)
                            }
                            .accessibilityFocused($fuoco, equals: r.id)
                        }
                    }
                }
            } else if vm.caricatore.dato == nil, let e = vm.caricatore.errore {
                ErroreVista(messaggio: e) { Task { await vm.carica() } }
            } else {
                ScheletroRighe(righe: 5).listRowBackground(Color.clear)
            }
        }
        .scrollContentBackground(.hidden)
        .refreshable { await vm.carica() }
    }

    /// Una riga dell'elenco dell'iPad che si sceglie con un tocco (una giornata o «Dettagli»). La scelta, cioè quella che sta a
    /// destra (`PaginaGiornate.aDestra`: la toccata, se no la più recente), ha il fondo grigio dell'app (`Color.rigaScelta`) e per
    /// VoiceOver è «selezionata». I testi hanno i loro colori: nome e punti quello del testo, non quello dei pulsanti.
    private func rigaSceglibile<Etichetta: View>(_ id: String, scelta: String?,
                                                 @ViewBuilder etichetta: () -> Etichetta) -> some View {
        let scelto = id == scelta
        return Button { vm.scelta = id } label: {
            etichetta()
                .foregroundStyle(Color.primary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
        }
        .listRowBackground(scelto ? Color.rigaScelta : nil)
        .accessibilityAddTraits(scelto ? .isSelected : [])
    }

    /// Sull'iPad la frase sulla precisione e la riga «Dettagli», che si sceglie come una giornata e apre i numeri a destra: la
    /// freccia dice che si tocca (#919).
    @ViewBuilder
    private func testaIPad(_ p: PaginaGiornate, scelta: String?) -> some View {
        if p.precisione != nil || p.dettagli != nil {
            Section {
                if let frase = p.precisione {
                    Text(frase)
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let titolo = p.titoloDettagli, p.dettagli != nil {
                    rigaSceglibile(PaginaGiornate.idDettagli, scelta: scelta) {
                        HStack(spacing: 8) {
                            Text(titolo)
                                .font(.subheadline.weight(.semibold))
                                .fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 0)
                            Image(systemName: "chevron.right")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(Color.testoSecondario)
                                .accessibilityHidden(true)
                        }
                        .frame(minHeight: Tema.areaTocco)
                    }
                }
            }
        }
    }

    /// A destra, larga al massimo come la colonna della web: il nome e gli 11 della giornata scelta (i punti e la frase li dice
    /// già la sua riga a sinistra), oppure i numeri di «Dettagli».
    private var dettaglioIPad: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let p = vm.paginaDaMostrare {
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
    /// dati (#863). La riga è l'intestazione di una sezione vuota, non una riga della lista: una riga sola fa una sezione con gli
    /// angoli tondi, che tagliavano la prima lettera di ogni riga di testo quando davanti non c'è lo stemma (#936).
    @ViewBuilder
    private var capo: some View {
        TitoloNellaPagina()
        if let riga = vm.rigaStato {
            Section {} header: { RigaStatoView(riga: riga) }
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
