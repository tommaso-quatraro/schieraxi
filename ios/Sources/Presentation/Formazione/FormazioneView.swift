import SwiftUI

/// La Formazione unica (#673), al posto di Oggi e Formazione, come `mostraFormazione` della web (#616): la testa per fase, al
/// massimo due decisioni, il modulo come menu con i punti attesi, il campo, la riga dello stato con «Torna alla consigliata», «Copia
/// per l'app della lega» e «L'ho messa», la panchina nell'ordine in cui entra, i non schierati, gli infortunati e squalificati e le
/// partite rinviate. Il salvataggio è automatico. Sull'iPad due colonne: a sinistra testa e campo, a destra decisioni ed elenchi.
/// Solo presentazione: la logica è in `FormazioneViewModel` (formazione e scelta) e `OggiViewModel` (la giornata).
struct FormazioneView: View {
    @ObservedObject var vm: FormazioneViewModel
    @ObservedObject var oggi: OggiViewModel
    @EnvironmentObject private var nav: Navigazione
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.apriGiocatore) private var apriGiocatore
    @Environment(\.vaiASezione) private var vaiASezione
    @Environment(\.apriRosaDi) private var apriRosaDi
    @Environment(\.apriImpostazioni) private var apriImpostazioni
    @Environment(\.horizontalSizeClass) private var classe
    @Environment(\.dynamicTypeSize) private var taglia
    @Environment(\.scenePhase) private var fase

    /// Mentre la formazione arriva, come la web (`formazione.calcolo`).
    static let testoCaricamento = Catalogo.Formazione.calcolo

    /// La formazione di un'altra squadra, come la web: «Stai guardando la formazione di Gli Amici.»
    static func testoSquadraVista(_ nome: String) -> String {
        "\(Catalogo.Formazione.staiGuardandoFormazione) \(nome)."
    }

    /// Quanto restano a video gli avvisi brevi (un salvataggio non riuscito, la formazione copiata).
    private static let durataAvviso: Duration = .seconds(8)

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    ScrollViewReader { proxy in
                        contenuto
                            .padding(.horizontal, Tema.margine)
                            .padding(.bottom, 24)
                            .animation(Tema.morbida, value: vm.formazione != nil)
                            // fotografie `formazione-chiusa` e `formazione-rinvio`: la riga dello stato e il riquadro stanno sotto la piega
                            .demoScorriA("stato", proxy: proxy, schermate: ["formazione-chiusa"], pronto: vm.formazione != nil)
                            .demoScorriA("rinvio", proxy: proxy, schermate: ["formazione-rinvio"],
                                         pronto: vm.formazione != nil && oggi.oggi != nil)
                    }
                }
                .demoInFondo()
                .refreshable { await ricarica() }
                .avvisoDatiSalvati(vm.caricatore)
                .bordiMorbidi()
            }
            .navigationTitle(Catalogo.Nav.formazione)
            .ricercaGlobale()
            .sheet(item: $vm.daSostituire) { g in
                if let f = vm.formazione {
                    SceltaSostituto(uscente: g, candidati: vm.sostituti(di: g, f)) { nuovo in
                        vm.daSostituire = nil
                        Task { await vm.sostituisciTitolare(g.id, con: nuovo) }
                    }
                }
            }
            .task { await ricarica() }
            // mentre si gioca i punti cambiano quando escono i voti: si rilegge ogni 5 minuti, solo con la schermata visibile
            .task(id: "\(fase == .active)-\(oggi.oggi?.faseGiornata.rawValue ?? "")") {
                guard fase == .active, oggi.oggi?.faseGiornata == .inCorso else { return }
                await seguiGiornata()
            }
            // allo scadere della formazione si rilegge UNA volta (5 secondi dopo, per dare tempo al server): diventa di sola lettura
            .task(id: "\(fase == .active)-\(oggi.oggi?.chiusura ?? "")") {
                guard fase == .active, let inizio = Quando.data(oggi.oggi?.chiusura) else { return }
                let attesa = inizio.timeIntervalSinceNow + 5
                guard attesa > 0, attesa < 2 * 24 * 3600 else { return }
                try? await Task.sleep(for: .seconds(attesa))
                guard !Task.isCancelled else { return }
                await ricarica()
            }
            .task(id: vm.messaggio) {
                guard vm.messaggio != nil else { return }
                try? await Task.sleep(for: Self.durataAvviso)
                guard !Task.isCancelled else { return }
                vm.messaggio = nil
            }
            .onChange(of: vm.messaggio) { _, nuovo in
                if let nuovo { AccessibilityNotification.Announcement(nuovo).post() }
            }
        }
    }

    /// La giornata (`/api/oggi`, che passa i dati a widget e promemoria) e, insieme, formazione e scelta.
    private func ricarica() async {
        await Self.ricarica(vm, oggi: oggi)
    }

    /// Senza la scheda Oggi la Formazione è l'unica schermata che legge la giornata: a ogni apertura e rilettura `/api/oggi`, che
    /// passa i dati freschi a widget e promemoria (`OggiViewModel.dopoLetturaFresca`), e insieme formazione e scelta. Statica per
    /// provarla senza disegnare la schermata (`OggiPerWidgetTests`).
    static func ricarica(_ vm: FormazioneViewModel, oggi: OggiViewModel) async {
        let giornata = Task { await oggi.carica() }
        await vm.carica()
        await giornata.value
    }

    /// A giornata in corso: ogni 5 minuti la giornata e la formazione (lo stato di ogni partita), finché la fase resta quella.
    private func seguiGiornata() async {
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(OggiViewModel.ripassoGiornata))
            guard !Task.isCancelled else { return }
            await oggi.caricatore.ricarica()
            await vm.carica()
            guard oggi.oggi?.faseGiornata == .inCorso else { return }
        }
    }

    // MARK: pagina

    @ViewBuilder
    private var contenuto: some View {
        if vm.squadraVista == nil, oggi.oggi?.senzaRose == true {
            benvenuto
        } else if let f = vm.formazione {
            pagina(f)
        } else if let errore = vm.errore {
            ErroreVista(messaggio: errore) { Task { await ricarica() } }
        } else {
            Scheletro(schede: 3, righe: 3, testo: Self.testoCaricamento)
        }
    }

    /// Sull'iPad (e con il telefono grande in orizzontale) due colonne, sempre in ordine di lettura; con il testo molto grande una.
    private var dueColonne: Bool { classe == .regular && !taglia.isAccessibilitySize }

    @ViewBuilder
    private func pagina(_ f: Formazione) -> some View {
        let v = vm.vista(f)
        let decisioni = vm.decisioni(oggi.oggi, tecniche: sessione.puoAmministrare)
        if dueColonne {
            HStack(alignment: .top, spacing: Tema.spazioSchede) {
                VStack(alignment: .leading, spacing: Tema.spazioSchede) {
                    testa(f)
                    campo(f, v)
                }
                VStack(alignment: .leading, spacing: Tema.spazioSchede) {
                    decisioniInCima(decisioni)
                    lato(f, v)
                }
            }
        } else {
            VStack(alignment: .leading, spacing: Tema.spazioSchede) {
                testa(f)
                decisioniInCima(decisioni)
                campo(f, v)
                lato(f, v)
            }
        }
    }

    /// Account nuovo, senza rose: il benvenuto e un solo pulsante, come `mostraSenzaRose` della web.
    private var benvenuto: some View {
        Carta(Catalogo.Oggi.benvenutoSchieraxi, simbolo: "hand.wave") {
            Text(Catalogo.Oggi.perCominciareImporta)
                .font(.subheadline).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
            Button { nav.guidaAperta = true } label: {
                Label(Catalogo.Comune.importaRose, systemImage: "square.and.arrow.down")
                    .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
        }
    }

    // MARK: testa e decisioni

    @ViewBuilder
    private func testa(_ f: Formazione) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            if let nome = vm.squadraVista {
                Carta {
                    Label(Self.testoSquadraVista(nome), systemImage: "eye").font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                    Button { vm.tornaAllaMia() } label: { Text(Catalogo.Formazione.tornaAllaTua).frame(minHeight: Tema.areaTocco) }
                        .pulsanteVetro()
                }
            }
            TestaFormazioneView(oggi: vm.squadraVista == nil ? oggi.oggi : nil, formazione: f) { _ in
                // fino alla pagina Giornate (passo 2 di #673) «Com'è andata» apre il Diario
                nav.vai(a: .pagina(.diario))
            }
        }
    }

    private func decisioniInCima(_ voci: [DaFareVoce]) -> some View {
        DecisioniFormazione(voci: voci, guadagno: { vm.guadagno($0) }, spento: vm.comandiSpenti) { v in esegui(v) }
    }

    /// L'azione di una decisione, come i gestori di `#decisioni` della web: il cambio di un titolare (se non si può più fare da qui,
    /// la sua scheda), «Usa la consigliata», oppure la pagina dove si fa la cosa.
    private func esegui(_ v: DaFareVoce) {
        if v.scrive && vm.comandiSpenti { return }
        if let cambio = v.cambio {
            Task {
                let fatto = await vm.sostituisciTitolare(cambio.esce, con: cambio.entra)
                if !fatto { apriGiocatore(cambio.esce) }
            }
            return
        }
        if v.consigliataCambiata {
            Task { await vm.tornaAllaConsigliata() }
            return
        }
        apri(v)
    }

    /// Dove porta una decisione che non scrive (`dfApri` della web): la guida, la rosa della tua squadra, le rose da aggiornare, le
    /// Impostazioni, una pagina di Squadra o di Altro.
    private func apri(_ v: DaFareVoce) {
        if v.tipo == "primo_avvio" {
            nav.guidaAperta = true
            return
        }
        if v.allaRosa {
            if let nome = vm.formazione?.squadra ?? oggi.oggi?.formazione?.squadra, let apriRosaDi { apriRosaDi(nome) } else { vaiASezione(.squadra) }
            return
        }
        guard let d = v.destinazione?.destinazione else { return }
        if v.tipo == "rose", case .sezione = d {
            nav.vai(a: .pagina(.importa))
            return
        }
        switch d {
        case .sezione(let s):
            if s != .formazione { vaiASezione(s) }
        case .giocatore(let id):
            apriGiocatore(id)
        case .impostazioni:
            apriImpostazioni?()
        case .pagina, .collegaWidget:
            nav.vai(a: d)
        }
    }

    // MARK: modulo, campo e stato

    private func campo(_ f: Formazione, _ v: VistaFormazione) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .center, spacing: 12) {
                    modulo(f, v)
                    Spacer(minLength: 8)
                    punti(f, v, allineamento: .trailing)
                }
                VStack(alignment: .leading, spacing: 6) {
                    modulo(f, v)
                    punti(f, v, allineamento: .leading)
                }
            }
            CampoFormazione(titolari: v.titolari, apribile: true)
            RigaStatoScelta(stato: vm.statoScelta, spento: vm.comandiSpenti, occupato: vm.occupato,
                            tornaAllaConsigliata: { Task { await vm.tornaAllaConsigliata() } },
                            riprova: { Task { await ricarica() } })
                .id("stato")
            if vm.copiaFerma { copiaFerma }
            if vm.squadraVista == nil, !vm.chiusa { azioni(f) }
            if let messaggio = vm.messaggio {
                Text(messaggio).font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !vm.chiusa, f.conProbabili == false {
                Label(Catalogo.Formazione.mancanoProbabiliFormazioni, systemImage: "clock")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if vm.squadraVista == nil, !vm.chiusa { probabili }
        }
    }

    /// Il modulo come menu (`formazione.opzione_*`: «4-3-3 · 73,7 punti · consigliato»); a giornata chiusa fisso. Per la tua
    /// formazione un altro modulo si salva subito.
    @ViewBuilder
    private func modulo(_ f: Formazione, _ v: VistaFormazione) -> some View {
        let moduli = vm.moduli(f)
        if vm.chiusa || moduli.isEmpty {
            Text(v.modulo).font(.system(.title2, design: .rounded).weight(.bold))
                .lineLimit(1).fixedSize()
                .accessibilityLabel("\(Catalogo.Formazione.modulo) \(v.modulo)")
        } else {
            Menu {
                ForEach(moduli) { m in
                    Button { Task { await vm.scegliModulo(m.modulo) } } label: {
                        if m.modulo == v.modulo {
                            Label(vm.etichettaModulo(m, f), systemImage: "checkmark")
                        } else {
                            Text(vm.etichettaModulo(m, f))
                        }
                    }
                }
            } label: {
                HStack(spacing: 6) {
                    Text(v.modulo).font(.system(.title2, design: .rounded).weight(.bold)).lineLimit(1).fixedSize()
                    Image(systemName: "chevron.up.chevron.down").font(.footnote.weight(.semibold))
                }
                .frame(minHeight: Tema.areaTocco)
                .contentShape(Rectangle())
            }
            .disabled(vm.comandiSpenti)
            .accessibilityLabel(Catalogo.Formazione.modulo)
            .accessibilityValue(v.modulo)
        }
    }

    /// I punti attesi degli 11 in campo e «di solito fra 65 e 82».
    private func punti(_ f: Formazione, _ v: VistaFormazione, allineamento: HorizontalAlignment) -> some View {
        VStack(alignment: allineamento, spacing: 1) {
            Text("\(Text(Formato.punti(v.punti)).font(.title2.bold()).monospacedDigit()) \(Catalogo.Formazione.puntiAttesi)")
                .font(.subheadline)
            if let fascia = vm.fascia(f) {
                Text(fascia).font(.caption).foregroundStyle(Color.testoSecondario)
            }
        }
        .multilineTextAlignment(allineamento == .trailing ? .trailing : .leading)
        .accessibilityElement(children: .combine)
    }

    /// I dati nuovi non sono arrivati: la copia del telefono non si può cambiare, e «Riprova».
    private var copiaFerma: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Label(Catalogo.Formazione.copiaFerma, systemImage: "icloud.slash")
                .font(.footnote).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 4)
            Button(Catalogo.Comune.riprova) { Task { await ricarica() } }
                .font(.footnote.weight(.semibold))
                .frame(minHeight: Tema.areaTocco)
        }
    }

    /// «Copia per l'app della lega» e la spunta «L'ho messa» (salva gli 11 in campo con `messa`).
    private func azioni(_ f: Formazione) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) {
                copia(f)
                Spacer(minLength: 0)
                spunta
            }
            VStack(alignment: .leading, spacing: 8) {
                copia(f)
                spunta
            }
        }
    }

    private func copia(_ f: Formazione) -> some View {
        Button { vm.copiaTesto(f) } label: {
            Label(Catalogo.Formazione.copiaLega, systemImage: "doc.on.doc")
                .frame(minHeight: Tema.areaTocco)
        }
        .buttonStyle(.bordered)
        .tint(Color.verde)
        .disabled(!vm.sceltaLetta)
    }

    /// Una spunta, non un interruttore: su iOS lo stile «casella» non c'è, quindi un pulsante con il cerchio che si riempie.
    private var spunta: some View {
        Button { Task { await vm.segnaMessa(!vm.messa) } } label: {
            Label(Catalogo.Formazione.messa, systemImage: vm.messa ? "checkmark.circle.fill" : "circle")
                .font(.subheadline.weight(.semibold))
                .frame(minHeight: Tema.areaTocco)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(vm.messa ? Color.verde : Color.primary)
        .disabled(vm.comandiSpenti || vm.salvataNonValida)
        .accessibilityAddTraits(vm.messa ? [.isToggle, .isSelected] : [.isToggle])
    }

    /// Quando sono state lette le probabili («Probabili aggiornate alle 13:05 (2 ore fa)») e, se sono vecchie, l'avviso.
    @ViewBuilder
    private var probabili: some View {
        if let p = oggi.oggi?.probabili?.valore, let testo = p.testo, !testo.isEmpty {
            let eta = p.eta.map { " (\($0))" } ?? ""
            Text(testo + eta).font(.caption).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
            if let avviso = p.avvisoVisibile {
                Label(avviso, systemImage: "exclamationmark.triangle")
                    .font(.footnote).foregroundStyle(Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: panchina ed elenchi

    @ViewBuilder
    private func lato(_ f: Formazione, _ v: VistaFormazione) -> some View {
        let mia = vm.squadraVista == nil
        if mia, let cambi = oggi.oggi?.giornataInCorso?.sostituzioni.filter({ $0.esce != nil }), !cambi.isEmpty {
            Carta(Catalogo.Oggi.cambiPanchina, simbolo: "arrow.left.arrow.right") {
                ForEach(Array(cambi.enumerated()), id: \.offset) { i, c in
                    RigaConFilo(prima: i == 0) { RigaCambioPanchina(cambio: c) }
                }
            }
        }
        Carta("Panchina", simbolo: "chair.lounge.fill") {
            Text(Catalogo.Formazione.questOrdineEntra).font(.caption).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(Array(v.panchina.enumerated()), id: \.element.id) { i, g in
                RigaConFilo(prima: i == 0) {
                    HStack(alignment: .center, spacing: 8) {
                        Text("\(i + 1)").font(.footnote.weight(.semibold)).monospacedDigit()
                            .foregroundStyle(Color.testoSecondario)
                            .accessibilityHidden(true)
                        RigaGiocatore(g: g, apribile: true)
                    }
                }
            }
        }
        elenco(Catalogo.Formazione.nonSchierati(n: String(vm.nonSchierati(f, v).count)), vm.nonSchierati(f, v),
               nota: (f.senzaDati ?? []).isEmpty ? nil : Catalogo.Formazione.senzaDati(nomi: (f.senzaDati ?? []).joined(separator: ", ")))
        elenco(Catalogo.Formazione.indisponibili(n: String(vm.indisponibili(f, v).count)), vm.indisponibili(f, v), nota: nil)
        if mia, let r = oggi.oggi?.partiteRinviate {
            CartaPartitaRinviata(scelta: r, inCorso: oggi.rinvioInCorso, errore: oggi.erroreRinvio) { m in
                await oggi.cambiaRinvio(r, modo: m)
            }
            .id("rinvio")
        }
        if mia, let s = oggi.oggi?.riepilogoGiornata?.rinvio {
            Carta {
                MenuRinvio(scelta: s, inCorso: oggi.rinvioInCorso) { scelta, m in await oggi.cambiaRinvio(scelta, modo: m) }
            }
        }
    }

    /// Un elenco chiuso («Non schierati (4)», «Infortunati e squalificati (2)»): si apre con un tocco.
    @ViewBuilder
    private func elenco(_ titolo: String, _ giocatori: [Giocatore], nota: String?) -> some View {
        if !giocatori.isEmpty || nota != nil {
            Carta {
                DisclosureGroup {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(giocatori) { RigaGiocatore(g: $0, apribile: true) }
                        if let nota {
                            Text(nota).font(.caption).foregroundStyle(Color.testoSecondario)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(.top, 6)
                } label: {
                    Text(titolo).font(.subheadline.weight(.semibold)).frame(minHeight: Tema.areaTocco, alignment: .leading)
                }
                .tint(Color.testoSecondario)
            }
        }
    }
}

#Preview("Formazione") {
    FormazioneView(vm: FormazioneViewModel(server: FinteServer.esempio), oggi: OggiViewModel(server: FinteServer.esempio, conPromemoria: false))
        .environmentObject(Navigazione())
        .environmentObject(SessioneAccount(server: FinteServer.esempio))
}
