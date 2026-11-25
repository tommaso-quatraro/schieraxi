import Foundation
import BackgroundTasks
import WidgetKit

/// Aggiornamento in background: ogni tanto iOS sveglia l'app (BGAppRefreshTask), che riscarica la giornata,
/// riprogramma i promemoria e, se la formazione consigliata è cambiata, manda una notifica locale.
/// iOS decide quando svegliarla (di solito poche volte al giorno, di più se usi spesso l'app): non c'è un orario garantito.
enum Aggiornamento {
    static let identificativo = "it.schieraxi.app.aggiorna"

    /// Chiede a iOS di svegliare l'app fra non meno di due ore.
    static func programma() {
        if Demo.attivo { return }   // demo: nessun lavoro in background
        let richiesta = BGAppRefreshTaskRequest(identifier: identificativo)
        richiesta.earliestBeginDate = Date(timeIntervalSinceNow: 2 * 3600)
        try? BGTaskScheduler.shared.submit(richiesta)
    }

    /// Riprogramma i promemoria sulla scadenza del certificato (se il profilo si legge).
    static func riprogrammaScadenza() async {
        if Demo.attivo { return }
        if let scadenza = Certificato.scadenza() { await Notifiche.programmaScadenza(scadenza) }
    }

    /// Il lavoro vero: scarica /api/oggi, lo salva nella cache e confronta con l'ultima volta. Se la lettura non riesce, i promemoria
    /// tornano in programma con l'ultima giornata salvata e partono: mai tacere per un dato incerto.
    static func esegui() async {
        if Demo.attivo { return }
        programma()   // prima di tutto: riprogramma il prossimo risveglio
        await riprogrammaScadenza()
        await NuovaVersione.controllaEAvvisa()
        await aggiornaOreTranquille()
        let repository = OggiRepository(server: ServerCorrente.condiviso)
        let chiesta = Date()
        guard let oggi = try? await repository.aggiornato() else {
            if let salvato = await repository.salvato() { await programmaPromemoria(salvato, lettura: .nonRiuscita) }
            return
        }
        await elabora(oggi, avvisaSeCambia: true, chiestaIl: chiesta)
    }

    /// Riempie in anticipo la copia di `/api/widget` (con If-None-Match), così i widget mostrano subito dati freschi.
    static func precaricaWidget() async {
        let base = IndirizzoServer.attuale
        if Demo.attivo || base.isEmpty { return }
        // Nei test unitari l'app che li ospita non deve scaricare niente dal server predefinito (scriverebbe la copia mentre un test la controlla).
        if ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil { return }
        // la copia porta l'impronta del collegamento che userà il widget (indirizzo e token del WIDGET): se è un altro, non la mostra
        let chi = MemoriaWidget.impronta(indirizzo: base, token: TokenWidget.leggi(server: base))
        let copia = MemoriaWidget.leggi(per: chi)
        if case .dati(_, let grezzo, let etag) = await ScaricoWidget.scarica(base: base, token: Accesso.archivio.leggi(server: base), etag: copia?.etag) {
            MemoriaWidget.salva(CopiaWidget(dati: grezzo, etag: etag, scaricatoIl: Date(), chi: chi))
        }
    }

    /// Rilegge le ore tranquille dal server (se risponde) per i promemoria locali.
    static func aggiornaOreTranquille() async {
        if Demo.attivo { return }
        if let stato: StatoAvvisi = try? await ServerCorrente.condiviso.get("/api/avvisi", snake: false) {
            ArchivioOreTranquille.salva(stato.impostazioni.oreTranquille)
        }
    }

    /// Da dove arriva la giornata con cui si programmano i promemoria (`promemoriaTace`).
    enum Lettura: Equatable {
        /// Appena letta dal server, con la richiesta partita a quell'ora: vale il suo `serve_promemoria` e i tocchi di prima si
        /// dimenticano.
        case fresca(chiestaIl: Date)
        /// La copia salvata sul telefono, senza provare la rete (avvisi riaccesi, ore tranquille cambiate, spunta appena toccata).
        case salvata
        /// La lettura dal server non è riuscita: la copia salvata dice la giornata, ma il suo `serve_promemoria` non basta.
        case nonRiuscita
    }

    /// I promemoria di questa giornata tacciono? La spunta toccata sul telefono dopo l'ultima lettura vale subito; altrimenti decide il
    /// server con la regola dei suoi promemoria (`serve_promemoria`, `Notifiche.tacePromemoria`).
    static func promemoriaTace(_ oggi: Oggi, lettura: Lettura, memoria: UserDefaults = .standard) -> Bool {
        let serve: Bool?
        switch lettura {
        case .fresca(let chiestaIl):
            ArchivioMessa.dimentica(primaDi: chiestaIl, memoria)
            serve = oggi.servePromemoria?.valore
        case .salvata:
            serve = oggi.servePromemoria?.valore
        case .nonRiuscita:
            serve = nil
        }
        return Notifiche.tacePromemoria(serve: serve, toccata: ArchivioMessa.toccata(giornata: oggi.giornata, memoria))
    }

