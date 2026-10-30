import SwiftUI

/// Logica dell'editor delle regole della lega. Il JSON del server resta intero (`valore`): i campi lo leggono e lo scrivono con
/// percorsi come `bonus.gol.D`, così nessun campo che l'app non conosce va perso. Si può anche incollare il regolamento di Leghe:
/// il server riconosce i valori e l'app li mostra prima di applicarli.
@MainActor
final class RegoleEditorViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<JSONValue>
    @Published var valore: JSONValue = .nullo
    @Published var caricato = false
    @Published var modificato = false
    @Published var esito: String?
    @Published var esitoRiuscito = true
    @Published var inCorso = false
    /// Le fasce del modificatore difesa (si tengono a parte per non far saltare le righe mentre si modificano).
    @Published var fasce: [RegoleLogica.Fascia] = [] {
        didSet { fasceCambiate(fasce) }
    }
    /// Prova del modificatore: voti di portiere e tre difensori.
    @Published var votiProva: [Double] = [6.5, 6, 6.5, 7]
    // Importa dal regolamento di Leghe
    @Published var testoRegolamento = ""
    @Published var riconoscimento: RiconoscimentoRegole?
    @Published var erroreRiconoscimento: String?
    @Published var riconoscimentoInCorso = false

    init(server: any ServerClient) {
        self.server = server
        // Dati che si modificano: niente cache (non si deve ripartire da una copia vecchia).
        caricatore = Caricatore<JSONValue>("/api/regole", snake: false, cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async {
        await caricatore.ricarica()
        if let d = caricatore.dato {
            valore = d
            fasce = RegoleLogica.fasce(d)
            caricato = true
            modificato = false
            esito = nil
        }
    }

    // MARK: campi

    func numero(_ percorso: String, _ predefinito: Double = 0) -> Binding<Double> {
        Binding(get: { self.valore.valore(percorso)?.numero ?? predefinito },
                set: { self.valore.imposta(percorso, JSONValue.numero($0)); self.modificato = true })
    }

    func booleano(_ percorso: String) -> Binding<Bool> {
        Binding(get: { self.valore.valore(percorso)?.booleano ?? false },
                set: { self.valore.imposta(percorso, .booleano($0)); self.modificato = true })
    }

    func testo(_ percorso: String) -> Binding<String> {
        Binding(get: { self.valore.valore(percorso)?.testo ?? "" },
                set: { self.valore.imposta(percorso, .testo($0)); self.modificato = true })
    }

    /// Tutti i moduli che si possono scegliere: quelli noti più quelli già nelle regole.
    var moduliDisponibili: [String] {
        var tutti = RegoleLogica.tuttiIModuli
        for m in moduliAttivi where !tutti.contains(m) { tutti.append(m) }
        return tutti
    }

    var moduliAttivi: [String] { (valore.valore("moduli")?.elenco ?? []).compactMap(\.testo) }

    func alternaModulo(_ modulo: String) {
        var attivi = moduliAttivi
        if let i = attivi.firstIndex(of: modulo) { attivi.remove(at: i) } else { attivi.append(modulo) }
        valore.imposta("moduli", .lista(attivi.map { JSONValue.testo($0) }))
        modificato = true
    }

    /// Posti fissi per ruolo in panchina: se attivi `panchina.posti` è un oggetto, altrimenti null.
    var postiFissi: Binding<Bool> {
        Binding(get: { if case .oggetto? = self.valore.valore("panchina.posti") { return true }; return false },
                set: { acceso in
                    if acceso {
                        self.valore.imposta("panchina.posti", .oggetto(["P": .intero(2), "D": .intero(3), "C": .intero(3), "A": .intero(3)]))
                    } else {
                        self.valore.imposta("panchina.posti", .nullo)
                    }
                    self.modificato = true
                })
    }

    /// Voto d'ufficio quando manca il sostituto: attivo se `voto_senza_sostituto` non è null.
    var votoUfficioAttivo: Binding<Bool> {
        Binding(get: { self.valore.valore("voto_senza_sostituto")?.numero != nil },
                set: { acceso in
                    self.valore.imposta("voto_senza_sostituto", acceso ? JSONValue.numero(4) : .nullo)
                    self.modificato = true
                })
    }

    // MARK: fasce del modificatore difesa

    /// Scrive nel JSON le fasce modificate (se sono davvero diverse da quelle che ci sono già: così il caricamento non conta come modifica).
    func fasceCambiate(_ nuove: [RegoleLogica.Fascia]) {
        let ordinate = nuove.sorted { $0.media < $1.media }
        guard ordinate != RegoleLogica.fasce(valore) else { return }
        RegoleLogica.scriviFasce(nuove, in: &valore)
        modificato = true
    }

    func aggiungiFascia() {
        let ultima = fasce.sorted { $0.media < $1.media }.last
        fasce.append(RegoleLogica.Fascia(media: min(9, (ultima?.media ?? 6) + 0.5), bonus: (ultima?.bonus ?? 0) + 1))
    }

    func togliFascia(_ id: UUID) {
        fasce.removeAll { $0.id == id }
    }

    /// Bonus che darebbero i voti della prova con le fasce attuali.
    var mediaProva: Double { RegoleLogica.mediaDifesa(votiProva) }
    var bonusProva: Double { RegoleLogica.bonusDifesa(media: mediaProva, fasce: fasce) }

    // MARK: importa dal regolamento

    func riconosci() async {
        let testo = testoRegolamento.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !testo.isEmpty else {
            erroreRiconoscimento = "Incolla prima il testo del regolamento."
            return
        }
        riconoscimentoInCorso = true
        defer { riconoscimentoInCorso = false }
        do {
            riconoscimento = try await server.posta("POST", "/api/regole/riconosci", RichiestaTesto(testo: testo))
            erroreRiconoscimento = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            riconoscimento = nil
            erroreRiconoscimento = error.localizedDescription
        }
    }

    /// Mette nei campi i valori riconosciuti. Non salva: lo fa l'utente con «Salva le regole», dopo aver controllato.
    func applicaRiconosciute() {
        guard let r = riconoscimento, !r.modifiche.isEmpty else { return }
        valore = RegoleLogica.applica(r.modifiche, a: valore)
        fasce = RegoleLogica.fasce(valore)
        modificato = true
        esito = "Valori applicati: controlla e tocca «Salva le regole»."
        esitoRiuscito = true
        riconoscimento = nil
        Haptics.selezione()
    }

    // MARK: salvataggio

    func salva() async {
        inCorso = true
        defer { inCorso = false }
        do {
            let pronto = try RegoleLogica.preparaPerSalvataggio(valore)
            let nuove: JSONValue = try await server.posta("PUT", "/api/regole", pronto, snake: false)
            valore = nuove
            fasce = RegoleLogica.fasce(nuove)
            modificato = false
            esito = "Regole salvate: i consigli ora le usano."
            esitoRiuscito = true
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            let conflitto = (error as? ErroreApi)?.eConflitto == true
            if conflitto { await carica() }   // un altro dispositivo ha cambiato le regole: si rilegge la versione nuova
            esito = error.localizedDescription
            esitoRiuscito = false
            Haptics.esito(riuscito: false)
        }
    }

    func annulla() async { await carica() }
}

// MARK: - Vista

/// Un valore numerico con − e + (un Stepper di iOS), con il valore scritto accanto al titolo.
struct RigaStepper: View {
    let titolo: String
    @Binding var valore: Double
    var passo = 0.5
    var minimo = 0.0
    var massimo = 20.0
    var cifre = 1
    var aiuto: String? = nil

    var body: some View {
        Stepper(value: $valore, in: minimo...massimo, step: passo) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 1) {
                    Text(titolo)
                    if let aiuto { Text(aiuto).font(.caption).foregroundStyle(.secondary) }
                }
                Spacer(minLength: 8)
                Text(Formato.decimali(valore, cifre: cifre)).monospacedDigit().foregroundStyle(.secondary)
            }
        }
        .frame(minHeight: 44)
        .accessibilityValue(Formato.decimali(valore, cifre: cifre))
    }
}

