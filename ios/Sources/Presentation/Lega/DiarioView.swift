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

    /// La giornata che si sta salvando (un solo salvataggio alla volta) e l'esito dell'ultimo.
    @Published var inSalvataggio: Int?
    @Published var messaggio: String?
    @Published var messaggioRiuscito = false

    /// «Ho schierato un'altra formazione»: undici titolari scelti a mano tra i giocatori della tua rosa (il server controlla modulo e rosa).
    /// Restituisce vero se è stata salvata.
    func haSchieratoAMano(giornata: Int, titolari: [Int]) async -> Bool {
        guard inSalvataggio == nil else { return false }
        inSalvataggio = giornata
        defer { inSalvataggio = nil }
        do {
            _ = try await server.corpoJSON("POST", "/api/diario/schierata", CorpoSchierata(giornata: giornata, tipo: "manuale", titolari: titolari))
            messaggio = "Salvato: la formazione che hai schierato nella giornata \(giornata)."
            messaggioRiuscito = true
            Haptics.esito(riuscito: true)
            await caricatore.ricarica()
            return true
        } catch {
            messaggio = error.localizedDescription
            messaggioRiuscito = false
            if (error as? ErroreApi)?.eConflitto == true { await caricatore.ricarica() }
            Haptics.esito(riuscito: false)
            return false
        }
    }

    /// «Ho schierato la consigliata»: il server salva come tua scelta la formazione che il modello avrebbe consigliato per quella
    /// giornata già finita e rifà solo quella voce del diario (non conta nei limiti di ricerca).
    func haSchieratoLaConsigliata(giornata: Int) async {
        guard inSalvataggio == nil else { return }
        inSalvataggio = giornata
        defer { inSalvataggio = nil }
        do {
            _ = try await server.corpoJSON("POST", "/api/diario/schierata", CorpoSchierata(giornata: giornata, tipo: "consigliata"))
            messaggio = "Salvato: per la giornata \(giornata) hai schierato la consigliata."
            messaggioRiuscito = true
            Haptics.esito(riuscito: true)
            await caricatore.ricarica()
        } catch {
            messaggio = error.localizedDescription
            messaggioRiuscito = false
            if (error as? ErroreApi)?.eConflitto == true { await caricatore.ricarica() }
            Haptics.esito(riuscito: false)
        }
    }
}

/// Il corpo di `POST /api/diario/schierata`.
struct CorpoSchierata: Encodable {
    let giornata: Int
    /// «consigliata» o «manuale» (con `titolari`).
    let tipo: String
    var titolari: [Int]? = nil
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
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    if let p = d.precisione {
                        // server nuovo: i numeri di «Quanto ci abbiamo preso» (niente sezione se non ci sono giornate)
                        if let t = TestoPrecisione(p) {
                            Section {
                                PrecisioneView(testo: t)
                            } header: {
                                Text(TestoPrecisione.titolo)
                            }
                        }
                    } else if let t = TestoAffidabilita(d.affidabilita) {
                        Section {
                            QuantoCiAbbiamoPresoView(testo: t, punti: PuntoAttesoFatto.elenco(d.giornate ?? []))
                        } header: {
                            Text(TestoAffidabilita.titolo)
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
                    if let m = vm.messaggio {
                        Section {
                            Label(m, systemImage: vm.messaggioRiuscito ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                                .font(.footnote).foregroundStyle(vm.messaggioRiuscito ? Color.verde : Color.attenzione)
                        }
                    }
                    ForEach(d.giornate ?? []) { voce in giornata(voce) }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .avvisoDatiSalvati(vm.caricatore.datiSalvati)
        }
        .navigationTitle("Diario")
        .sheet(item: $daCorreggere) { v in
            FormazioneManualeDiarioView(voce: v, server: server) { titolari in
                guard let g = v.giornata else { return false }
                return await vm.haSchieratoAMano(giornata: g, titolari: titolari)
            }
        }
        .ricercaGlobale()
        .refreshable { await vm.carica() }
        .task { await vm.carica() }
    }

    private func sintesi(_ s: SintesiDiario) -> some View {
        Section("In sintesi (\(s.giornate ?? 0) giornate)") {
            RigaValore(titolo: "Punti medi tuoi", valore: Formato.punti(s.puntiSchierata), cifreFisse: true)
            RigaValore(titolo: "Punti medi di SchieraXI", valore: Formato.punti(s.puntiConsigliata), cifreFisse: true)
            RigaValore(titolo: "Meglio tu – meglio SchieraXI", valore: "\(s.meglioTua ?? 0)–\(s.meglioConsigliata ?? 0)", cifreFisse: true)
        }
    }

    private func giornata(_ v: VoceDiario) -> some View {
        Section {
            if v.schierata == nil {
                Text("Non avevi salvato la tua formazione per questa giornata.").font(.footnote).foregroundStyle(.secondary)
            }
            if let c = v.confronto {
                ConfrontoDiarioView(confronto: c)
                    .padding(.vertical, 4)
            }
            if let s = v.schierata {
                riga(s.tipo == "consigliata" ? "La tua, la consigliata (\(s.modulo ?? "–"))" : "La tua (\(s.modulo ?? "–"))", s)
            } else if let g = v.giornata {
                Button {
                    Task { await vm.haSchieratoLaConsigliata(giornata: g) }
                } label: {
                    HStack {
                        if vm.inSalvataggio == g { ProgressView() }
                        Label("Ho schierato questa", systemImage: "checkmark.circle").font(.body.weight(.semibold))
                    }
                    .frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.borderedProminent)
                .disabled(vm.inSalvataggio != nil)
                .accessibilityHint("Salva come tua scelta la formazione consigliata per la giornata \(g)")
            }
            if let g = v.giornata {
                Button { daCorreggere = v } label: {
                    Label(v.schierata == nil ? "Ho schierato un'altra formazione" : "Correggi a mano", systemImage: "pencil")
                        .font(.subheadline).frame(maxWidth: .infinity, minHeight: 44)
                }
                .disabled(vm.inSalvataggio != nil)
                .accessibilityHint("Scegli a mano i tuoi undici della giornata \(g)")
            }
            if let c = v.consigliata {
                riga(v.istantanea?.titolari?.isEmpty == false ? "Ricostruita oggi (\(c.modulo ?? "–"))" : "Di SchieraXI (\(c.modulo ?? "–"))", c)
            }
            if let p = PuntoAttesoFatto(giornata: v.giornata, v.attesoVsFatto), p.dentro != nil {
                Label(p.frase, systemImage: p.dentro == true ? "checkmark.circle" : "exclamationmark.circle")
                    .font(.caption)
                    .foregroundStyle(p.dentro == true ? Color.secondary : Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
        } header: {
            Text("Giornata \(v.giornata ?? 0)" + (v.stagione.map { " · \($0)" } ?? ""))
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
                Text("attesi \(Formato.punti(f.atteso))").font(.caption).foregroundStyle(.secondary).monospacedDigit()
                if let fascia { Text(fascia).font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.trailing) }
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(titolo): \(Formato.punti(f.reale)) punti, attesi \(Formato.punti(f.atteso))" + (fascia.map { ", \($0)" } ?? ""))
    }
}
