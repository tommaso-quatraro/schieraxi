import SwiftUI
import TipKit

/// Schermata Formazione: solo presentazione. Dati e logica sono in `FormazioneViewModel`.
struct FormazioneView: View {
    @ObservedObject var vm: FormazioneViewModel
    @State private var daSostituire: Giocatore?
    @Namespace private var moduloNS
    @Namespace private var stileNS

    /// Dall'alto in basso come sul campo: attacco in alto, portiere in basso.
    private let ruoli = ["A", "C", "D", "P"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    /// Cosa fa ogni stile, a parole (come nella web app).
    static func descrizioneStile(_ rischio: Int) -> String {
        switch rischio {
        case ...(-2): return "Punta su chi gioca quasi di sicuro: meno rischio di una brutta giornata, anche se i punti attesi scendono un po'."
        case -1: return "Preferisce i titolari più sicuri, accettando di perdere qualche decimo di punto atteso."
        case 0: return "Il sistema sceglie la formazione con più punti attesi e, a parità, quella con i titolari più sicuri."
        case 1: return "Qualche scommessa su chi, se gioca, può fare molti punti: più possibilità di una giornata eccezionale."
        default: return "Scommette di più su chi può fare il colpo: la giornata eccezionale è più probabile, ma anche quella brutta."
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: Tema.spazioSchede) {
                        if let f = vm.formazione {
                            bannerSquadra
                            let v = vm.vista(f)
                            cardStile(f, v).ingresso(0)
                            if !Demo.attivo { TipView(Suggerimenti.campo).tipBackground(Color.sfondoScheda) }
                            Carta("Campo", simbolo: "sportscourt") { CampoFormazione(titolari: v.titolari, apribile: true) }.ingresso(3)
                            // Un'unica scheda con i quattro reparti in ordine (Portiere, Difensori, Centrocampisti, Attaccanti):
                            // sull'iPad le colonne si leggono così dall'alto in basso senza saltare da una parte all'altra.
                            Carta("Titolari", simbolo: "person.3.fill") {
                                ForEach(ruoli, id: \.self) { r in
                                    let gruppo = v.titolari.filter { $0.ruolo == r }
                                    if !gruppo.isEmpty {
                                        Text("\(nomiRuolo[r] ?? r) (\(gruppo.count))").titoletto().padding(.top, 4)
                                        ForEach(gruppo) { g in rigaTitolare(g, f, v) }
                                    }
                                }
                            }
                            .ingresso(4)
                            Carta("Panchina", simbolo: "chair.lounge.fill") {
                                Text("In quest'ordine: entra il primo che può sostituire chi resta senza voto.").font(.caption).foregroundStyle(.secondary)
                                ForEach(Array(v.panchina.enumerated()), id: \.element.id) { i, g in
                                    RigaConFilo(prima: i == 0) { RigaGiocatore(g: g, apribile: true) }
                                }
                            }
                            .ingresso(5)
                            fuori(f, v)
                            Text("Il numero è il fantavoto atteso se gioca. I punti attesi della squadra pesano ogni fantavoto per la probabilità di giocare. Anello arancio: non titolare sicuro. Anello attorno alla foto: indice (100 = il migliore del ruolo).")
                                .font(.caption).foregroundStyle(.secondary).padding(.horizontal, 4)
                        } else if let errore = vm.errore {
                            ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                        } else {
                            Scheletro(schede: 3, righe: 3, testo: "Scelgo gli undici…")
                        }
                    }
                    .padding(.horizontal, Tema.margine)
                    .padding(.bottom, 24)
                    .animation(Tema.morbida, value: vm.formazione != nil)
                }
                .demoInFondo()
                .refreshable { await vm.carica() }
                .avvisoDatiSalvati(vm.datiSalvati)
                .bordiMorbidi()
            }
            .navigationTitle("Formazione")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if let f = vm.formazione {
                        Menu {
                            ShareLink(item: vm.testo(f)) { Label("Condividi come testo", systemImage: "text.alignleft") }
                            Button { vm.preparaImmagine(f) } label: { Label("Condividi come immagine", systemImage: "photo") }
                            Button { vm.copiaTesto(f) } label: { Label("Copia il testo", systemImage: "doc.on.doc") }
                        } label: {
                            Image(systemName: "square.and.arrow.up").frame(minWidth: 44, minHeight: 44)
                        }
                        .sensoryFeedback(trigger: vm.anteprimaImmagine?.id) { _, nuovo in nuovo != nil ? .success : nil }
                        .accessibilityLabel("Condividi la formazione")
                    }
                }
            }
            .ricercaGlobale()
            .sheet(item: $daSostituire) { g in
                if let f = vm.formazione {
                    SostituzioneSheet(uscente: g, formazione: f, titolari: vm.manuale ?? []) { nuovo in
                        vm.sostituisci(g.id, con: nuovo)
                        daSostituire = nil
                    }
                }
            }
            .sheet(item: $vm.confrontoAperto) { inizio in
                ConfrontoSheet(inizio: inizio, contesto: vm.contestoConfronto, server: vm.server)
            }
            .sheet(item: $vm.anteprimaImmagine) { immagine in
                AnteprimaImmagineSheet(elemento: immagine)
            }
            .task { await vm.carica() }
        }
    }

    // MARK: un'altra squadra

    @ViewBuilder
    private var bannerSquadra: some View {
        if let nome = vm.squadraVista {
            Carta {
                Label("Stai guardando la formazione di \(nome)", systemImage: "eye").font(.subheadline)
                Button { vm.tornaAllaMia() } label: { Text("Torna alla tua").frame(minHeight: 44) }
                    .pulsanteVetro()
            }
        }
    }

    // MARK: righe

    /// In modifica a mano ogni titolare è un bottone che apre la scelta del sostituto; altrimenti un tocco apre la scheda,
    /// «⇄» confronta con un altro della rosa e sotto i titolari incerti ci sono le alternative vicine (ballottaggio).
    @ViewBuilder
    private func rigaTitolare(_ g: Giocatore, _ f: Formazione, _ v: VistaFormazione) -> some View {
        if vm.manuale != nil {
            Button { daSostituire = g } label: {
                HStack { RigaGiocatore(g: g); Image(systemName: "arrow.left.arrow.right").foregroundStyle(Color.verde).accessibilityHidden(true) }
                    .frame(minHeight: 44)
            }
            .buttonStyle(StilePressione())
            .accessibilityHint("Apre la scelta del giocatore che prende il suo posto")
        } else {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 4) {
                    RigaGiocatore(g: g, apribile: true)
                    Button { vm.confrontoAperto = .scelta(g.id) } label: {
                        Image(systemName: "arrow.left.arrow.right").frame(minWidth: 44, minHeight: 44).contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Color.verde)
                    .accessibilityLabel("Confronta \(g.nome) con un altro della rosa")
                }
                ballottaggio(g, f, v)
            }
        }
    }

    @ViewBuilder
    private func ballottaggio(_ g: Giocatore, _ f: Formazione, _ v: VistaFormazione) -> some View {
        let alternative = vm.ballottaggio(per: g, f, v)
        if !alternative.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text("Ballottaggio · alternative vicine").font(.caption).foregroundStyle(.secondary)
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 8) { ForEach(alternative) { a in chipAlternativa(a, rispetto: g) } }
                    VStack(alignment: .leading, spacing: 6) { ForEach(alternative) { a in chipAlternativa(a, rispetto: g) } }
                }
            }
            .padding(.leading, 58)
        }
    }

    private func chipAlternativa(_ a: Ballottaggio.Alternativa, rispetto g: Giocatore) -> some View {
        Button { vm.confrontoAperto = .coppia(g.id, a.giocatore.id) } label: {
            HStack(spacing: 5) {
                Text(a.giocatore.nomeCorto).font(.caption.weight(.semibold))
                Text(Formato.conSegno(a.differenza)).font(.caption.bold()).monospacedDigit()
                    .foregroundStyle(a.quasiPari ? Color.secondary : (a.differenza > 0 ? Color.verde : Color.attenzione))
                if a.quasiPari { Text("quasi pari").font(.caption2).foregroundStyle(.secondary) }
            }
            .padding(.horizontal, 10)
            .frame(minHeight: 44)
            .background(Color.sfondoIncavo, in: Capsule())
        }
        .buttonStyle(StilePressione())
        .accessibilityLabel("Confronta \(g.nome) con \(a.giocatore.nome), \(Formato.conSegno(a.differenza)) punti attesi\(a.quasiPari ? ", quasi pari" : "")")
    }

    @ViewBuilder
    private func fuori(_ f: Formazione, _ v: VistaFormazione) -> some View {
        let altri = vm.fuori(f, v)
        if !altri.isEmpty || !(f.senzaDati ?? []).isEmpty {
            Carta {
                DisclosureGroup("Fuori dalla formazione (\(altri.count))") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(altri) { RigaGiocatore(g: $0, apribile: true) }
                        if let senza = f.senzaDati, !senza.isEmpty {
                            Text("Senza dati per questa giornata: " + senza.joined(separator: ", ")).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.top, 6)
                }
                .tint(.secondary)
            }
        }
    }

    // MARK: stile, modulo e punti (una sola card)

    /// Giornata, punti, stile con la sua descrizione, modulo proposto e «Modifica a mano» in una card compatta:
    /// il campo parte subito sotto.
    private func cardStile(_ f: Formazione, _ v: VistaFormazione) -> some View {
        Carta {
            intestazione(f, v)
            if f.conProbabili == false {
                Label("Probabili formazioni non ancora uscite: uso le presenze recenti.", systemImage: "clock").font(.footnote).foregroundStyle(.secondary)
            }
            if vm.manuale == nil {
                if let livelli = f.livelli, !livelli.isEmpty { sceltaStile(f, livelli) }
            } else {
                testoManuale
            }
            if let messaggio = vm.messaggio { Text(messaggio).font(.footnote).foregroundStyle(.secondary) }
        }
    }

    private func intestazione(_ f: Formazione, _ v: VistaFormazione) -> some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 8) {
                    if let nome = f.squadra { StemmaSquadra(nome: nome, dimensione: 28, nascondiSeMancante: true) }
                    Text(v.modulo).font(.system(.title2, design: .rounded).weight(.bold))
                }
                Text("Giornata \(f.giornata) · " + (vm.manuale != nil ? "la tua scelta" : (v.modulo == f.modulo && vm.rischio == (f.stileConsigliato ?? 0) ? "modulo consigliato" : "modulo scelto")))
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 0) {
                Text(Formato.punti(v.punti)).font(.title2.bold()).monospacedDigit().numerico(v.punti)
                Text("punti attesi" + (vm.fascia(f).map { " · \($0)" } ?? "")).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.trailing)
            }
        }
        .accessibilityElement(children: .combine)
    }

    /// Gli stili come scelte in fila, la loro descrizione, il modulo proposto e i moduli.
    @ViewBuilder
    private func sceltaStile(_ f: Formazione, _ livelli: [LivelloRischio]) -> some View {
        let livello = livelli.first(where: { $0.rischio == vm.rischio }) ?? livelli[0]
        let consigliato = f.stileConsigliato ?? 0
        FilaScorrevole {
            ForEach(livelli) { l in
                let attivo = l.rischio == livello.rischio
                Button { withAnimation(Tema.molla) { vm.scegliStile(l.rischio) } } label: {
                    Text(l.nome + (l.rischio == consigliato ? " ★" : ""))
                        .font(.subheadline.bold())
                        .padding(.horizontal, 14)
                        .frame(minHeight: 44)
                        .pillola(attiva: attivo, spazio: stileNS)
                }
                .buttonStyle(StilePressione())
                .accessibilityLabel("Stile \(l.nome)\(l.rischio == consigliato ? ", consigliato" : "")")
                .accessibilityAddTraits(attivo ? .isSelected : [])
            }
        }
        (Text(livello.nome).bold() + Text(" · " + (livello.descrizione ?? Self.descrizioneStile(livello.rischio))))
            .font(.footnote).foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
        HStack {
            Text("Modulo proposto: \(livello.modulo)").font(.footnote.weight(.semibold))
            Spacer()
            modificaAMano(f)
        }
        FilaScorrevole {
            ForEach(livello.moduli) { m in
                let attivo = vm.moduloAttivo(livello) == m.modulo
                Button { withAnimation(Tema.molla) { vm.scegliModulo(m.modulo) } } label: {
                    VStack(spacing: 0) {
                        Text(m.modulo + (m.modulo == livello.modulo ? " ★" : "")).font(.subheadline.bold())
                        Text(Formato.punti(m.punteggioAtteso)).font(.caption2).monospacedDigit()
                    }
                    .padding(.horizontal, 14)
                    .frame(minHeight: 44)
                    .pillola(attiva: attivo, spazio: moduloNS)
                }
                .buttonStyle(StilePressione())
                .accessibilityLabel("Modulo \(m.modulo), \(Formato.punti(m.punteggioAtteso)) punti attesi\(m.modulo == livello.modulo ? ", proposto dallo stile" : "")")
                .accessibilityAddTraits(attivo ? .isSelected : [])
            }
        }
    }

    /// Pulsante piccolo (l'area di tocco resta da 44 pt).
    private func modificaAMano(_ f: Formazione) -> some View {
        Button { vm.iniziaModificaManuale(f) } label: {
            Label("Modifica a mano", systemImage: "hand.tap").font(.footnote.weight(.semibold))
                .padding(.horizontal, 10).padding(.vertical, 5)
                .background(Color.sfondoIncavo, in: Capsule())
                .frame(minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(StilePressione())
        .foregroundStyle(Color.verde)
    }

    @ViewBuilder
    private var testoManuale: some View {
        Text("Hai modificato la formazione a mano: tocca un titolare per sostituirlo con un altro della rosa, i punti attesi si ricalcolano.")
            .font(.footnote).foregroundStyle(.secondary)
        if let r = vm.valutazione, let d = r.differenza {
            Text("\(Formato.conSegno(d)) rispetto alla consigliata con lo stesso modulo (\(Formato.punti(r.consigliataStessoModulo ?? r.consigliata))). "
                 + (IntervalloPunti.frase(r.intervallo, dev: nil).map { "Punti attesi \($0)." }
                    ?? "Brutta giornata \(Formato.intero(r.bruttaGiornata)) · giornata eccezionale \(Formato.intero(r.giornataEccezionale))."))
                .font(.subheadline).foregroundStyle(d >= 0 ? Color.verde : .orange)
        }
        // Affiancati se ci stanno; con il testo grande uno sotto l'altro (invece di spezzarsi su tre righe).
        if let f = vm.formazione {
            ViewThatFits(in: .horizontal) {
                HStack { salva; Spacer(); torna(f) }
                VStack(alignment: .leading, spacing: 0) { salva; torna(f) }
            }
            .font(.subheadline)
        }
    }

    @ViewBuilder
    private var salva: some View {
        // La scelta salvata vale solo per la propria squadra.
        if vm.squadraVista == nil {
            Button { Task { await vm.valuta(salva: true) } } label: {
                Label("Salva come mia scelta", systemImage: "tray.and.arrow.down").fixedSize().frame(minHeight: 44)
            }
            .keyboardShortcut("s", modifiers: .command)
        }
    }

    private func torna(_ f: Formazione) -> some View {
        Button(role: .destructive) { Task { await vm.tornaAllaConsigliata(f) } } label: {
            Text("Torna alla consigliata").fixedSize().frame(minHeight: 44)
        }
    }

}

/// Scelta del sostituto: giocatori della stessa categoria che non sono già titolari.
struct SostituzioneSheet: View {
    let uscente: Giocatore
    let formazione: Formazione
    let titolari: [Int]
    let scelto: (Int) -> Void
    @Environment(\.dismiss) private var chiudi

    private var candidati: [Giocatore] {
        (formazione.schede ?? [:]).values
            .filter { $0.ruolo == uscente.ruolo && !titolari.contains($0.id) }
            .sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
    }

    var body: some View {
        NavigationStack {
            List {
                Section("Al posto di \(uscente.nome)") {
                    ForEach(candidati) { g in
                        Button { scelto(g.id) } label: { RigaGiocatore(g: g).frame(minHeight: 44) }.buttonStyle(.plain)
                    }
                    if candidati.isEmpty {
                        VistaVuota(titolo: "Nessun altro giocatore", icona: "person.slash", descrizione: "Non ci sono altri giocatori di questo ruolo in rosa.")
                    }
                }
            }
            .navigationTitle("Sostituisci")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Annulla") { chiudi() } } }
        }
    }
}

/// L'immagine della formazione, con il pulsante per condividerla (menu Condividi di iOS).
struct AnteprimaImmagineSheet: View {
    let elemento: ImmagineCondivisa
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    Image(uiImage: elemento.immagine).resizable().scaledToFit()
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .frame(maxWidth: 480)
                        .accessibilityLabel("Immagine della formazione")
                    ShareLink(item: Image(uiImage: elemento.immagine), preview: SharePreview(elemento.titolo, image: Image(uiImage: elemento.immagine))) {
                        Label("Condividi l'immagine", systemImage: "square.and.arrow.up").frame(minHeight: 44)
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding(16)
                .frame(maxWidth: .infinity)
            }
            .navigationTitle("Formazione")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
        }
    }
}

#Preview("Formazione") {
    FormazioneView(vm: FormazioneViewModel(server: FinteServer.esempio))
}
