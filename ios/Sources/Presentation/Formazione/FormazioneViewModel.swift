import SwiftUI

/// I giocatori da mostrare in questo momento: la consigliata, la tua scelta salvata, a giornata in corso la formazione schierata o,
/// per un'altra squadra, un altro modulo.
struct VistaFormazione {
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let modulo: String
    /// nil finché il server non ha valutato quegli 11 (allora niente numero, mai i punti della consigliata) e a giornata in corso
    /// (contano i punti fatti, nella testa).
    let punti: Double?
    /// Gli 11 sono la tua formazione cambiata a mano e non quelli di una formazione calcolata dal server (anche nello stesso
    /// modulo): nel menu del modulo hanno una voce loro, in cima («4-3-3 · 71,0 punti · la tua», `vociModulo`).
    var tua = false
}

/// Logica della Formazione unica (#673), come `mostraFormazione` della web (#616): in campo la consigliata o la tua scelta salvata;
/// ogni cambio degli 11 (un altro modulo, «Sostituisci», una decisione in cima, la spunta «L'ho messa») si salva subito con
/// `POST /api/formazione/valuta` (`salva: true`, If-Match della scelta), «Torna alla consigliata» è `DELETE /api/scelta`. Una
/// scrittura alla volta; una risposta arrivata dopo una rilettura non vale e si rilegge. I comandi che scrivono restano spenti sulla
/// copia del telefono, con la scelta non letta e con una scrittura in volo. La formazione di un'altra squadra si guarda e basta.
/// A giornata in corso in campo c'è la formazione schierata di `/api/oggi` (`in_corso.giocatori`), come la web; prima della scadenza
/// la scelta letta resta sul telefono accanto alla copia della Formazione (`CopiaScelta`), così riaprendo senza rete in campo c'è
/// la formazione salvata e non la consigliata. Vive nell'`AppModel`: cambiando sezione non si perde niente.
@MainActor
final class FormazioneViewModel: ViewModelBase {
    let caricatore: Caricatore<Formazione>
    let server: any ServerClient
    /// La giornata (`/api/oggi`): a giornata in corso dice la formazione schierata; le sue copie spengono le decisioni che scrivono.
    let oggi: OggiViewModel?

    /// L'ultimo avviso (un salvataggio non riuscito, la scelta cambiata da un altro dispositivo, la formazione copiata).
    @Published var messaggio: String?
    /// Un salvataggio partito da qui non è riuscito quando eri già su un'altra scheda (#726): l'avviso che la radice mostra sulle
    /// altre schede (`AvvisoNonSalvata`), con una frase del catalogo che nomina la formazione (`testoNonSalvata`).
    @Published var avvisoAltrove: String?
    /// La Formazione è la scheda aperta (lo dice la radice a ogni cambio di scheda). Decide dove si dice una scrittura che non
    /// riesce: qui sotto il campo (`messaggio`) o sulle altre schede (`avvisoAltrove`). Tornando qui l'avviso delle altre schede se
    /// ne va e, se c'è un guasto o un 412 arrivato a scheda lasciata, compare l'avviso di sempre.
    var inVista = true {
        didSet {
            guard inVista else { return }
            avvisoAltrove = nil
            if cambiataFuori {
                messaggio = testoCambiataFuori
            } else if let guasto {
                messaggio = testoQui(guasto)
            }
        }
    }
    /// L'errore dell'ultima scrittura non riuscita a scheda lasciata, finché una dopo non riesce o arriva un'altra giornata: tornando
    /// sulla Formazione se ne rivede l'avviso, anche se quello delle altre schede è passato senza che lo vedessi (sotto un foglio).
    private var guasto: Error?
    /// L'ultima scrittura ha avuto un 412 a scheda lasciata (#751): tornando sulla Formazione, a ogni ritorno finché non fai una nuova
    /// modifica o arriva un'altra giornata, la frase di sempre del 412 (`testoCambiataFuori`). Chi non ha visto l'avviso in basso
    /// sa così perché in campo c'è un'altra formazione.
    private var cambiataFuori = false
    /// Nome di un'altra squadra della lega, se se ne sta guardando la formazione consigliata (nil = la mia).
    @Published private(set) var squadraVista: String?
    /// Un altro modulo guardato nella formazione di un'altra squadra: solo sullo schermo, non si salva niente.
    @Published private(set) var moduloScelto: String?
    /// L'elenco di «Sostituisci» aperto (dalla scheda di un titolare): chi esce e chi può prendere il suo posto; nil = chiuso.
    @Published var elencoSostituti: ElencoSostituti?
    /// «Sostituisci» toccato nella scheda: la scelta del sostituto si apre quando il foglio della scheda è sparito.
    private var sostituzioneInAttesa: Int?
    /// L'elenco di «Metti in campo» aperto (#778): chi entra e chi può lasciargli il posto; nil = chiuso.
    @Published var elencoEntra: ElencoMettiInCampo?
    /// «Metti in campo» toccato nella scheda: l'elenco si apre quando il foglio della scheda è sparito.
    private var mettiInCampoInAttesa: Int?
    /// Cresce a ogni elenco aperto: la risposta di un elenco già chiuso, o sostituito da un altro, non vale.
    private var numeroElenco = 0

    /// La scelta della giornata è stata letta dal server (anche «nessuna»): finché no, non si può cambiare niente.
    @Published private(set) var sceltaLetta = false
    /// Scelta, 11 in campo e valutazione vengono dalla copia del telefono (`CopiaScelta`), non ancora dal server: si mostrano finché
    /// si vede la copia della Formazione o si sta rileggendo, ma non si scrive niente (`sceltaLetta` resta falso).
    @Published private(set) var sceltaInCopia = false
    /// La scelta salvata (nil = nessuna, vale la consigliata).
    @Published private(set) var salvata: SceltaSalvata?
    /// La scelta salvata non si può più schierare (lo dice il server): in campo la consigliata, finché non la cambi. Per leggerla
    /// `salvataNonValida`, che la lega alla giornata in pagina.
    @Published private var sceltaNonValida = false
    /// Gli 11 in campo quando non sono quelli della consigliata (la tua scelta salvata); nil = la consigliata.
    @Published private(set) var manuale: [Int]?
    /// La valutazione del server per `manuale`, quando quegli 11 non sono un modulo già calcolato.
    @Published private(set) var valutazione: ValutazioneManuale?
    /// Una scrittura è partita e il server non ha ancora risposto: una alla volta, gli altri comandi aspettano.
    @Published private(set) var occupato = false
    /// Formazione e scelta si stanno rileggendo: i comandi aspettano i dati nuovi.
    @Published private(set) var leggendo = false

    /// Quando è partita l'ultima lettura della Formazione (`sc.letta` della web): tornando dal secondo piano, con i dati di più di
    /// 5 minuti fa, la schermata si rilegge (`DatiVecchi.rileggiAlRitorno`).
    private(set) var lettaIl: Date?

    /// La giornata della scelta letta: se cambia si riparte da zero.
    private var giornata: Int?
    /// Cresce a ogni rilettura: una risposta (lettura o scrittura) partita prima non vale più.
    private var generazione = 0

    /// Dove si ricorda la spunta «L'ho messa» per i promemoria del telefono (`ArchivioMessa`; nei test una memoria a parte).
    private let memoria: UserDefaults
    /// Rimette in programma i promemoria del telefono quando la spunta cambia (nei test conta le chiamate).
    private let promemoria: @MainActor () -> Void

