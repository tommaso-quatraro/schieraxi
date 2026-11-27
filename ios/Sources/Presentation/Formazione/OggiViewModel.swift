import SwiftUI

/// I dati della giornata (`GET /api/oggi`) per la Formazione unica (#673): testa per fase, decisioni in cima, partite rinviate.
/// Dopo ogni lettura fresca chiede il permesso per le notifiche (una volta) e passa la giornata a `Aggiornamento.elabora`, che
/// riprogramma i promemoria e aggiorna i widget: prima lo faceva la scheda Oggi, ora la Formazione (`OggiPerWidgetTests`).
@MainActor
final class OggiViewModel: ViewModelBase {
    let caricatore: Caricatore<Oggi>
    /// Rose salvate ma la tua squadra non scelta: la Formazione chiede la squadra invece della giornata (collaudo del 26/11).
    let squadra: SquadraDaScegliere
    private let server: any ServerClient
    /// Cresce a ogni lettura della giornata che passa a promemoria e widget (`leggi`): una lettura partita prima di un'altra e
    /// arrivata dopo, o mentre l'altra è in viaggio, è superata e non decide niente.
    private var letture = 0
    /// Partite rinviate: la scelta «per questa giornata» è in viaggio (il menu si blocca) e l'eventuale errore da mostrare, finché
    /// una lettura della giornata non riesce o la scelta dopo non si salva (collaudo del 26/11: prima restava per sempre).
    @Published private(set) var rinvioInCorso = false
    @Published var erroreRinvio: String?
    /// La scelta sul rinvio si è salvata: la conferma della web («Fatto: consigli aggiornati per questa giornata»,
    /// `TestiRinvio.salvato`), sotto il menu; la Formazione la toglie dopo qualche secondo.
    @Published var confermaRinvio: String?
    /// Cosa si fa con una giornata appena letta dal server (mai con la copia sul telefono), l'ora in cui è partita la lettura e di
    /// chi era (server e sessione di quel momento, `ChiLegge`): permesso per le notifiche la prima volta, promemoria e widget
    /// (`passaAWidgetEPromemoria`). Senza promemoria (test) niente; `OggiPerWidgetTests` la sostituisce per vedere che la giornata arriva.
    var dopoLetturaFresca: @MainActor (Oggi, Date, ChiLegge) async -> Void
    /// Cosa si fa se la giornata riletta dopo un tuo salvataggio non arriva dal server (`rileggiDopoUnSalvataggio`): i promemoria
    /// tornano in programma con la copia salvata e partono, mai tacere per un dato incerto. Nei test la sostituisce chi conta.
    var dopoLetturaNonRiuscita: @MainActor () async -> Void

    /// `conPromemoria: false` nei test: niente richiesta del permesso per le notifiche, promemoria, widget.
    init(server: any ServerClient, conPromemoria: Bool = true,
         percorso: @escaping @MainActor () -> String = { OggiRepository.percorso }) {
        self.server = server
        // Il comando «Aggiorna» lo gestisce questo ViewModel (deve anche riprogrammare i promemoria), non il Caricatore.
        caricatore = Caricatore<Oggi>(percorso(), ascolta: false, server: server)
        squadra = SquadraDaScegliere(server: server)
        if conPromemoria {
            dopoLetturaFresca = { oggi, chiestaIl, chi in await OggiViewModel.passaAWidgetEPromemoria(oggi, chiestaIl: chiestaIl, di: chi) }
            dopoLetturaNonRiuscita = { await Aggiornamento.riprogrammaPromemoria(lettura: .nonRiuscita) }
        } else {
            dopoLetturaFresca = { _, _, _ in }
            dopoLetturaNonRiuscita = {}
        }
        super.init()
        osserva(caricatore)
        osserva(squadra)
        alComandoAggiorna { [weak self] in
            await self?.carica()
        }
    }

    var oggi: Oggi? { caricatore.dato }
    var errore: String? { caricatore.errore }
    var datiSalvati: Date? { caricatore.datiSalvati }

    /// Si vede la giornata salvata sul telefono: all'apertura finché non arriva quella nuova, o perché non è arrivata. Le decisioni
    /// che scrivono restano spente (`FormazioneViewModel.decisioniSpente`).
    var copia: Bool { caricatore.dallaCache || caricatore.datiSalvati != nil }

    /// Ogni quanto si rilegge la giornata mentre si gioca (i voti escono a fine partita: non serve di più).
    static let ripassoGiornata: TimeInterval = 300

    /// Fase `in_corso`: rilegge la giornata ogni 5 minuti (punti fatti, cambi), finché la Formazione è visibile e la giornata è in
    /// corso. Solo la lettura: niente promemoria né permessi. La vista annulla il lavoro quando sparisce.
    func seguiGiornata() async {
        while !Task.isCancelled {
            do { try await Task.sleep(nanoseconds: UInt64(Self.ripassoGiornata * 1_000_000_000)) } catch { return }
            guard !Task.isCancelled else { return }
            await caricatore.ricarica()
            guard oggi?.faseGiornata == .inCorso else { return }
        }
    }

