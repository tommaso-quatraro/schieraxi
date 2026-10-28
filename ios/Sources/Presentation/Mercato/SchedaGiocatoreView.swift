import SwiftUI

/// Scheda di un giocatore (sheet): previsione, statistiche della stagione, «Osserva».
struct GiocatoreSheet: View {
    @StateObject private var vm: SchedaGiocatoreViewModel
    @Environment(\.dismiss) private var chiudi

    init(id: Int, server: any ServerClient) {
        _vm = StateObject(wrappedValue: SchedaGiocatoreViewModel(id: id, server: server))
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    VStack(spacing: 14) {
                        if let s = vm.caricatore.dato {
                            intestazione(s)
                            if let p = s.previsione { previsione(p) }
                            if let st = s.stagione { stagione(st) }
                            Button { Task { await vm.aggiungiAgliOsservati() } } label: { Label("Osserva", systemImage: "star").frame(minHeight: 44) }
                                .buttonStyle(.borderedProminent)
                            if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(.secondary) }
                        } else if let e = vm.caricatore.errore {
                            ErroreVista(messaggio: e) { Task { await vm.carica() } }
                        } else {
                            ProgressView().padding(40)
                        }
                    }
                    .padding(16)
                }
            }
            .navigationTitle(vm.caricatore.dato?.calciatore.nome ?? "Giocatore")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
            .task { await vm.carica() }
        }
    }

    private func intestazione(_ s: SchedaGiocatore) -> some View {
        Carta {
            HStack(spacing: 12) {
                BadgeRuolo(ruolo: s.calciatore.ruolo)
                VStack(alignment: .leading) {
                    Text(s.calciatore.nome).font(.title2.bold())
                    Text(s.calciatore.squadra ?? "").foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text("\(Formato.intero(s.calciatore.quotazione))").font(.title2.bold()).monospacedDigit()
                    Text("quotazione").font(.caption2).foregroundStyle(.secondary)
                }
            }
            Text(s.proprietario.map { "Nella squadra: \($0)" } ?? "Svincolato").font(.footnote).foregroundStyle(.secondary)
        }
    }

    private func previsione(_ p: Giocatore) -> some View {
        Carta("Previsione") {
            dato("Punti attesi", Formato.punti(p.puntiAttesi))
            dato("Probabilità di giocare", "\(Formato.percento(p.pVoto))%")
            dato("Gol attesi", Formato.decimali(p.golAttesi ?? 0, cifre: 2))
            dato("Assist attesi", Formato.decimali(p.assistAttesi ?? 0, cifre: 2))
            if let a = p.avversario { dato("Prossima partita", "\(p.inCasa == true ? "vs" : "@") \(a.uppercased())") }
        }
    }

    private func stagione(_ s: StagioneGiocatore) -> some View {
        Carta("Stagione") {
            dato("Presenze", "\(Formato.intero(s.presenze))")
            dato("Media voto", Formato.decimali(s.mediaVoto ?? 0, cifre: 2))
            dato("Fantamedia", Formato.decimali(s.fantamedia ?? 0, cifre: 2))
            dato("Gol / assist", "\(Formato.intero(s.gol)) / \(Formato.intero(s.assist))")
            dato("Ammonizioni / espulsioni", "\(Formato.intero(s.ammonizioni)) / \(Formato.intero(s.espulsioni))")
        }
    }

    private func dato(_ titolo: String, _ valore: String) -> some View {
        HStack { Text(titolo).foregroundStyle(.secondary); Spacer(); Text(valore).monospacedDigit() }
            .accessibilityElement(children: .combine)
    }
}
