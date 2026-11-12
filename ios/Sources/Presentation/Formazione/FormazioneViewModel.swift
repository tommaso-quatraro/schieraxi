import SwiftUI

/// I giocatori da mostrare in questo momento (consigliata, un altro modulo, oppure modifica a mano).
struct VistaFormazione {
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let modulo: String
    /// nil in modifica a mano finché il server non ha calcolato quella formazione (o se il calcolo non è riuscito):
    /// al suo posto si mostra «Calcolo…», mai i punti della consigliata.
    let punti: Double?
}

/// Una riga della nota sotto il campo (#356): il nome del titolare e il perché della scelta, con le parole del server.
struct RigaScelta: Identifiable, Equatable {
    /// L'id del titolare.
    let id: Int
    let nome: String
    let testo: String
    /// Come la scrive la web («Nome · riga») e come la legge VoiceOver.
    var voce: String { nome + " · " + testo }
}

/// Logica della schermata Formazione: modulo, modifica a mano, salvataggio della scelta, formazione di un'altra squadra.
/// Vive nell'`AppModel`, quindi cambiando sezione (barra laterale dell'iPad) la modifica a mano non si perde.
@MainActor
final class FormazioneViewModel: ViewModelBase {
    let caricatore: Caricatore<Formazione>
    let server: any ServerClient

    @Published var moduloScelto: String?
    /// Id dei titolari scelti a mano; nil = si usa la formazione consigliata.
    @Published var manuale: [Int]?
    @Published var valutazione: ValutazioneManuale?
    @Published var messaggio: String?
    /// Nome di un'altra squadra della lega, se se ne sta guardando la formazione consigliata (nil = la mia).
    @Published var squadraVista: String?
    /// Il titolare di cui si sceglie il sostituto (foglio della sostituzione): da «Sostituisci» nella scheda del giocatore o,
    /// in modifica a mano, dal tocco sulla riga.
    @Published var daSostituire: Giocatore?
    /// «Sostituisci» toccato nella scheda: la scelta del sostituto si apre quando il foglio della scheda è sparito.
    private var sostituzioneInAttesa: Int?

    /// La scelta della giornata è stata letta dal server (anche «nessuna»): solo allora la riga di stato dice qualcosa.
    @Published private(set) var sceltaLetta = false
    /// I titolari salvati sul server per questa giornata (nil = nessuna scelta salvata) e quando.
    @Published private(set) var salvati: [Int]?
    @Published private(set) var salvataIl: Date?
    /// La scelta salvata non vale più (rosa o regole cambiate): come sulla web non si cancella da sola, lo dice la riga di stato
    /// e si vede la consigliata finché non la rifai o torni alla consigliata.
    @Published private(set) var salvataNonValida = false
    /// Il server sta provando la scelta salvata appena letta: finché non risponde la riga non dice niente (come la web).
    @Published private(set) var provaSalvata = false
    /// Un salvataggio è partito e il server non ha ancora risposto: un secondo tocco su Salva (o ⌘S) non ne manda un altro, come
    /// `sc.occupato` della web. Finché dura, i pulsanti di salvataggio e «Annulla modifiche» sono spenti; «Torna alla consigliata»
    /// e i moduli restano attivi, come sulla web (`StatoScelta.Pulsante.spentoSalvando`, #477).
    @Published private(set) var salvataggioInCorso = false
    /// Il calcolo della modifica a mano non è riuscito: invece dei punti, «Non riesco a calcolare» con «Riprova».
    @Published private(set) var calcoloNonRiuscito = false
    /// I titolari a cui si riferisce `valutazione` (dopo una sostituzione la valutazione vecchia non vale più).
    private var valutati: [Int]?
    /// Il codice dell'ultimo errore di `valuta` (campo `codice` del server), se c'era.
    private var codiceUltimoErrore: String?

    /// Hai toccato tu un modulo (fuori dalla modifica a mano). Solo allora, rileggendo la scelta, quello che guardi resta
    /// e la scelta salvata non lo copre. Si azzera con tutto ciò che riparte da capo (`azzeraManuale`: «Torna alla consigliata»,
    /// un'altra squadra e ritorno, scelta cambiata da un altro dispositivo).
    private var moduloToccato = false

