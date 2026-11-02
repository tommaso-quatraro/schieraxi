import SwiftUI

/// I giocatori da mostrare in questo momento (consigliata, stile e modulo scelti, oppure modifica a mano).
struct VistaFormazione {
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let modulo: String
    /// nil in modifica a mano finché il server non ha calcolato quella formazione (o se il calcolo non è riuscito):
    /// al suo posto si mostra «Calcolo…», mai i punti della consigliata.
    let punti: Double?
}

/// Un'immagine pronta da condividere (la formazione disegnata), con un identificativo per `.sheet(item:)`.
struct ImmagineCondivisa: Identifiable {
    let id = UUID()
    let immagine: UIImage
    let titolo: String
}

/// Logica della schermata Formazione: stile e modulo, modifica a mano, salvataggio della scelta, formazione di un'altra squadra.
/// Vive nell'`AppModel`, quindi cambiando sezione (barra laterale dell'iPad) la modifica a mano non si perde.
@MainActor
final class FormazioneViewModel: ViewModelBase {
    let caricatore: Caricatore<Formazione>
    let server: any ServerClient

    @Published var rischio = 0
    @Published var moduloScelto: String?
    /// Id dei titolari scelti a mano; nil = si usa la formazione consigliata.
    @Published var manuale: [Int]?
    @Published var valutazione: ValutazioneManuale?
    @Published var messaggio: String?
    /// Nome di un'altra squadra della lega, se se ne sta guardando la formazione consigliata (nil = la mia).
    @Published var squadraVista: String?
    /// Confronto aperto dalla formazione (ballottaggio o «⇄» su un titolare).
    @Published var confrontoAperto: ConfrontoSheet.Inizio?
    /// L'immagine della formazione, pronta da condividere.
    @Published var anteprimaImmagine: ImmagineCondivisa?
    /// Il giocatore di cui si guarda «Perché questo numero» (tocco sul fantavoto atteso).
    @Published var percheAperto: Giocatore?

    /// La scelta della giornata è stata letta dal server (anche «nessuna»): solo allora la riga di stato dice qualcosa.
    @Published private(set) var sceltaLetta = false
    /// I titolari salvati sul server per questa giornata (nil = nessuna scelta salvata) e quando.
    @Published private(set) var salvati: [Int]?
    @Published private(set) var salvataIl: Date?
    /// Il calcolo della modifica a mano non è riuscito: invece dei punti, «Non riesco a calcolare» con «Riprova».
    @Published private(set) var calcoloNonRiuscito = false
    /// I titolari a cui si riferisce `valutazione` (dopo una sostituzione la valutazione vecchia non vale più).
    private var valutati: [Int]?
    /// Il codice dell'ultimo errore di `valuta` (campo `codice` del server), se c'era.
    private var codiceUltimoErrore: String?

    /// Giornata a cui si riferisce la modifica a mano: se cambia, si riparte da zero.
    private var giornata: Int?
    /// Numera le valutazioni inviate: una risposta arrivata in ritardo (fuori ordine) viene ignorata.
    private var contatore = 0

    /// A che punto è la tua scelta (riga di stato della Formazione). Per le altre squadre non si dice niente.
    var statoScelta: StatoScelta {
        guard squadraVista == nil else { return .sconosciuto }
        return StatoScelta.calcola(letta: sceltaLetta, salvati: salvati, salvataIl: salvataIl, manuale: manuale)
    }

