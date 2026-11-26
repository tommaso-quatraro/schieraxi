import SwiftUI

/// La configurazione guidata («Primo avvio», come si chiama sulla web): un passo alla volta, tutti saltabili, con un riepilogo
/// alla fine. I passi sono quelli della web («Le rose», «La tua squadra», «I tempi della lega») più «Il widget» e «Gli avvisi»,
/// che ha solo l'iPhone (#931); nomi, frasi, «Salta» e il riepilogo hanno le parole della web.
/// Parte da sola se la lega non ha ancora le rose e non è mai stata iniziata (con gli account, se nemmeno la vecchia procedura è
/// finita: #600), o si riprende se era stata lasciata prima delle rose (anche sulla web), come la web (#595); si apre anche dalla
/// lista «Da fare» di Oggi. Salta i passi già fatti. Un passo che porta in un'altra schermata (rose, squadra, widget) la chiude e,
/// lasciata quella, la guida si riapre da quel passo fino a «Tutto pronto» (#880, come la web, dove tutto succede dentro la
/// guida); i tempi della lega si scelgono qui dentro, come sulla web.
struct ConfigurazioneGuidataView: View {
    @StateObject private var vm: ConfigurazioneGuidataViewModel
    /// Cosa fare quando un passo porta in un'altra schermata (la guida si chiude prima).
    let vai: (AzioneGuida) -> Void
    /// Vero se il foglio l'ha chiuso l'app e non l'utente (sessione finita o cambiata, un file arrivato da fuori): alla chiusura
    /// i passi rimasti non diventano saltati.
    let chiusaDallApp: @MainActor () -> Bool
    @Environment(\.dismiss) private var chiudi
    @Environment(\.accessibilityReduceMotion) private var ridotto

