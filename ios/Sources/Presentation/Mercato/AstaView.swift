import SwiftUI

enum ModoAsta: String, CaseIterable, Identifiable {
    case estiva = "Asta di agosto"
    case riparazione = "Riparazione (febbraio)"
    var id: String { rawValue }
}

/// Logica dell'asta: il piano per l'asta estiva e quello per la riparazione di febbraio (solo gli svincolati).
@MainActor
final class AstaViewModel: ViewModelBase {
    let estiva: Caricatore<PianoAsta>
    let riparazione: Caricatore<PianoRiparazione>
    @Published var modo: ModoAsta = .estiva
    @Published var ruolo = "A"

    init(server: any ServerClient) {
        estiva = Caricatore<PianoAsta>("/api/asta", server: server)
        riparazione = Caricatore<PianoRiparazione>("/api/asta?modo=riparazione", server: server)
        super.init()
        osserva(estiva)
        osserva(riparazione)
    }

    func carica() async {
        switch modo {
        case .estiva: await estiva.ricarica()
        case .riparazione: await riparazione.ricarica()
        }
    }

    /// I giocatori del reparto scelto (per l'asta in corso).
    func giocatori(_ ruoli: [RuoloAsta]) -> [RuoloAsta.Voce] {
        (ruoli.first { $0.ruolo == ruolo } ?? ruoli.first)?.giocatori ?? []
    }

    var errore: String? { modo == .estiva ? estiva.errore : riparazione.errore }
    var datiSalvati: Date? { modo == .estiva ? estiva.datiSalvati : riparazione.datiSalvati }
}

private let nomiReparti = ["P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

/// Pagina «Asta e riparazione» (dalla Lega).
struct AstaView: View {
    @StateObject private var vm: AstaViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: AstaViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            AstaContenuto(vm: vm)
        }
        .navigationTitle("Asta")
        .ricercaGlobale()
    }
}

/// Il contenuto dell'asta: serve sia alla pagina della Lega sia alla sezione «Asta» del Mercato.
struct AstaContenuto: View {
    @ObservedObject var vm: AstaViewModel
    @Environment(\.apriGiocatore) private var apri