    /// In modifica a mano, il server sta calcolando i punti di questa formazione.
    var inCalcolo: Bool { manuale != nil && valutati != manuale && !calcoloNonRiuscito }

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
        await caricatore.ricarica(percorso)
        if let f = caricatore.dato { await caricaScelta(f) }
    }

    /// Legge dal server la scelta salvata per questa giornata (solo per la propria squadra): tiene lo stato «salvata» e, se non
    /// c'è una modifica in corso, riparte da lì. Se la lettura non riesce lo stato resta com'era (all'inizio: non si sa).
    private func caricaScelta(_ f: Formazione) async {
        // Un'altra giornata: la modifica a mano e la scelta della vecchia non valgono più.
        if giornata != f.giornata {
            azzeraManuale()
            sceltaLetta = false
            salvati = nil
            salvataIl = nil
            giornata = f.giornata
        }
        guard squadraVista == nil else { return }
        let salvata: SceltaSalvata?
        do {
            salvata = try await server.get("/api/scelta?giornata=\(f.giornata)")
        } catch {
            return
        }
        guard squadraVista == nil, giornata == f.giornata else { return }
        // Nessuna modifica di questo telefono: la formazione mostrata è quella salvata di prima (o la consigliata).
        let senzaModifiche = manuale == nil || salvati.map { Set($0) == Set(manuale ?? []) } == true
        sceltaLetta = true
        guard let salvata else {
            salvati = nil
            salvataIl = nil
            if senzaModifiche { azzeraManuale() }   // cancellata da un altro dispositivo: si torna alla consigliata
            return
        }
        // Una scelta che non vale più (rosa cambiata) si cancella, ma solo se la rosa c'è davvero: senza rosa non si giudica.
        if ValiditaScelta.controlla(titolari: salvata.titolari, rosa: f.schede) == .nonValida {
            await cancellaSceltaNonValida(f)
            return
        }
        salvati = salvata.titolari
        salvataIl = Quando.data(salvata.salvata)
        guard senzaModifiche else { return }   // c'è una modifica in corso: non si sovrascrive (la riga dice «Modifiche non salvate»)
        if manuale.map({ Set($0) == Set(salvata.titolari) }) == true, valutati == manuale { return }   // già lei, già calcolata
        manuale = salvata.titolari
        await valuta(salva: false)
        // Il server dice che non si può valutare (codice, non il testo): non vale più. Di nuovo, solo con la rosa presente.
        if codiceUltimoErrore == ValiditaScelta.codiceNonValida, manuale == salvata.titolari, let rosa = f.schede, !rosa.isEmpty {
            await cancellaSceltaNonValida(f)
        }
    }

    static let sceltaNonValida = "La formazione salvata non vale più (sono cambiate la rosa o le regole): ti mostro la consigliata."

    /// Cancella sul server una scelta che non vale più e lo dice. Se il server non la cancella, resta tutto com'è.
    private func cancellaSceltaNonValida(_ f: Formazione) async {
        do {
            try await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
            azzeraManuale()
            salvati = nil
            salvataIl = nil
            sceltaLetta = true
            messaggio = Self.sceltaNonValida
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            messaggio = error.localizedDescription
        }
    }

    private func azzeraManuale() {
        manuale = nil
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
        rischio = 0
        moduloScelto = nil
        azzeraManuale()
        Task { await carica() }
    }

    func tornaAllaMia() {
        squadraVista = nil
        rischio = 0
        moduloScelto = nil
        azzeraManuale()
        Task { await carica() }
    }

    // MARK: cosa mostrare

    /// Titolari, panchina, modulo e punteggio secondo la modalità (a mano, o stile e modulo scelti).
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
        guard let livelli = f.livelli, let schede = f.schede,
              let livello = livelli.first(where: { $0.rischio == rischio }) ?? livelli.first,
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
        guard let livelli = f.livelli, let livello = livelli.first(where: { $0.rischio == rischio }) ?? livelli.first else {
            return IntervalloPunti.frase(f.intervallo, dev: f.dev)
        }
        let modulo = livello.moduli.first(where: { $0.modulo == (moduloScelto ?? livello.modulo) })
        return IntervalloPunti.frase(modulo?.intervallo ?? (modulo?.dev == nil ? (livello.intervallo ?? f.intervallo) : nil), dev: modulo?.dev ?? f.dev)
    }

    /// Chi è fuori dalla formazione mostrata, dal più forte (punti attesi).
    func fuori(_ f: Formazione, _ v: VistaFormazione) -> [Giocatore] {
        let scelti = Set((v.titolari + v.panchina).map(\.id))
        return (f.schede ?? [:]).values.filter { !scelti.contains($0.id) }.sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
    }

    /// I due della rosa che più si avvicinano a un titolare non sicuro (ballottaggio). Non in modifica a mano.
    func ballottaggio(per g: Giocatore, _ f: Formazione, _ v: VistaFormazione) -> [Ballottaggio.Alternativa] {
        guard manuale == nil else { return [] }
        return Ballottaggio.alternative(per: g, rosa: Array((f.schede ?? [:]).values), titolari: v.titolari)
    }

    /// Il modulo attivo per lo stile corrente (serve per evidenziare il chip giusto).
    func moduloAttivo(_ livello: LivelloRischio) -> String { moduloScelto ?? livello.modulo }

    /// In che formazione si sta guardando: il confronto spiega la scelta dentro quella formazione.
    var contestoConfronto: ContestoConfronto? {
        guard let f = formazione else { return nil }
        return ContestoConfronto(livello: rischio, modulo: vista(f).modulo, squadra: squadraVista)
    }

    /// Sceglie uno stile: il modulo scelto a mano si azzera e modulo e punti tornano quelli proposti dallo stile.
    func scegliStile(_ stile: Int) {
        rischio = stile
        cambiaStile()
    }

    func cambiaStile() {
        moduloScelto = nil
        Haptics.selezione()
    }

    func scegliModulo(_ modulo: String) {
        moduloScelto = modulo
        Haptics.selezione()
    }

    // MARK: testo e immagine

    /// La formazione mostrata, scritta a parole (da copiare o condividere).
    func testo(_ f: Formazione) -> String {
        let v = vista(f)
        return TestoFormazione.crea(giornata: f.giornata, giornataLega: f.giornataLega, modulo: v.modulo, titolari: v.titolari, panchina: v.panchina)
    }

    func copiaTesto(_ f: Formazione) {
        UIPasteboard.general.string = testo(f)
        messaggio = "Formazione copiata: incollala dove vuoi."
        Haptics.esito(riuscito: true)
    }

    /// Disegna la formazione come immagine (campo con i titolari e la panchina) e apre l'anteprima con il pulsante Condividi.
    func preparaImmagine(_ f: Formazione) {
        let v = vista(f)
        let disegno = ImmagineFormazione(giornata: f.giornata, giornataLega: f.giornataLega, squadra: f.squadra ?? "", modulo: v.modulo, punti: v.punti,
                                         titolari: v.titolari, panchina: v.panchina)
        let renderer = ImageRenderer(content: disegno)
        renderer.scale = 3   // 360 x 490 punti → 1080 x 1470 pixel
        if let immagine = renderer.uiImage {
            anteprimaImmagine = ImmagineCondivisa(immagine: immagine, titolo: f.etichettaGiornata.replacingOccurrences(of: "Giornata", with: "Formazione giornata"))
        } else {
            messaggio = "Non riesco a creare l'immagine."
        }
    }

    // MARK: modifica a mano

    /// La valutazione dei titolari mostrati adesso (nil durante il calcolo o se non è riuscito).
    var valutazioneAttuale: ValutazioneManuale? {
        guard let manuale, valutati == manuale else { return nil }
        return valutazione
    }

    func iniziaModificaManuale(_ f: Formazione) {
        manuale = vista(f).titolari.map(\.id)
        Task { await valuta(salva: false) }
    }

    func sostituisci(_ vecchio: Int, con nuovo: Int) {
        guard var m = manuale, let i = m.firstIndex(of: vecchio) else { return }
        m[i] = nuovo
        manuale = m
        Haptics.selezione()
        Task { await valuta(salva: false) }
    }

    /// «Salva questa»: salva come tua scelta gli undici che stai guardando (consigliata, stile o modulo scelti, o modifica a mano).
    func salvaQuesta(_ f: Formazione) async {
        guard squadraVista == nil else { return }
        if manuale == nil { manuale = vista(f).titolari.map(\.id) }
        await valuta(salva: true)
    }

    /// «Annulla modifiche»: si torna agli undici salvati.
    func annullaModifiche() {
        guard let salvati else { return }
        manuale = salvati
        messaggio = nil
        calcoloNonRiuscito = false
        contatore += 1   // un calcolo partito con la modifica annullata non deve più contare
        if valutati != salvati { Task { await valuta(salva: false) } }
    }

    /// Chiede al server i punti della formazione scelta a mano (e, se `salva`, la salva: solo per la propria squadra).
    /// Se nel frattempo la scelta è cambiata, la risposta (arrivata in ritardo) viene ignorata.
    func valuta(salva: Bool) async {
        guard let m = manuale else { return }
        contatore += 1
        let numero = contatore
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
                sceltaLetta = true
                Haptics.esito(riuscito: true)
                AccessibilityNotification.Announcement(Self.annuncioSalvata).post()
            }
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            guard numero == contatore, manuale == m else { return }
            if salvaDavvero, (error as? ErroreApi)?.eConflitto == true { await sceltaCambiataAltrove(); return }
            if case .codificato(let codice, _)? = error as? ErroreApi { codiceUltimoErrore = codice }
            // Il salvataggio non riuscito non cancella i punti già calcolati per questi titolari.
            calcoloNonRiuscito = valutati != m
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }

    static let annuncioSalvata: String = "Formazione salvata"

    static let sceltaCambiata = "La scelta di questa giornata è stata cambiata da un altro dispositivo: ho ricaricato quella salvata. Controlla e, se serve, rifai la modifica."

    /// 412 sulla scelta salvata: un altro dispositivo l'ha cambiata (o cancellata) dopo l'ultima lettura. Come per le altre risorse
    /// si rilegge tutto (formazione e scelta, con l'ETag nuovo) e lo si dice: la modifica a mano di questo telefono non si salva sopra.
    private func sceltaCambiataAltrove() async {
        azzeraManuale()
        await carica()
        messaggio = Self.sceltaCambiata
        Haptics.esito(riuscito: false)
    }

    func tornaAllaConsigliata(_ f: Formazione) async {
        // La scelta salvata esiste solo per la propria squadra.
        guard squadraVista == nil else { azzeraManuale(); return }
        do {
            try await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
            azzeraManuale()
            salvati = nil
            salvataIl = nil
        } catch let e as ErroreApi where e.eConflitto {
            await sceltaCambiataAltrove()
        } catch {
            // Se il server non cancella la scelta salvata, resta com'è e lo si dice.
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