    /// I promemoria di un'ora e di un quarto d'ora prima della scadenza di questa giornata (con «Avvisi su questo dispositivo» acceso),
    /// se servono (`promemoriaTace`).
    static func programmaPromemoria(_ oggi: Oggi, lettura: Lettura) async {
        let tace = promemoriaTace(oggi, lettura: lettura)
        if let inizio = Quando.data(oggi.chiusura), let nome = oggi.nomeGiornata {
            await Notifiche.programma(giornata: nome, inizio: inizio, modulo: oggi.formazione?.modulo, tace: tace)
        }
    }

    /// Dopo che gli avvisi si sono riaccesi o sono cambiate le ore tranquille: rimette in programma i promemoria con l'ultima giornata
    /// salvata, senza rete. `lettura: .nonRiuscita` quando una rilettura della giornata non è riuscita: allora partono.
    /// Senza una copia salvata ci pensa la prossima lettura di Oggi.
    static func riprogrammaPromemoria(lettura: Lettura = .salvata) async {
        if Demo.attivo { return }
        guard let oggi = await OggiRepository(server: ServerCorrente.condiviso).salvato() else { return }
        await programmaPromemoria(oggi, lettura: lettura)
    }

    /// Promemoria, widget e (se richiesto) notifica quando la formazione consigliata cambia nella stessa giornata. `chiestaIl`: quando
    /// è partita la lettura di questa giornata dal server.
    static func elabora(_ oggi: Oggi, avvisaSeCambia: Bool, chiestaIl: Date) async {
        if Demo.attivo { return }   // demo: niente promemoria, widget o notifiche
        await programmaPromemoria(oggi, lettura: .fresca(chiestaIl: chiestaIl))
        // Il widget trova subito l'ultima giornata (senza aspettare il suo scarico) e si ridisegna.
        Condiviso.salvaRiassunto(RiassuntoOggi(oggi: oggi))
        await precaricaWidget()
        WidgetCenter.shared.reloadAllTimelines()
        // Senza una formazione vera (modulo mancante o «–», punti assenti) non si confronta né si ricorda niente.
        guard let f = oggi.formazione, f.disponibile, let modulo = f.modulo, let giornata = oggi.giornata else { return }
        let memoria = UserDefaults.standard
        let probabili = oggi.conProbabili ?? false
        let giornataPrima = memoria.object(forKey: "bg.giornata") as? Int
        let moduloPrima = memoria.string(forKey: "bg.modulo")
        let probabiliPrima = memoria.object(forKey: "bg.probabili") as? Bool

        if avvisaSeCambia, giornataPrima == giornata {
            let punti = Formato.punti(f.punteggioAtteso)
            if let moduloPrima, moduloPrima != modulo {
                await Notifiche.avviso(id: "fanta-cambio", titolo: "SchieraXI · Cambio di modulo",
                                       corpo: corpoCambioModulo(oggi, modulo: modulo, punti: punti, moduloPrima: moduloPrima))
            } else if probabiliPrima == false, probabili {
                await Notifiche.avviso(id: "fanta-probabili", titolo: "SchieraXI · Escono le probabili",
                                       corpo: corpoProbabili(oggi, modulo: modulo, punti: punti))
            }
        }
        memoria.set(giornata, forKey: "bg.giornata")
        memoria.set(modulo, forKey: "bg.modulo")
        memoria.set(probabili, forKey: "bg.probabili")
    }

    /// I testi degli avvisi: la giornata con i due numeri in testa, seguita dai due punti, come gli avvisi del server (#299).
    static func corpoCambioModulo(_ oggi: Oggi, modulo: String, punti: String, moduloPrima: String) -> String {
        "\(oggi.nomeGiornata?.intero ?? "Prossima giornata"): ora \(modulo), \(punti) punti attesi (prima \(moduloPrima))."
    }

    static func corpoProbabili(_ oggi: Oggi, modulo: String, punti: String) -> String {
        "\(oggi.nomeGiornata?.intero ?? "Prossima giornata"): modulo consigliato \(modulo), \(punti) punti attesi."
    }

    /// La giornata di oggi per Siri e Comandi: dal server, o dalla cache se non risponde.
    static func leggiOggi() async -> (oggi: Oggi, salvato: Bool)? {
        await OggiRepository(server: ServerCorrente.condiviso).ultimo()
    }
}

extension Oggi {
    /// I due promemoria della scadenza già scritti dal server (`testi_promemoria`, #906); nil con un server di prima o con un
    /// campo strano.
    var promemoriaDelServer: [TestoPromemoria]? { testiPromemoria?.valore?.voci }
}
