import SwiftUI

/// La configurazione guidata («Primo avvio», come si chiama sulla web): un passo alla volta, tutti saltabili, con un riepilogo
/// alla fine. I passi sono quelli dell'iPhone (la web ne ha altri): titolo, «Salta» e il riepilogo hanno le parole della web.
/// Parte da sola se la lega non ha ancora le rose e non è mai stata iniziata (con gli account, se nemmeno la vecchia procedura è
/// finita: #600), o si riprende se era stata lasciata prima delle rose (anche sulla web), come la web (#595); si apre anche dalla
/// lista «Da fare» di Oggi. Salta i passi già fatti.
struct ConfigurazioneGuidataView: View {
    @StateObject private var vm: ConfigurazioneGuidataViewModel
    /// Cosa fare quando un passo porta in un'altra schermata (la guida si chiude prima).
    let vai: (AzioneGuida) -> Void
    /// Vero se il foglio l'ha chiuso l'app e non l'utente (sessione finita o cambiata, un file arrivato da fuori): alla chiusura
    /// i passi rimasti non diventano saltati.
    let chiusaDallApp: @MainActor () -> Bool
    @Environment(\.dismiss) private var chiudi
    @Environment(\.accessibilityReduceMotion) private var ridotto

    init(server: any ServerClient, vai: @escaping (AzioneGuida) -> Void, chiusaDallApp: @escaping @MainActor () -> Bool = { false }) {
        _vm = StateObject(wrappedValue: ConfigurazioneGuidataViewModel(server: server))
        self.vai = vai
        self.chiusaDallApp = chiusaDallApp
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                switch vm.fase {
                case .carica:
                    ScrollView { Scheletro(schede: 1, righe: 3, testo: "Preparo la configurazione…").padding(Tema.margine) }
                case .errore(let messaggio):
                    ScrollView { ErroreVista(messaggio: messaggio) { Task { await vm.carica() } }.padding(Tema.margine) }
                case .pronta:
                    ScrollView {
                        VStack(spacing: 20) {
                            if let passo = vm.passoCorrente {
                                pagina(passo)
                                    .id(passo)
                                    .transition(ridotto ? .opacity : .asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity), removal: .opacity))
                            } else {
                                riepilogo
                            }
                            if let avviso = vm.avviso {
                                Label(avviso, systemImage: "info.circle").font(.footnote).foregroundStyle(Color.attenzione)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                        .frame(maxWidth: 520)
                        .padding(Tema.margine)
                        .frame(maxWidth: .infinity)
                    }
                    .animation(Tema.morbida, value: vm.indice)
                }
            }
            .navigationTitle(Catalogo.Pav.primoAvvio)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(vm.eRiepilogo ? Catalogo.Shell.chiudi : "Più tardi") {
                        Task {
                            if vm.fase == .pronta && !vm.eRiepilogo { await vm.piuTardi() }
                            chiudi()
                        }
                    }
                    .accessibilityHint(vm.eRiepilogo ? "" : "Esce e ti ricorda i passi da fare")
                }
            }
            .task { await vm.carica() }
        }
        .tint(Color.verde)
        // trascinata giù (o un tocco fuori sull'iPad) senza «Più tardi»: vale come «Più tardi», come la ✕ della web. Chiusa
        // dall'app (fine della sessione, altro server, un file da fuori) non segna niente; si chiede nel Task, cioè dopo che chi
        // l'ha chiusa ha finito di aggiornare lo stato.
        .onDisappear { Task { await vm.chiusa(dallApp: chiusaDallApp()) } }
    }

    // MARK: un passo

    private func pagina(_ passo: PassoGuidato) -> some View {
        VStack(spacing: 18) {
            VStack(spacing: 6) {
                Text(vm.testoAvanzamento).font(.footnote.weight(.semibold)).foregroundStyle(Color.testoSecondario)
                puntini
            }
            Image(systemName: passo.icona)
                .font(.system(size: 44, weight: .regular))
                .symbolRenderingMode(.hierarchical)
                .foregroundStyle(Color.verde)
                .accessibilityHidden(true)
            Text(passo.titolo).font(.title2.bold()).multilineTextAlignment(.center)
            Text(passo.spiegazione).font(.body).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 10) {
                principale(passo)
                if passo == .widget || passo == .avvisi {
                    Button { Task { await vm.segnaFatto(passo) } } label: {
                        Label("L'ho già fatto", systemImage: "checkmark.circle").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .pulsanteVetro()
                }
                Button { Task { await vm.salta(passo) } } label: {
                    Text(Catalogo.Pav.salta).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .buttonStyle(.plain)
                .foregroundStyle(Color.testoSecondario)
            }
        }
    }

    private var puntini: some View {
        HStack(spacing: 6) {
            ForEach(0..<vm.passi.count, id: \.self) { i in
                Circle().fill(i == vm.indice ? Color.verde : Color.secondary.opacity(0.3)).frame(width: 7, height: 7)
            }
        }
        .accessibilityHidden(true)
    }

    @ViewBuilder
    private func principale(_ passo: PassoGuidato) -> some View {
        Button {
            Task { await azione(passo) }
        } label: {
            HStack {
                if vm.inCorso { ProgressView() }
                Label(passo.azione, systemImage: passo.icona).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
        }
        .pulsanteVetro(prominente: true)
        .disabled(vm.inCorso)
    }

    private func azione(_ passo: PassoGuidato) async {
        switch passo {
        case .avvisi:
            await vm.attivaNotifiche()
        case .rose:
            await uscendo(.importaRose)
        case .squadra:
            await uscendo(.squadre(nome: nil))
        case .stemma:
            await uscendo(.squadre(nome: vm.stato.miaSquadra))
        case .widget:
            await uscendo(.collegaWidget)
        }
    }

    /// Il passo porta in un'altra schermata: si ricorda cosa resta da fare, si chiude la guida e si va lì.
    private func uscendo(_ azione: AzioneGuida) async {
        await vm.piuTardi()
        chiudi()
        vai(azione)
    }

    // MARK: riepilogo

    private var riepilogo: some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 44))
                .symbolRenderingMode(.hierarchical)
                .foregroundStyle(Color.verde)
                .accessibilityHidden(true)
            // titolo e «Hai finito la configurazione.» come la web; dove ritrovare i passi saltati lo dice l'iPhone (si riprendono
            // da «Da fare» in Oggi, non dalle Impostazioni come sulla web)
            Text(Catalogo.Pav.tuttoProntoMister).font(.title2.bold()).multilineTextAlignment(.center)
            Text(tuttoFatto ? Catalogo.Pav.haiFinito : "Quello che hai saltato lo trovi in Oggi, nella lista «Da fare».")
                .font(.body).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
            Carta {
                ForEach(PassoGuidato.allCases) { passo in
                    let esito = vm.esito(passo)
                    HStack(spacing: 10) {
                        Image(systemName: simbolo(esito)).foregroundStyle(colore(esito)).frame(width: 24).accessibilityHidden(true)
                        Text(passo.titolo).font(.subheadline)
                        Spacer(minLength: 8)
                        Text(esito.testo).font(.caption).foregroundStyle(Color.testoSecondario)
                    }
                    .frame(minHeight: 36)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(passo.titolo): \(esito.testo)")
                }
            }
            Button {
                Task {
                    await vm.termina()
                    chiudi()
                }
            } label: {
                Text("Fine").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
        }
    }

    private var tuttoFatto: Bool { PassoGuidato.allCases.allSatisfy { vm.esito($0) == .fatto } }

    private func simbolo(_ e: EsitoPasso) -> String {
        switch e {
        case .fatto: return "checkmark.circle.fill"
        case .saltato: return "arrow.uturn.forward.circle"
        case .daFare: return "circle"
        }
    }

    private func colore(_ e: EsitoPasso) -> Color {
        switch e {
        case .fatto: return Color.verde
        case .saltato: return Color.attenzione
        case .daFare: return Color.testoSecondario
        }
    }
}

#Preview("Configurazione guidata") {
    ConfigurazioneGuidataView(server: FinteServer.esempio, vai: { _ in })
}
