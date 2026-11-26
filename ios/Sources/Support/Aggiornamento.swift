import Foundation
import BackgroundTasks
import WidgetKit

/// Aggiornamento in background: ogni tanto iOS sveglia l'app (BGAppRefreshTask), che riscarica la giornata e riprogramma i
/// promemoria. Gli avvisi quando cambia la formazione li manda solo il server (#676): l'app non ne manda di suoi (#906).
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

    /// Il lavoro vero: scarica /api/oggi, lo salva nella cache e riprogramma promemoria e widget. Se la lettura non riesce, i
    /// promemoria tornano in programma con l'ultima giornata salvata e partono: mai tacere per un dato incerto.
    static func esegui() async {
        if Demo.attivo { return }
        programma()   // prima di tutto: riprogramma il prossimo risveglio
        await tokenDelWidget()
        await aggiornaAvvisiDelServer()   // ore tranquille e avvisi del server, per i promemoria qui sotto
        await riprogrammaScadenza()
        await NuovaVersione.controllaEAvvisa()
        let server = ServerCorrente.condiviso
        let repository = OggiRepository(server: server)
        let chiesta = Date()
        let chi = ChiLegge.adesso(indirizzo: server.indirizzo)
        guard let oggi = try? await repository.aggiornato() else {
            if let salvato = await repository.salvatoConData() {
                await programmaPromemoria(salvato.oggi, lettura: .nonRiuscita, salvataIl: salvato.il)
            }
            return
        }
        await elabora(oggi, chiestaIl: chiesta, di: chi)
    }

    /// Con una sessione su questo telefono, il token del widget (`TokenWidget.assicura`): se il widget ha segnalato che il server
    /// glielo rifiuta (401, `SegnaleWidget`), se manca o se sta per scadere, se ne chiede uno nuovo anche senza aprire l'app.
    static func tokenDelWidget(server: any ServerClient = ServerCorrente.condiviso, sessione: any ArchivioToken = Accesso.archivio) async {
        guard sessione.leggi(server: server.indirizzo) != nil else { return }
        await TokenWidget.assicura(server: server, luoghi: .sistema, sessione: sessione)
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

    /// Rilegge dal server gli avvisi (`GET /api/avvisi`, se risponde) per i promemoria locali: le ore tranquille e se il server manda
    /// già i suoi avvisi a questo telefono (#906). Se non risponde resta quello che si sapeva.
    static func aggiornaAvvisiDelServer() async {
        if Demo.attivo { return }
        if let stato: StatoAvvisi = try? await ServerCorrente.condiviso.get("/api/avvisi", snake: false) {
            ricordaAvvisi(stato)
        }
    }

    /// Ricorda sul telefono gli avvisi come li ha il server: le ore tranquille e se manda già i suoi avvisi a questa app
    /// (`StatoAvvisi.mandaGiaIlServer`, ntfy per l'app nativa: allora l'app non programma i suoi promemoria). Dice se una delle due
    /// cose è cambiata rispetto a quello che il telefono sapeva: allora i promemoria vanno rimessi in programma.
    @discardableResult
    static func ricordaAvvisi(_ stato: StatoAvvisi, memoria: UserDefaults = .standard) -> Bool {
        let ore = stato.impostazioni.oreTranquille
        let manda = stato.mandaGiaIlServer
        let cambiato = ArchivioOreTranquille.leggi(memoria) != ore || ArchivioAvvisiDalServer.mandaGia(memoria) != manda
        ArchivioOreTranquille.salva(ore, memoria)
        ArchivioAvvisiDalServer.salva(manda, memoria)
        return cambiato
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
    /// server con la regola dei suoi promemoria (`serve_promemoria`, o la lista vuota di `testi_promemoria`: `Oggi.serveIlPromemoria`;
    /// `Notifiche.tacePromemoria`).
    static func promemoriaTace(_ oggi: Oggi, lettura: Lettura, memoria: UserDefaults = .standard) -> Bool {
        let serve: Bool?
        switch lettura {
        case .fresca(let chiestaIl):
            ArchivioMessa.dimentica(primaDi: chiestaIl, memoria)
            serve = oggi.serveIlPromemoria
        case .salvata:
            serve = oggi.serveIlPromemoria
        case .nonRiuscita:
            serve = nil
        }
        return Notifiche.tacePromemoria(serve: serve, toccata: ArchivioMessa.toccata(giornata: oggi.giornata, memoria))
    }

    /// I promemoria di un'ora e di un quarto d'ora prima della scadenza di questa giornata (con «Avvisi su questo dispositivo» acceso),
    /// se servono (`promemoriaTace`) e se il server non manda già i suoi a questo telefono, con i testi del server
    /// (`Notifiche.promemoriaDaProgrammare`). `salvataIl`: quando è stata salvata la copia, per una lettura non fresca.
    static func programmaPromemoria(_ oggi: Oggi, lettura: Lettura, salvataIl: Date? = nil) async {
        let tace = promemoriaTace(oggi, lettura: lettura)
        guard let inizio = Quando.data(oggi.chiusura), let nome = oggi.nomeGiornata else { return }
        let lettaIl: Date?
        if case .fresca(let chiestaIl) = lettura { lettaIl = chiestaIl } else { lettaIl = salvataIl }
        let elenco = Notifiche.promemoriaDaProgrammare(giornata: nome, inizio: inizio, testi: oggi.promemoriaDelServer, lettaIl: lettaIl,
                                                       ore: ArchivioOreTranquille.leggi(), attivi: ArchivioAvvisiQui.minutiAttivi(),
                                                       tace: tace, dalServer: ArchivioAvvisiDalServer.mandaGia())
        await Notifiche.programma(elenco)
    }

    /// Dopo che gli avvisi si sono riaccesi o sono cambiate le ore tranquille: rimette in programma i promemoria con l'ultima giornata
    /// salvata, senza rete. `lettura: .nonRiuscita` quando una rilettura della giornata non è riuscita: allora partono.
    /// Senza una copia salvata ci pensa la prossima lettura di Oggi.
    static func riprogrammaPromemoria(lettura: Lettura = .salvata) async {
        if Demo.attivo { return }
        guard let salvato = await OggiRepository(server: ServerCorrente.condiviso).salvatoConData() else { return }
        await programmaPromemoria(salvato.oggi, lettura: lettura, salvataIl: salvato.il)
    }

    /// Promemoria e widget dopo una lettura fresca della giornata. `chiestaIl`: quando è partita la lettura dal server; `chi`: di
    /// chi era la lettura (server e sessione di quel momento). Se nel frattempo la sessione è cambiata (un «Esci» o un altro accesso
    /// mentre la lettura era in viaggio, 26/11/2026), la giornata è dell'account di prima: niente promemoria e niente riassunto nel file
    /// condiviso, dove riscriverebbe i dati di chi è uscito. Si controlla anche subito prima di scrivere, dopo i promemoria.
    /// «Cambio di modulo» ed «Escono le probabili» non partono più dal telefono (#906): annunciavano come notizia anche il modulo
    /// salvato dall'utente, e il server li ha tolti con #676. `sessione`, `cartella` e `promemoria`: i test ne passano di loro (i
    /// promemoria veri passano dal centro delle notifiche di iOS, che nei test non si tocca).
    static func elabora(_ oggi: Oggi, chiestaIl: Date, di chi: ChiLegge, sessione: any ArchivioToken = Accesso.archivio,
                        cartella: URL? = Condiviso.cartella(),
                        promemoria: (Oggi, Date) async -> Void = { oggi, chiestaIl in
                            await Aggiornamento.programmaPromemoria(oggi, lettura: .fresca(chiestaIl: chiestaIl))
                        }) async {
        if Demo.attivo { return }   // demo: niente promemoria né widget
        guard chi.ancoraLui(sessione) else { return }
        await promemoria(oggi, chiestaIl)
        guard chi.ancoraLui(sessione) else { return }
        // Il widget trova subito l'ultima giornata (senza aspettare il suo scarico) e si ridisegna.
        Condiviso.aggiorna(cartella: cartella) { $0.riassunto = RiassuntoOggi(oggi: oggi) }
        await precaricaWidget()
        WidgetCenter.shared.reloadAllTimelines()
    }

    /// La giornata di oggi per Siri e Comandi: dal server, o dalla cache se non risponde.
    static func leggiOggi() async -> (oggi: Oggi, salvato: Bool)? {
        await OggiRepository(server: ServerCorrente.condiviso).ultimo()
    }
}

/// Di chi è una lettura della giornata: il server e il token della sessione di quando è partita (nil senza account). Serve a
/// `Aggiornamento.elabora` per non scrivere i dati di un account da cui nel frattempo si è usciti (come `TokenWidget.assicura` con il
/// token del widget). Resta solo in memoria.
struct ChiLegge: Equatable, Sendable {
    let indirizzo: String
    let sessione: String?

    /// Chi legge adesso da questo server.
    static func adesso(indirizzo: String, sessione: any ArchivioToken = Accesso.archivio) -> ChiLegge {
        ChiLegge(indirizzo: indirizzo, sessione: sessione.leggi(server: indirizzo))
    }

    /// La sessione per questo server è ancora la stessa di quando è partita la lettura?
    func ancoraLui(_ archivio: any ArchivioToken = Accesso.archivio) -> Bool {
        archivio.leggi(server: indirizzo) == sessione
    }
}

extension Oggi {
    /// I due promemoria della scadenza già scritti dal server (`testi_promemoria`, #906); nil con un server di prima o con un
    /// campo strano.
    var promemoriaDelServer: [TestoPromemoria]? { testiPromemoria?.valore?.voci }

    /// Il promemoria serve, secondo il server? No con `serve_promemoria: false` o con la lista dei testi vuota (#906); nil se il
    /// server non lo dice (server di prima, valore strano).
    var serveIlPromemoria: Bool? {
        if promemoriaDelServer?.isEmpty == true { return false }
        return servePromemoria?.valore
    }
}