    /// `promemoria`: nil = quelli veri, con l'ultima giornata salvata e senza rete (mai nei test né nella demo).
    init(server: any ServerClient, oggi: OggiViewModel? = nil, memoria: UserDefaults = .standard,
         promemoria: (@MainActor () -> Void)? = nil) {
        self.server = server
        self.oggi = oggi
        self.memoria = memoria
        self.promemoria = promemoria ?? {
            guard !Ambiente.ospiteDeiTest, !Demo.attivo else { return }
            Task { await Aggiornamento.riprogrammaPromemoria() }
        }
        // il comando «Aggiorna» rilegge formazione e scelta insieme (non solo la formazione)
        caricatore = Caricatore<Formazione>("/api/formazione", ascolta: false, server: server)
        super.init()
        osserva(caricatore)
        // campo, striscia e decisioni dipendono anche dalla giornata: chi guarda solo questo ViewModel si ridisegna lo stesso
        if let oggi { osserva(oggi) }
        alComandoAggiorna { [weak self] in
            _ = await self?.carica()
        }
    }

    var formazione: Formazione? { caricatore.dato }
    var errore: String? { caricatore.errore }
    var datiSalvati: Date? { caricatore.datiSalvati }

    // MARK: stato della schermata

    /// La giornata è chiusa (dopo la scadenza, `iniziata` del server, o a giornata in corso come la web): la formazione si vede in
    /// sola lettura.
    var chiusa: Bool { formazione.map { $0.iniziata == true || dalVivo($0) != nil } ?? false }

    /// Si vedono i dati salvati sul telefono: all'apertura finché non arriva la risposta nuova, o perché non è arrivata.
    var copia: Bool { caricatore.dallaCache || caricatore.datiSalvati != nil }

    /// I dati nuovi non sono arrivati: resta la copia, che non si può cambiare (`formazione.copia_ferma`, con «Riprova»).
    var copiaFerma: Bool { squadraVista == nil && caricatore.datiSalvati != nil }

    /// I comandi che scrivono sono spenti (`sc.sola` della web): sulla copia del telefono, con la scelta non letta, mentre la si
    /// rilegge e con una scrittura in volo. Solo per la tua formazione: quella di un'altra squadra non scrive niente.
    var comandiSpenti: Bool { squadraVista == nil && (copia || !sceltaLetta || leggendo || occupato) }

    /// Si può scrivere sulla scelta: la tua formazione, aperta, con i comandi accesi.
    private var puoScrivere: Bool { squadraVista == nil && !chiusa && !comandiSpenti }

    /// Perché adesso un cambio della tua formazione non si può fare, con la frase del catalogo che lo dice (nil = si può): la
    /// formazione si è chiusa (`err.formazione_chiusa`, la frase della web e del 409 del server), restano i dati salvati sul
    /// telefono (`formazione.copia_ferma`), stanno arrivando i dati, si rilegge o un salvataggio è in volo
    /// (`formazione.sto_ancora_ricalcolando`, come `libero()` della web), la scelta salvata non si è letta
    /// (`formazione.scelta_non_letta`). Negli elenchi di «Sostituisci» e «Metti in campo» spegne le righe e si legge sopra di loro;
    /// un cambio che non parte lo dice sotto il campo (collaudo del 26/11).
    var motivoCambiSpenti: String? {
        guard squadraVista == nil else { return nil }
        if chiusa { return Catalogo.Err.formazioneChiusa }
        if copiaFerma { return Catalogo.Formazione.copiaFerma }
        if leggendo || occupato || copia { return Catalogo.Formazione.stoAncoraRicalcolando }
        if !sceltaLetta { return Catalogo.Formazione.sceltaNonLetta }
        return nil
    }

    /// La scelta da mostrare è nota: letta dal server o, mentre si vede la copia della Formazione o si sta rileggendo, dalla copia del
    /// telefono. Sempre della giornata in pagina.
    var sceltaNota: Bool {
        guard let f = formazione, giornata == f.giornata else { return false }
        return sceltaLetta || (sceltaInCopia && (copia || leggendo))
    }

    /// La riga dello stato sotto il campo (vedi `StatoScelta`). Mentre si rilegge non si dice che la scelta non è letta (sta
    /// arrivando); se il server dice che ce n'è una salvata e non si è letta lo si dice sempre, tranne a giornata in corso, quando in
    /// campo c'è già la formazione schierata.
    var statoScelta: StatoScelta {
        guard let f = formazione else { return .nessuno }
        let v = vista(f)
        return StatoScelta.calcola(mia: squadraVista == nil, letta: sceltaNota, copia: copia || leggendo, chiusa: chiusa, salvata: salvataQui,
                                   nonValida: salvataNonValida, titolari: v.titolari.map(\.id), consigliati: consigliati(f),
                                   punti: v.punti, puntiConsigliata: consigliato(f)?.punteggioAtteso ?? f.punteggioAtteso,
                                   salvataNonLetta: !leggendo && dalVivo(f) == nil && f.statoScelta == Self.statoValida)
    }

    /// `stato_scelta` del server quando c'è una scelta salvata che vale.
    static let statoValida = "valida"

    /// Le decisioni in cima che scrivono sono spente: come gli altri comandi e, in più, quando la giornata da cui vengono
    /// (`/api/oggi`) è la copia del telefono.
    var decisioniSpente: Bool { comandiSpenti || (squadraVista == nil && oggi?.copia == true) }

    /// La striscia dei dati salvati: la Formazione o la giornata (`/api/oggi`) non sono arrivate fresche. La data più vecchia delle
    /// due, con il suo motivo (nil = server non raggiungibile). A campionato finito la Formazione non si mostra (il server risponde
    /// 409 e resta in memoria quella di prima): conta solo la giornata.
    var striscia: (data: Date, motivo: String?)? {
        var vecchi: [(data: Date, motivo: String?)] = []
        if !campionatoFinito, let d = caricatore.datiSalvati { vecchi.append((d, caricatore.motivoDatiSalvati)) }
        if squadraVista == nil, let o = oggi, let d = o.datiSalvati { vecchi.append((d, o.caricatore.motivoDatiSalvati)) }
        return vecchi.min { $0.data < $1.data }
    }

    /// L'errore di `/api/oggi` quando non c'è nemmeno una copia da mostrare: mancano testa e decisioni, e lo si dice.
    var erroreGiornata: String? {
        guard squadraVista == nil, let o = oggi, o.oggi == nil else { return nil }
        return o.errore
    }

    /// Il campionato è finito (`campionato_finito` di `/api/oggi`, #656): non c'è una giornata da preparare e `/api/formazione`
    /// risponde 409. La Formazione mostra il riepilogo dell'ultima giornata, se c'è, e la frase del server, senza errore né
    /// «Riprova», come `mostraCampionatoFinito` della web (#727). Solo per la tua squadra. Se di `/api/oggi` c'è solo la copia del
    /// telefono (a inizio stagione può essere quella di giugno) e la Formazione è arrivata fresca, vince il dato fresco: si mostra la
    /// formazione, non la frase vecchia.
    var campionatoFinito: Bool {
        guard squadraVista == nil, let o = oggi, o.oggi?.testoCampionatoFinito != nil else { return false }
        let formazioneFresca = formazione != nil && !copia
        return !(o.copia && formazioneFresca)
    }

