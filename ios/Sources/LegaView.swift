import SwiftUI

struct LegaView: View {
    @StateObject private var caricatore = Caricatore<Stato>("/api/stato")
    @AppStorage("indirizzo") private var indirizzo = ""
    @State private var permesso: String = "…"

    var body: some View {
        NavigationStack {
            List {
                Section("Server") {
                    TextField(Config.indirizzoPredefinito, text: $indirizzo)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    Button("Prova la connessione") { Task { await caricatore.ricarica() } }
                    if caricatore.inCorso {
                        ProgressView()
                    } else if let s = caricatore.dato {
                        if let salvati = caricatore.datiSalvati {
                            Label("Server non raggiungibile. Dati salvati del \(salvati.formatted(date: .abbreviated, time: .shortened))", systemImage: "icloud.slash")
                                .font(.footnote).foregroundStyle(.orange)
                        }
                        riga("Squadra", s.miaSquadra ?? "—")
                        riga("Stagione", s.stagione ?? "—")
                        riga("Versione del server", s.versione ?? "—")
                        riga("Dati aggiornati", Quando.leggibile((s.ultimoAggiornamento ?? "").replacingOccurrences(of: "T", with: " ")))
                    } else if let e = caricatore.errore {
                        Text(e).foregroundStyle(.orange)
                    }
                }
                Section("Lega") {
                    NavigationLink { ImportaExcelView() } label: { Label("Aggiorna le rose da Excel", systemImage: "doc.badge.plus") }
                    NavigationLink { SquadreView() } label: { Label("Squadre e rose", systemImage: "person.3") }
                    NavigationLink { AstaView() } label: { Label("Asta e riparazione", systemImage: "hammer") }
                    NavigationLink { RegoleEditorView() } label: { Label("Regole", systemImage: "list.bullet.rectangle") }
                    NavigationLink { CreditiView() } label: { Label("Crediti delle squadre", systemImage: "eurosign.circle") }
                    NavigationLink { AvvisiServerView() } label: { Label("Avvisi del server", systemImage: "bell.badge") }
                    NavigationLink { StatoDatiView() } label: { Label("Stato dei dati", systemImage: "externaldrive") }
                    NavigationLink { NovitaView() } label: { Label("Novità del server", systemImage: "sparkles") }
                }
                Section("Promemoria") {
                    riga("Notifiche", permesso)
                    Button("Attiva i promemoria sul telefono") {
                        Task {
                            _ = await Notifiche.chiediPermesso()
                            await aggiornaPermesso()
                        }
                    }
                    riga("Aggiornamento in background", sfondo)
                    Text("Un'ora e un quarto d'ora prima della prima partita, anche con l'app chiusa. Si programmano quando apri la schermata Oggi e, ogni tanto, da soli: iOS sveglia l'app in background, riscarica la giornata e ti avvisa se la formazione consigliata cambia. Quando succede lo decide iOS (di solito poche volte al giorno).")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("App") {
                    riga("Versione", Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Sfondo())
            .navigationTitle("Lega")
            .task {
                await caricatore.ricarica()
                await aggiornaPermesso()
            }
        }
    }

    /// Se iOS permette all'app di aggiornarsi in background (Impostazioni > Generali > Aggiornamento app in background).
    private var sfondo: String {
        switch UIApplication.shared.backgroundRefreshStatus {
        case .available: return "attivo"
        case .denied: return "disattivato"
        default: return "limitato"
        }
    }

    private func riga(_ titolo: String, _ valore: String) -> some View {
        HStack {
            Text(titolo)
            Spacer()
            Text(valore).foregroundStyle(.secondary)
        }
    }

    private func aggiornaPermesso() async {
        switch await Notifiche.stato() {
        case .authorized, .provisional, .ephemeral: permesso = "attive"
        case .denied: permesso = "negate (Impostazioni di iOS)"
        default: permesso = "da attivare"
        }
    }
}