    /// Giornata a cui si riferisce la modifica a mano: se cambia, si riparte da zero.
    private var giornata: Int?
    /// Numera le valutazioni inviate: una risposta arrivata in ritardo (fuori ordine) viene ignorata.
    private var contatore = 0

    /// A che punto è la tua scelta (riga di stato della Formazione). Per le altre squadre non si dice niente.
    var statoScelta: StatoScelta {
        guard squadraVista == nil else { return .sconosciuto }
        return StatoScelta.calcola(letta: sceltaLetta && !provaSalvata, salvati: salvati, salvataIl: salvataIl, manuale: manuale,
                                   mostrati: titolariMostrati, chiusa: chiusa,
                                   nonValida: salvataNonValida || sceltaNonValidaPerIlServer, altra: altraDallaConsigliata)
    }

    /// Senza modifica a mano, gli undici del modulo sullo schermo: con una scelta salvata dicono se è ancora lei
    /// («salvata») o se hai toccato un altro modulo («Modifiche non salvate»), come la web.
    private var titolariMostrati: [Int]? {
        guard manuale == nil, let f = formazione else { return nil }
        return vista(f).titolari.map(\.id)
    }

    /// Senza modifica a mano hai toccato un modulo diverso dalla scelta salvata, che vale ancora: è una modifica di
    /// questo telefono. Rileggendo la scelta (ritorno sulla Formazione, tira per aggiornare) non si copre con quella salvata.
    /// Conta solo un tocco vero (`moduloToccato`): dopo un 412, «Torna alla consigliata» o il ritorno da un'altra squadra sullo
    /// schermo c'è la consigliata, ma la scelta salvata va rimessa in campo.
    private var modificaSenzaMano: Bool {
        guard moduloToccato, manuale == nil, let salvati, !salvataNonValida, let mostrati = titolariMostrati else { return false }
        return Set(mostrati) != Set(salvati)
    }

    /// A giornata chiusa il server dice se la tua scelta salvata si può schierare (`stato_scelta`, facoltativo: un server vecchio
    /// non lo manda). Come la web, conta solo a giornata chiusa: prima la scelta può cambiare e il campo sarebbe vecchio.
    var sceltaNonValidaPerIlServer: Bool { chiusa && formazione?.statoScelta == "non_valida" }

    /// Lo stile «Equilibrata» del server (`rischio` 0): dal 12/11/2026 è l'unico, come sulla web (#634).
    static let rischioEquilibrato = 0

    /// Il livello da cui vengono moduli e titolari: quello equilibrato. Gli altri livelli di `livelli` restano nella risposta del
    /// server e non si mostrano; se manca quello equilibrato vale il primo. Nil con un server che non manda `livelli`.
    func livello(_ f: Formazione) -> LivelloRischio? {
        guard let livelli = f.livelli else { return nil }
        return livelli.first(where: { $0.rischio == Self.rischioEquilibrato }) ?? livelli.first
    }

    /// Senza modifica a mano si vede un altro modulo, non la consigliata (come `altra` della web).
    var altraDallaConsigliata: Bool {
        guard manuale == nil, let f = formazione, let livello = self.livello(f) else { return false }
        let modulo = (livello.moduli.first(where: { $0.modulo == (moduloScelto ?? livello.modulo) }) ?? livello.moduli.first)?.modulo
        return modulo.map { $0 != livello.modulo } ?? false
    }

    /// La giornata è chiusa (dopo la scadenza, `iniziata` del server): la tua formazione si vede in sola lettura, niente modifiche.
    var chiusa: Bool { formazione?.iniziata == true }

