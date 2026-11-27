import SwiftUI

/// Avvisa nelle Impostazioni se c'è una versione più nuova di quella installata. Chi amministra vede anche i passi di SideStore.
struct NuovaVersioneSezione: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var esito: NuovaVersione.Esito?

    var body: some View {
        Group {
            if !ProvaEsempio.attiva, let esito {
                Section(titolo: "Aggiornamento dell'app") {
                    Label(sessione.puoAmministrare ? Self.disponibile(esito, installata: NuovaVersione.buildInstallata) : "C'è una versione più nuova di SchieraXI", systemImage: "arrow.down.circle")
                        .foregroundStyle(Color.verde)
                    Text(sessione.puoAmministrare ? "Apri SideStore, tocca Sorgenti, poi SchieraXI e «Aggiorna». Se non vedi il sorgente: in Sorgenti aggiungi https://github.com/tommaso-quatraro/schieraxi/releases/latest/download/sorgente.json" : "Aggiornala dall'app con cui l'hai installata: i tuoi dati restano dove sono.")
                        .font(.footnote).foregroundStyle(Color.testoSecondario)
                }
            }
        }
        .task { if !ProvaEsempio.attiva { esito = await NuovaVersione.controllaEAvvisa() } }
    }

    /// La riga di chi gestisce il server, con le versioni come le dicono l'avviso e Informazioni («1.0.38», `NuovaVersione.versione`)
    /// e non con la sigla della release («build-38»).
    nonisolated static func disponibile(_ esito: NuovaVersione.Esito, installata: Int) -> String {
        "È disponibile la versione \(NuovaVersione.versione(build: esito.build)) (hai la \(NuovaVersione.versione(build: installata)))"
    }
}

/// Scadenza del certificato dell'app, con il colore giusto (arancio sotto 2 giorni, rosso se scaduto).
struct CertificatoSezione: View {
    @State private var scadenza: Date?
    @State private var letta = false

    private var info: Certificato.Info { Certificato.info(scadenza: scadenza) }

    /// La riga sotto la scadenza, dal catalogo (`avv.certificato_aiuto`): quando arrivano i due promemoria, come fa
    /// `Notifiche.promemoriaCertificato` con le ore tranquille, e il testo vero di quello di 6 ore prima (`avv.certificato_ore`; diceva
    /// «Rinnovala con SideStore»).
    nonisolated static var aiuto: String {
        Catalogo.Avv.certificatoAiuto(promemoria: Catalogo.Avv.certificatoOre(6))
    }

    private var colore: Color {
        switch info.livello {
        case .ok: return .testoSecondario
        case .attenzione: return .attenzione
        case .scaduto: return .malus
        case .ignoto: return .testoSecondario
        }
    }

    var body: some View {
        if !ProvaEsempio.attiva { corpo }
    }

    private var corpo: some View {
        Section(titolo: "Certificato dell'app") {
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
                    Text(scadenza.formatted(date: .abbreviated, time: .shortened)).foregroundStyle(Color.testoSecondario)
                }
                .accessibilityElement(children: .combine)
            }
            Text(Self.aiuto)
                .font(.footnote).foregroundStyle(Color.testoSecondario)
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
        if !ProvaEsempio.attiva { corpo }
    }

    private var corpo: some View {
        Section(titolo: "Rinnovo automatico (SideStore)") {
            VStack(alignment: .leading, spacing: 8) {
                Text("1. Nell'app Comandi crea un comando con l'azione di SideStore «Refresh All Apps».")
                Text("2. Vai su Automazione, tocca +, scegli «Ora del giorno», alle 3:00, ogni giorno.")
                Text("3. Come azione scegli quel comando, poi «Esegui subito» e spegni «Notifica quando viene eseguito».")
                Text("4. LocalDevVPN deve essere attiva durante il rinnovo: puoi lasciarla sempre accesa. Il server ha un indirizzo pubblico (https) e non serve altro per usare SchieraXI.")
            }
            .font(.footnote)
            .foregroundStyle(Color.testoSecondario)
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
        if !ProvaEsempio.attiva { corpo }
    }

    private var corpo: some View {
        Section(titolo: "Notifiche ntfy che mandi tu") {
            Text("Gli avvisi del server aprono già l'app (con «Avvisi anche per l'app nativa»). Solo se mandi tu una notifica con ntfy, per esempio da Comandi, aggiungi questa intestazione: toccandola si apre l'app sulla schermata scelta.")
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            Text(Collegamenti.esempioNtfy)
                .font(.system(.footnote, design: .monospaced))
                .textSelection(.enabled)
            Text("Altre destinazioni: giornate, impostazioni, e giocatore/<numero> per la scheda di un giocatore.")
                .font(.footnote).foregroundStyle(Color.testoSecondario)
        }
    }
}