    var body: some View {
        ScrollView {
            Colonne(spazio: 14) {
                Carta {
                    Picker("Tipo di asta", selection: $vm.modo) {
                        ForEach(ModoAsta.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                }
                switch vm.modo {
                case .estiva: estiva
                case .riparazione: riparazione
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 8).padding(.bottom, 16)
        }
        .refreshable { await vm.carica() }
        .avvisoDatiSalvati(vm.datiSalvati)
        .task(id: vm.modo) { await vm.carica() }
    }

    // MARK: asta di agosto

    @ViewBuilder
    private var estiva: some View {
        if let a = vm.estiva.dato {
            Carta("Piano per l'asta") {
                Text("Stime per orientarsi, non prezzi garantiti: contano anche gli altri allenatori. Metodo: ogni giocatore vale quanto fa in più di un sostituto, e il budget (\(Formato.intero(a.crediti)) crediti, \(Formato.intero(a.panchina)) per la panchina) si divide in proporzione. Con \(a.squadre ?? 10) squadre.")
                    .font(.footnote).foregroundStyle(.secondary)
                FilaTessere {
                    ForEach(a.ruoli) { r in
                        TesseraDato(valore: "\(Formato.intero(r.crediti))", etichetta: "\(nomiReparti[r.ruolo] ?? r.ruolo) (\(Formato.percento(r.quota))%)")
                    }
                }
            }
            sceltaReparto(a.ruoli.map(\.ruolo))
            Carta {
                ForEach(vm.giocatori(a.ruoli)) { g in riga(g) }
            }
        } else if let e = vm.estiva.errore {
            ErroreVista(messaggio: e) { Task { await vm.carica() } }
        } else {
            Scheletro(schede: 2, righe: 3, testo: "Preparo il piano…")
        }
    }

    // MARK: riparazione di febbraio

    @ViewBuilder
    private var riparazione: some View {
        if let a = vm.riparazione.dato {
            Carta("Riparazione") {
                if let nota = a.nota { Text(nota).font(.footnote).foregroundStyle(.secondary) }
                FilaTessere {
                    TesseraDato(valore: a.tuoiCrediti.map { "\(Formato.intero($0))" } ?? "–", etichetta: "i tuoi crediti")
                    TesseraDato(valore: a.creditiLega.map { "\(Formato.intero($0))" } ?? "–", etichetta: "crediti della lega")
                    TesseraDato(valore: "\(Formato.intero(a.postiLiberi))", etichetta: "posti da riempire")
                }
            }
            if let perTe = a.perTe, !perTe.isEmpty {
                Carta("Ti conviene") {
                    Text("Chi migliora di più la tua squadra rispetto al tuo giocatore più debole dello stesso reparto, entro i tuoi crediti.")
                        .font(.footnote).foregroundStyle(.secondary)
                    ForEach(perTe) { g in
                        Button { apri(g.id) } label: {
                            HStack(alignment: .top, spacing: 10) {
                                BadgeRuolo(ruolo: g.ruolo ?? "?", piccolo: true)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(g.nome).font(.headline)
                                    Text("\(ColoriSquadra.sigla(g.squadra)) · \(Formato.conSegno(g.miglioramento ?? 0, cifre: 0)) punti attesi sul tuo \(g.alPostoDi ?? "giocatore")")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer(minLength: 8)
                                prezzo(g.prezzo)
                            }
                            .frame(minHeight: 44).contentShape(Rectangle())
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel("\(g.nome), \(Formato.conSegno(g.miglioramento ?? 0, cifre: 0)) punti attesi sul tuo \(g.alPostoDi ?? "giocatore"), \(Formato.intero(g.prezzo)) crediti")
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint("Apre la scheda del giocatore")
                    }
                }
            } else {
                Carta { Text("Nessuno svincolato migliora la tua squadra entro i tuoi crediti.").foregroundStyle(.secondary) }
            }
            sceltaReparto(a.ruoli.map(\.ruolo))
            Carta {
                ForEach(vm.giocatori(a.ruoli)) { g in riga(g) }
            }
        } else if let e = vm.riparazione.errore {
            ErroreVista(messaggio: e) { Task { await vm.carica() } }
        } else {
            Scheletro(schede: 2, righe: 3, testo: "Preparo il piano…")
        }
    }

    // MARK: pezzi

    private func prezzo(_ valore: Double?) -> some View {
        VStack(alignment: .trailing, spacing: 0) {
            Text("\(Formato.intero(valore))").font(.headline).monospacedDigit()
            Text("crediti").font(.caption2).foregroundStyle(.secondary)
        }
    }

    private func riga(_ g: RuoloAsta.Voce) -> some View {
        Button { apri(g.id) } label: {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(g.nome).font(.headline)
                    Text("\(ColoriSquadra.sigla(g.squadra)) · quot. \(Formato.intero(g.quotazione)) · \(Formato.intero(g.puntiStagione)) punti attesi")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 8)
                prezzo(g.prezzo)
            }
            .frame(minHeight: 44).contentShape(Rectangle())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(g.nome), \(ColoriSquadra.sigla(g.squadra)), prezzo consigliato \(Formato.crediti(Formato.intero(g.prezzo))), \(Formato.intero(g.puntiStagione)) punti attesi")
        }
        .buttonStyle(.plain)
        .accessibilityHint("Apre la scheda del giocatore")
    }

    private func sceltaReparto(_ ruoli: [String]) -> some View {
        Carta {
            HStack(spacing: 8) {
                ForEach(ruoli, id: \.self) { r in
                    let attivo = vm.ruolo == r
                    Button { vm.ruolo = r; Haptics.selezione() } label: {
                        Text(nomiReparti[r] ?? r).font(.footnote.weight(.semibold)).lineLimit(2).minimumScaleFactor(0.7)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .background(attivo ? Color.verde.opacity(0.35) : Color.primary.opacity(0.08), in: Capsule())
                            .overlay(Capsule().strokeBorder(attivo ? Color.verde : .clear, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(attivo ? .isSelected : [])
                }
            }
        }
    }
}