    /// La frase della web per la formazione chiusa di un'altra squadra (`formazione.chiusa`).
    static let testoChiusa = Catalogo.Formazione.chiusa
    /// La fascia sopra la formazione a giornata chiusa, come la web: solo dove non c'è la riga di stato della scelta (un'altra
    /// squadra). Per la tua squadra lo dice già la riga di stato («Giornata iniziata: la formazione è chiusa»): niente seconda frase.
    var fasciaChiusa: String? { chiusa && statoScelta == .sconosciuto ? Self.testoChiusa : nil }
    /// Salvataggio rifiutato perché la scadenza è passata con la pagina aperta: la frase della web (`err.formazione_chiusa`).
    static let testoChiusaAlSalvataggio = "La giornata è già iniziata: la formazione non si può più cambiare."
    /// Il codice del server per una scrittura arrivata dopo la scadenza (409).
    static let codiceChiusa = "formazione_chiusa"

    /// In modifica a mano, il server sta calcolando i punti di questa formazione.
    var inCalcolo: Bool { manuale != nil && valutati != manuale && !calcoloNonRiuscito }

    /// Anticipi già cominciati (#373, campo `bloccati` del server): chi gioca una partita già cominciata non si sposta più. Vuoto
    /// senza anticipi cominciati e con un server vecchio; il server rifiuta comunque un salvataggio che ne sposta uno.
    var fermi: Set<Int> { Set(formazione?.bloccati ?? []) }
    /// La frase della web sotto i titolari in modifica a mano (`formazione.bloccati`), solo se qualcuno è fermo.
    static let testoFermi = Catalogo.Formazione.bloccati
    var notaFermi: String? { manuale != nil && !chiusa && !fermi.isEmpty ? Self.testoFermi : nil }

    /// Chi può prendere il posto di `uscente` nella modifica a mano, come `sostituti` della web: stesso ruolo, non già titolare e non
    /// fermo, il migliore per punti attesi in cima. Nessuno se `uscente` stesso è fermo.
    /// Fuori dalla modifica a mano (dalla scheda del giocatore) i titolari sono gli undici sullo schermo.
    func sostituti(di uscente: Giocatore, _ f: Formazione) -> [Giocatore] {
        let fermi = Set(f.bloccati ?? [])
        guard !fermi.contains(uscente.id) else { return [] }
        let titolari = Set(manuale ?? vista(f).titolari.map(\.id))
        return (f.schede ?? [:]).values
            .filter { $0.ruolo == uscente.ruolo && !titolari.contains($0.id) && !fermi.contains($0.id) }
            .sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
    }

    init(server: any ServerClient) {
        self.server = server
        caricatore = Caricatore<Formazione>("/api/formazione", server: server)
        super.init()
        osserva(caricatore)
    }

    var formazione: Formazione? { caricatore.dato }
    var errore: String? { caricatore.errore }
    var datiSalvati: Date? { caricatore.datiSalvati }

    // MARK: caricamento

    /// L'indirizzo della formazione che si sta guardando.
    var percorso: String {
        if let s = squadraVista { return "/api/formazione?squadra=\(IndirizzoServer.codifica(s))" }
        return "/api/formazione"
    }

    func carica() async {
        await ricaricaConScelta()
    }

    /// Rilegge la formazione e, per la tua squadra, la scelta della giornata. true se il server ha dato la scelta (anche
    /// «nessuna»): solo allora lo stato della scelta è quello del server.
    @discardableResult
    private func ricaricaConScelta() async -> Bool {
        await caricatore.ricarica(percorso)
        guard let f = caricatore.dato else { return false }
        return await caricaScelta(f)
    }