    /// La scelta che si conosce è della giornata in pagina, come per `manualeDi`: la copia sul telefono può essere di un'altra
    /// giornata (la scelta non riletta dopo il cambio di giornata, poi l'app riaperta senza rete), e allora qui non vale (#699).
    private var sceltaDellaGiornata: Bool { giornata != nil && giornata == formazione?.giornata }

    /// La scelta salvata, se è della giornata in pagina.
    private var salvataQui: SceltaSalvata? { sceltaDellaGiornata ? salvata : nil }

    /// La scelta salvata non si può più schierare: solo se è della giornata in pagina.
    var salvataNonValida: Bool { sceltaNonValida && sceltaDellaGiornata }

    /// La spunta «L'ho messa»: vale per gli 11 salvati della giornata in pagina.
    var messa: Bool { salvataQui?.messa == true }

    /// Anticipi già cominciati (#373, campo `bloccati` del server): chi gioca una partita già cominciata non si sposta più.
    var fermi: Set<Int> { Set(formazione?.bloccati ?? []) }

    // MARK: livello, consigliata e moduli

    /// Lo stile «Equilibrata» del server (`rischio` 0): dal 12/11/2026 è l'unico, come sulla web (#634).
    static let rischioEquilibrato = 0

    /// Il livello da cui vengono moduli e titolari: quello equilibrato (se manca, il primo). Nil con un server senza `livelli`.
    func livello(_ f: Formazione) -> LivelloRischio? {
        guard let livelli = f.livelli else { return nil }
        return livelli.first(where: { $0.rischio == Self.rischioEquilibrato }) ?? livelli.first
    }

    /// Il modulo consigliato del livello equilibrato.
    func consigliato(_ f: Formazione) -> OpzioneModulo? {
        guard let l = livello(f) else { return nil }
        return l.moduli.first(where: { $0.modulo == l.modulo }) ?? l.moduli.first
    }

    /// Gli 11 della consigliata.
    func consigliati(_ f: Formazione) -> [Int] { consigliato(f)?.titolari ?? f.titolari.map(\.id) }

    /// Il modulo già calcolato dal server che ha proprio questi 11 (l'ordine non conta), come `moduloDi` della web.
    func moduloDi(_ f: Formazione, _ ids: [Int]) -> OpzioneModulo? {
        livello(f)?.moduli.first { Set($0.titolari) == Set(ids) }
    }

    /// Le formazioni calcolate dal server per il menu del modulo, quelle del livello equilibrato (la tua, se è un'altra, la mette in
    /// cima `vociModulo`).
    func moduli(_ f: Formazione) -> [OpzioneModulo] { livello(f)?.moduli ?? [] }

    // MARK: cosa mostrare

    /// A giornata in corso la formazione che vale la dice `/api/oggi` (`in_corso.giocatori`: titolari e panchina in ordine, con chi è
    /// entrato), come `live` di `mostraFormazione` della web: anche sulla copia del telefono, ed è quella dei punti della testa. Solo
    /// per la tua squadra e per la giornata in pagina.
    func dalVivo(_ f: Formazione) -> GiornataInCorso? {
        guard squadraVista == nil, let o = oggi?.oggi, !o.senzaFormazioneInCorso, let c = o.giornataInCorso,
              c.giocatori.contains(where: \.titolare), (c.giornata ?? o.giornata).map({ $0 == f.giornata }) ?? true else { return nil }
        return c
    }

    /// Il modulo e i punti attesi sopra il campo: non a giornata in corso, quando contano i punti fatti (la web li nasconde).
    func conModulo(_ f: Formazione) -> Bool { dalVivo(f) == nil }

    /// La scheda di un giocatore schierato con lo stato vero della sua partita (`scheda` della web a giornata in corso).
    private func scheda(_ g: GiocatoreInCorso, _ f: Formazione) -> Giocatore? {
        let x = f.schede?[String(g.id)] ?? (f.titolari + f.panchina).first { $0.id == g.id }
        return x.map { $0.dalVivo(g) } ?? Giocatore.soloDalVivo(g)
    }

    /// Gli 11 della tua scelta da mettere in campo, se sono della giornata in pagina.
    private func manualeDi(_ f: Formazione) -> [Int]? {
        guard let manuale, giornata == f.giornata else { return nil }
        return manuale
    }

    /// Titolari, panchina, modulo e punti attesi in campo.
    func vista(_ f: Formazione) -> VistaFormazione {
        let base = VistaFormazione(titolari: f.titolari, panchina: f.panchina, modulo: f.modulo, punti: f.punteggioAtteso)
        if let live = dalVivo(f) {
            return VistaFormazione(titolari: live.giocatori.filter(\.titolare).compactMap { scheda($0, f) },
                                   panchina: live.giocatori.filter { !$0.titolare }.compactMap { scheda($0, f) },
                                   modulo: oggi?.oggi?.formazione?.modulo ?? consigliato(f)?.modulo ?? f.modulo, punti: nil)
        }
        guard let schede = f.schede else { return base }
        func giocatori(_ ids: [Int]) -> [Giocatore] { ids.compactMap { schede[String($0)] } }
        if squadraVista == nil, let manuale = manualeDi(f) {
            let titolari = giocatori(manuale)
            if let m = moduloDi(f, manuale) {
                return VistaFormazione(titolari: titolari, panchina: giocatori(m.panchina), modulo: m.modulo, punti: m.punteggioAtteso)
            }
            let panchina = valutazione?.panchina ?? f.panchina.map(\.id).filter { !manuale.contains($0) }
            return VistaFormazione(titolari: titolari, panchina: giocatori(panchina),
                                   modulo: valutazione?.modulo ?? ModuloTitolari.modulo(ruoli: titolari.map(\.ruolo)),
                                   punti: valutazione?.punteggioAtteso, tua: true)
        }
        let guardato = squadraVista == nil ? nil : moduloScelto.flatMap { m in livello(f)?.moduli.first { $0.modulo == m } }
        guard let opzione = guardato ?? consigliato(f) else { return base }
        let titolari = giocatori(opzione.titolari)
        if titolari.isEmpty { return base }
        return VistaFormazione(titolari: titolari, panchina: giocatori(opzione.panchina), modulo: opzione.modulo,
                               punti: opzione.punteggioAtteso)
    }

    /// «di solito fra 65 e 82» (la fascia del server, 8 volte su 10) o, con una risposta vecchia, «oscilla di ±N», come
    /// `fraseDiSolito` della web. Nil se il server non manda niente.
    func fascia(_ f: Formazione) -> String? {
        if squadraVista == nil, let manuale = manualeDi(f) {
            if let m = moduloDi(f, manuale) { return Self.diSolito(m.intervallo, dev: m.dev) }
            return Self.diSolito(valutazione?.intervallo, dev: valutazione?.dev)
        }
        let guardato = squadraVista == nil ? nil : moduloScelto.flatMap { m in livello(f)?.moduli.first { $0.modulo == m } }
        if let opzione = guardato ?? consigliato(f) { return Self.diSolito(opzione.intervallo, dev: opzione.dev) }
        return Self.diSolito(f.intervallo, dev: f.dev)
    }

