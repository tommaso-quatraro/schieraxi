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
    @Environment(\.apriRosaDi) private var apriRosaDi
    @ObservedObject private var immagini = Immagini.condivise
    /// L'ultima versione delle novità che l'utente ha guardato (la scrive la pagina Novità).
    @AppStorage("novitaVista") private var novitaVista = ""
    @ScaledMetric(relativeTo: .largeTitle) private var corpoGrande: CGFloat = 46
    @ScaledMetric(relativeTo: .body) private var latoIcona: CGFloat = 24
    /// Altezza del nome in testa: segue la dimensione del testo, con un tetto (non deve rubare spazio alle schede).
    @ScaledMetric(relativeTo: .title3) private var altezzaNome: CGFloat = 22
    @State private var novitaAnimata = false
    @Environment(\.accessibilityReduceMotion) private var ridotto
    @Environment(\.dynamicTypeSize) private var dimensioneTesto
    @State private var tutteLeCose = false
    @Environment(\.scenePhase) private var fase

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    ScrollViewReader { proxy in
                    // Il nome dell'app in testa allo scorrimento: sparisce scorrendo, senza rubare spazio alle schede.
                    VStack(alignment: .leading, spacing: Tema.spazioSchede) {
                        intestazione
                        Colonne(spazio: Tema.spazioSchede) {
                            if let oggi = vm.oggi {
                                benvenuto(oggi).ingresso(0)
                                senzaGiornata(oggi).ingresso(0)
                                if !oggi.senzaGiornata { testata(oggi).ingresso(0) }
                                // Le fasi della giornata: durante (punti fatti, niente consigli su chi schierare), dopo (riepilogo), prima (come sempre).
                                switch oggi.faseGiornata {
                                case .inCorso:
                                    CartaGiornataInCorso(blocco: oggi.giornataInCorso, attesiPrima: oggi.formazione?.punteggioAtteso,
                                                         partite: oggi.contoPartite).ingresso(1)
                                    partiteRinviate(oggi).ingresso(1)
                                    if let b = oggi.giornataInCorso, !b.sostituzioni.isEmpty { CartaCambiPanchina(cambi: b.sostituzioni).ingresso(2) }
                                    if let b = oggi.giornataInCorso, !b.giocatori.isEmpty { CartaChiGioca(blocco: b).ingresso(3) }
                                    daFare(oggi).ingresso(4)
                                    novita.ingresso(4)
                                case .finita:
                                    CartaRiepilogoGiornata(riepilogo: oggi.riepilogoGiornata, rinvioInCorso: vm.rinvioInCorso) { s, m in
                                        await vm.cambiaRinvio(s, modo: m)
                                    }
                                    .ingresso(1)
                                    .id("riepilogo")
                                    partiteRinviate(oggi).ingresso(1)
                                    daFare(oggi).ingresso(2)
                                    novita.ingresso(2)
                                    if !oggi.senzaGiornata { formazione(oggi).ingresso(3) }
                                case .prima:
                                    partiteRinviate(oggi).ingresso(1)
                                    daFare(oggi).ingresso(1)
                                    novita.ingresso(1)
                                    if !oggi.senzaGiornata { formazione(oggi).ingresso(2) }
                                    daControllare.ingresso(3)
                                    suggerimento
                                    migliori(oggi).ingresso(4)
                                    indisponibili.ingresso(5)
                                    diffidati.ingresso(6)
                                }
                                if funzioni.acceso(Funzione.live) { partite.ingresso(7) }
                            } else if let errore = vm.errore {
                                ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                            } else {
                                Scheletro(schede: 3, righe: 2, testo: "Preparo la giornata…")
                            }
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

    /// Partite rinviate della giornata: quali, i miei coinvolti e cosa vale per questa giornata (niente se non ce ne sono).
    @ViewBuilder
    private func partiteRinviate(_ oggi: Oggi) -> some View {
        if let r = oggi.partiteRinviate {
            CartaPartitaRinviata(scelta: r, inCorso: vm.rinvioInCorso, errore: vm.erroreRinvio) { m in await vm.cambiaRinvio(r, modo: m) }
                .id("rinvio")
        }
    }

    /// Il nome dell'app con lo slogan, piccolo e discreto, in testa allo scorrimento.
    private var intestazione: some View {
        VStack(alignment: .leading, spacing: 3) {
            WordmarkSchieraXI().frame(height: min(altezzaNome, 34))
            SloganSchieraXI()
                .font(.caption.weight(.semibold))
                .foregroundStyle(Color.testoSecondario)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 2)
        .accessibilityElement(children: .combine)
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
            // Giornata e, se manca la divisa, l'invito ad aggiungerla sulla stessa riga; se non ci stanno (testo grande,
            // finestra stretta) l'invito va sotto. Mai accanto al conto alla rovescia: lì diventava una colonna stretta e altissima.
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 8) {
                    etichettaGiornata(oggi)
                    Spacer(minLength: 8)
                    aggiungiDivisa(oggi)
                }
                VStack(alignment: .leading, spacing: 8) {
                    etichettaGiornata(oggi)
                    aggiungiDivisa(oggi)
                }
            }
            // Conto alla rovescia e maglia sulla stessa riga: il riquadro è più basso e il resto di Oggi sale.
            // Con le misure di accessibilità grandi la maglia va sotto: il testo della fase resta intero.
            rigaTestata {
                contoAllaRovescia(oggi).layoutPriority(1)
                if let squadra = oggi.formazione?.squadra, immagini.haImmagine(squadra, tipo: "maglia") {
                    StemmaSquadra(nome: squadra, tipo: "maglia", dimensione: 56, nascondiSeMancante: true)
                        .shadow(color: .black.opacity(0.35), radius: 6, y: 3)
                }
            }
            if oggi.conProbabili == false {
                Label("Mancano le probabili formazioni di questa giornata: i consigli usano le presenze recenti.", systemImage: "clock")
                    .font(.footnote)
                    .foregroundStyle(.white.opacity(0.85))
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background { MagiaColori() }
        .clipShape(RoundedRectangle(cornerRadius: 30, style: .continuous))
        .environment(\.colorScheme, .dark)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(oggi.etichettaGiornata ?? "Giornata")
    }

    private func etichettaGiornata(_ oggi: Oggi) -> some View {
        Label(oggi.etichettaGiornata ?? "Giornata", systemImage: "calendar")
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 12).padding(.vertical, 6)
            .vetro(in: Capsule())
            .fixedSize()
    }

    /// La divisa è LA TUA: se non c'è non si mostra quella di un'altra squadra, si invita ad aggiungerla.
    @ViewBuilder
    private func aggiungiDivisa(_ oggi: Oggi) -> some View {
        if let squadra = oggi.formazione?.squadra, !immagini.haImmagine(squadra, tipo: "maglia"), let apri = apriRosaDi {
            Button { apri(squadra) } label: {
                Label("Aggiungi la tua divisa", systemImage: "tshirt").font(.footnote.weight(.semibold))
                    .padding(.horizontal, 10).padding(.vertical, 6).vetro(in: Capsule())
                    .fixedSize()
                    .frame(minHeight: Tema.areaTocco)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityHint("Apre la tua squadra per caricare la divisa")
        }
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
            // Ogni secondo ricontrolla: a zero il conto alla rovescia lascia il posto a «Chiusa» (come la web).
            TimelineView(.periodic(from: Date(), by: 1)) { contesto in
                let ora = Orologio.daSistema(contesto.date)
                VStack(alignment: .leading, spacing: 4) {
                    if inizio > ora {
                        TestoConto(inizio: inizio, adesso: ora)
                            .font(.system(size: corpoGrande, weight: .bold, design: .rounded))
                            .foregroundStyle(.white)
                            .minimumScaleFactor(0.5)
                            .lineLimit(1)
                        Text(Self.quandoSiChiude(oggi)).font(.subheadline).foregroundStyle(.white.opacity(0.8))
                    } else {
                        Text("Chiusa")
                            .font(.system(size: corpoGrande * 0.87, weight: .bold, design: .rounded))
                            .lineLimit(1)
                            .minimumScaleFactor(0.5)   // testo molto grande: si rimpicciolisce invece di andare a capo a metà parola
                            .foregroundStyle(.white)
                        Text(Self.siEChiusa(oggi)).font(.subheadline).foregroundStyle(.white.opacity(0.8))
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
    /// o «Prima partita …: la formazione va inserita prima» se la scadenza è l'inizio della prima partita.
    static func quandoSiChiude(_ oggi: Oggi) -> String {
        if let s = oggi.scadenza, !s.trimmingCharacters(in: .whitespaces).isEmpty, s != oggi.inizio, let m = oggi.minutiScadenza {
            return "La formazione si chiude \(Quando.leggibile(s)) (\(m) min prima della prima partita)"
        }
        return "Prima partita \(Quando.leggibile(oggi.chiusura)): la formazione va inserita prima"
    }

    /// A scadenza passata, come la web: «La formazione della giornata 7 si è chiusa sab 31 14:50» (numero della lega).
    static func siEChiusa(_ oggi: Oggi) -> String {
        let quando = Quando.leggibile(oggi.chiusura)
        guard let g = oggi.giornataMostrata else { return "La formazione si è chiusa \(quando)" }
        return "La formazione della giornata \(g) si è chiusa \(quando)"
    }

    // MARK: novità

    @ViewBuilder
    private var novita: some View {
        if funzioni.acceso(Funzione.novita), let versione = vm.novitaDaVedere(ultimaVista: novitaVista) {
            Button { apriNovita() } label: {
                HStack(spacing: 10) {
                    Image(systemName: "sparkles")
                        .symbolRenderingMode(.hierarchical)
                        .symbolEffect(.bounce, value: ridotto ? false : novitaAnimata)
                        .accessibilityHidden(true)
                    // Come la web: «Novità nell'app (versione X): tocca per vedere», con «Novità nell'app» in grassetto.
                    Text("\(Text("Novità nell'app").fontWeight(.semibold)) (versione \(versione)): tocca per vedere")
                        .font(.subheadline)
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
            .onAppear { novitaAnimata.toggle() }
        }
    }

    // MARK: formazione e avvisi

    /// La formazione della giornata da giocare. Dopo una giornata finita parla della PROSSIMA: si chiama così e dice da quando prepararla.
    private func formazione(_ oggi: Oggi) -> some View {
        let finita = oggi.faseGiornata == .finita
        return Carta(finita ? "Prossima giornata" : (oggi.formazione?.titoloScheda ?? "La formazione consigliata"),
                     simbolo: finita ? "calendar.badge.clock" : "sportscourt") {
            if let p = oggi.prossimaGiornata {
                Label(TestiFase.prossima(p), systemImage: "clock")
                    .font(.subheadline)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let f = oggi.formazione, f.disponibile {
                HStack(alignment: .firstTextBaseline) {
                    Text(f.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold))
                    Spacer()
                    VStack(alignment: .trailing, spacing: 0) {
                        NumeroCheSale(valore: f.punteggioAtteso ?? 0).font(.title2.bold())
                        Text("punti attesi").font(.caption).foregroundStyle(Color.testoSecondario)
                        if let fascia = IntervalloPunti.frase(f.intervallo, dev: f.dev) {
                            Text(fascia).font(.caption2).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.trailing)
                        }
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel("\(f.tuaScelta ? "La tua scelta" : "Consigliata"): modulo \(f.modulo ?? "non disponibile"), \(Formato.punti(f.punteggioAtteso)) punti attesi")
                Button { vaiASezione(.formazione) } label: { Label("Apri la formazione", systemImage: "sportscourt").frame(maxWidth: .infinity, minHeight: Tema.areaTocco) }
                    .pulsanteVetro(prominente: true)
                if let p = oggi.probabili?.valore {
                    if let avviso = p.avvisoVisibile {
                        Label(avviso, systemImage: "exclamationmark.triangle.fill")
                            .font(.subheadline.weight(.semibold)).foregroundStyle(.orange)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if let riga = p.riga {
                        Text(riga).font(.footnote).foregroundStyle(Color.testoSecondario)
                            .fixedSize(horizontal: false, vertical: true)
                            .accessibilityLabel(riga)
                    }
                }
            } else {
                Text("Formazione non disponibile.").foregroundStyle(Color.testoSecondario)
            }
        }
    }

    /// «Da fare»: le cose che aspettano te, una per riga con il suo pulsante (4 righe, poi «Altre N cose»). Solo se ce n'è almeno una.
    @ViewBuilder
    private func daFare(_ oggi: Oggi) -> some View {
        let cose = oggi.cose(funzioni: funzioni, tecniche: sessione.puoAmministrare)
        if !cose.isEmpty {
            let visibili = tutteLeCose ? cose : Array(cose.prefix(4))
            Carta("Da fare", simbolo: "checklist") {
                ForEach(Array(visibili.enumerated()), id: \.element.id) { i, c in
                    RigaConFilo(prima: i == 0) { rigaDaFare(c) }
                }
                if cose.count > 4 {
                    Button {
                        withAnimation(Tema.morbida) { tutteLeCose.toggle() }
                    } label: {
                        Text(tutteLeCose ? "Meno cose" : "Altre \(cose.count - 4) \(cose.count - 4 == 1 ? "cosa" : "cose")")
                            .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Color.verde)
                }
            }
        } else if oggi.daFare != nil, oggi.conConsigli {   // durante e dopo la giornata la riga vuota non serve
            Text("Nessuna azione utile oggi")
                .font(.footnote).foregroundStyle(Color.testoSecondario)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 4)
        }
    }

    private func rigaDaFare(_ c: DaFareVoce) -> some View {
        // Con il testo molto grande il pulsante va sotto la frase: affiancati, frase e pulsante andavano a capo a metà parola
        // («Ho schiera-to la consi-gliata»).
        let grande = dimensioneTesto.isAccessibilitySize
        return HStack(alignment: grande ? .top : .center, spacing: 10) {
            Image(systemName: Self.iconaDaFare(c.tipo))
                .font(.body).foregroundStyle((c.priorita ?? 3) == 1 ? Color.attenzione : Color.testoSecondario)
                .frame(width: latoIcona)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: grande ? 8 : 2) {
                Text(c.testo).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                if let m = c.motivo?.trimmingCharacters(in: .whitespacesAndNewlines), !m.isEmpty {
                    Text(m).font(.caption).foregroundStyle(Color.testoSecondario).fixedSize(horizontal: false, vertical: true)
                }
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
            Carta("Da controllare", simbolo: "exclamationmark.triangle") {
                Text("Mister, c'è qualche dubbio in formazione. Riguarda le probabili prima del fischio.").font(.caption).foregroundStyle(Color.testoSecondario)
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
                DisclosureGroup("Indisponibili in rosa (\(vm.indisponibili.count))") {
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
            Carta("Diffidati", simbolo: "rectangle.portrait.fill") {
                ForEach(Array(vm.diffidati.enumerated()), id: \.element.ident) { i, a in
                    RigaConFilo(prima: i == 0) { riga(a) }
                }
            }
        }
    }

    private func colore(_ tipo: String?) -> Color {
        switch tipo {
        case "infortunato", "squalificato": return .red
        case "dubbio": return .orange
        default: return .yellow
        }
    }

    /// «In dubbio · gioca 55%» come nella web app: per i dubbi, la probabilità di giocare.
    private func etichettaTipo(_ a: Avviso) -> String {
        let nome = nomeTipo(a.tipo)
        if a.tipo == "dubbio", let p = a.pVoto { return "\(nome) · gioca \(Formato.percento(p))%" }
        return nome
    }

    private func nomeTipo(_ tipo: String?) -> String {
        switch tipo {
        case "infortunato": return "Infortunato"
        case "squalificato": return "Squalificato"
        case "dubbio": return "In dubbio"
        case "diffidato": return "Diffidato"
        default: return (tipo ?? "").primaMaiuscola
        }
    }

    /// Un avviso su un giocatore: un tocco apre la sua scheda. Il pallino colorato dice la gravità (e il testo la ripete).
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
                Capsula(testo: etichettaTipo(a), colore: colore(a.tipo)).accessibilityHidden(true)
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(a.nome), \(nomeRuolo(a.ruolo ?? "")), \(etichettaTipo(a))\(a.nota.map { ": " + $0 } ?? "")")
        }
        .buttonStyle(.plain)
        .accessibilityHint("Apre la scheda del giocatore")
    }

    @ViewBuilder
    private func migliori(_ oggi: Oggi) -> some View {
        if let lista = oggi.migliori, !lista.isEmpty {
            Carta("I tuoi migliori della giornata", simbolo: "star.fill") {
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
