import SwiftUI

// MARK: - Avvisi del server

extension AvvisiServerView {
    /// Il server ha spento le ore tranquille (inizio e fine alla stessa ora): la frase della web (`avv.avevi_scelto_ore`).
    static let testoOreTranquilleSpente = Catalogo.Avv.aveviSceltoOre
}

struct AvvisiServerView: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @StateObject private var vm: AvvisiServerViewModel
    /// Lo stato dei promemoria di questo telefono (permesso, aggiornamento in background): una sola pagina per tutti gli avvisi.
    @ObservedObject private var lega: LegaViewModel

    init(server: any ServerClient, lega: LegaViewModel) {
        _vm = StateObject(wrappedValue: AvvisiServerViewModel(server: server))
        self.lega = lega
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                TitoloNellaPagina()
                Section {
                    RigaValore(titolo: "Notifiche", valore: lega.permesso)
                    Button("Attiva i promemoria sul telefono") { Task { await lega.attivaPromemoria() } }.frame(minHeight: 44)
                    RigaValore(titolo: LegaViewModel.titoloControlli, valore: lega.aggiornamentoInBackground)
                } header: {
                    Text("Promemoria sul telefono").foregroundStyle(Color.testoSecondario)
                } footer: {
                    Text("Ti avvisiamo un'ora e un quarto d'ora prima della scadenza della formazione, anche con l'app chiusa, se lasci accesi i due promemoria qui sotto. Se la formazione consigliata cambia, l'app te lo dice da sola: è iOS a decidere quando controllare, di solito poche volte al giorno.").foregroundStyle(Color.testoSecondario)
                }
                if let s = vm.caricatore.dato {
                    if let errore = vm.erroreSalvataggio {
                        // Prima l'errore finiva solo nella sezione per chi gestisce il server: con gli account non si vedeva.
                        Section {
                            Label(errore, systemImage: "exclamationmark.triangle.fill")
                                .font(.footnote).foregroundStyle(Color.attenzione)
                                .fixedSize(horizontal: false, vertical: true)
                            if vm.puoRiprovare {
                                Button { Task { await vm.riprova() } } label: {
                                    Label(Catalogo.Comune.riprova, systemImage: "arrow.clockwise").frame(minHeight: 44)
                                }
                                .accessibilityHint("Prova di nuovo a salvare la modifica degli avvisi")
                            }
                        }
                        .onAppear { AccessibilityNotification.Announcement(errore).post() }
                    }
                    if vm.oreTranquilleSpente {
                        // Un avviso come quello dell'errore qui sopra: triangolo e colore d'attenzione, non solo testo in grassetto.
                        Section {
                            Label(Self.testoOreTranquilleSpente, systemImage: "exclamationmark.triangle.fill")
                                .font(.footnote).foregroundStyle(Color.attenzione)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    Section {
                        interruttore(TestiImpostazioni.cambi, aiuto: TestiImpostazioni.cambiAiuto, \.cambi)
                        if let prima = vm.impostazioni?.avviso_prima { sceltaAvvisoPrima(prima) }
                        interruttore(TestiImpostazioni.promemoria60, aiuto: TestiImpostazioni.promemoria60Aiuto, \.promemoria_60)
                        interruttore(TestiImpostazioni.promemoria15, \.promemoria_15)   // senza riga d'aiuto, come la web
                        interruttore(TestiImpostazioni.riepilogo, aiuto: TestiImpostazioni.riepilogoAiuto, \.riepilogo)
                        Toggle(isOn: Binding(
                            get: { vm.impostazioni?.copertura ?? true },
                            set: { nuovo in
                                vm.impostazioni?.copertura = nuovo
                                Task { await vm.salva() }
                            })) {
                            NomeConAiuto(TestiImpostazioni.copertura, aiuto: TestiImpostazioni.coperturaAiuto)
                        }
                        .tint(Color.verde)
                        .frame(minHeight: 44)
                    } header: {
                        Text(Catalogo.Asp.avvisiTitolo).foregroundStyle(Color.testoSecondario)
                    } footer: {
                        // Con gli account l'app nativa non riceve gli avvisi del server: lo si dice QUI, accanto agli interruttori,
                        // non in una sezione più in basso (sembrava che gli interruttori valessero per questo telefono).
                        if let nota = Self.notaQualiAvvisi(multiutente: sessione.multiutente) {
                            Text(nota).foregroundStyle(Color.testoSecondario)
                        }
                    }
                    sezioneOreTranquille
                    if !sessione.multiutente {
                    Section {
                        Toggle(isOn: Binding(
                            get: { vm.impostazioni?.app_nativa ?? false },
                            set: { nuovo in
                                vm.impostazioni?.app_nativa = nuovo
                                Task { await vm.salva() }
                            })) {
                            NomeConAiuto(TestiImpostazioni.nativa,
                                         aiuto: "Arrivano con l'app ntfy e il tocco apre questa app. Se hai attivato anche le notifiche della web app potresti riceverli doppi.")
                        }
                        .tint(Color.verde)
                        .frame(minHeight: 44)
                    } header: {
                        Text("Avanzate (per chi gestisce il server)").foregroundStyle(Color.testoSecondario)
                    } footer: {
                        Text("Il server aggiunge da solo il tocco che apre l'app: non devi impostare niente.").foregroundStyle(Color.testoSecondario)
                    }
                    Section {
                        Text("Dispositivi con avvisi web attivi: \(s.dispositivi ?? 0). Canale degli avvisi: \(s.canale == true ? "attivo" : "non configurato"). Con l'Apple ID gratuito l'app nativa non può ricevere notifiche push: gli avvisi del server arrivano con ntfy o dalla web app installata dalla Home.")
                            .font(.footnote).foregroundStyle(Color.testoSecondario)
                        Button(Catalogo.Avv.mandaAvvisoProva) { Task { await vm.provaAvviso() } }.frame(minHeight: 44)
                        if let messaggio = vm.messaggio { Text(messaggio).font(.footnote) }
                    }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .titoloPagina(TestiImpostazioni.notifiche)
        .task { await vm.carica() }
        .task { await lega.aggiornaPermesso() }
    }

    /// Sotto gli interruttori, solo con gli account: quali avvisi arrivano su questo telefono e quali solo dalla web app.
    /// Senza account niente nota (gli avvisi del server arrivano anche con ntfy, vedi «Avanzate»).
    static func notaQualiAvvisi(multiutente: Bool) -> String? {
        guard multiutente else { return nil }
        return "Su questo telefono arrivano i due promemoria, se accesi, e l'avviso quando cambia la formazione consigliata. Gli altri avvisi di questo elenco arrivano dalla web app: apri SchieraXI con Safari e aggiungilo alla schermata Home."
    }

    /// Ore tranquille: niente avvisi in quella fascia (anche i promemoria di questo telefono la rispettano).
    private var sezioneOreTranquille: some View {
        Section {
            Toggle(isOn: Binding(
                get: { vm.impostazioni?.silenzio ?? false },
                set: { nuovo in
                    vm.impostazioni?.silenzio = nuovo
                    if nuovo, vm.impostazioni?.silenzio_da == nil { vm.impostazioni?.silenzio_da = OreTranquille.predefinite.da }
                    if nuovo, vm.impostazioni?.silenzio_a == nil { vm.impostazioni?.silenzio_a = OreTranquille.predefinite.a }
                    Task { await vm.salva() }
                })) {
                NomeConAiuto(TestiImpostazioni.oreTranquille, aiuto: TestiImpostazioni.oreTranquilleAiuto)
            }
            .tint(Color.verde)
            .frame(minHeight: 44)
            if vm.impostazioni?.silenzio == true {
                selettoreOra(Catalogo.Avv.dalle, \.silenzio_da, predefinita: OreTranquille.predefinite.da)
                selettoreOra(Catalogo.Avv.alle, \.silenzio_a, predefinita: OreTranquille.predefinite.a)
            }
        } header: {
            Text(TestiImpostazioni.oreTranquille).foregroundStyle(Color.testoSecondario)
        } footer: { Group {
            if let ore = vm.impostazioni?.oreTranquille, ore.attive {
                Text(ore.da == ore.a ? "Con la stessa ora di inizio e di fine non c'è nessun silenzio." : "Silenzio \(ore.descrizione) (ora italiana).")
            }
        }.foregroundStyle(Color.testoSecondario) }
    }

    private func selettoreOra(_ titolo: String, _ chiave: WritableKeyPath<ImpostazioniAvvisi, Int?>, predefinita: Int) -> some View {
        Picker(titolo, selection: Binding(
            get: { vm.impostazioni?[keyPath: chiave] ?? predefinita },
            set: { nuovo in
                vm.impostazioni?[keyPath: chiave] = nuovo
                Task { await vm.salva() }
            })) {
            ForEach(0..<24, id: \.self) { Text(String(format: "%02d:00", $0)).tag($0) }
        }
        .frame(minHeight: 44)
    }

    /// «Avviso se il consiglio cambia»: si mostra solo se il server manda il campo (un server vecchio non lo conosce).
    /// Si salva come le altre impostazioni (stesso PUT, con If-Match).
    private func sceltaAvvisoPrima(_ attuale: Int) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Picker(selection: Binding(
                get: { vm.impostazioni?.avviso_prima ?? AvvisoPrima.predefinito },
                set: { nuovo in
                    guard nuovo != vm.impostazioni?.avviso_prima else { return }
                    vm.impostazioni?.avviso_prima = nuovo
                    Task { await vm.salva() }
                })) {
                ForEach(AvvisoPrima.scelte(attuale: attuale), id: \.self) { Text(AvvisoPrima.testo($0)).tag($0) }
            } label: {
                Text(AvvisoPrima.titolo)
            }
            .frame(minHeight: 44)
            .accessibilityHint(AvvisoPrima.aiuto)
            Text(AvvisoPrima.aiuto)
                .font(.caption).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityHidden(true)
        }
    }

    /// Un interruttore degli avvisi, con sotto la riga d'aiuto della web (se ce l'ha).
    private func interruttore(_ titolo: String, aiuto: String? = nil, _ chiave: WritableKeyPath<ImpostazioniAvvisi, Bool>) -> some View {
        Toggle(isOn: Binding(
            get: { vm.impostazioni?[keyPath: chiave] ?? false },
            set: { nuovo in
                vm.impostazioni?[keyPath: chiave] = nuovo
                Task { await vm.salva() }
            })) {
            NomeConAiuto(titolo, aiuto: aiuto)
        }
        .tint(Color.verde)
        .frame(minHeight: 44)
    }
}

// MARK: - Crediti e mia squadra

struct CreditiView: View {
    @StateObject private var vm: CreditiViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: CreditiViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                TitoloNellaPagina()
                if let s = vm.caricatore.dato {
                    Section(titolo: Catalogo.Lega.creditiResiduiOgni) {
                        ForEach(s) { sq in
                            HStack {
                                Text(sq.nome)
                                Spacer()
                                TextField("—", text: Binding(get: { vm.valori[sq.nome] ?? "" }, set: { vm.valori[sq.nome] = $0 }))
                                    .keyboardType(.numberPad).multilineTextAlignment(.trailing).frame(minWidth: 80, minHeight: 44)
                            }
                        }
                    }
                    Section {
                        if vm.modificati {
                            Label(Catalogo.Lega.creditiNonSalvati, systemImage: "pencil.circle")
                                .font(.footnote.weight(.semibold)).foregroundStyle(Color.attenzione)
                        }
                        Button(Catalogo.Lega.salvaCrediti) { Task { await vm.salva() } }.frame(minHeight: 44)
                        if let messaggio = vm.messaggio { Text(messaggio).font(.footnote) }
                        Text(Catalogo.Lega.servonoPerConsigli)
                            .font(.footnote).foregroundStyle(Color.testoSecondario)
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .ricercaGlobale()
        .titoloPagina("Crediti")
        .task { await vm.carica() }
    }
}