/// Regole della lega: punteggi, modificatore difesa, moduli, panchina, rosa e crediti. Si può anche incollare il regolamento di Leghe.
struct RegoleEditorView: View {
    @StateObject private var vm: RegoleEditorViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: RegoleEditorViewModel(server: server))
    }

    private let ruoli = [("P", "Gol di un portiere"), ("D", "Gol di un difensore"), ("C", "Gol di un centrocampista"), ("A", "Gol di un attaccante")]
    private let bonus = [("assist", "Assist"), ("rigore_segnato", "Rigore segnato"), ("rigore_parato", "Rigore parato (portiere)"),
                         ("portiere_imbattuto", "Portiere imbattuto"), ("mvp", "Migliore in campo")]
    private let malus = [("ammonizione", "Ammonizione"), ("espulsione", "Espulsione"), ("autogol", "Autogol"),
                         ("rigore_sbagliato", "Rigore sbagliato"), ("gol_subito_portiere", "Gol subito (portiere)")]
    private let nomiRuolo = ["P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    var body: some View {
        ZStack {
            Sfondo()
            if vm.caricato {
                List {
                    nome
                    importa
                    punteggi
                    difesa
                    moduli
                    panchina
                    rosa
                    salvataggio
                }
                .scrollContentBackground(.hidden)
            } else if let e = vm.caricatore.errore {
                ErroreVista(messaggio: e) { Task { await vm.carica() } }
            } else {
                ScheletroRighe(righe: 6)
            }
        }
        .navigationTitle("Regole")
        .task { await vm.carica() }
    }

    private var nome: some View {
        Section("Nome della lega") {
            TextField("La mia lega", text: vm.testo("nome_lega")).frame(minHeight: 44)
        }
    }

    // MARK: importa da Leghe

    private var importa: some View {
        Section {
            Text("Su Leghe apri il regolamento della competizione, copia il testo e incollalo qui: l'app riconosce i valori e te li mostra prima di applicarli. Non cambia nulla finché non tocchi «Salva le regole».")
                .font(.footnote).foregroundStyle(.secondary)
            TextEditor(text: $vm.testoRegolamento)
                .frame(minHeight: 96)
                .accessibilityLabel("Testo del regolamento")
            Button { Task { await vm.riconosci() } } label: {
                if vm.riconoscimentoInCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                else { Text("Riconosci le regole").frame(maxWidth: .infinity, minHeight: 44) }
            }
            .disabled(vm.riconoscimentoInCorso)
            if let e = vm.erroreRiconoscimento { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
            if let r = vm.riconoscimento { riconosciute(r) }
        } header: { Text("Importa da Leghe") }
    }

    @ViewBuilder
    private func riconosciute(_ r: RiconoscimentoRegole) -> some View {
        if r.modifiche.isEmpty {
            Label("Non ho riconosciuto nessuna regola in questo testo. Controlla di aver copiato la pagina del regolamento, oppure imposta i valori a mano qui sotto.",
                  systemImage: "questionmark.circle").font(.footnote).foregroundStyle(.secondary)
        } else {
            Text("Riconosciuto").font(.headline)
            ForEach(r.modifiche) { m in
                VStack(alignment: .leading, spacing: 2) {
                    Label("\(m.etichetta): \(RegoleLogica.descrivi(m.valore))", systemImage: "checkmark.circle.fill").font(.subheadline)
                    if let riga = m.riga { Text("da: «\(riga)»").font(.caption).foregroundStyle(.secondary) }
                }
                .accessibilityElement(children: .combine)
            }
            if let non = r.nonRiconosciute, !non.isEmpty {
                DisclosureGroup("Righe con numeri non riconosciute (\(non.count))") {
                    Text(non.joined(separator: "\n")).font(.caption).foregroundStyle(.secondary)
                }
            }
            Button { vm.applicaRiconosciute() } label: { Text("Applica ai campi").frame(maxWidth: .infinity, minHeight: 44) }
                .buttonStyle(.borderedProminent)
            Text("Controlla i valori qui sotto e tocca «Salva le regole» in fondo.").font(.caption).foregroundStyle(.secondary)
        }
    }

    // MARK: punteggi

    private var punteggi: some View {
        Group {
            Section("Gol") {
                ForEach(ruoli, id: \.0) { r in
                    RigaStepper(titolo: r.1, valore: vm.numero("bonus.gol.\(r.0)"), minimo: 0, massimo: 20)
                }
            }
            Section("Altri bonus") {
                ForEach(bonus, id: \.0) { b in
                    RigaStepper(titolo: b.1, valore: vm.numero("bonus.\(b.0)"), minimo: 0, massimo: 20)
                }
            }
            Section("Malus") {
                ForEach(malus, id: \.0) { m in
                    RigaStepper(titolo: m.1, valore: vm.numero("bonus.\(m.0)"), minimo: -20, massimo: 0,
                                aiuto: m.0 == "gol_subito_portiere" ? "per ogni gol" : nil)
                }
            }
            Section {
                Picker("Voto di partenza", selection: vm.testo("fonte_voto")) {
                    Text("Redazione").tag("redazione")
                    Text("Statistico").tag("statistico")
                    Text("Italia").tag("italia")
                }
                .pickerStyle(.segmented)
            } header: { Text("Voto di partenza") } footer: {
                Text("Quale voto si somma a bonus e malus: quello che usa la tua lega su Leghe.")
            }
        }
    }

    // MARK: modificatore difesa

    private var difesa: some View {
        Section {
            Toggle("Attivo nella mia lega", isOn: vm.booleano("modificatore_difesa.attivo")).tint(Color.verde).frame(minHeight: 44)
            if vm.valore.valore("modificatore_difesa.attivo")?.booleano == true {
                RigaStepper(titolo: "Difensori minimi in campo", valore: vm.numero("modificatore_difesa.min_difensori", 4), passo: 1,
                            minimo: 3, massimo: 6, cifre: 0, aiuto: "sotto questo numero non si applica")
                Text("La media è la somma di portiere + i 3 migliori difensori, divisa per 4. Per ogni fascia raggiunta si prende il bonus più alto raggiunto.")
                    .font(.footnote).foregroundStyle(.secondary)
                ForEach($vm.fasce) { $f in
                    VStack(alignment: .leading, spacing: 0) {
                        RigaStepper(titolo: "Media almeno", valore: $f.media, passo: 0.25, minimo: 4, massimo: 9, cifre: 2)
                        RigaStepper(titolo: "bonus", valore: $f.bonus, passo: 0.5, minimo: 0, massimo: 20)
                        Button(role: .destructive) { vm.togliFascia(f.id) } label: { Label("Togli la fascia", systemImage: "trash").frame(minHeight: 44) }
                    }
                }
                Button { vm.aggiungiFascia() } label: { Label("Aggiungi una fascia", systemImage: "plus.circle").frame(minHeight: 44) }
                prova
            }
        } header: { Text("Modificatore difesa") } footer: { Text("Un bonus se la difesa prende voti alti.") }
    }

    private var prova: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Prova: voti di portiere e 3 difensori").font(.subheadline.bold())
            ForEach(vm.votiProva.indices, id: \.self) { i in
                RigaStepper(titolo: i == 0 ? "Portiere" : "Difensore \(i)", valore: $vm.votiProva[i], minimo: 3, massimo: 10)
            }
            Text("Media \(Formato.decimali(vm.mediaProva, cifre: 2)) → bonus \(Formato.conSegno(vm.bonusProva, cifre: 0)) punti").font(.headline)
                .accessibilityElement(children: .combine)
        }
    }

    // MARK: moduli, panchina, rosa

    private var moduli: some View {
        Section {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 76), spacing: 8)], spacing: 8) {
                ForEach(vm.moduliDisponibili, id: \.self) { m in
                    let attivo = vm.moduliAttivi.contains(m)
                    Button { vm.alternaModulo(m) } label: {
                        Text(m).font(.subheadline.bold()).frame(maxWidth: .infinity, minHeight: 44)
                            .background(attivo ? Color.verde.opacity(0.35) : Color.primary.opacity(0.08), in: Capsule())
                            .overlay(Capsule().strokeBorder(attivo ? Color.verde : .clear, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Modulo \(m)")
                    .accessibilityAddTraits(attivo ? .isSelected : [])
                }
            }
        } header: { Text("Moduli ammessi") } footer: { Text("Quelli che puoi schierare nella tua lega.") }
    }

    private var panchina: some View {
        Section {
            Toggle("Posti fissi per ruolo", isOn: vm.postiFissi).tint(Color.verde).frame(minHeight: 44)
            if case .oggetto? = vm.valore.valore("panchina.posti") {
                ForEach(["P", "D", "C", "A"], id: \.self) { r in
                    RigaStepper(titolo: nomiRuolo[r] ?? r, valore: vm.numero("panchina.posti.\(r)"), passo: 1, minimo: 0, massimo: 8, cifre: 0)
                }
            } else {
                RigaStepper(titolo: "Giocatori in panchina", valore: vm.numero("panchina.numero", 7), passo: 1, minimo: 1, massimo: 14, cifre: 0)
            }
            RigaStepper(titolo: "Cambi massimi", valore: vm.numero("panchina.max_sostituzioni", 5), passo: 1, minimo: 0, massimo: 14, cifre: 0)
            Picker("Come entrano le riserve", selection: vm.testo("panchina.tipo")) {
                Text("Per ruolo").tag("per_ruolo")
                Text("Libera").tag("libera")
            }
            .pickerStyle(.segmented)
            Text(vm.valore.valore("panchina.tipo")?.testo == "libera"
                 ? "Libera: entra il primo della panchina che può sostituirlo, anche di un ruolo diverso se il modulo resta valido."
                 : "Per ruolo: se un titolare non gioca, entra il primo della panchina dello stesso ruolo.")
                .font(.footnote).foregroundStyle(.secondary)
            Toggle("Cambio modulo nelle sostituzioni", isOn: vm.booleano("panchina.cambio_modulo")).tint(Color.verde).frame(minHeight: 44)
            Toggle("Voto d'ufficio se manca il sostituto", isOn: vm.votoUfficioAttivo).tint(Color.verde).frame(minHeight: 44)
            if vm.votoUfficioAttivo.wrappedValue {
                RigaStepper(titolo: "Voto d'ufficio", valore: vm.numero("voto_senza_sostituto", 4), minimo: 0, massimo: 10)
            }
        } header: { Text("Panchina e sostituzioni") }
    }

    private var rosa: some View {
        Section("Rosa e crediti") {
            ForEach(["P", "D", "C", "A"], id: \.self) { r in
                RigaStepper(titolo: nomiRuolo[r] ?? r, valore: vm.numero("rosa.\(r)"), passo: 1, minimo: 0, massimo: 20, cifre: 0)
            }
            RigaStepper(titolo: "Crediti iniziali", valore: vm.numero("crediti_iniziali"), passo: 10, minimo: 0, massimo: 5000, cifre: 0)
        }
    }

    private var salvataggio: some View {
        Section {
            Button {
                Task { await vm.salva() }
            } label: {
                if vm.inCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                else { Label("Salva le regole", systemImage: "checkmark.circle").frame(maxWidth: .infinity, minHeight: 44) }
            }
            .buttonStyle(.borderedProminent)
            .disabled(vm.inCorso || !vm.modificato)
            Button { Task { await vm.annulla() } } label: { Text("Annulla le modifiche").frame(maxWidth: .infinity, minHeight: 44) }
                .disabled(!vm.modificato)
            if let esito = vm.esito { Text(esito).font(.footnote).foregroundStyle(vm.esitoRiuscito ? Color.secondary : Color.attenzione) }
        }
    }
}
