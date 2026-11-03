import SwiftUI
import UniformTypeIdentifiers

// MARK: - Diario delle giornate

@MainActor
final class DiarioViewModel: ViewModelBase {
    let caricatore: Caricatore<DiarioRisposta>
    private let server: any ServerClient

    init(server: any ServerClient) {
        self.server = server
        caricatore = Caricatore<DiarioRisposta>("/api/diario", server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async { await caricatore.ricarica() }

    /// I testi dell'esito, uguali alla web (`diario.salvata` e `diario.salvata_manuale` di `testi.js`).
    static let salvataConsigliata = "Salvato: ho segnato che hai schierato la consigliata"
    static let salvataAMano = "Salvato: ho segnato i tuoi undici della giornata"

    /// La voce del diario (`VoceDiario.id`: stagione e giornata) che si sta salvando, un salvataggio alla volta, e l'esito dell'ultimo.
    @Published var inSalvataggio: String?
    @Published var messaggio: String?
    @Published var messaggioRiuscito = false
    /// La voce (stagione e giornata) a cui si riferisce il messaggio: si mostra dentro la sua sezione, vicino al pulsante toccato.
    @Published var voceDelMessaggio: String?
    /// Fa leggere un esito a VoiceOver. Si sostituisce nei test per contare gli annunci.
    var annuncia: @MainActor (String) -> Void = { AccessibilityNotification.Announcement($0).post() }

    /// L'esito da mostrare nella sezione di questa voce, se è suo (con due stagioni nel Diario la stessa giornata compare due volte).
    func messaggio(per voce: VoceDiario) -> String? {
        voceDelMessaggio == voce.id ? messaggio : nil
    }

    /// «Ho schierato un'altra formazione»: undici titolari scelti a mano tra i giocatori della tua rosa (il server controlla modulo e rosa).
    /// Restituisce nil se è stata salvata, altrimenti l'errore da mostrare nel foglio «Cosa hai schierato» (la lista sotto è coperta).
    func haSchieratoAMano(_ voce: VoceDiario, titolari: [Int]) async -> String? {
        // non succede dal foglio (si apre solo per una voce che si può cambiare e a salvataggi fermi): un testo qualsiasi
        // tiene il foglio aperto
        guard voce.siPuoCambiare, let giornata = voce.giornata, inSalvataggio == nil else {
            return "Non riesco a salvare adesso: riprova tra poco."
        }
        inizia(voce)
        defer { inSalvataggio = nil }
        do {
            let corpo = CorpoSchierata(giornata: giornata, tipo: "manuale", titolari: titolari, stagione: voce.stagione)
            _ = try await server.corpoJSON("POST", "/api/diario/schierata", corpo)
            esito(Self.salvataAMano, riuscito: true)
            await caricatore.ricarica()
            return nil
        } catch {
            let testo = error.localizedDescription
            Haptics.esito(riuscito: false)
            annuncia(testo)
            if (error as? ErroreApi)?.eConflitto == true { await caricatore.ricarica() }
            return testo
        }
    }

    /// «Ho schierato la consigliata»: il server salva come tua scelta la formazione che il modello avrebbe consigliato per quella
    /// giornata già finita e rifà solo quella voce del diario (non conta nei limiti di ricerca).
    func haSchieratoLaConsigliata(_ voce: VoceDiario) async {
        guard voce.siPuoCambiare, let giornata = voce.giornata, inSalvataggio == nil else { return }
        inizia(voce)
        defer { inSalvataggio = nil }
        do {
            let corpo = CorpoSchierata(giornata: giornata, tipo: "consigliata", stagione: voce.stagione)
            _ = try await server.corpoJSON("POST", "/api/diario/schierata", corpo)
            esito(Self.salvataConsigliata, riuscito: true)
            await caricatore.ricarica()
        } catch {
            esito(error.localizedDescription, riuscito: false)
            if (error as? ErroreApi)?.eConflitto == true { await caricatore.ricarica() }
        }
    }

    /// Un salvataggio parte: l'esito di prima sparisce, così sotto la giornata nuova non resta «Salvato…» di un'altra.
    private func inizia(_ voce: VoceDiario) {
        inSalvataggio = voce.id
        voceDelMessaggio = voce.id
        messaggio = nil
    }

    /// Mostra l'esito nella sezione della giornata e lo fa leggere a VoiceOver: anche quando la riga è già sullo schermo
    /// (secondo salvataggio nella stessa giornata), dove un annuncio legato alla comparsa della riga non partirebbe.
    private func esito(_ testo: String, riuscito: Bool) {
        messaggio = testo
        messaggioRiuscito = riuscito
        Haptics.esito(riuscito: riuscito)
        annuncia(testo)
    }
}

/// Il corpo di `POST /api/diario/schierata`.
struct CorpoSchierata: Encodable {
    let giornata: Int
    /// «consigliata» o «manuale» (con `titolari`).
    let tipo: String
    var titolari: [Int]? = nil
    /// La stagione della voce del diario: il server rifiuta le stagioni passate invece di scrivere sulla giornata con lo stesso
    /// numero di quest'anno. Senza (nil) il campo non si manda e il server usa la stagione in corso.
    var stagione: String? = nil
}

/// Per ogni giornata finita: i punti fatti dalla formazione schierata e da quella che SchieraXI avrebbe consigliato.
struct DiarioView: View {
    @StateObject private var vm: DiarioViewModel
    @State private var daCorreggere: VoceDiario?
    private let server: any ServerClient

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: DiarioViewModel(server: server))
        self.server = server
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let d = vm.caricatore.dato {
                    Section {
                        Text("Per ogni giornata finita: i punti fatti («attesi» = quelli previsti prima) dalla formazione che hai schierato e da quella che SchieraXI avrebbe consigliato con i dati di allora e la rosa di oggi. La panchina è scelta dal sistema in entrambi i casi. Da ora SchieraXI ricorda anche la formazione che ti ha consigliato prima di ogni giornata: la vedi qui sotto, con in evidenza i giocatori che hai cambiato.")
                            .font(.footnote).foregroundStyle(Color.testoSecondario)
                    }
                    if let p = d.precisione {
                        // server nuovo: i numeri di «Quanto ci abbiamo preso» (niente sezione se non ci sono giornate)
                        if let t = TestoPrecisione(p) {
                            Section {
                                PrecisioneView(testo: t)
                            } header: {
                                Text(TestoPrecisione.titolo).foregroundStyle(Color.testoSecondario)
                            }
                        }
                    } else if let t = TestoAffidabilita(d.affidabilita) {
                        Section {
                            QuantoCiAbbiamoPresoView(testo: t, punti: PuntoAttesoFatto.elenco(d.giornate ?? []))
                        } header: {
                            Text(TestoAffidabilita.titolo).foregroundStyle(Color.testoSecondario)
                        }
                    }
                    if let s = d.sintesi, (s.giornate ?? 0) > 0 { sintesi(s) }
                    if let t = ScelteTueTesto(d.scelteTue) {
                        Section {
                            SchedaScelteTueView(testo: t)
                                .listRowInsets(EdgeInsets(top: 6, leading: Tema.margine, bottom: 6, trailing: Tema.margine))
                                .listRowBackground(Color.clear)
                        }
                    }
                    if (d.giornate ?? []).isEmpty {
                        VistaVuota(titolo: "Diario ancora vuoto", icona: "book.closed",
                                   descrizione: "Si riempie dopo la prima giornata finita (serve la tua squadra indicata in Squadra).")
                            .listRowBackground(Color.clear)
                    }
                    ForEach(d.giornate ?? []) { voce in giornata(voce) }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .avvisoDatiSalvati(vm.caricatore)
        }
        .navigationTitle("Diario")
        .sheet(item: $daCorreggere) { v in
            FormazioneManualeDiarioView(voce: v, server: server) { titolari in
                await vm.haSchieratoAMano(v, titolari: titolari)
            }
        }
        .ricercaGlobale()
        .refreshable { await vm.carica() }
        .task { await vm.carica() }
    }

