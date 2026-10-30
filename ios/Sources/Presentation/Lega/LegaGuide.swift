import SwiftUI

/// Avvisa in Lega se su GitHub c'è una build più nuova di quella installata, con i passi per aggiornare da SideStore.
struct NuovaVersioneSezione: View {
    @State private var esito: NuovaVersione.Esito?

    var body: some View {
        Group {
            if let esito {
                Section("Aggiornamento dell'app") {
                    Label("È disponibile la \(esito.nome) (hai la build \(NuovaVersione.buildInstallata))", systemImage: "arrow.down.circle")
                        .foregroundStyle(Color.verde)
                    Text("Apri SideStore, tocca Sorgenti, poi SchieraXI e «Aggiorna». Se non vedi il sorgente: in Sorgenti aggiungi https://github.com/tommaso-quatraro/schieraxi-ios/releases/latest/download/sorgente.json")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
        }
        .task { esito = await NuovaVersione.controllaEAvvisa() }
    }
}

/// Scadenza del certificato dell'app, con il colore giusto (arancio sotto 2 giorni, rosso se scaduto).
struct CertificatoSezione: View {
    @State private var scadenza: Date?
    @State private var letta = false

    private var info: Certificato.Info { Certificato.info(scadenza: scadenza) }

    private var colore: Color {
        switch info.livello {
        case .ok: return .secondary
        case .attenzione: return .orange
        case .scaduto: return .red
        case .ignoto: return .secondary
        }
    }

    var body: some View {
        Section("Certificato dell'app") {
            HStack {
                Text("Validità")
                Spacer()
                Text(letta ? info.testo : "…").foregroundStyle(colore).multilineTextAlignment(.trailing)
            }
            .accessibilityElement(children: .combine)
            if let scadenza {
                HStack {
                    Text("Scade il")
                    Spacer()
                    Text(scadenza.formatted(date: .abbreviated, time: .shortened)).foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
            }
            Text("Con l'Apple ID gratuito il certificato dura 7 giorni. 24 ore e 6 ore prima della scadenza arriva un promemoria: «Rinnovala con SideStore».")
                .font(.footnote).foregroundStyle(.secondary)
        }
        .task {
            scadenza = Certificato.scadenza()
            letta = true
            await Aggiornamento.riprogrammaScadenza()
        }
    }
}

/// Come far rinnovare l'app da sola ogni notte con SideStore e l'app Comandi.
struct RinnovoSideStoreSezione: View {
    var body: some View {
        Section("Rinnovo automatico (SideStore)") {
            VStack(alignment: .leading, spacing: 8) {
                Text("1. Nell'app Comandi crea un comando con l'azione di SideStore «Refresh All Apps».")
                Text("2. Vai su Automazione, tocca +, scegli «Ora del giorno», alle 3:00, ogni giorno.")
                Text("3. Come azione scegli quel comando, poi «Esegui subito» e spegni «Notifica quando viene eseguito».")
                Text("4. LocalDevVPN deve essere attiva durante il rinnovo: puoi lasciarla sempre accesa. Il server ha un indirizzo pubblico (https) e non serve altro per usare SchieraXI.")
            }
            .font(.footnote)
            .foregroundStyle(.secondary)
            // shortcuts:// apre soltanto l'app Comandi: nessun rischio.
            if let url = URL(string: "shortcuts://") {
                Link(destination: url) { Label("Apri Comandi", systemImage: "square.2.layers.3d").frame(minHeight: 44) }
            }
        }
    }
}

/// Come far aprire l'app nativa dal tocco su una notifica dell'app ntfy.
struct NotificheNtfySezione: View {
    var body: some View {
        Section("Notifiche ntfy che mandi tu") {
            Text("Gli avvisi del server aprono già l'app (con «Avvisi anche per l'app nativa»). Solo se mandi tu una notifica con ntfy, per esempio da Comandi, aggiungi questa intestazione: toccandola si apre l'app sulla schermata scelta.")
                .font(.footnote).foregroundStyle(.secondary)
            Text(Collegamenti.esempioNtfy)
                .font(.system(.footnote, design: .monospaced))
                .textSelection(.enabled)
            Text("Altre destinazioni: oggi, formazione, mercato, scambi, lega, e giocatore/<numero> per la scheda di un giocatore.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }
}
