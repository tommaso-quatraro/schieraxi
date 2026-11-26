import SwiftUI

/// La scheda di un giocatore (foglio), una sola come la web (#616, `htmlScheda` di app.js). In alto ciò che serve per decidere:
/// volto, nome, «Ruolo · club», la partita, il fantavoto atteso «se gioca» con «gioca N%» e lo stato a parole, la nota della
/// fonte, «Perché è titolare», «Perché questo numero», gli ultimi voti e, nella tua formazione ancora aperta, «Sostituisci» per
/// un titolare o «Metti in campo» per chi non è fra gli 11 (#778). Il resto sta in «Tutti i numeri», chiuso. Dalla Formazione si
/// apre subito con la previsione già letta (`ContestoScheda`); gli ultimi voti e «Tutti i numeri» arrivano con `/api/giocatore`.
struct GiocatoreSheet: View {
    let id: Int
    let server: any ServerClient
    var contesto: ContestoScheda? = nil
    /// «Sostituisci»: chi apre il foglio lo chiude e poi apre la scelta del sostituto.
    var sostituisci: (() -> Void)? = nil
    /// «Metti in campo»: chi apre il foglio lo chiude e poi apre l'elenco di chi può lasciargli il posto.
    var mettiInCampo: (() -> Void)? = nil
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack {
            GiocatoreCorpo(id: id, server: server, contesto: contesto, sostituisci: sostituisci, mettiInCampo: mettiInCampo)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button(Catalogo.Shell.chiudi) { chiudi() }.keyboardShortcut(.cancelAction)
                    }
                }
                .destinazioniGiocatore(server: server)
        }
    }
}

extension View {
    /// Le pagine che si aprono dentro un `NavigationStack` di giocatori: la scheda di un giocatore (dai risultati della ricerca).
    func destinazioniGiocatore(server: any ServerClient) -> some View {
        navigationDestination(for: PassoScheda.self) { passo in
            switch passo {
            case .scheda(let id):
                GiocatoreCorpo(id: id, server: server)
            }
        }
    }
}

struct GiocatoreCorpo: View {
    let id: Int
    let contesto: ContestoScheda?
    let sostituisci: (() -> Void)?
    let mettiInCampo: (() -> Void)?
    @StateObject private var vm: SchedaGiocatoreViewModel
    /// «Tutti i numeri» parte chiuso; solo nella foto `giocatore-fondo` (demo con `-DEMO_FONDO`) è aperto, per vederlo.
    @State private var numeriAperti = Demo.attivo && Demo.argomento("DEMO_FONDO") != nil

    init(id: Int, server: any ServerClient, contesto: ContestoScheda? = nil, sostituisci: (() -> Void)? = nil,
         mettiInCampo: (() -> Void)? = nil) {
        self.id = id
        self.contesto = contesto
        self.sostituisci = sostituisci
        self.mettiInCampo = mettiInCampo
        _vm = StateObject(wrappedValue: SchedaGiocatoreViewModel(id: id, server: server))
    }