    /// Legge dal server la scelta salvata per questa giornata (solo per la propria squadra): tiene lo stato «salvata» e, se non
    /// c'è una modifica in corso, riparte da lì. Se la lettura non riesce lo stato resta com'era (all'inizio: non si sa).
    /// true se il server ha dato la scelta (anche «nessuna»).
    private func caricaScelta(_ f: Formazione) async -> Bool {
        // Un'altra giornata: la modifica a mano e la scelta della vecchia non valgono più.
        if giornata != f.giornata {
            azzeraManuale()
            sceltaLetta = false
            salvati = nil
            salvataIl = nil
            salvataNonValida = false
            giornata = f.giornata
        }
        guard squadraVista == nil else { return false }
        let salvata: SceltaSalvata?
        do {
            salvata = try await server.get("/api/scelta?giornata=\(f.giornata)")
        } catch {
            return false
        }
        guard squadraVista == nil, giornata == f.giornata else { return false }
        // Nessuna modifica di questo telefono: la formazione mostrata è quella salvata di prima (o la consigliata).
        // A giornata chiusa le modifiche non salvate di questo telefono non contano più: vale quella salvata (o la consigliata).
        let senzaModifiche = f.iniziata == true || (manuale == nil && !modificaSenzaMano)
            || salvati.map { Set($0) == Set(manuale ?? []) } == true
        sceltaLetta = true
        guard let salvata else {
            salvati = nil
            salvataIl = nil
            salvataNonValida = false
            if senzaModifiche { azzeraManuale() }   // cancellata da un altro dispositivo: si torna alla consigliata
            return true
        }
        // Già giudicata non valida (anche dal server) e intanto non è cambiata: resta così senza riprovarla, come la web che
        // tiene `nonValida` per la giornata. Altrimenti a ogni ritorno sulla Formazione tornerebbe in campo con errore e vibrazione.
        let stessa = salvati.map { Set($0) == Set(salvata.titolari) } == true && salvataIl == Quando.data(salvata.salvata)
        let giaNonValida = salvataNonValida && stessa
        salvati = salvata.titolari
        salvataIl = Quando.data(salvata.salvata)
        // Una scelta che non vale più (fuori dalla rosa) NON si cancella da sola, come sulla web: lo dice la riga di stato e si
        // vede la consigliata. Solo se la rosa c'è davvero: senza rosa non si giudica (decide il server, sotto).
        // A giornata chiusa con `stato_scelta: "non_valida"` lo sa già il server: si vede la consigliata, senza riprovarla.
        salvataNonValida = giaNonValida || (f.iniziata == true && f.statoScelta == "non_valida")
            || ValiditaScelta.controlla(titolari: salvata.titolari, rosa: f.schede) == .nonValida
        guard senzaModifiche else { return true }   // c'è una modifica in corso: non si sovrascrive (la riga dice «Modifiche non salvate»)
        if salvataNonValida {
            if manuale != nil { azzeraManuale() }
            return true
        }
        if manuale.map({ Set($0) == Set(salvata.titolari) }) == true, valutati == manuale { return true }   // già lei, già calcolata
        manuale = salvata.titolari
        // Mentre il server la prova la riga non dice niente (come la web, che la mostra solo dopo): niente «salvata» per un
        // attimo se poi non vale.
        provaSalvata = true
        await valuta(salva: false, silenzioso: true)
        provaSalvata = false
        // Il server dice che non si può valutare (il codice, non il testo): non vale più. Si vede la consigliata, senza il testo
        // dell'errore (lo dice la riga di stato).
        if codiceUltimoErrore == ValiditaScelta.codiceNonValida, manuale == salvata.titolari {
            salvataNonValida = true
            azzeraManuale()
        }
        return true
    }

    private func azzeraManuale() {
        manuale = nil
        moduloToccato = false
        valutazione = nil
        valutati = nil
        calcoloNonRiuscito = false
        codiceUltimoErrore = nil
        messaggio = nil
        contatore += 1
    }

    // MARK: formazione di un'altra squadra

    /// Mostra la formazione consigliata per un'altra squadra della lega (dalla sua rosa: «Formazione consigliata per loro»).
    func vediSquadra(_ nome: String) {
        squadraVista = nome
        moduloScelto = nil
        azzeraManuale()
        Task { await carica() }
    }

    func tornaAllaMia() {
        squadraVista = nil
        moduloScelto = nil
        azzeraManuale()
        Task { await carica() }
    }

    // MARK: cosa mostrare

