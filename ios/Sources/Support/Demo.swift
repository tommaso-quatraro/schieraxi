import SwiftUI

/// Modalità demo: se l'app parte con l'argomento di lancio `-DEMO` usa `FinteServer.demo` (dati finti, nessuna rete),
/// non chiede permessi, non programma notifiche e non registra lavori in background.
/// Serve a fotografare l'app nel simulatore di un Mac di GitHub (workflow `screenshot.yml`): nel comportamento normale non cambia niente.
///
/// Argomenti di lancio opzionali (solo con `-DEMO`):
/// - `-DEMO_SCHERMATA <nome>`: apre subito una schermata (vedi `applica`), perché dal simulatore non si può toccare lo schermo.
/// - `-DEMO_FONDO 1`: le schermate lunghe partono scorse in fondo (iOS 17 o più).
/// - `-DEMO_ORIENTAMENTO orizzontale`: chiede l'orientamento orizzontale.
enum Demo {
    static let attivo: Bool = ProcessInfo.processInfo.arguments.contains("-DEMO")

    /// Il valore che segue `-NOME` negli argomenti di lancio.
    static func argomento(_ nome: String) -> String? {
        let tutti = ProcessInfo.processInfo.arguments
        guard let i = tutti.firstIndex(of: "-" + nome), i + 1 < tutti.count else { return nil }
        return tutti[i + 1]
    }

    static var schermata: String? { attivo ? argomento("DEMO_SCHERMATA") : nil }

    /// Solo per la fotografia «ricerca»: la lente si apre da sola la prima volta (e il testo da cercare arriva da `-DEMO_CERCA`).
    static var ricercaMostrata = false

    /// `-DEMO_ACCESSO <scenario>`: la demo con gli account accesi. Scenari: `accedi`, `registra`, `recupero` (schermata di accesso),
    /// `codice` (il codice di recupero appena creato), `account` (Lega con «Il tuo account»), `rose` (lega senza rose: configurazione).
    static var accesso: String? { attivo ? argomento("DEMO_ACCESSO") : nil }

    /// Gli scenari che provano da soli ad accedere, per fotografare gli errori: `rete` (rete assente), `limite` (429), `non-valido` (il server non è SchieraXI).
    static var accessoAutomatico: Bool { ["rete", "limite", "non-valido"].contains(accesso ?? "") }

    /// La scheda della schermata di accesso da mostrare per lo scenario.
    static var schedaAccesso: SchermataAccesso.Scheda {
        switch accesso {
        case "registra": return .registrati
        case "recupero": return .recupera
        default: return .accedi
        }
    }

    /// Il server di partenza dell'app: quello finto in demo, quello vero altrimenti.
    static func serverPredefinito() -> any ServerClient {
        if attivo {
            if accesso == "rose" {
                // La lega non ha rose: il server risponde 409 «Nessuna rosa importata» a tutto quello che le richiede.
                var senzaRose = FinteServer.demo
                senzaRose.indirizzoFinto = "https://finto-senza-rose.invalid"   // niente copie salvate della lega di prova
                senzaRose.errori = ["/api/oggi": "Nessuna rosa importata", "/api/formazione": "Nessuna rosa importata", "/api/stato": "Nessuna rosa importata"]
                return senzaRose
            }
            // Errori dell'accesso, per le fotografie: rete assente, troppi tentativi, un server che risponde HTML invece del JSON.
            var errore = FinteServer.demo
            switch accesso {
            case "rete": errore.fallimenti = ["/api/account/accedi": .rete("senza rete")]
            case "limite": errore.fallimenti = ["/api/account/accedi": .troppiTentativi("Troppi tentativi sbagliati: aspetta prima di riprovare.", riprovaTra: 45)]
            case "non-valido": errore.risposte["/api/account/accedi"] = "<html><body><h1>Benvenuto</h1><p>Pagina di prova</p></body></html>"
            default: return FinteServer.demo
            }
            errore.indirizzoFinto = "https://finto-accesso-errore.invalid"
            return errore
        }
        return ServerHTTP()
    }
}

