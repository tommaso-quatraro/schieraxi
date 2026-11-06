import SwiftUI
import TipKit

/// Schermata Oggi: solo presentazione. Dati e logica sono in `OggiViewModel`.
struct OggiView: View {
    @ObservedObject var vm: OggiViewModel
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.vaiASezione) private var vaiASezione
    @Environment(\.apriNovita) private var apriNovita
    @Environment(\.funzioni) private var funzioni
    @Environment(\.apriImpostazioni) private var apriImpostazioni
    @EnvironmentObject private var nav: Navigazione
    @EnvironmentObject private var sessione: SessioneAccount
    @ObservedObject private var immagini = Immagini.condivise
    /// L'ultima versione delle novità che l'utente ha guardato (la scrive la pagina Novità).
    @AppStorage("novitaVista") private var novitaVista = ""
    @ScaledMetric(relativeTo: .largeTitle) private var corpoGrande: CGFloat = 46
    @ScaledMetric(relativeTo: .body) private var latoIcona: CGFloat = 24
    @Environment(\.dynamicTypeSize) private var dimensioneTesto
    @State private var tutteLeCose = false
    @Environment(\.scenePhase) private var fase

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    ScrollViewReader { proxy in
                    // Le sezioni nell'ordine della web (`SezioneOggi.ordine`, #416): si parte dalla giornata con il conto alla
                    // rovescia, senza nome né slogan in cima. Le fasi: prima (consigli e avvisi), durante (punti fatti, niente
                    // consigli su chi schierare), dopo (riepilogo e prossima giornata).
                    Colonne(spazio: Tema.spazioSchede) {
                        if let oggi = vm.oggi {
                            let sezioni = SezioneOggi.ordine(fase: oggi.faseGiornata, conGiornata: !oggi.senzaGiornata)
                            ForEach(Array(sezioni.enumerated()), id: \.element) { posto, s in
                                sezione(s, oggi).ingresso(posto)
                            }
                        } else if let errore = vm.errore {
                            ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                        } else {
                            Scheletro(schede: 3, righe: 2, testo: "Preparo la giornata…")
                        }
                    }
                    .padding(.horizontal, Tema.margine)
                    .padding(.bottom, 24)
                    .animation(Tema.morbida, value: vm.oggi != nil)
                    // fotografie `oggi-rinvio` e `oggi-finita-recupero`: il riquadro sta sotto la piega dell'iPhone
                    .demoScorriA("rinvio", proxy: proxy, schermate: ["oggi-rinvio"], pronto: vm.oggi != nil)
                    .demoScorriA("riepilogo", proxy: proxy, schermate: ["oggi-finita-recupero"], pronto: vm.oggi != nil)
                    }
                }
                .demoInFondo()
                .refreshable {
                    await vm.carica()
                    if funzioni.acceso(Funzione.live) { await vm.live.ricarica() }
                }
                .avvisoDatiSalvati(vm.caricatore)
                .bordiMorbidi()
            }
            .navigationTitle("Oggi")
            .ricercaGlobale()
            .task { await vm.carica() }
            // Prima installazione (o dopo l'uscita dall'account): non c'è niente di «nuovo» da vedere, si segna la versione attuale senza riga.
            .onChange(of: vm.info.dato?.versione, initial: true) { _, v in
                if novitaVista.isEmpty, let v, !v.isEmpty, v != "?" { novitaVista = v }
            }
            // «Risultati in diretta» spenta: Partite del turno resta, senza punteggio né minuto in diretta.
            .onChange(of: funzioni.acceso(Funzione.live), initial: true) { _, acceso in vm.liveAcceso = acceso }
            // Risultati in diretta: solo con la schermata visibile e l'app in primo piano (il lavoro si annulla da solo quando
            // la schermata sparisce) e riparte quando arriva la giornata o cambia.
            .task(id: "\(fase == .active)-\(vm.oggi?.giornata ?? 0)-\(funzioni.acceso(Funzione.live))") {
                guard fase == .active, funzioni.acceso(Funzione.live) else { return }   // «Risultati in diretta» spenta: non si chiede nulla al server
                await vm.seguiLive()
            }
            // Durante la giornata i punti cambiano quando escono i voti: Oggi si rilegge da solo ogni tanto, solo con la schermata visibile.
            .task(id: "\(fase == .active)-\(vm.oggi?.faseGiornata.rawValue ?? "")") {
                guard fase == .active, vm.oggi?.faseGiornata == .inCorso else { return }
                await vm.seguiGiornata()
            }
            // Allo scadere della formazione il conto alla rovescia diventa «Chiusa»: Oggi si rilegge UNA volta (5 secondi dopo,
            // per dare tempo al server), così spariscono consigli e «Apri la formazione». Solo con la schermata visibile.
            .task(id: "\(fase == .active)-\(vm.oggi?.chiusura ?? "")") {
                guard fase == .active, let inizio = Quando.data(vm.oggi?.chiusura) else { return }
                let attesa = inizio.timeIntervalSinceNow + 5
                guard attesa > 0, attesa < 2 * 24 * 3600 else { return }
                try? await Task.sleep(for: .seconds(attesa))
                guard !Task.isCancelled else { return }
                await vm.carica()
            }
        }
    }

    /// Una sezione di Oggi (l'ordine lo decide `SezioneOggi.ordine`). Ognuna si nasconde da sola se non ha niente da mostrare.
    @ViewBuilder
    private func sezione(_ s: SezioneOggi, _ oggi: Oggi) -> some View {
        switch s {
        case .benvenuto: benvenuto(oggi)
        case .senzaGiornata: senzaGiornata(oggi)
        case .conto: testata(oggi)
        case .riepilogo:
            CartaRiepilogoGiornata(riepilogo: oggi.riepilogoGiornata, prossima: oggi.prossimaGiornata,
                                   rinvioInCorso: vm.rinvioInCorso) { scelta, modo in
                await vm.cambiaRinvio(scelta, modo: modo)
            }
            .id("riepilogo")
        case .inCorso:
            // come `mostraOggi` della web: chi è entrato a giornata iniziata vede «Questa giornata è già iniziata»; con i dati della
            // giornata la carta dei punti; senza (non si sa ancora cosa hai schierato) la carta della formazione
            if oggi.senzaFormazioneInCorso {
                CartaSenzaFormazione(prossima: oggi.prossimaGiornata)
            } else if let b = oggi.giornataInCorso {
                CartaGiornataInCorso(blocco: b, attesiPrima: oggi.formazione?.punteggioAtteso)
            } else {
                CartaFormazioneOggi(oggi: oggi)
            }
        case .formazione: CartaFormazioneOggi(oggi: oggi)
        case .rinvio: partiteRinviate(oggi)
        case .daFare: daFare(oggi)
        case .novita: novita
        case .suggerimento: suggerimento
        case .migliori: migliori(oggi)
        case .daControllare: daControllare
        case .indisponibili: indisponibili
        case .diffidati: diffidati
        case .partite:
            // sempre, come la web (decisione del 6/11): con «Risultati in diretta» spenta senza i risultati in diretta (vm.liveAcceso)
            partite
        }
    }

    /// Partite rinviate della giornata: quali, i miei coinvolti e cosa vale per questa giornata (niente se non ce ne sono).
    @ViewBuilder
    private func partiteRinviate(_ oggi: Oggi) -> some View {
        if let r = oggi.partiteRinviate {
            CartaPartitaRinviata(scelta: r, inCorso: vm.rinvioInCorso, errore: vm.erroreRinvio) { m in await vm.cambiaRinvio(r, modo: m) }
                .id("rinvio")
        }
    }

    /// Lega senza rose: un benvenuto con un solo passo chiaro, che apre la configurazione guidata.
    @ViewBuilder
    private func benvenuto(_ oggi: Oggi) -> some View {
        if oggi.senzaRose == true {
            Carta("Benvenuto in SchieraXI", simbolo: "hand.wave") {
                Text("Importa la tua rosa per cominciare: per darti i consigli servono le rose della tua lega, poi ti guido nei passi successivi.")
                    .font(.subheadline).foregroundStyle(Color.testoSecondario)
                Button { nav.guidaAperta = true } label: {
                    Label("Importa le rose", systemImage: "square.and.arrow.down").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .pulsanteVetro(prominente: true)
            }
        }
    }

    /// Il server non manda nessuna giornata (calendario non pronto, stagione finita): una frase semplice al posto del riquadro principale.
    /// Per l'account nuovo senza rose c'è già il benvenuto, che dice cosa fare.
    @ViewBuilder
    private func senzaGiornata(_ oggi: Oggi) -> some View {
        if oggi.senzaGiornata, oggi.senzaRose != true {
            Carta("Oggi", simbolo: "calendar") {
                Text("Nessuna giornata in programma per ora.")
                    .font(.subheadline).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    /// Il suggerimento (TipKit) «tocca un giocatore»: compare una volta sola, finché non si apre una scheda.
    @ViewBuilder
    private var suggerimento: some View {
        if !Demo.attivo {
            TipView(Suggerimenti.scheda)
                .tipBackground(Color.sfondoScheda)
        }
    }

    // MARK: riquadro principale

    /// Il riquadro in alto: sfondo vivo, giornata, conto alla rovescia grande e maglia della squadra.
    private func testata(_ oggi: Oggi) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            // Solo la giornata, come la web: niente invito a caricare la maglia (#436).
            CapsulaGiornata(nome: oggi.nomeGiornata)
            // Conto alla rovescia e maglia sulla stessa riga: il riquadro è più basso e il resto di Oggi sale.
            // Con le misure di accessibilità grandi la maglia va sotto: il testo della fase resta intero.
            rigaTestata {
                contoAllaRovescia(oggi).layoutPriority(1)
                if let squadra = oggi.formazione?.squadra, immagini.haImmagine(squadra, tipo: "maglia") {
                    StemmaSquadra(nome: squadra, tipo: "maglia", dimensione: 56, nascondiSeMancante: true)
                        .shadow(color: .black.opacity(0.35), radius: 6, y: 3)
                }
            }
            // «Mancano le probabili» sta sotto «Apri la formazione», come la web (#416): qui solo giornata e conto alla rovescia.
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background { MagiaColori() }
        .clipShape(RoundedRectangle(cornerRadius: 30, style: .continuous))
        .environment(\.colorScheme, .dark)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(oggi.nomeGiornata?.voce ?? "Giornata")
    }

    /// Riga della testata: orizzontale di norma, verticale con le misure di accessibilità (testo molto grande).
    private var rigaTestata: AnyLayout {
        dimensioneTesto.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 10))
            : AnyLayout(HStackLayout(alignment: .center, spacing: 8))
    }

    @ViewBuilder
    private func contoAllaRovescia(_ oggi: Oggi) -> some View {
        if let inizio = Quando.data(oggi.chiusura) {
            // Ogni secondo ricontrolla: a zero il conto alla rovescia («6 h 44 min», come la web) lascia il posto a «Chiusa».
            TimelineView(.periodic(from: Date(), by: 1)) { contesto in
                let ora = Orologio.daSistema(contesto.date)
                VStack(alignment: .leading, spacing: 4) {
                    if Quando.contoAllaRovescia(fino: inizio, adesso: ora) != nil {
                        TestoConto(inizio: inizio, adesso: ora)
                            .font(.system(size: corpoGrande, weight: .bold, design: .rounded))
                            .foregroundStyle(.white)
                            .minimumScaleFactor(0.5)
                            .lineLimit(1)
                        Text(Self.quandoSiChiude(oggi, adesso: ora)).font(.subheadline).foregroundStyle(.white.opacity(0.8))
                    } else {
                        Text("Chiusa")
                            .font(.system(size: corpoGrande * 0.87, weight: .bold, design: .rounded))
                            .lineLimit(1)
                            .minimumScaleFactor(0.5)   // testo molto grande: si rimpicciolisce invece di andare a capo a metà parola
                            .foregroundStyle(.white)
                        Text(Self.siEChiusa(oggi, adesso: ora)).font(.subheadline).foregroundStyle(.white.opacity(0.8))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .combine)
            }
        } else {
            // Senza scadenza: «Chiusa» se la giornata è cominciata, altrimenti una frase al posto di un trattino enorme.
            if oggi.iniziata == true {
                Text("Chiusa").lineLimit(1).minimumScaleFactor(0.5)
                    .font(.system(size: corpoGrande * 0.87, weight: .bold, design: .rounded)).foregroundStyle(.white)
            } else {
                Text("Data da definire")
                    .font(.system(.title2, design: .rounded, weight: .bold)).foregroundStyle(.white)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    /// Sotto il conto alla rovescia, come la web: «La formazione si chiude sab 31 14:50 (10 min prima della prima partita)»,
    /// o «Prima partita …: la formazione va inserita prima» se la scadenza è l'inizio della prima partita. «oggi», «domani» si
    /// contano dall'ora dell'app (`Orologio`), la stessa del conto alla rovescia.
    static func quandoSiChiude(_ oggi: Oggi, adesso: Date = Orologio.adesso()) -> String {
        if let s = oggi.scadenza, !s.trimmingCharacters(in: .whitespaces).isEmpty, s != oggi.inizio, let m = oggi.minutiScadenza {
            return "La formazione si chiude \(Quando.leggibile(s, adesso: adesso)) (\(m) min prima della prima partita)"
        }
        return "Prima partita \(Quando.leggibile(oggi.chiusura, adesso: adesso)): la formazione va inserita prima"
    }

    /// A scadenza passata, come la web: «La formazione si è chiusa sab 31 14:50». La giornata è scritta subito sopra il conto,
    /// con i due numeri, e non si ripete (#299). «ieri» si conta dall'ora dell'app (`Orologio`), come il conto alla rovescia e il
    /// widget: nella demo a giornata in corso «si è chiusa ieri 20:35» anche con la foto scattata di notte (#424).
    static func siEChiusa(_ oggi: Oggi, adesso: Date = Orologio.adesso()) -> String {
        "La formazione si è chiusa \(Quando.leggibile(oggi.chiusura, adesso: adesso))"
    }

    // MARK: novità

    @ViewBuilder
    private var novita: some View {
        if funzioni.acceso(Funzione.novita), let versione = vm.novitaDaVedere(ultimaVista: novitaVista) {
            Button { apriNovita() } label: {
                HStack(spacing: 10) {
                    // Come la web: «Novità della versione X» in grassetto, senza stelline né «tocca per vedere» (STILE-SENZA-AI.md).
                    Text(TestiOggi.novita(versione))
                        .font(.subheadline)
                        .bold()
                        .multilineTextAlignment(.leading)
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(Color.testoSecondario).accessibilityHidden(true)
                }
                .foregroundStyle(Color.verde)
                .frame(maxWidth: .infinity, alignment: .leading)
                .frame(minHeight: Tema.areaTocco)
                .padding(.horizontal, 14)
                .background(Color.verde.opacity(0.14), in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .combine)
            .accessibilityHint("Apre l'elenco delle novità")
        }
    }

    // MARK: formazione e avvisi

    /// «Da fare», come `cardDaFare` della web (#436): il titolo con il numero delle voci, le prime 4 una per riga con il suo
    /// pulsante, le altre sotto «Altre N cose da fare». Senza voci, in ogni fase, «✓ Tutto a posto, Mister. Nessuna azione utile
    /// oggi.»; un server vecchio senza il campo non mostra niente.
    @ViewBuilder
    private func daFare(_ oggi: Oggi) -> some View {
        let cose = oggi.cose(funzioni: funzioni, tecniche: sessione.puoAmministrare)
        if !cose.isEmpty {
            let primi = Array(cose.prefix(TestiOggi.daFareVisibili))
            let altri = Array(cose.dropFirst(TestiOggi.daFareVisibili))
            Carta {
                titoloDaFare(cose.count)
                ForEach(Array(primi.enumerated()), id: \.element.id) { i, c in
                    RigaConFilo(prima: i == 0) { rigaDaFare(c) }
                }
                if !altri.isEmpty {
                    DisclosureGroup(isExpanded: $tutteLeCose) {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(Array(altri.enumerated()), id: \.element.id) { i, c in
                                RigaConFilo(prima: i == 0) { rigaDaFare(c) }
                            }
                        }
                        .padding(.top, 6)
                    } label: {
                        Text(TestiOggi.altreCose(altri.count))
                            .font(.subheadline.weight(.semibold))
                            .frame(minHeight: Tema.areaTocco, alignment: .leading)
                    }
                    .tint(Color.verde)
                }
            }
        } else if oggi.daFare != nil {
            Carta {
                Label {
                    Text("\(Text(TestiOggi.tuttoAPosto).bold()) \(TestiOggi.nienteDaFare)")
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                } icon: {
                    Image(systemName: "checkmark").foregroundStyle(Color.verde)
                }
            }
            .accessibilityElement(children: .combine)
        }
    }

    /// «Da fare» con accanto, in grigio, quante sono le voci (come la web); VoiceOver lo legge come intestazione: «Da fare, 3».
    private func titoloDaFare(_ n: Int) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "checklist")
                .symbolRenderingMode(.hierarchical)
                .foregroundStyle(Color.verde)
            Text(TestiOggi.daFare).font(.headline)
            Text(String(n)).font(.headline).monospacedDigit().foregroundStyle(Color.testoSecondario)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(TestiOggi.daFareVoce(n))
        .accessibilityAddTraits(.isHeader)
    }

    private func rigaDaFare(_ c: DaFareVoce) -> some View {
        // Con il testo molto grande il pulsante va sotto la frase: affiancati, frase e pulsante andavano a capo a metà parola
        // («Ho schiera-to la consi-gliata»).
        let grande = dimensioneTesto.isAccessibilitySize
        let urgente = c.priorita == TestiOggi.prioritaUrgente
        return HStack(alignment: grande ? .top : .center, spacing: 10) {
            Image(systemName: Self.iconaDaFare(c.tipo))
                .font(.body).foregroundStyle(urgente ? Color.attenzione : Color.testoSecondario)
                .frame(width: latoIcona)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: grande ? 8 : 2) {
                // solo il testo del server, come la web; la voce urgente lo dice anche a parole («Urgente»), non solo con il colore
                Group {
                    if urgente {
                        Text("\(Text(TestiOggi.urgente).bold().foregroundStyle(Color.malus)) \(c.testo)")
                    } else {
                        Text(c.testo)
                    }
                }
                .font(.subheadline).fixedSize(horizontal: false, vertical: true)
                if grande { pulsanteDaFare(c) }
            }
            if !grande {
                Spacer(minLength: 6)
                pulsanteDaFare(c)
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func pulsanteDaFare(_ c: DaFareVoce) -> some View {
        if let d = c.destinazione?.destinazione {
            Button(c.azione ?? "Apri") { vaiA(d, tipo: c.tipo) }
                .font(.subheadline.weight(.semibold))
                .buttonStyle(.bordered)
                .tint(Color.verde)
                .frame(minHeight: 44)
        }
    }

    /// Apre la destinazione di una cosa da fare.
    private func vaiA(_ d: Destinazione, tipo: String? = nil) {
        if tipo == "rose", case .sezione = d { nav.vai(a: .pagina(.importa)) }   // «rose vecchie»: l'importazione sta in Squadra
        else if case .sezione(let s) = d { vaiASezione(s) }
        else if case .pagina = d { nav.vai(a: d) }
        else if case .giocatore(let id) = d { apri(id) }
        else if case .impostazioni = d {
            // «Riprendi» la configurazione guidata riapre la guida; le altre voci aprono le Impostazioni
            if tipo == "primo_avvio" { nav.guidaAperta = true } else { apriImpostazioni?() }
        }
    }

    static func iconaDaFare(_ tipo: String?) -> String {
        switch tipo {
        case "dubbio": return "exclamationmark.triangle"
        case "formazione": return "sportscourt"
        case "svincolato": return "arrow.triangle.swap"
        case "scambio": return "arrow.left.arrow.right"
        case "rose": return "doc.badge.plus"
        case "certificato": return "clock.badge.exclamationmark"
        case "diario": return "book"
        case "backup": return "externaldrive"
        case "server": return "server.rack"
        case "primo_avvio": return "sparkles"
        default: return "checkmark.circle"
        }
    }

    @ViewBuilder
    private var daControllare: some View {
        if !vm.daControllare.isEmpty {
            Carta(TestiOggi.daControllare, simbolo: "exclamationmark.triangle") {
                Text(TestiOggi.daControllareSotto).font(.caption).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
                ForEach(Array(vm.daControllare.enumerated()), id: \.element.ident) { i, a in
                    RigaConFilo(prima: i == 0) { riga(a) }
                }
            }
        }
    }

    @ViewBuilder
    private var indisponibili: some View {
        if !vm.indisponibili.isEmpty {
            Carta {
                DisclosureGroup(TestiOggi.indisponibili(vm.indisponibili.count)) {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(vm.indisponibili.enumerated()), id: \.element.ident) { i, a in
                            RigaConFilo(prima: i == 0) { riga(a) }
                        }
                    }
                    .padding(.top, 6)
                }
                .tint(Color.testoSecondario)
            }
        }
    }

    @ViewBuilder
    private var diffidati: some View {
        if !vm.diffidati.isEmpty {
            Carta(TestiOggi.diffidati, simbolo: "rectangle.portrait.fill") {
                ForEach(Array(vm.diffidati.enumerated()), id: \.element.ident) { i, a in
                    RigaConFilo(prima: i == 0) { riga(a) }
                }
            }
        }
    }

    /// Il colore della pillola, come il pallino della web: rosso per le assenze, arancio da guardare, giallo il resto.
    private func colore(_ gravita: Etichetta.Gravita) -> Color {
        switch gravita {
        case .grave: return .red
        case .attenzione: return .orange
        case .normale: return .yellow
        }
    }

    /// Un avviso su un giocatore: un tocco apre la sua scheda. Il pallino colorato dice la gravità (e il testo la ripete).
    /// Il testo è quello del server («In dubbio · gioca 55%»), o le stesse parole se un server vecchio non lo manda.
    private func riga(_ a: Avviso) -> some View {
        Button { apri(a.id) } label: {
            HStack(alignment: .top, spacing: 10) {
                BadgeRuolo(ruolo: a.ruolo ?? "?")
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(a.nome).font(.headline)
                        Text(ColoriSquadra.sigla(a.squadra)).font(.caption).foregroundStyle(Color.testoSecondario)
                    }
                    // Il tipo («In dubbio · gioca 55%») sta già nella pillola a destra: qui solo la nota, se c'è.
                    if let nota = a.nota, !nota.isEmpty {
                        Text(nota).font(.caption).foregroundStyle(Color.testoSecondario)
                    }
                }
                Spacer(minLength: 0)
                Capsula(testo: a.descrizione, colore: colore(a.gravita)).accessibilityHidden(true)
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(a.nome), \(nomeRuolo(a.ruolo ?? "")), \(a.descrizione)\(a.nota.map { ": " + $0 } ?? "")")
        }
        .buttonStyle(.plain)
        .accessibilityHint("Apre la scheda del giocatore")
    }

    @ViewBuilder
    private func migliori(_ oggi: Oggi) -> some View {
        if let lista = oggi.migliori, !lista.isEmpty {
            Carta(TestiOggi.migliori, simbolo: "star.fill") {
                ForEach(Array(lista.enumerated()), id: \.element.id) { i, g in
                    RigaConFilo(prima: i == 0) { RigaGiocatore(g: g, apribile: true) }
                }
            }
        }
    }

    private var partite: some View { PartiteDelTurnoView(vm: vm) }
}

#Preview("Oggi") {
    OggiView(vm: OggiViewModel(server: FinteServer.esempio))
        .environmentObject(Navigazione())
        .environmentObject(SessioneAccount(server: FinteServer.esempio))
}