    /// Intestazione e previsione: dalla Formazione subito, altrimenti dalla scheda del server.
    private var testa: TestaScheda? {
        if let contesto { return TestaScheda(previsione: contesto.previsione) }
        return vm.caricatore.dato.map { TestaScheda(scheda: $0) }
    }

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                Colonne(spazio: 14) {
                    if let t = testa {
                        cartaTesta(t)
                        if let perche = contesto?.perche {
                            Carta(Catalogo.Formazione.percheTitolare) {
                                Text(perche).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        if let p = t.previsione, let motivi = LetturaScheda.perche(p) {
                            Carta(PercheNumero.titolo) { BloccoPercheNumero(perche: motivi) }
                        }
                        cartaUltimiVoti
                        azioneFormazione
                        cartaTuttiINumeri
                    } else if let e = vm.caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await vm.carica() } }
                    } else {
                        Scheletro(schede: 3, righe: 2, testo: Catalogo.Mercato.caricoScheda)
                    }
                }
                .padding(16)
                .animation(Tema.morbida, value: vm.caricatore.dato != nil)
            }
            // foto `giocatore-fondo`: la scheda parte scorsa in fondo, dove sta «Dati fino al …», l'ultima riga di «Tutti i
            // numeri» (#911), anche col testo grande. Dal #862 la foto scorreva al titolo «Statistiche avanzate», dove la riga
            // stava allora: con la riga in fondo, scorrere al fondo del blocco col testo al massimo si fermava più in alto
            .demoInFondo()
            .refreshable { await vm.carica() }
            .avvisoDatiSalvati(vm.caricatore)
            .bordiMorbidi()
        }
        // Il nome si legge una volta sola, grande, nell'intestazione.
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.carica() }
    }

    // MARK: intestazione e cifre

    private func cartaTesta(_ t: TestaScheda) -> some View {
        Carta {
            FilaAdattiva(spazio: 14) {
                AvatarGiocatore(id: t.id, squadra: t.slug, dimensione: 84, nome: t.nome, ruolo: t.ruolo)
                VStack(alignment: .leading, spacing: 4) {
                    Text(t.nome).font(.title2.bold())
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityAddTraits(.isHeader)
                    ruoloEClub(t)
                    if let p = t.previsione, let partita = LetturaScheda.partita(p, adesso: Orologio.adesso()) {
                        Text(TestoACapo.puntoInFondo(partita)).font(.subheadline).foregroundStyle(Color.testoSecondario)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Spacer(minLength: 0)
            }
            .accessibilityElement(children: .combine)
            Divider().padding(.vertical, 2)
            CifreScheda(cifre: LetturaScheda.cifre(t.previsione))
            if let p = t.previsione, let nota = LetturaScheda.nota(p) {
                Text(nota).font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    /// «Attaccante · Genoa» e, per un diffidato, la pillola arancio accanto (sotto, se non ci sta).
    @ViewBuilder
    private func ruoloEClub(_ t: TestaScheda) -> some View {
        let testo = Text(TestoACapo.puntoInFondo(LetturaScheda.ruoloEClub(ruolo: t.ruolo, club: t.club)))
            .font(.subheadline).foregroundStyle(Color.testoSecondario)
        if t.previsione?.diffidato == true {
            let diffidato = PillolaEtichetta(etichetta: Etichetta(testo: Catalogo.Oggi.diffidatoTipo, tono: .attenzione))
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 6) { testo.fixedSize(); diffidato }
                VStack(alignment: .leading, spacing: 4) { testo.fixedSize(horizontal: false, vertical: true); diffidato }
            }
        } else {
            testo.fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: ultimi voti, «Sostituisci», tutti i numeri

    /// Le ultime cinque giornate in pallini, come la web, a capo se non ci stanno; mentre arriva la scheda del server «Carico…», se
    /// non arriva il motivo.
    private var cartaUltimiVoti: some View {
        Carta(Catalogo.Formazione.ultimiVoti) {
            if let s = vm.caricatore.dato {
                if let forma = Forma.di(s.voti ?? [], andamento: s.codiceAndamento) {
                    FilaPillole(spazio: 6) {
                        ForEach(forma.ultime) { pallino($0) }
                    }
                } else {
                    Text(Catalogo.Mercato.nessunaPresenzaQuesta).font(.subheadline).foregroundStyle(Color.testoSecondario)
                }
            } else {
                attesa
            }
        }
    }

    @ViewBuilder
    private var attesa: some View {
        if let e = vm.caricatore.errore {
            Text(e).font(.footnote).foregroundStyle(Color.testoSecondario).fixedSize(horizontal: false, vertical: true)
        } else {
            Text(Catalogo.Comune.carico).font(.footnote).foregroundStyle(Color.testoSecondario)
        }
    }

    /// Un voto passato in un pallino neutro, come la web (`.pallini i`) e il vocabolario comune: mai verde, arancio o rosso per
    /// valore (#863). Con il testo grande il pallino si allarga in una pillola: il numero non si taglia.
    private func pallino(_ v: VotoGiornata) -> some View {
        let etichetta = v.fv.map { Catalogo.Mercato.fantavoto + " " + Formato.decimali($0) } ?? Catalogo.Mercato.sv
        return Text(v.fv.map { Formato.decimali($0) } ?? Catalogo.Mercato.sv)
            .font(.caption.bold()).monospacedDigit()
            .foregroundStyle(.primary)
            .padding(.horizontal, 6)
            .frame(minWidth: 40, minHeight: 40)
            .background(Color.primary.opacity(0.08), in: Capsule())
            .overlay(Capsule().strokeBorder(Color.testoSecondario.opacity(0.35), lineWidth: 1))
            .accessibilityLabel("\(TempiLega.serieA(v.giornata)): \(etichetta)")
    }

    /// Nella tua formazione ancora aperta «Sostituisci» per un titolare e «Metti in campo» per chi non è fra gli 11 (alle stesse
    /// condizioni, come la web); per chi gioca un anticipo già cominciato la frase della web (`formazione.bloccati`).
    @ViewBuilder
    private var azioneFormazione: some View {
        if let contesto, contesto.sostituibile, let sostituisci {
            pulsanteFormazione(Catalogo.Formazione.sostituisci, azione: sostituisci)
        } else if let contesto, contesto.entrabile, let mettiInCampo {
            pulsanteFormazione(Catalogo.Formazione.mettiInCampo, azione: mettiInCampo)
        } else if contesto?.fermo == true {
            Text(Catalogo.Formazione.bloccati).font(.footnote).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// Il pulsante pieno di un cambio nella formazione: chi apre il foglio lo chiude e apre la scelta.
    private func pulsanteFormazione(_ titolo: String, azione: @escaping () -> Void) -> some View {
        Button(action: azione) {
            Label(titolo, systemImage: "arrow.left.arrow.right")
                .frame(maxWidth: .infinity, minHeight: 44)
        }
        .pulsanteVetro(prominente: true)
    }

    private var cartaTuttiINumeri: some View {
        Carta {
            DisclosureGroup(isExpanded: $numeriAperti) {
                Group {
                    if let s = vm.caricatore.dato {
                        TuttiINumeri(scheda: s, prossime: vm.prossime)
                    } else {
                        attesa
                    }
                }
                .padding(.top, 8)
            } label: {
                Text(Catalogo.Formazione.tuttiNumeri).font(.headline).foregroundStyle(.primary)
            }
            .tint(Color.testoSecondario)
        }
    }
}

#Preview("Scheda dalla Formazione") {
    let json = """
    {"id": 7, "nome": "Leonel Marténi", "ruolo": "A", "squadra": "inter", "avversario": "como", "in_casa": true,
     "data_partita": "2026-10-31T20:45:00", "p_voto": 0.62, "fv_atteso": 7.9, "dubbio": true, "diffidato": true,
     "nota": "affaticamento, si decide domani", "fv_atteso_medio_ruolo": 6.9,
     "perche_numero": [{"chiave": "gioca", "testo": "gioca il 62%: dubbio", "effetto": null},
                       {"chiave": "gol", "testo": "segna più della media del ruolo", "effetto": 0.9}]}
    """
    if let g: Giocatore = try? Decodifica.decodifica(Data(json.utf8)) {
        GiocatoreSheet(id: g.id, server: FinteServer.esempio,
                       contesto: ContestoScheda(previsione: g, perche: "Preferito a Rossi: vale di più.", sostituibile: true),
                       sostituisci: {})
    }
}