    /// Titolari, panchina, modulo e punteggio secondo la modalità (a mano, o il modulo scelto).
    func vista(_ f: Formazione) -> VistaFormazione {
        let consigliata = VistaFormazione(titolari: f.titolari, panchina: f.panchina, modulo: f.modulo, punti: f.punteggioAtteso)
        if let manuale, let schede = f.schede {
            let titolari = manuale.compactMap { schede[String($0)] }
            // Solo la valutazione di QUESTI titolari: durante il calcolo (o se non è riuscito) niente punti, e il modulo si conta dai ruoli.
            let calcolata = valutati == manuale ? valutazione : nil
            let ids = calcolata?.panchina ?? f.panchina.map(\.id).filter { !manuale.contains($0) }
            return VistaFormazione(titolari: titolari, panchina: ids.compactMap { schede[String($0)] },
                                   modulo: calcolata?.modulo ?? ModuloTitolari.modulo(ruoli: titolari.map(\.ruolo)),
                                   punti: calcolata?.punteggioAtteso)
        }
        guard let schede = f.schede, let livello = self.livello(f),
              let opzione = livello.moduli.first(where: { $0.modulo == (moduloScelto ?? livello.modulo) }) ?? livello.moduli.first
        else { return consigliata }
        let titolari = opzione.titolari.compactMap { schede[String($0)] }
        if titolari.isEmpty { return consigliata }
        return VistaFormazione(titolari: titolari, panchina: opzione.panchina.compactMap { schede[String($0)] },
                               modulo: opzione.modulo, punti: opzione.punteggioAtteso)
    }

    /// La fascia dei punti del modulo scelto (o della valutazione a mano): «tra 62 e 84 · 8 volte su 10»,
    /// o «oscilla di ±3» se il server non manda la fascia.
    func fascia(_ f: Formazione) -> String? {
        if manuale != nil {
            guard let v = valutazioneAttuale else { return nil }
            return IntervalloPunti.frase(v.intervallo, dev: v.dev)
        }
        guard let livello = self.livello(f) else {
            return IntervalloPunti.frase(f.intervallo, dev: f.dev)
        }
        let modulo = livello.moduli.first(where: { $0.modulo == (moduloScelto ?? livello.modulo) })
        return IntervalloPunti.frase(modulo?.intervallo ?? (modulo?.dev == nil ? (livello.intervallo ?? f.intervallo) : nil), dev: modulo?.dev ?? f.dev)
    }

    /// La nota sotto il campo (#356): il perché delle scelte che sembrano storte nel modulo mostrato (`perche_scelta`), con le
    /// parole del server, come la web. Solo per la proposta del server: niente righe in modifica a mano né a giornata chiusa.
    func righeScelta(_ f: Formazione) -> [RigaScelta] {
        guard manuale == nil, !chiusa, let schede = f.schede, let livello = self.livello(f),
              let opzione = livello.moduli.first(where: { $0.modulo == (moduloScelto ?? livello.modulo) }) ?? livello.moduli.first
        else { return [] }
        return (opzione.percheScelta ?? []).compactMap { r in
            guard let id = r.titolare, let g = schede[String(id)], let testo = r.testo, !testo.isEmpty else { return nil }
            return RigaScelta(id: g.id, nome: g.nome, testo: testo)
        }
    }

    // MARK: scheda del giocatore (come `stato.formaz` della web, #616)

    /// La scheda di un giocatore aperta da qui: la previsione già letta, il perché del titolare e cosa ci si può fare. nil se la
    /// Formazione non ha quel giocatore (allora la scheda aspetta il server).
    func contestoScheda(_ id: Int) -> ContestoScheda? {
        guard let f = formazione,
              let g = f.schede?[String(id)] ?? (f.titolari + f.panchina).first(where: { $0.id == id }) else { return nil }
        return ContestoScheda(previsione: g, perche: percheTitolare(id), sostituibile: sostituibile(id), fermo: fermo(id))
    }