    static func diSolito(_ intervallo: IntervalloPunti?, dev: Double?) -> String? {
        if let b = intervallo?.basso, let a = intervallo?.alto, b.isFinite, a.isFinite, b <= a {
            return Catalogo.Formazione.diSolito(a: Formato.decimali(b, cifre: 0), b: Formato.decimali(a, cifre: 0))
        }
        if let dev, dev.isFinite, dev >= 0 { return Catalogo.Formazione.oscilla(n: Formato.decimali(dev, cifre: 0)) }
        return nil
    }

    /// Una voce del menu dei moduli: «4-3-3 · 73,7 punti · consigliato».
    func etichettaModulo(_ m: OpzioneModulo, _ f: Formazione) -> String {
        m.modulo == consigliato(f)?.modulo
            ? Catalogo.Formazione.opzioneConsigliato(modulo: m.modulo, punti: Formato.punti(m.punteggioAtteso))
            : Catalogo.Formazione.opzioneModulo(modulo: m.modulo, punti: Formato.punti(m.punteggioAtteso))
    }

    /// Le voci del menu del modulo, come `voci` di `mostraFormazione` della web (#978): le formazioni calcolate dal server e, se gli
    /// 11 in campo non sono quelli di una di loro (un cambio a mano, anche nello stesso modulo), in cima la tua con i suoi punti,
    /// quelli del server (`formazione.opzione_tua`), con la spunta. Prima la spunta stava sulla voce del server con lo stesso
    /// modulo e altri punti, e la tua non c'era. Vuote senza moduli: allora il modulo è fisso.
    func vociModulo(_ f: Formazione) -> [VoceModulo] {
        let calcolati = moduli(f)
        guard !calcolati.isEmpty else { return [] }
        let v = vista(f)
        let delServer = calcolati.map { m in
            VoceModulo(modulo: m.modulo, etichetta: etichettaModulo(m, f), scelta: !v.tua && m.modulo == v.modulo)
        }
        guard v.tua else { return delServer }
        let tua = VoceModulo(modulo: nil, etichetta: Catalogo.Formazione.opzioneTua(modulo: v.modulo, punti: Formato.punti(v.punti)),
                             scelta: true)
        return [tua] + delServer
    }

    /// Chi non è fra titolari e panchina e può giocare, dal più forte (punti attesi): «Non schierati».
    func nonSchierati(_ f: Formazione, _ v: VistaFormazione) -> [Giocatore] { altri(f, v).filter { !Self.nonGioca($0) } }
    /// Chi non è fra titolari e panchina ed è infortunato, squalificato o fuori: «Infortunati e squalificati».
    func indisponibili(_ f: Formazione, _ v: VistaFormazione) -> [Giocatore] { altri(f, v).filter { Self.nonGioca($0) } }

    private func altri(_ f: Formazione, _ v: VistaFormazione) -> [Giocatore] {
        let scelti = Set((v.titolari + v.panchina).map(\.id))
        return (f.schede ?? [:]).values.filter { !scelti.contains($0.id) }.sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
    }

    /// Non gioca di sicuro (`fermo` della web): infortunato, squalificato o fuori.
    static func nonGioca(_ g: Giocatore) -> Bool {
        ["infortunato", "squalificato", "fuori"].contains(ParolaStato(g)?.codice ?? "")
    }

    // MARK: decisioni in cima

    /// Al massimo due decisioni, quelle che il server segna e che hanno ancora senso con gli 11 in campo (`Decisioni`). Solo per la
    /// tua formazione. `tecniche`: chi gestisce l'app vede anche le voci tecniche.
    func decisioni(_ oggi: Oggi?, tecniche: Bool) -> [DaFareVoce] {
        guard squadraVista == nil, let oggi, let f = formazione else { return [] }
        let titolari = vista(f).titolari.map(\.id)
        let dentro = Set(consigliati(f))
        let pagina = Decisioni.Pagina(titolari: titolari, chiusa: chiusa, conScelta: salvataQui != nil,
                                      diversi: titolari.filter { !dentro.contains($0) }.count, tecniche: tecniche)
        return Decisioni.prime(oggi.daFare ?? [], pagina: pagina)
    }

    /// «+1,3 punti attesi.» accanto al cambio proposto: il numero della formazione, dal server.
    func guadagno(_ v: DaFareVoce) -> String? {
        Decisioni.guadagno(v)
    }

    // MARK: caricamento

    /// L'indirizzo della formazione che si sta guardando.
    var percorso: String {
        if let s = squadraVista { return "/api/formazione?squadra=\(IndirizzoServer.codifica(s))" }
        return "/api/formazione"
    }

    /// Rilegge la formazione e, per la tua squadra, la scelta della giornata. true se la scelta è stata letta (anche «nessuna»).
    @discardableResult
    func carica() async -> Bool {
        generazione += 1
        let g = generazione
        leggendo = true
        lettaIl = Date()
        defer {
            if g == generazione {
                leggendo = false
                chiudiElenchiSuperati()
            }
        }
        // all'apertura, prima della copia della Formazione, la scelta tenuta sul telefono: in campo subito la formazione salvata
        if squadraVista == nil, giornata == nil { await riprendiSceltaDalTelefono() }
        await caricatore.ricarica(percorso)
        // la risposta nuova non è arrivata: resta la copia, con la scelta di prima
        guard g == generazione, let f = caricatore.dato, caricatore.datiSalvati == nil else { return false }
        return await leggiScelta(f, generazione: g)
    }

    /// Legge la scelta salvata (come `caricaGiornata` della web): se gli 11 non sono un modulo già calcolato li valuta il server,
    /// senza salvare. Non letta o non valutata: la riga lo dice e non si può cambiare niente (un salvataggio scriverebbe sopra una
    /// scelta che non si è vista). Una lettura annullata (la schermata è sparita) lascia tutto com'era.
    private func leggiScelta(_ f: Formazione, generazione g: Int) async -> Bool {
        guard squadraVista == nil else { return false }
        if giornata != f.giornata {
            giornata = f.giornata
            dimentica()
            sceltaLetta = false
            guasto = nil        // era della giornata di prima
            cambiataFuori = false
        }
        let letta: SceltaSalvata?
        do {
            letta = try await server.get("/api/scelta?giornata=\(f.giornata)")
        } catch {
            if Task.isCancelled || error is CancellationError { return false }
            if g == generazione { sceltaLetta = false }
            return false
        }
        guard g == generazione, squadraVista == nil, giornata == f.giornata else { return false }
        guard let s = letta else {
            dimentica()
            sceltaLetta = true
            ricordaSulTelefono(f)
            return true
        }
        let nonValida = f.statoScelta == "non_valida"
        // a giornata in corso in campo c'è la formazione schierata di `/api/oggi` (`dalVivo`): valutare gli 11 salvati non serve, e
        // la rilettura ogni 5 minuti non lo chiede più al server (come `caricaGiornata` della web, collaudo del 26/11)
        if nonValida || dalVivo(f) != nil || Set(s.titolari) == Set(consigliati(f)) || moduloDi(f, s.titolari) != nil {
            ricorda(s, nonValida: nonValida, f, valutazione: nil)
            return true
        }
        do {
            let r: ValutazioneManuale = try await server.posta("POST", "/api/formazione/valuta",
                                                                RichiestaValutazione(titolari: s.titolari, salva: false, giornata: f.giornata))
            guard g == generazione else { return false }
            ricorda(s, nonValida: false, f, valutazione: r)
            return true
        } catch {
            if Task.isCancelled || error is CancellationError { return false }
            guard g == generazione else { return false }
            if case .codificato(let codice, _)? = error as? ErroreApi, codice == ValiditaScelta.codiceNonValida {
                ricorda(s, nonValida: true, f, valutazione: nil)
                return true
            }
            sceltaLetta = false
            return false
        }
    }