extension View {
    /// Solo in demo con `-DEMO_FONDO`: la schermata parte scorsa in fondo, per vedere anche la parte sotto la piega.
    @ViewBuilder
    func demoInFondo() -> some View {
        if Demo.attivo, Demo.argomento("DEMO_FONDO") != nil, #available(iOS 17, *) {
            self.defaultScrollAnchor(.bottom)
        } else {
            self
        }
    }
}

@MainActor
extension Demo {
    private static var applicata = false

    /// Porta l'app sulla schermata chiesta con `-DEMO_SCHERMATA`. Chiamata una volta sola all'avvio.
    static func applica(nav: Navigazione, modello: AppModel) {
        guard attivo, !applicata else { return }
        applicata = true

        if argomento("DEMO_ORIENTAMENTO") == "orizzontale" {
            // Più tentativi: sull'iPad la scena può non essere ancora pronta al primo.
            Task {
                for attesa in [0.0, 0.8, 1.6] as [Double] {
                    try? await Task.sleep(nanoseconds: UInt64(attesa * 1_000_000_000))
                    let scena = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first
                    scena?.requestGeometryUpdate(.iOS(interfaceOrientations: .landscapeRight)) { _ in }
                }
            }
        }

        if accesso == "account" {
            // l'account sta nelle Impostazioni (ingranaggio): in demo si apre subito il foglio
            nav.sezione = .lega
            nav.impostazioniAperte = true
        }
        guard let nome = argomento("DEMO_SCHERMATA") else { return }
        switch nome {
        case "oggi":
            nav.sezione = .oggi
        case "guida":
            // la configurazione guidata (si riapre dalle Impostazioni): in demo mostra i passi non ancora fatti
            nav.guidaAperta = true
        case "impostazioni-cofano":
            // le Impostazioni si aprono sulla pagina «Sotto il cofano» (la apre ImpostazioniView da sola)
            nav.impostazioniAperte = true

        case "formazione":
            nav.sezione = .formazione
        case "formazione-manuale":
            nav.sezione = .formazione
            Task {
                await modello.formazione.carica()
                try? await Task.sleep(nanoseconds: 400_000_000)
                if let f = modello.formazione.formazione { modello.formazione.iniziaModificaManuale(f) }
            }

        case "formazione-confronto", "confronto", "confronto-fondo":
            nav.sezione = .formazione
            Task {
                await modello.formazione.carica()
                try? await Task.sleep(nanoseconds: 400_000_000)
                modello.formazione.confrontoAperto = .coppia(120, 123)
            }
        case "formazione-immagine":
            nav.sezione = .formazione
            Task {
                await modello.formazione.carica()
                try? await Task.sleep(nanoseconds: 1_500_000_000)   // il tempo di caricare le foto
                if let f = modello.formazione.formazione { modello.formazione.preparaImmagine(f) }
            }

        case "mercato", "mercato-consigliati":
            nav.sezione = .mercato
            modello.mercato.sezione = .consigliati
        case "mercato-classifica":
            nav.sezione = .mercato
            modello.mercato.sezione = .giocatori
        case "mercato-calendario":
            nav.sezione = .mercato
            modello.mercato.sezione = .calendario
        case "mercato-osservati":
            nav.sezione = .mercato
            modello.mercato.sezione = .osservati
        case "mercato-asta", "mercato-asta-riparazione":
            // l'asta sta in Lega (due volte l'anno): Lega > Asta e riparazione
            apriLega(nav, modello, [.asta])
        case "mercato-cerca":
            nav.sezione = .mercato
            modello.mercato.sezione = .giocatori
            modello.mercato.testoRicerca = "ma"
        case "giocatore":
            nav.vai(a: .giocatore(203))

        case "scambi":
            nav.sezione = .scambi
        case "scambi-dettaglio":
            nav.sezione = .scambi
            Task {
                await modello.scambi.caricaProposte()
                try? await Task.sleep(nanoseconds: 800_000_000)
                modello.scambi.selezionata = modello.scambi.proposte.dato?.proposte.first(where: { $0.`do`.count > 1 })
                    ?? modello.scambi.proposte.dato?.proposte.first
            }
        case "scambi-offerta":
            nav.sezione = .scambi
            modello.scambi.testoOfferta = "Ciao! Ti do Vlahovic e tu mi dai Lukaku, ci stai?"
            Task {
                try? await Task.sleep(nanoseconds: 600_000_000)
                await modello.scambi.valutaOfferta()
            }
        case "scambi-analizza":
            nav.sezione = .scambi
            modello.scambi.percorso = [.analizza]

        case "lega":
            nav.sezione = .lega
        case "lega-squadre":
            apriLega(nav, modello, [.squadre])
        case "lega-rosa":
            apriLega(nav, modello, [.squadre, .rosa("Gli Amici del Bar Sport Centrale")])
        case "lega-regole":
            apriLega(nav, modello, [.regole])
        case "lega-asta":
            apriLega(nav, modello, [.asta])
        case "lega-stato":
            apriLega(nav, modello, [.stato])
        case "lega-crediti":
            apriLega(nav, modello, [.crediti])
        case "lega-avvisi":
            apriLega(nav, modello, [.avvisi])
        case "lega-diario":
            apriLega(nav, modello, [.diario])
        case "lega-backup":
            apriLega(nav, modello, [.backup])
        case "lega-novita":
            apriLega(nav, modello, [.novita])
        case "lega-importa":
            apriLega(nav, modello, [.importa])
        case "lega-importa-csv":
            // Un CSV vero (separatore «;», accenti) scritto in una cartella temporanea e importato come se arrivasse da un'altra app.
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("rose-schieraxi.csv")
            let csv = "Squadra;Ruolo;Giocatore;Costo\nGli Amici del Bar Sport Centrale;P;Giocatore 089;12\nGli Amici del Bar Sport Centrale;D;Giocatore 004;18\nGli Amici del Bar Sport Centrale;A;Giocatore 045;85\n"
            try? Data(csv.utf8).write(to: url)
            apriLega(nav, modello, [.importa])
            nav.fileDaImportare = url
        case "lega-movimenti":
            apriLega(nav, modello, [.movimenti])
        case "lega-stagione":
            apriLega(nav, modello, [.stagione])
        case "lega-aspetto":
            apriLega(nav, modello, [.aspetto])
        case "lega-icona":
            apriLega(nav, modello, [.icona])
        case "ricerca":
            nav.sezione = .oggi
        default:
            break
        }
    }

    private static func apriLega(_ nav: Navigazione, _ modello: AppModel, _ pagine: [PaginaLega]) {
        nav.sezione = .lega
        modello.lega.percorso = pagine
    }
}

/// Solo per le fotografie (`-DEMO_SCHERMATA marchio`): il marchio di SchieraXI fermo, in quattro momenti del movimento,
/// il segnaposto di caricamento e uno stato vuoto, sul fondo chiaro o scuro del sistema.
struct ProvaMarchio: View {
    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                VStack(spacing: 18) {
                    Scheletro(schede: 1, righe: 2, testo: "Scelgo gli undici…")
                    Carta("Il marchio, quattro momenti") {
                        HStack(spacing: 8) {
                            ForEach([0.0, 0.3, 0.5, 0.8], id: \.self) { f in
                                Marchio(lato: 76, muove: true, fermoAllaFase: f)
                            }
                        }
                        MarchioConNome(lato: 60)
                    }
                    Carta { VistaVuota(titolo: "Nessun giocatore osservato", icona: "star", descrizione: "Apri la scheda di un giocatore e tocca «Osserva».") }
                }
                .padding(Tema.margine)
            }
        }
    }
}