    /// «Perché è titolare» (`PercheTitolare`): solo con la consigliata sullo schermo e a formazione aperta, come la web (dopo un
    /// cambio, con un altro modulo o a giornata chiusa non si dice).
    func percheTitolare(_ id: Int) -> String? {
        guard !chiusa, let f = formazione, let schede = f.schede, let livello = self.livello(f),
              let consigliata = livello.moduli.first(where: { $0.modulo == livello.modulo }) ?? livello.moduli.first,
              Set(vista(f).titolari.map(\.id)) == Set(consigliata.titolari) else { return nil }
        return PercheTitolare.testo(consigliata, id: id, schede: schede)
    }

    /// Un titolare della tua formazione ancora aperta, sullo schermo: nella scheda «Sostituisci».
    func sostituibile(_ id: Int) -> Bool {
        titolareTuo(id) && !fermi.contains(id)
    }

    /// Un titolare della tua formazione che gioca un anticipo già cominciato: nella scheda la frase di `formazione.bloccati`.
    func fermo(_ id: Int) -> Bool {
        titolareTuo(id) && fermi.contains(id)
    }

    private func titolareTuo(_ id: Int) -> Bool {
        guard squadraVista == nil, !chiusa, let f = formazione else { return false }
        return vista(f).titolari.contains { $0.id == id }
    }

    /// «Sostituisci» nella scheda: il foglio della scheda si chiude e la scelta del sostituto parte quando è sparito
    /// (`apriSostituzioneInAttesa`).
    func chiediSostituzione(_ id: Int) {
        sostituzioneInAttesa = id
    }

    /// Chiamata quando il foglio della scheda è sparito: apre la scelta del sostituto chiesta con «Sostituisci», se quel
    /// titolare si può ancora sostituire.
    func apriSostituzioneInAttesa() {
        guard let id = sostituzioneInAttesa else { return }
        sostituzioneInAttesa = nil
        guard sostituibile(id), let g = formazione?.schede?[String(id)] else { return }
        daSostituire = g
    }

    /// Sostituisce un titolare degli undici sullo schermo: fuori dalla modifica a mano ci entra partendo da quegli undici (la riga
    /// dello stato dice che la formazione è cambiata e si salva con «Salva»). Mai a giornata chiusa, mai un giocatore fermo, mai
    /// un titolare al posto di un altro.
    func sostituisciTitolare(_ vecchio: Int, con nuovo: Int) {
        guard let f = formazione, !chiusa, !fermi.contains(vecchio), !fermi.contains(nuovo) else { return }
        let titolari = manuale ?? vista(f).titolari.map(\.id)
        guard titolari.contains(vecchio), !titolari.contains(nuovo) else { return }
        if manuale == nil { manuale = titolari }
        sostituisci(vecchio, con: nuovo)
    }

    /// Chi è fuori dalla formazione mostrata, dal più forte (punti attesi).
    func fuori(_ f: Formazione, _ v: VistaFormazione) -> [Giocatore] {
        let scelti = Set((v.titolari + v.panchina).map(\.id))
        return (f.schede ?? [:]).values.filter { !scelti.contains($0.id) }.sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
    }

    /// I due della rosa che più si avvicinano a un titolare non sicuro (ballottaggio). Non in modifica a mano.
    func ballottaggio(per g: Giocatore, _ f: Formazione, _ v: VistaFormazione) -> [Ballottaggio.Alternativa] {
        guard manuale == nil, !chiusa else { return [] }
        return Ballottaggio.alternative(per: g, rosa: Array((f.schede ?? [:]).values), titolari: v.titolari)
    }

    /// Il modulo attivo (serve per evidenziare il chip giusto).
    func moduloAttivo(_ livello: LivelloRischio) -> String { moduloScelto ?? livello.modulo }

    func scegliModulo(_ modulo: String) {
        moduloScelto = modulo
        esciDallaModificaAMano()
        moduloToccato = true
        Haptics.selezione()
    }

    /// Come la web (#463): in modifica a mano un tocco su un modulo torna alla proposta del server. La scelta salvata
    /// resta sul server (se è diversa la riga dice «Modifiche non salvate», con «Annulla modifiche»); un calcolo ancora in corso
    /// non conta più. A giornata chiusa no: si vede la formazione che vale.
    private func esciDallaModificaAMano() {
        guard manuale != nil, !chiusa else { return }
        azzeraManuale()
    }

