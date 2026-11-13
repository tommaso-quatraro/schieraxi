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
    /// Nome di un'altra squadra della lega, se se ne sta guardando la formazione consigliata (nil = la mia).
    @Published private(set) var squadraVista: String?
    /// Un altro modulo guardato nella formazione di un'altra squadra: solo sullo schermo, non si salva niente.
    @Published private(set) var moduloScelto: String?
    /// Il titolare di cui si sceglie il sostituto (da «Sostituisci» nella scheda del giocatore).
    @Published var daSostituire: Giocatore?
    /// «Sostituisci» toccato nella scheda: la scelta del sostituto si apre quando il foglio della scheda è sparito.
    private var sostituzioneInAttesa: Int?

    /// La scelta della giornata è stata letta dal server (anche «nessuna»): finché no, non si può cambiare niente.
    @Published private(set) var sceltaLetta = false
    /// Scelta, 11 in campo e valutazione vengono dalla copia del telefono (`CopiaScelta`), non ancora dal server: si mostrano finché
    /// si vede la copia della Formazione o si sta rileggendo, ma non si scrive niente (`sceltaLetta` resta falso).
    @Published private(set) var sceltaInCopia = false
    /// La scelta salvata (nil = nessuna, vale la consigliata).
    @Published private(set) var salvata: SceltaSalvata?
    /// La scelta salvata non si può più schierare (lo dice il server): in campo la consigliata, finché non la cambi.
    @Published private(set) var salvataNonValida = false
    /// Gli 11 in campo quando non sono quelli della consigliata (la tua scelta salvata); nil = la consigliata.
    @Published private(set) var manuale: [Int]?
    /// La valutazione del server per `manuale`, quando quegli 11 non sono un modulo già calcolato.
    @Published private(set) var valutazione: ValutazioneManuale?
    /// Una scrittura è partita e il server non ha ancora risposto: una alla volta, gli altri comandi aspettano.
    @Published private(set) var occupato = false
    /// Formazione e scelta si stanno rileggendo: i comandi aspettano i dati nuovi.
    @Published private(set) var leggendo = false

    /// La giornata della scelta letta: se cambia si riparte da zero.
    private var giornata: Int?
    /// Cresce a ogni rilettura: una risposta (lettura o scrittura) partita prima non vale più.
    private var generazione = 0

    init(server: any ServerClient, oggi: OggiViewModel? = nil) {
        self.server = server
        self.oggi = oggi
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
        return StatoScelta.calcola(mia: squadraVista == nil, letta: sceltaNota, copia: copia || leggendo, chiusa: chiusa, salvata: salvata,
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
    /// due, con il suo motivo (nil = server non raggiungibile).
    var striscia: (data: Date, motivo: String?)? {
        var vecchi: [(data: Date, motivo: String?)] = []
        if let d = caricatore.datiSalvati { vecchi.append((d, caricatore.motivoDatiSalvati)) }
        if squadraVista == nil, let o = oggi, let d = o.datiSalvati { vecchi.append((d, o.caricatore.motivoDatiSalvati)) }
        return vecchi.min { $0.data < $1.data }
    }

    /// L'errore di `/api/oggi` quando non c'è nemmeno una copia da mostrare: mancano testa e decisioni, e lo si dice.
    var erroreGiornata: String? {
        guard squadraVista == nil, let o = oggi, o.oggi == nil else { return nil }
        return o.errore
    }

    /// La spunta «L'ho messa»: vale per gli 11 salvati.
    var messa: Bool { salvata?.messa == true }

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

    /// I moduli del menu: quelli del livello equilibrato e, se gli 11 in campo non sono uno di loro, anche il loro.
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
                                   punti: valutazione?.punteggioAtteso)
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
        let pagina = Decisioni.Pagina(titolari: titolari, chiusa: chiusa, conScelta: salvata != nil,
                                      diversi: titolari.filter { !dentro.contains($0) }.count, tecniche: tecniche)
        return Decisioni.prime(oggi.daFare ?? [], pagina: pagina)
    }

    /// «+0,9 punti attesi.» accanto al cambio proposto.
    func guadagno(_ v: DaFareVoce) -> String? {
        Decisioni.guadagno(v, puntiTitolare: v.giocatore.flatMap { formazione?.schede?[String($0.id)]?.puntiAttesi })
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
        defer { if g == generazione { leggendo = false } }
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
        if nonValida || Set(s.titolari) == Set(consigliati(f)) || moduloDi(f, s.titolari) != nil {
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
        salvataNonValida = nonValida
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
        salvataNonValida = false
        manuale = nil
        valutazione = nil
        sceltaInCopia = false
    }

    // MARK: la scelta sul telefono

    /// Tiene sul telefono la scelta appena letta o salvata, accanto alla copia della Formazione (`CopiaScelta`).
    private func ricordaSulTelefono(_ f: Formazione) {
        guard squadraVista == nil,
              let dati = CopiaScelta(giornata: f.giornata, scelta: salvata, nonValida: salvataNonValida, valutazione: valutazione).dati
        else { return }
        Cache.salva(dati, CopiaScelta.percorso, indirizzo: server.indirizzo)
    }

    /// All'apertura, prima della copia della Formazione: la scelta tenuta sul telefono, finché il server non risponde. In campo
    /// subito la formazione salvata, mai la consigliata al suo posto; i comandi restano spenti (`sceltaLetta` è falso).
    private func riprendiSceltaDalTelefono() async {
        guard let salvato = await Cache.leggi(CopiaScelta.percorso, indirizzo: server.indirizzo),
              let c = CopiaScelta.da(salvato.dati), squadraVista == nil, giornata == nil else { return }
        giornata = c.giornata
        salvata = c.scelta
        salvataNonValida = c.nonValida
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
        let g = generazione
        occupato = true
        defer { occupato = false }
        do {
            if salvata != nil { try await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)") }
            guard g == generazione else {
                await carica()
                return
            }
            dimentica()
            ricordaSulTelefono(f)
            Haptics.esito(riuscito: true)
        } catch {
            await nonRiuscita(error, generazione: g)
        }
    }

    /// Salva questi 11 come tua scelta (`salvaTitolari` della web). `messa`: la spunta; senza, il server la lascia com'era finché
    /// gli 11 sono gli stessi (la stessa regola qui, per la riga e la spunta).
    private func salva(_ ids: [Int], messa: Bool? = nil) async {
        guard let f = formazione, puoScrivere else { return }
        let g = generazione
        occupato = true
        defer { occupato = false }
        do {
            let corpo = RichiestaValutazione(titolari: ids, salva: true, giornata: f.giornata, messa: messa)
            let r: ValutazioneManuale = try await server.posta("POST", "/api/formazione/valuta", corpo)
            // nel frattempo la schermata si è riletta: questa risposta non vale, si rilegge dal server (mai una scelta che non si vede)
            guard g == generazione else {
                await carica()
                return
            }
            let stessi = salvata.map { Set($0.titolari) == Set(ids) } ?? false
            let eraConsigliata = Set(ids) == Set(consigliati(f)) || (stessi && salvata?.eraConsigliata == true)
            let messaOra = messa ?? (stessi && salvata?.messa == true)
            ricorda(SceltaSalvata(titolari: ids, modulo: r.modulo, eraConsigliata: eraConsigliata ? true : nil, messa: messaOra ? true : nil),
                    nonValida: false, f, valutazione: r)
            Haptics.esito(riuscito: true)
        } catch {
            await nonRiuscita(error, generazione: g)
        }
    }

    /// Una scrittura non riuscita: 412 rilegge e lo dice (`comune.cambiato_ricarico`); 409 `formazione_chiusa` rilegge (la scadenza
    /// è passata con la schermata aperta); gli altri errori (per esempio 400 `giocatore_bloccato`) dicono il messaggio del server.
    private func nonRiuscita(_ error: Error, generazione g: Int) async {
        if let e = error as? ErroreApi, e.eConflitto {
            await cambiataAltrove()
            return
        }
        Haptics.esito(riuscito: false)
        messaggio = error.localizedDescription
        if g != generazione {
            await carica()
        } else if case .codificato(let codice, _)? = error as? ErroreApi, codice == Self.codiceChiusa {
            await carica()
        }
    }

    /// Il codice del server per una scrittura arrivata dopo la scadenza (409).
    static let codiceChiusa = "formazione_chiusa"

    /// 412: la scelta è stata cambiata su un altro dispositivo e la scrittura non è stata fatta. Si dice che si sta ricaricando, si
    /// rilegge tutto (formazione e scelta, con l'ETag nuovo) e, a dati riletti, si chiede di controllare e rifare la modifica.
    private func cambiataAltrove() async {
        Haptics.esito(riuscito: false)
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
        return ContestoScheda(previsione: previsione, perche: percheTitolare(id), sostituibile: sostituibile(id), fermo: fermo(id))
    }

    /// «Perché è titolare» (`PercheTitolare`): solo con la consigliata in campo e a formazione aperta, come la web.
    func percheTitolare(_ id: Int) -> String? {
        guard !chiusa, let f = formazione, let schede = f.schede, let consigliata = consigliato(f),
              Set(vista(f).titolari.map(\.id)) == Set(consigliata.titolari) else { return nil }
        return PercheTitolare.testo(consigliata, id: id, schede: schede)
    }

    /// Un titolare della tua formazione ancora aperta, con i comandi accesi: nella scheda «Sostituisci».
    func sostituibile(_ id: Int) -> Bool {
        titolareTuo(id) && !fermi.contains(id) && !comandiSpenti
    }

    /// Un titolare della tua formazione che gioca un anticipo già cominciato: nella scheda la frase di `formazione.bloccati`.
    func fermo(_ id: Int) -> Bool {
        titolareTuo(id) && fermi.contains(id)
    }

    private func titolareTuo(_ id: Int) -> Bool {
        guard squadraVista == nil, !chiusa, let f = formazione else { return false }
        return vista(f).titolari.contains { $0.id == id }
    }

    /// Chi può prendere il posto di `uscente`, come `sostituti` della web: stesso ruolo, non già titolare e non fermo, il migliore
    /// per punti attesi in cima. Nessuno se `uscente` stesso è fermo.
    func sostituti(di uscente: Giocatore, _ f: Formazione) -> [Giocatore] {
        let fermi = Set(f.bloccati ?? [])
        guard !fermi.contains(uscente.id) else { return [] }
        let titolari = Set(vista(f).titolari.map(\.id))
        return (f.schede ?? [:]).values
            .filter { $0.ruolo == uscente.ruolo && !titolari.contains($0.id) && !fermi.contains($0.id) }
            .sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
    }

    /// «Sostituisci» nella scheda: il foglio della scheda si chiude e la scelta del sostituto parte quando è sparito.
    func chiediSostituzione(_ id: Int) {
        sostituzioneInAttesa = id
    }

    /// Chiamata quando il foglio della scheda è sparito: apre la scelta del sostituto chiesta con «Sostituisci», se quel titolare si
    /// può ancora sostituire.
    func apriSostituzioneInAttesa() {
        guard let id = sostituzioneInAttesa else { return }
        sostituzioneInAttesa = nil
        guard sostituibile(id), let g = formazione?.schede?[String(id)] else { return }
        daSostituire = g
    }
}