    /// `riprendiDa`: riaperta dopo una pagina in cui l'aveva portata un passo, riparte da quel passo (#880); `passoFatto`: quel passo
    /// è stato fatto nella pagina (il widget collegato) e si segna da solo.
    init(server: any ServerClient, riprendiDa: PassoGuidato? = nil, passoFatto: PassoGuidato? = nil,
         vai: @escaping (AzioneGuida) -> Void, chiusaDallApp: @escaping @MainActor () -> Bool = { false }) {
        _vm = StateObject(wrappedValue: ConfigurazioneGuidataViewModel(server: server, riprendiDa: riprendiDa, passoFatto: passoFatto))
        self.vai = vai
        self.chiusaDallApp = chiusaDallApp
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                switch vm.fase {
                case .carica:
                    ScrollView { Scheletro(schede: 1, righe: 3, testo: Catalogo.Comune.carico).padding(Tema.margine) }
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
                ToolbarItem(placement: .topBarTrailing) {
                    Button(vm.eRiepilogo ? Catalogo.Shell.chiudi : Catalogo.Pav.piuTardi) {
                        Task {
                            if vm.fase == .pronta && !vm.eRiepilogo { await vm.piuTardi() }
                            chiudi()
                        }
                    }
                    .accessibilityHint(vm.eRiepilogo ? "" : Catalogo.Pav.piuTardiAiuto)
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
                .accessibilityAddTraits(.isHeader)
            Text(passo.spiegazione).font(.body).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            if passo == .tempi { domandeTempi }
            VStack(spacing: 10) {
                principale(passo)
                if passo.siSegnaAMano {
                    Button { Task { await vm.segnaFatto(passo) } } label: {
                        Label(Catalogo.Pav.giaFatto, systemImage: "checkmark.circle").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
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
        // i tempi salvati della lega si leggono quando il passo compare, come `paTempiCarica` della web
        .task(id: passo) {
            if passo == .tempi, !vm.tempiLetti { await vm.caricaTempi() }
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

    /// Le due domande dei tempi della lega, ognuna con il suo menu, come il passo della web; sotto, dove si cambiano dopo.
    private var domandeTempi: some View {
        Carta {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 4) {
                    domanda(Catalogo.Pav.scadDomanda)
                    Picker(Catalogo.Pav.scadDomanda, selection: $vm.scadenza) {
                        ForEach(vm.scadenzeScelte, id: \.self) { minuti in
                            Text(TempiGuida.nomeScadenza(minuti)).tag(minuti)
                        }
                    }
                    .pickerStyle(.menu)
                    .labelsHidden()
                    .frame(minHeight: Tema.areaTocco)
                }
                VStack(alignment: .leading, spacing: 4) {
                    domanda(Catalogo.Pav.primaDomanda)
                    Picker(Catalogo.Pav.primaDomanda, selection: $vm.prima) {
                        ForEach(TempiGuida.giornate, id: \.self) { giornata in
                            Text(TempiGuida.nomePrima(giornata)).tag(giornata)
                        }
                    }
                    .pickerStyle(.menu)
                    .labelsHidden()
                    .frame(minHeight: Tema.areaTocco)
                }
                Text(Catalogo.Pav.tempiDove).font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .disabled(vm.inCorso)
    }

    /// La domanda sopra il suo menu; VoiceOver la legge già come nome del menu.
    private func domanda(_ testo: String) -> some View {
        Text(testo).font(.subheadline.weight(.semibold))
            .fixedSize(horizontal: false, vertical: true)
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
            // niente diventa saltato: lasciata la pagina delle rose la guida si riapre (#880)
            await vm.versoLeRose()
            chiudi()
            vai(.importaRose)
        case .squadra:
            await uscendo(.scegliSquadra)
        case .tempi:
            await vm.salvaTempi()
        case .widget:
            await uscendo(.collegaWidget)
        }
    }

    /// Il passo porta in un'altra schermata: si ricorda cosa resta da fare (se l'app si chiude prima di tornare, la guida si
    /// ritrova in «Da fare» della Formazione), si chiude la guida e si va lì. Lasciata quella pagina, o chiuso il foglio del widget,
    /// la guida si riapre da questo passo e continua fino a «Tutto pronto» (`RitornoAllaGuida`, revisione della #887).
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
            // come «Tutto pronto» della web: il titolo, la frase con i passi saltati per nome, i punteggi usati e dove sono stemma e
            // avvisi, i passi con «(fatto)» e «(saltato)», «Vai alla Formazione»
            Text(Catalogo.Pav.tuttoProntoMister).font(.title2.bold()).multilineTextAlignment(.center)
                .accessibilityAddTraits(.isHeader)
            Text(vm.frasePronto)
                .font(.body).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            regoleComuni
            Text(Catalogo.Pav.ilResto)
                .font(.footnote).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            Carta {
                ForEach(PassoGuidato.allCases) { passo in
                    let esito = vm.esito(passo)
                    HStack(spacing: 10) {
                        Image(systemName: simbolo(esito)).foregroundStyle(colore(esito)).frame(width: 24).accessibilityHidden(true)
                        Text(passo.titolo + esito.suffisso).font(.subheadline)
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: 0)
                    }
                    .frame(minHeight: 36)
                    .accessibilityElement(children: .combine)
                }
            }
            // come la web: «Vai alla Formazione» chiude la guida, finita, e apre la Formazione
            Button {
                Task { await finisci(andando: .formazione) }
            } label: {
                Text(Catalogo.Pav.vaiFormazione).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
        }
    }

    /// Le regole la guida non le chiede: si dice quali punteggi usano i fantavoti attesi e dove si cambiano, come «Tutto pronto»
    /// della web (#880). «Regole e scadenza» chiude la guida come «Vai alla Formazione» e apre quella pagina; tutta la frase è il
    /// pulsante, perché un collegamento dentro il testo sarebbe troppo piccolo da toccare.
    private var regoleComuni: some View {
        Button {
            Task { await finisci(andando: .regole) }
        } label: {
            Text(Self.fraseRegole)
                .font(.body).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    /// `pav.regole_comuni` con «Regole e scadenza» (`imp.regole`) nel colore dell'app e sottolineato, come un collegamento.
    private static var fraseRegole: AttributedString {
        let nome = Catalogo.Imp.regole
        var frase = AttributedString(Catalogo.Pav.regoleComuni(regole: nome))
        if let dove = frase.range(of: nome) {
            var collegamento = AttributeContainer()
            collegamento.foregroundColor = Color.verde
            collegamento.underlineStyle = Text.LineStyle.single
            frase[dove].mergeAttributes(collegamento)
        }
        return frase
    }

    /// La guida è finita: non si riapre più da sola; si chiude e l'app va dove porta il pulsante.
    private func finisci(andando dove: AzioneGuida) async {
        await vm.termina()
        chiudi()
        vai(dove)
    }

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
