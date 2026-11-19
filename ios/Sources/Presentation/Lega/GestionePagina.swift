import SwiftUI

/// Impostazioni > Gestione, solo per chi gestisce il server (come `paginaGestione` della web, #673 passo 3): l'aggiornamento dei dati,
/// lo stato dei dati, il collegamento con il server e, solo sull'iPhone, la diagnostica del widget, il certificato, il rinnovo con
/// SideStore e le notifiche ntfy. Sul server senza account anche «Avvisi anche per l'app nativa» (ntfy). Erano le «Avanzate».
struct GestionePagina: View {
    @ObservedObject var vm: LegaViewModel
    @ObservedObject var avvisi: AvvisiDispositivoViewModel
    @EnvironmentObject private var sessione: SessioneAccount

    var body: some View {
        List {
            TitoloNellaPagina()
            Section {
                AggiornaDatiSezione(vm: vm.aggiornamento)
                NavigationLink(value: PaginaImpostazioni.stato) {
                    Label(Catalogo.Av.stato, systemImage: "externaldrive").labelStyle(.voce(.gray)).frame(minHeight: Tema.areaTocco)
                }
                if let v = vm.info.dato?.versione { RigaValore(titolo: "Versione del server", valore: v) }
                RigaValore(titolo: LegaViewModel.titoloControlli, valore: vm.aggiornamentoInBackground)
            } footer: {
                Text(Catalogo.Imp.aggiornaSpiega).foregroundStyle(Color.testoSecondario)
            }
            if !ProvaEsempio.attiva { sezioneCollegamento }
            if !sessione.multiutente, let nativa = avvisi.appNativa { sezioneAppNativa(nativa) }
            DiagnosticaWidgetSezione()
            CertificatoSezione()
            RinnovoSideStoreSezione()
            NotificheNtfySezione()
        }
        .scrollContentBackground(.hidden)
        .background(Sfondo())
        .titoloPagina(Catalogo.Imp.gestione)
        .task { await avvisi.carica() }
    }

    /// Il server, la prova del collegamento e i dati principali che dà.
    private var sezioneCollegamento: some View {
        Section(titolo: "Collegamento") {
            ProvaServerView(utente: sessione.utente?.nome, dopoProva: { await vm.info.ricarica() })
            if vm.info.inCorso {
                ProgressView()
            } else if let s = vm.info.dato {
                if let salvati = vm.info.datiSalvati {
                    Label("Non riesco a raggiungere SchieraXI. Quello che vedi è stato salvato il \(salvati.formatted(date: .abbreviated, time: .shortened)) e può essere vecchio.", systemImage: "icloud.slash")
                        .font(.footnote).foregroundStyle(Color.attenzione)
                }
                RigaValore(titolo: "Squadra", valore: s.miaSquadra ?? "—")
                RigaValore(titolo: "Stagione", valore: s.stagione ?? "—")
                RigaValore(titolo: "Dati aggiornati", valore: Quando.leggibile((s.ultimoAggiornamento ?? "").replacingOccurrences(of: "T", with: " ")))
            } else if let e = vm.info.errore {
                Text(e).foregroundStyle(Color.attenzione)
            }
        }
    }

    /// Sul server senza account gli avvisi possono arrivare anche con ntfy, il cui tocco apre questa app (`app_nativa`).
    private func sezioneAppNativa(_ acceso: Bool) -> some View {
        Section {
            Toggle(isOn: Binding(get: { acceso }, set: { nuovo in Task { await avvisi.cambiaAppNativa(nuovo) } })) {
                NomeConAiuto(Catalogo.Avv.nativa, aiuto: Catalogo.Avv.nativaAiuto)
            }
            .tint(Color.verde)
            .frame(minHeight: Tema.areaTocco)
            .disabled(avvisi.inCorso)
            if let errore = avvisi.erroreSalvataggio {
                Label(errore, systemImage: "exclamationmark.triangle.fill")
                    .font(.footnote).foregroundStyle(Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