    private func sintesi(_ s: SintesiDiario) -> some View {
        Section(titolo: "In sintesi (\(Formato.giornate(s.giornate ?? 0)))") {
            RigaValore(titolo: "Punti medi tuoi", valore: Formato.punti(s.puntiSchierata), cifreFisse: true)
            RigaValore(titolo: "Punti medi di SchieraXI", valore: Formato.punti(s.puntiConsigliata), cifreFisse: true)
            RigaValore(titolo: "Meglio tu – meglio SchieraXI", valore: "\(s.meglioTua ?? 0)–\(s.meglioConsigliata ?? 0)", cifreFisse: true)
        }
    }

    private func giornata(_ v: VoceDiario) -> some View {
        Section {
            // L'esito di «Ho schierato…» sta nella sezione della giornata toccata: in cima alla lista non si vedeva.
            if let m = vm.messaggio(per: v) {
                Label(m, systemImage: vm.messaggioRiuscito ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                    .font(.footnote.weight(.semibold)).foregroundStyle(vm.messaggioRiuscito ? Color.verde : Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if v.schierata == nil {
                Text("Non avevi salvato la tua formazione per questa giornata.").font(.footnote).foregroundStyle(Color.testoSecondario)
            }
            if let c = v.confronto {
                ConfrontoDiarioView(confronto: c)
                    .padding(.vertical, 4)
            }
            // «Ho schierato…» e «Correggi» solo per le voci che si possono ancora cambiare (stagione in corso, come la web)
            if let s = v.schierata {
                riga(s.tipo == "consigliata" ? "La tua, la consigliata (\(s.modulo ?? "–"))" : "La tua (\(s.modulo ?? "–"))", s)
            } else if v.siPuoCambiare, let g = v.giornata {
                Button {
                    Task { await vm.haSchieratoLaConsigliata(v) }
                } label: {
                    HStack {
                        if vm.inSalvataggio == v.id { ProgressView() }
                        Label("Ho schierato la consigliata", systemImage: "checkmark.circle").font(.body.weight(.semibold))
                    }
                    .frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.borderedProminent)
                .disabled(vm.inSalvataggio != nil)
                .accessibilityHint("Salva come tua scelta la formazione consigliata per la giornata \(v.numero ?? g)")
            }
            if v.siPuoCambiare, let g = v.giornata {
                Button { daCorreggere = v } label: {
                    Label(v.schierata == nil ? "Ho schierato un'altra formazione" : "Correggi a mano", systemImage: "pencil")
                        .font(.subheadline).frame(maxWidth: .infinity, minHeight: 44)
                }
                .disabled(vm.inSalvataggio != nil)
                .accessibilityHint("Scegli a mano i tuoi undici della giornata \(v.numero ?? g)")
            }
            if let c = v.consigliata {
                riga(v.istantanea?.titolari?.isEmpty == false ? "Ricostruita oggi (\(c.modulo ?? "–"))" : "Di SchieraXI (\(c.modulo ?? "–"))", c)
            }
            if let p = PuntoAttesoFatto(giornata: v.numero, v.attesoVsFatto), p.dentro != nil {
                Label(p.frase, systemImage: p.dentro == true ? "checkmark.circle" : "exclamationmark.circle")
                    .font(.caption)
                    .foregroundStyle(p.dentro == true ? Color.testoSecondario : Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
        } header: {
            Text(v.titolo + (v.stagione.map { " · \($0)" } ?? "")).foregroundStyle(Color.testoSecondario)
        }
    }

    private func riga(_ titolo: String, _ f: FormazioneDiario) -> some View {
        let fascia = IntervalloPunti.frase(f.intervallo, dev: f.dev)
        return rigaConFascia(titolo, f, fascia)
    }

    private func rigaConFascia(_ titolo: String, _ f: FormazioneDiario, _ fascia: String?) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(titolo)
            Spacer()
            VStack(alignment: .trailing, spacing: 0) {
                Text(Formato.punti(f.reale)).font(.headline).monospacedDigit()
                Text("attesi \(Formato.punti(f.atteso))").font(.caption).foregroundStyle(Color.testoSecondario).monospacedDigit()
                if let fascia { Text(fascia).font(.caption2).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.trailing) }
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(titolo): \(Formato.punti(f.reale)) punti, attesi \(Formato.punti(f.atteso))" + (fascia.map { ", \($0)" } ?? ""))
    }
}