    // MARK: testo

    /// La formazione mostrata, scritta a parole (da copiare o condividere).
    func testo(_ f: Formazione) -> String {
        let v = vista(f)
        return TestoFormazione.crea(giornata: f.giornata, giornataLega: f.giornataLega, modulo: v.modulo, titolari: v.titolari, panchina: v.panchina)
    }

    func copiaTesto(_ f: Formazione) {
        UIPasteboard.general.string = testo(f)
        messaggio = Catalogo.Formazione.copiata
        Haptics.esito(riuscito: true)
    }

    // MARK: modifica a mano

    /// La valutazione dei titolari mostrati adesso (nil durante il calcolo o se non è riuscito).
    var valutazioneAttuale: ValutazioneManuale? {
        guard let manuale, valutati == manuale else { return nil }
        return valutazione
    }

    func iniziaModificaManuale(_ f: Formazione) {
        guard !chiusa else { return }
        manuale = vista(f).titolari.map(\.id)
        Task { await valuta(salva: false) }
    }

    func sostituisci(_ vecchio: Int, con nuovo: Int) {
        guard !chiusa, !fermi.contains(vecchio), !fermi.contains(nuovo), var m = manuale, let i = m.firstIndex(of: vecchio) else { return }
        m[i] = nuovo
        manuale = m
        Haptics.selezione()
        Task { await valuta(salva: false) }
    }

    /// «Salva questa», «Salva le modifiche», «Salva come mia scelta»: salva come tua scelta gli undici che stai guardando
    /// (consigliata, un altro modulo, o modifica a mano).
    func salvaQuesta(_ f: Formazione) async {
        guard squadraVista == nil, !chiusa, !salvataggioInCorso else { return }
        salvataggioInCorso = true
        defer { salvataggioInCorso = false }
        if manuale == nil { manuale = vista(f).titolari.map(\.id) }
        await valuta(salva: true)
    }

    /// «Annulla modifiche»: si torna agli undici salvati (o, se non valgono più, alla consigliata con la riga che lo dice), anche
    /// da un modulo toccato fuori dalla modifica a mano.
    func annullaModifiche() {
        guard !chiusa, !salvataggioInCorso, let salvati else { return }
        if salvataNonValida { azzeraManuale(); return }
        manuale = salvati
        messaggio = nil
        calcoloNonRiuscito = false
        contatore += 1   // un calcolo partito con la modifica annullata non deve più contare
        if valutati != salvati { Task { await valuta(salva: false) } }
    }