    /// La scelta letta (o appena salvata) e gli 11 da mettere in campo: quelli salvati, se valgono e non sono la consigliata.
    private func ricorda(_ s: SceltaSalvata, nonValida: Bool, _ f: Formazione, valutazione r: ValutazioneManuale?) {
        salvata = s
        sceltaNonValida = nonValida
        metti(nonValida ? nil : s.titolari, f, valutazione: r)
        sceltaLetta = true
        sceltaInCopia = false
        ricordaSulTelefono(f)
    }

    /// Mette in campo questi 11 (nil = la consigliata).
    private func metti(_ ids: [Int]?, _ f: Formazione, valutazione r: ValutazioneManuale?) {
        guard let ids, Set(ids) != Set(consigliati(f)) else {
            manuale = nil
            valutazione = nil
            return
        }
        manuale = ids
        valutazione = moduloDi(f, ids) == nil ? r : nil
    }

    /// Niente scelta: in campo la consigliata.
    private func dimentica() {
        salvata = nil
        sceltaNonValida = false
        manuale = nil
        valutazione = nil
        sceltaInCopia = false
    }

    // MARK: la scelta sul telefono

    /// Tiene sul telefono la scelta appena letta o salvata, accanto alla copia della Formazione (`CopiaScelta`).
    private func ricordaSulTelefono(_ f: Formazione) {
        guard squadraVista == nil else { return }
        guard let dati = CopiaScelta(giornata: f.giornata, scelta: salvata, nonValida: sceltaNonValida, valutazione: valutazione).dati
        else { return }
        Cache.salva(dati, CopiaScelta.percorso, indirizzo: server.indirizzo)
    }

    /// La spunta «L'ho messa» che vale: sugli 11 salvati, se la scelta si può ancora schierare.
    private var spuntaValida: Bool { messa && !salvataNonValida }

    /// La spunta dopo un tuo salvataggio (o «Torna alla consigliata»): se è cambiata (spuntata, tolta, o caduta perché gli 11 sono
    /// cambiati) il telefono la ricorda per i promemoria locali e li rimette in programma, così vale subito; alla prossima lettura di
    /// Oggi decide il server (`serve_promemoria`, `ArchivioMessa`). Una semplice lettura della scelta non la tocca: lì vale il server.
    private func ricordaLaSpunta(_ f: Formazione, prima: Bool) {
        guard squadraVista == nil, spuntaValida != prima else { return }
        ArchivioMessa.ricorda(giornata: f.giornata, messa: spuntaValida, memoria)
        promemoria()
    }

    /// All'apertura, prima della copia della Formazione: la scelta tenuta sul telefono, finché il server non risponde. In campo
    /// subito la formazione salvata, mai la consigliata al suo posto; i comandi restano spenti (`sceltaLetta` è falso).
    private func riprendiSceltaDalTelefono() async {
        guard let salvato = await Cache.leggi(CopiaScelta.percorso, indirizzo: server.indirizzo),
              let c = CopiaScelta.da(salvato.dati), squadraVista == nil, giornata == nil else { return }
        giornata = c.giornata
        salvata = c.scelta
        sceltaNonValida = c.nonValida
        manuale = c.nonValida ? nil : c.titolari
        valutazione = c.valutazioneManuale
        sceltaInCopia = true
    }

    // MARK: formazione di un'altra squadra

    /// Mostra la formazione consigliata per un'altra squadra della lega (dalla sua rosa: «Formazione consigliata per loro»).
    func vediSquadra(_ nome: String) {
        squadraVista = nome
        moduloScelto = nil
        Task { await carica() }
    }

    func tornaAllaMia() {
        squadraVista = nil
        moduloScelto = nil
        Task { await carica() }
    }

    // MARK: scritture (salvataggio automatico)

    /// Un altro modulo dal menu. Per la tua formazione si salva subito (il consigliato toglie la scelta, come la web); per un'altra
    /// squadra si guarda e basta.
    func scegliModulo(_ modulo: String) async {
        guard let f = formazione, let l = livello(f), let scelto = l.moduli.first(where: { $0.modulo == modulo }) else { return }
        if squadraVista != nil {
            moduloScelto = scelto.modulo == consigliato(f)?.modulo ? nil : scelto.modulo
            return
        }
        guard puoScrivere, Set(scelto.titolari) != Set(vista(f).titolari.map(\.id)) else { return }
        Haptics.selezione()
        if scelto.modulo == consigliato(f)?.modulo {
            await tornaAllaConsigliata()
        } else {
            await salva(scelto.titolari)
        }
    }

    /// Un titolare esce e al suo posto entra un altro dello stesso ruolo (da «Sostituisci» o da una decisione in cima): si salva
    /// subito. false se il cambio non si può fare da qui (giornata chiusa, comandi spenti, giocatore fermo, già fatto).
    @discardableResult
    func sostituisciTitolare(_ esce: Int, con entra: Int) async -> Bool {
        guard let f = formazione, puoScrivere, !fermi.contains(esce), !fermi.contains(entra) else { return false }
        let titolari = vista(f).titolari.map(\.id)
        guard titolari.contains(esce), !titolari.contains(entra) else { return false }
        Haptics.selezione()
        await salva(titolari.map { $0 == esce ? entra : $0 })
        return true
    }

    /// La spunta «L'ho messa»: salva gli 11 in campo con `messa` (messa o tolta, la scelta salvata non si cancella da sola).
    func segnaMessa(_ messa: Bool) async {
        guard let f = formazione, puoScrivere, !salvataNonValida else { return }
        await salva(vista(f).titolari.map(\.id), messa: messa)
    }

    /// «Torna alla consigliata» (e «Usa la consigliata»): toglie la scelta salvata (`DELETE /api/scelta`), e da lì vale la
    /// consigliata. Per un'altra squadra rimette il modulo consigliato.
    func tornaAllaConsigliata() async {
        if squadraVista != nil {
            moduloScelto = nil
            return
        }
        guard let f = formazione, puoScrivere else { return }
        if await togliLaScelta(f) { await oggi?.rileggiDopoUnSalvataggio() }
    }

    /// `DELETE /api/scelta`, se c'è una scelta salvata. true se il server l'ha tolta e la risposta vale (allora si rilegge la giornata).
    private func togliLaScelta(_ f: Formazione) async -> Bool {
        nuovaModifica()
        let g = generazione
        let cera = salvata != nil
        occupato = true
        defer { occupato = false }
        do {
            if cera { try await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)") }
            riuscita()
            guard g == generazione else {
                await carica()
                return false
            }
            let spuntaPrima = spuntaValida
            dimentica()
            ricordaSulTelefono(f)
            ricordaLaSpunta(f, prima: spuntaPrima)
            Haptics.esito(riuscito: true)
            return cera
        } catch {
            await nonRiuscita(error, generazione: g)
            return false
        }
    }

    /// Salva questi 11 come tua scelta e poi rilegge la giornata, a comandi già riaccesi: i promemoria del telefono li decide il
    /// server (`OggiViewModel.rileggiDopoUnSalvataggio`), anche se la spunta che conosce il telefono non è cambiata (#710).
    private func salva(_ ids: [Int], messa: Bool? = nil) async {
        if await scrivi(ids, messa: messa) { await oggi?.rileggiDopoUnSalvataggio() }
    }