    /// Rilegge solo la giornata, senza promemoria né permessi (la rilettura ogni 5 minuti a giornata in corso).
    func rileggi() async {
        await caricatore.ricarica()
    }

    /// Ricarica la giornata e, se i dati sono freschi, riprogramma i promemoria.
    /// Partite rinviate, decisione per una sola giornata (`PUT /api/regole/rinvio`): la stessa scelta della regola della lega
    /// toglie l'eccezione. Poi si ricarica tutto (consigli, formazione, Oggi) come dopo un salvataggio delle regole.
    func cambiaRinvio(_ scelta: SceltaRinvio, modo: String) async {
        guard modo != scelta.modo, !rinvioInCorso else { return }
        rinvioInCorso = true
        confermaRinvio = nil
        defer { rinvioInCorso = false }
        do {
            let corpo = CorpoRinvio(giornata: scelta.giornata, modo: modo == scelta.predefinito ? nil : modo, stagione: scelta.stagione)
            _ = try await server.corpoJSON("PUT", "/api/regole/rinvio", corpo)
            erroreRinvio = nil
            confermaRinvio = TestiRinvio.salvato
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            erroreRinvio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }

    func carica() async {
        // Con dati vecchi (server irraggiungibile, o ancora la cache) non si riprogrammano i promemoria: sarebbero su una giornata vecchia.
        if case .fresca(let oggi, let chiestaIl, let chi) = await leggi() { await dopoLetturaFresca(oggi, chiestaIl, chi) }
    }

    /// Dopo un tuo salvataggio riuscito (o «Torna alla consigliata»): la giornata si rilegge e i promemoria del telefono li decide il
    /// server (`serve_promemoria`), che sa della spunta e dei titolari a rischio meglio della spunta ricordata qui (#710). Se la
    /// giornata non arriva, tornano in programma con la copia salvata e partono (`dopoLetturaNonRiuscita`).
    func rileggiDopoUnSalvataggio() async {
        switch await leggi() {
        case .fresca(let oggi, let chiestaIl, let chi): await dopoLetturaFresca(oggi, chiestaIl, chi)
        case .superata: break
        case .nonRiuscita: await dopoLetturaNonRiuscita()
        }
    }

    /// Com'è andata una lettura della giornata.
    private enum EsitoLettura {
        /// Arrivata fresca dal server, con l'ora in cui è partita (una spunta toccata dopo quest'ora vale ancora, `ArchivioMessa`) e
        /// di chi era la lettura (`ChiLegge`).
        case fresca(Oggi, chiestaIl: Date, chi: ChiLegge)
        /// Nel frattempo è partita un'altra lettura: decide quella. Così una risposta vecchia arrivata per ultima non toglie i
        /// promemoria e non cancella la spunta appena toccata (#710).
        case superata
        /// È rimasta la copia salvata (server irraggiungibile, o un errore).
        case nonRiuscita
    }

    /// Rilegge la giornata e dice com'è andata.
    private func leggi() async -> EsitoLettura {
        letture += 1
        let numero = letture
        let chiesta = Date()
        let chi = ChiLegge.adesso(indirizzo: server.indirizzo)
        await caricatore.ricarica()
        guard numero == letture else { return .superata }
        guard let oggi = caricatore.dato, caricatore.datiSalvati == nil, !caricatore.dallaCache else { return .nonRiuscita }
        erroreRinvio = nil          // la giornata è arrivata: l'errore di una scelta sul rinvio di prima non vale più
        return .fresca(oggi, chiestaIl: chiesta, chi: chi)
    }

    /// Una giornata fresca per i promemoria e i widget: la prima volta il permesso per le notifiche, poi gli avvisi del server (ore
    /// tranquille e se il server manda già i suoi avvisi a questo telefono, #906) e `Aggiornamento.elabora` (promemoria con i testi
    /// del server, riassunto per il widget). `chiestaIl`: quando è partita la lettura; `chi`: di chi era (se nel frattempo la
    /// sessione è cambiata, `elabora` non scrive niente). In demo niente.
    static func passaAWidgetEPromemoria(_ oggi: Oggi, chiestaIl: Date, di chi: ChiLegge) async {
        guard !Demo.attivo else { return }
        let memoria = UserDefaults.standard
        if !memoria.bool(forKey: "permessoChiesto") {
            memoria.set(true, forKey: "permessoChiesto")
            _ = await Notifiche.chiediPermesso()
            await Aggiornamento.riprogrammaScadenza()
        }
        await Aggiornamento.aggiornaAvvisiDelServer()
        await Aggiornamento.elabora(oggi, chiestaIl: chiestaIl, di: chi)
    }
}