    /// Chiede al server i punti della formazione scelta a mano (e, se `salva`, la salva: solo per la propria squadra).
    /// Se nel frattempo la scelta è cambiata, la risposta (arrivata in ritardo) viene ignorata.
    /// `silenzioso`: la prova della scelta salvata appena letta; se il server dice che non vale più, niente messaggio né vibrazione
    /// (lo dice la riga di stato).
    func valuta(salva: Bool, silenzioso: Bool = false) async {
        guard let m = manuale else { return }
        contatore += 1
        let numero = contatore
        if salva && chiusa { return }
        let salvaDavvero = salva && squadraVista == nil
        calcoloNonRiuscito = false
        codiceUltimoErrore = nil
        do {
            let richiesta = RichiestaValutazione(titolari: m, salva: salvaDavvero, squadra: squadraVista, giornata: formazione?.giornata)
            let v: ValutazioneManuale = try await server.posta("POST", "/api/formazione/valuta", richiesta)
            guard numero == contatore, manuale == m else { return }
            valutazione = v
            valutati = m
            messaggio = nil
            if salvaDavvero {
                // Lo stato «salvata» resta nella riga fissa (e alla riapertura lo rilegge dal server): niente messaggio che sparisce.
                salvati = m
                salvataIl = Date()
                salvataNonValida = false
                sceltaLetta = true
                Haptics.esito(riuscito: true)
                AccessibilityNotification.Announcement(Self.annuncioSalvata).post()
            }
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            guard numero == contatore, manuale == m else { return }
            if salvaDavvero, (error as? ErroreApi)?.eConflitto == true { await sceltaCambiataAltrove(); return }
            if case .codificato(let codice, _)? = error as? ErroreApi { codiceUltimoErrore = codice }
            // solo un salvataggio rifiutato porta a ricaricare (una semplice valutazione no: niente giri a vuoto)
            if salvaDavvero, codiceUltimoErrore == Self.codiceChiusa, !chiusa { await formazioneChiusa(); return }
            if silenzioso, codiceUltimoErrore == ValiditaScelta.codiceNonValida { return }
            // Il salvataggio non riuscito non cancella i punti già calcolati per questi titolari.
            calcoloNonRiuscito = valutati != m
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }

    /// Detto da VoiceOver dopo il salvataggio: la frase dell'avviso della web (`formazione.salvata_come_tua`).
    static let annuncioSalvata = Catalogo.Formazione.salvataComeTua

    static let sceltaCambiata = "La scelta di questa giornata è stata cambiata da un altro dispositivo: ho ricaricato quella salvata. Controlla e, se serve, rifai la modifica."
    /// Dopo un 412 la rilettura della scelta non è riuscita (rete, server): «ho ricaricato» sarebbe falso (#477).
    static let sceltaCambiataSenzaRicarica = "La scelta di questa giornata è stata cambiata da un altro dispositivo, ma non riesco a ricaricarla: tira giù per aggiornare e, se serve, rifai la modifica."

    /// 412 sulla scelta salvata: un altro dispositivo l'ha cambiata (o cancellata) dopo l'ultima lettura. Come per le altre risorse
    /// si rilegge tutto (formazione e scelta, con l'ETag nuovo) e lo si dice: la modifica di questo telefono non si salva sopra.
    /// Come la web, che dopo un 412 ricarica la pagina, anche il modulo riparte da quello consigliato (#477): se l'altro
    /// dispositivo ha cancellato la scelta, non resta in vista il modulo toccato.
    private func sceltaCambiataAltrove() async {
        azzeraManuale()
        let riletta = await ricaricaConScelta()
        moduloScelto = nil
        if riletta {
            messaggio = Self.sceltaCambiata
        } else {
            // La scelta che si conosceva non è più quella del server, e quella nuova non si è potuta leggere: la riga non dice
            // niente (come la web quando la rilettura non riesce, niente «salvata» falso) e la prossima lettura la rimette a posto.
            sceltaLetta = false
            salvati = nil
            salvataIl = nil
            salvataNonValida = false
            messaggio = Self.sceltaCambiataSenzaRicarica
        }
        Haptics.esito(riuscito: false)
    }

    /// 409 `formazione_chiusa`: la scadenza è passata mentre la pagina era aperta. Si ricarica (il server dice `iniziata`)
    /// e lo si dice con una frase chiara, senza l'errore del server.
    private func formazioneChiusa() async {
        azzeraManuale()
        await carica()
        messaggio = Self.testoChiusaAlSalvataggio
        Haptics.esito(riuscito: false)
    }

    /// «Torna alla consigliata»: toglie la tua scelta e, come la web, rimette anche il modulo consigliato.
    func tornaAllaConsigliata(_ f: Formazione) async {
        guard !chiusa else { return }
        moduloScelto = nil
        // La scelta salvata esiste solo per la propria squadra; se il server ha detto che non ce n'è, non c'è niente da togliere.
        guard squadraVista == nil, !(sceltaLetta && salvati == nil) else { azzeraManuale(); return }
        do {
            try await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
            azzeraManuale()
            salvati = nil
            salvataIl = nil
            salvataNonValida = false
        } catch let e as ErroreApi where e.eConflitto {
            await sceltaCambiataAltrove()
        } catch ErroreApi.codificato(let codice, _) where codice == Self.codiceChiusa {
            await formazioneChiusa()
        } catch {
            // Se il server non cancella la scelta salvata, resta com'è e lo si dice.
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