    /// Salva questi 11 come tua scelta (`salvaTitolari` della web). `messa`: la spunta; senza, il server la lascia com'era finché
    /// gli 11 sono gli stessi (la stessa regola qui, per la riga e la spunta). true se il server l'ha salvata e la risposta vale.
    private func scrivi(_ ids: [Int], messa: Bool?) async -> Bool {
        guard let f = formazione, puoScrivere else { return false }
        nuovaModifica()
        let g = generazione
        occupato = true
        defer { occupato = false }
        do {
            let corpo = RichiestaValutazione(titolari: ids, salva: true, giornata: f.giornata, messa: messa)
            let r: ValutazioneManuale = try await server.posta("POST", "/api/formazione/valuta", corpo)
            riuscita()
            // nel frattempo la schermata si è riletta: questa risposta non vale, si rilegge dal server (mai una scelta che non si vede)
            guard g == generazione else {
                await carica()
                return false
            }
            let stessi = salvata.map { Set($0.titolari) == Set(ids) } ?? false
            let eraConsigliata = Set(ids) == Set(consigliati(f)) || (stessi && salvata?.eraConsigliata == true)
            let messaOra = messa ?? (stessi && salvata?.messa == true)
            let spuntaPrima = spuntaValida
            ricorda(SceltaSalvata(titolari: ids, modulo: r.modulo, eraConsigliata: eraConsigliata ? true : nil, messa: messaOra ? true : nil),
                    nonValida: false, f, valutazione: r)
            ricordaLaSpunta(f, prima: spuntaPrima)
            Haptics.esito(riuscito: true)
            return true
        } catch {
            await nonRiuscita(error, generazione: g)
            return false
        }
    }

    /// Una scrittura non riuscita: 412 rilegge e lo dice (`cambiataAltrove`); 409 `formazione_chiusa` (la scadenza è passata con
    /// la schermata aperta) e 400 `giocatore_bloccato` (è cominciata una partita che la schermata non sapeva) dicono la frase del
    /// server e rileggono, come `rileggereDopo` della web (#978: prima dopo `giocatore_bloccato` restava spostabile chi gioca la
    /// partita cominciata); gli altri errori dicono il messaggio del server. Come `nonSalvata` della web (#667, #726): nella tua
    /// Formazione il motivo; lasciata la scheda, o guardando la formazione di un'altra squadra, una frase che nomina la formazione
    /// (lì «Non riesco a collegarmi» da solo sembrerebbe parlare d'altro). Le scritture sono una alla volta, quindi questa è sempre
    /// l'ultima partita da qui.
    private func nonRiuscita(_ error: Error, generazione g: Int) async {
        if let e = error as? ErroreApi, e.eConflitto {
            guasto = nil        // l'ultima scrittura è questa, e il suo seguito è la rilettura: un guasto di prima non vale più
            await cambiataAltrove()
            return
        }
        Haptics.esito(riuscito: false)
        if !inVista {
            avvisoAltrove = Self.testoNonSalvata(error)
            guasto = error
        } else {
            messaggio = testoQui(error)
        }
        if g != generazione {
            await carica()
        } else if case .codificato(let codice, _)? = error as? ErroreApi, Self.codiciDaRileggere.contains(codice) {
            await carica()
        }
    }

    /// Il codice del server per una scrittura arrivata dopo la scadenza (409).
    static let codiceChiusa = "formazione_chiusa"

    /// I rifiuti di una scrittura che dicono che i dati a video sono vecchi: dopo, la Formazione si rilegge.
    static let codiciDaRileggere: Set<String> = [codiceChiusa, codiceBloccato]

    /// L'avviso di una scrittura non riuscita nella Formazione: il motivo per la tua; guardando la formazione di un'altra squadra la
    /// frase che nomina la formazione, come la web.
    private func testoQui(_ error: Error) -> String {
        squadraVista == nil ? error.localizedDescription : Self.testoNonSalvata(error)
    }

    /// Una scrittura è riuscita (anche se la sua risposta arriva dopo una rilettura): il guasto di prima non vale più, nemmeno il
    /// suo avviso.
    private func riuscita() {
        guard guasto != nil else { return }
        guasto = nil
        messaggio = nil
    }

    /// Parte una nuova modifica: la frase di un 412 arrivato a scheda lasciata non vale più, nemmeno quella a schermo.
    private func nuovaModifica() {
        guard cambiataFuori else { return }
        cambiataFuori = false
        messaggio = nil
    }

    /// Tornando sulla Formazione dopo un 412 a scheda lasciata: nella tua la frase di sempre del 412 (quella che dice anche con la
    /// Formazione aperta, dopo la rilettura); guardando la formazione di un'altra squadra la frase della web (`comune.cambiato_altrove`).
    private var testoCambiataFuori: String {
        squadraVista == nil ? ErroreApi.conflitto.localizedDescription : Catalogo.Comune.cambiatoAltrove
    }

    /// La frase di una scrittura non riuscita fuori dalla tua Formazione: la rete solo se è lei il motivo (rete giù o server troppo
    /// lento, come `e.rete` della web), altrimenti il rifiuto del server, che chiede di controllare.
    static func testoNonSalvata(_ error: Error) -> String {
        DatiVecchi.eDiRete(error) ? Catalogo.Formazione.nonSalvataRete : Catalogo.Formazione.nonSalvata
    }

    /// 412: la scelta è stata cambiata su un altro dispositivo e la scrittura non è stata fatta. Nella tua Formazione si dice che si
    /// sta ricaricando, si rilegge tutto (formazione e scelta, con l'ETag nuovo) e, a dati riletti, si chiede di controllare e rifare
    /// la modifica. Lasciata la scheda, o guardando la formazione di un'altra squadra, come `cambiataAltrove` della web (#751): solo
    /// che i dati sono cambiati (`comune.cambiato_altrove`), sulle altre schede nell'avviso in basso (`avvisoAltrove`), per un'altra
    /// squadra sotto il campo. A scheda lasciata la tua formazione si rilegge subito: dopo il 412 il telefono ha già la versione
    /// nuova della scelta, e una scrittura partita dalla scelta vecchia passerebbe; così tornando c'è già quella giusta. Guardando
    /// un'altra squadra non si scrive niente, e la tua si rilegge tornandoci (`tornaAllaMia`). Tornando sulla Formazione dopo un 412
    /// a scheda lasciata compare la frase di sempre del 412 (`cambiataFuori`).
    private func cambiataAltrove() async {
        Haptics.esito(riuscito: false)
        if !inVista {
            avvisoAltrove = Catalogo.Comune.cambiatoAltrove
            cambiataFuori = true
            if squadraVista == nil { await carica() }
            return
        }
        if squadraVista != nil {
            messaggio = Catalogo.Comune.cambiatoAltrove
            return
        }
        messaggio = Catalogo.Comune.cambiatoRicarico
        if await carica() { messaggio = ErroreApi.conflitto.localizedDescription }
    }

    // MARK: testo da copiare

    /// La formazione in campo, scritta a parole per l'app della lega.
    func testo(_ f: Formazione) -> String {
        let v = vista(f)
        return TestoFormazione.crea(giornata: f.giornata, giornataLega: f.giornataLega, modulo: v.modulo, titolari: v.titolari,
                                    panchina: v.panchina)
    }

    /// «Copia per l'app della lega».
    func copiaTesto(_ f: Formazione) {
        UIPasteboard.general.string = testo(f)
        messaggio = Catalogo.Formazione.copiataLega
        Haptics.esito(riuscito: true)
    }

    // MARK: scheda del giocatore (come `stato.formaz` della web, #616)

    /// La scheda di un giocatore aperta da qui: la previsione già letta, il perché del titolare e cosa ci si può fare. nil se la
    /// Formazione non ha quel giocatore (allora la scheda aspetta il server).
    func contestoScheda(_ id: Int) -> ContestoScheda? {
        guard let f = formazione,
              let g = f.schede?[String(id)] ?? (f.titolari + f.panchina).first(where: { $0.id == id }) else { return nil }
        // a giornata in corso con lo stato vero della sua partita, come sul campo
        let previsione = dalVivo(f)?.giocatori.first { $0.id == id }.map { g.dalVivo($0) } ?? g
        return ContestoScheda(previsione: previsione, perche: percheTitolare(id), sostituibile: sostituibile(id),
                              entrabile: entrabile(id), fermo: fermo(id), pronta: puoScrivere)
    }

    /// La scheda già aperta da qui, letta adesso (`SchedaAperta` la ridisegna a ogni cambio della Formazione), come la web che a ogni
    /// ridisegno accende o spegne «Sostituisci» e «Metti in campo» nella scheda aperta: toccato un giocatore mentre arrivano i dati,
    /// i pulsanti ci sono spenti e si accendono all'arrivo (prima la scheda teneva la fotografia dell'apertura, e i pulsanti non
    /// comparivano più, collaudo del 26/11). Se la Formazione non ha più quel giocatore resta la previsione dell'apertura, senza
    /// pulsanti.
    func contestoAttuale(_ id: Int, aperta: ContestoScheda) -> ContestoScheda {
        contestoScheda(id) ?? ContestoScheda(previsione: aperta.previsione)
    }

    /// «Perché è titolare» (`PercheTitolare`): solo con la consigliata in campo e a formazione aperta, come la web.
    func percheTitolare(_ id: Int) -> String? {
        guard !chiusa, let f = formazione, let schede = f.schede, let consigliata = consigliato(f),
              Set(vista(f).titolari.map(\.id)) == Set(consigliata.titolari) else { return nil }
        return PercheTitolare.testo(consigliata, id: id, schede: schede)
    }

    /// La condizione sola di «Sostituisci» e di «Metti in campo», come `siSposta` della web (#643): la tua formazione, ancora
    /// aperta, e lui non gioca un anticipo già cominciato. I due pulsanti ci sono sempre insieme; con i comandi spenti (copia del
    /// telefono, scelta non letta, rilettura, scrittura in volo) ci sono ma spenti (`ContestoScheda.pronta`, `pronta()` della web).
    private func siSposta(_ id: Int) -> Bool {
        squadraVista == nil && !chiusa && !fermi.contains(id)
    }

    /// Un titolare della tua formazione ancora aperta: nella scheda «Sostituisci» (acceso quando i comandi sono accesi).
    func sostituibile(_ id: Int) -> Bool {
        siSposta(id) && inCampo(id)
    }

    /// Un giocatore della tua formazione che non è fra gli 11 in campo (panchina, non schierati, infortunati e squalificati), alle
    /// stesse condizioni di «Sostituisci»: nella scheda «Metti in campo» (#778).
    func entrabile(_ id: Int) -> Bool {
        guard siSposta(id), formazione?.schede?[String(id)] != nil else { return false }
        return !inCampo(id)
    }

    /// Chi gioca un anticipo già cominciato, nella tua formazione ancora aperta, titolare o no (`fermo` della web): nella scheda la
    /// frase di `formazione.bloccati` al posto del pulsante.
    func fermo(_ id: Int) -> Bool {
        squadraVista == nil && !chiusa && fermi.contains(id)
    }

    /// È fra gli 11 in campo.
    private func inCampo(_ id: Int) -> Bool {
        guard let f = formazione else { return false }
        return vista(f).titolari.contains { $0.id == id }
    }

    // MARK: «Sostituisci» (come `apriSostituzione` della web)

    /// «Sostituisci» nella scheda: il foglio della scheda si chiude e la scelta del sostituto parte quando è sparito.
    func chiediSostituzione(_ id: Int) {
        sostituzioneInAttesa = id
    }

    /// Chiamata quando il foglio della scheda è sparito: apre la scelta del sostituto chiesta con «Sostituisci», se quel titolare si
    /// può ancora sostituire. Se nel frattempo i comandi si sono spenti (è partita una rilettura) lo dice sotto il campo.
    func apriSostituzioneInAttesa() {
        guard let id = sostituzioneInAttesa else { return }
        sostituzioneInAttesa = nil
        guard sostituibile(id) else { return }
        if let motivo = motivoCambiSpenti {
            messaggio = motivo
            return
        }
        Task { await sostituisci(id) }
    }

    /// Apre l'elenco di «Sostituisci» per il titolare `id` («Carico…») e chiede al server chi può prendere il suo posto, con gli 11
    /// in campo (`POST /api/formazione/sostituisci`): i compagni dello stesso ruolo, ognuno con i punti attesi della formazione in più
    /// o in meno con lui al posto del titolare. Numeri e ordine sono del server (prima l'app scriveva la differenza fra i due
    /// giocatori, che non tornava con la formazione dopo il cambio); restano le righe di chi non è fra gli 11 e ha una scheda. Gli
    /// errori come «Metti in campo»: `giocatore_bloccato` è un'informazione al posto dell'elenco, `formazione_chiusa` chiude l'elenco,
    /// lo dice e rilegge, un altro errore va nell'elenco. Una risposta arrivata a elenco chiuso o sostituito non lo tocca; se nel
    /// frattempo gli 11 in campo sono cambiati, l'elenco si chiude (direbbe di un'altra formazione).
    func sostituisci(_ id: Int) async {
        guard let f = formazione, sostituibile(id), puoScrivere, let uscente = f.schede?[String(id)] else { return }
        numeroElenco += 1
        let numero = numeroElenco
        let titolari = vista(f).titolari.map(\.id)
        elencoSostituti = ElencoSostituti(id: numero, uscente: uscente, titolari: titolari)
        do {
            let r: RispostaSostituisci = try await server.posta("POST", "/api/formazione/sostituisci",
                                                               RichiestaSostituisci(esce: id, titolari: titolari, giornata: f.giornata))
            guard elencoSostituti?.id == numero else { return }
            guard let ora = formazione, squadraVista == nil, !chiusa, Set(vista(ora).titolari.map(\.id)) == Set(titolari) else {
                elencoSostituti = nil
                return
            }
            let schede = ora.schede ?? [:]
            // il posto di chi entra nella formazione in campo («Panchina 2», «Non schierato»), come la web
            let panchina = vista(ora).panchina.map(\.id)
            let righe: [ElencoSostituti.Riga] = (r.entrate ?? []).compactMap { e in
                guard let entra = e.entra, !titolari.contains(entra), let g = schede[String(entra)] else { return nil }
                let posto = PostoInFormazione.testo(entra, titolari: titolari, panchina: panchina, inRosa: true)
                return ElencoSostituti.Riga(entra: g, differenza: e.differenza, posto: posto)
            }
            elencoSostituti?.stato = .entrate(righe)
        } catch {
            guard elencoSostituti?.id == numero else { return }
            if Task.isCancelled || error is CancellationError {
                elencoSostituti = nil
                return
            }
            if case .codificato(let codice, _)? = error as? ErroreApi {
                if codice == Self.codiceChiusa {
                    elencoSostituti = nil
                    messaggio = testoQui(error)
                    await carica()
                    return
                }
                if codice == Self.codiceBloccato {
                    elencoSostituti?.stato = .informazione(error.localizedDescription)
                    return
                }
            }
            elencoSostituti?.stato = .errore(error.localizedDescription)
        }
    }

    /// Un tocco su una riga dell'elenco: l'elenco si chiude e chi entra prende il posto del titolare (`sostituisciTitolare`: si salva
    /// subito, al 412 si rilegge e lo si dice). false se il cambio non si può più fare da qui: allora lo si dice sotto il campo
    /// (`cambioNonPartito`).
    @discardableResult
    func scegliSostituto(_ entra: Int) async -> Bool {
        guard let esce = elencoSostituti?.uscente.id else { return false }
        elencoSostituti = nil
        if await sostituisciTitolare(esce, con: entra) { return true }
        cambioNonPartito(esce: esce, entra: entra)
        return false
    }

    /// Un cambio scelto in un elenco non è partito: sotto il campo il perché, mai un elenco che si chiude senza niente (collaudo del
    /// 26/11). La formazione chiusa, la rilettura, la copia del telefono o la scelta non letta (`motivoCambiSpenti`), oppure uno dei
    /// due gioca ora una partita già cominciata (`formazione.bloccati`). Con gli 11 cambiati da una rilettura l'elenco si è già
    /// chiuso da solo (`chiudiElenchiSuperati`).
    private func cambioNonPartito(esce: Int, entra: Int) {
        if let motivo = motivoCambiSpenti {
            messaggio = motivo
        } else if fermi.contains(esce) || fermi.contains(entra) {
            messaggio = Catalogo.Formazione.bloccati
        }
    }

    /// Dopo una rilettura gli 11 in campo non sono più quelli da cui è partito l'elenco aperto di «Sostituisci» o di «Metti in
    /// campo»: l'elenco si chiude, come `chiudiSostituzione` della web, perché i suoi numeri e i suoi giocatori erano di un'altra
    /// formazione (revisione della #946). Con gli stessi 11 resta aperto (le righe si riaccendono a rilettura finita).
    private func chiudiElenchiSuperati() {
        let ora = formazione.map { Set(vista($0).titolari.map(\.id)) }
        if let e = elencoSostituti, Set(e.titolari) != ora { elencoSostituti = nil }
        if let e = elencoEntra, Set(e.titolari) != ora { elencoEntra = nil }
    }

    // MARK: «Metti in campo» (#778, come `apriMettiInCampo` della web)

    /// Il codice del server per chi gioca una partita già cominciata (400).
    static let codiceBloccato = "giocatore_bloccato"

    /// «Metti in campo» nella scheda: il foglio della scheda si chiude e l'elenco parte quando è sparito.
    func chiediMettiInCampo(_ id: Int) {
        mettiInCampoInAttesa = id
    }

    /// Chiamata quando il foglio della scheda è sparito: apre l'elenco chiesto con «Metti in campo», se quel giocatore si può
    /// ancora mettere in campo. Se nel frattempo i comandi si sono spenti (è partita una rilettura) lo dice sotto il campo.
    func apriMettiInCampoInAttesa() {
        guard let id = mettiInCampoInAttesa else { return }
        mettiInCampoInAttesa = nil
        guard entrabile(id) else { return }
        if let motivo = motivoCambiSpenti {
            messaggio = motivo
            return
        }
        Task { await mettiInCampo(id) }
    }

    /// Apre l'elenco di «Metti in campo» per `id` («Carico…») e chiede al server chi può lasciargli il posto, con gli 11 in campo
    /// (`POST /api/formazione/metti-in-campo`). Numeri e ordine sono del server; restano le righe dei titolari ancora in campo.
    /// `giocatore_bloccato` (la sua partita è cominciata e la schermata non lo sapeva): la frase del server al posto dell'elenco,
    /// come informazione. `formazione_chiusa` (la scadenza è passata con la schermata aperta): l'elenco si chiude, si dice il motivo
    /// e si rilegge. Un altro errore: il motivo nell'elenco. Se l'elenco si chiude, o se ne apre un altro, prima della risposta, la
    /// risposta non lo tocca; se nel frattempo gli 11 in campo sono cambiati, l'elenco si chiude (direbbe di un'altra formazione).
    func mettiInCampo(_ id: Int) async {
        guard let f = formazione, entrabile(id), puoScrivere, let entra = f.schede?[String(id)] else { return }
        numeroElenco += 1
        let numero = numeroElenco
        let titolari = vista(f).titolari.map(\.id)
        elencoEntra = ElencoMettiInCampo(id: numero, entra: entra, titolari: titolari)
        do {
            let r: RispostaMettiInCampo = try await server.posta("POST", "/api/formazione/metti-in-campo",
                                                                RichiestaMettiInCampo(entra: id, titolari: titolari, giornata: f.giornata))
            guard elencoEntra?.id == numero else { return }
            guard let ora = formazione, squadraVista == nil, !chiusa, Set(vista(ora).titolari.map(\.id)) == Set(titolari) else {
                elencoEntra = nil
                return
            }
            let schede = ora.schede ?? [:]
            let righe: [ElencoMettiInCampo.Riga] = (r.uscite ?? []).compactMap { u in
                guard let esce = u.esce, titolari.contains(esce), let g = schede[String(esce)] else { return nil }
                return ElencoMettiInCampo.Riga(esce: g, modulo: u.modulo, cambiaModulo: u.cambiaModulo == true, differenza: u.differenza)
            }
            elencoEntra?.stato = .uscite(righe)
        } catch {
            guard elencoEntra?.id == numero else { return }
            if Task.isCancelled || error is CancellationError {
                elencoEntra = nil
                return
            }
            if case .codificato(let codice, _)? = error as? ErroreApi {
                if codice == Self.codiceChiusa {
                    elencoEntra = nil
                    messaggio = testoQui(error)
                    await carica()
                    return
                }
                if codice == Self.codiceBloccato {
                    elencoEntra?.stato = .informazione(error.localizedDescription)
                    return
                }
            }
            elencoEntra?.stato = .errore(error.localizedDescription)
        }
    }

    /// Un tocco su una riga dell'elenco: l'elenco si chiude e quel titolare lascia il posto a chi entra, per la stessa strada di
    /// «Sostituisci» (`sostituisciTitolare`: si salva subito, al 412 si rilegge e lo si dice). false se il cambio non si può più
    /// fare da qui (lui non è più fuori, quel titolare non è più in campo, la giornata si è chiusa): allora lo si dice sotto il campo.
    @discardableResult
    func scegliChiEsce(_ esce: Int) async -> Bool {
        guard let entra = elencoEntra?.entra.id else { return false }
        elencoEntra = nil
        if await sostituisciTitolare(esce, con: entra) { return true }
        cambioNonPartito(esce: esce, entra: entra)
        return false
    }
}
