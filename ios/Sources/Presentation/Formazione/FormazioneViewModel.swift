import SwiftUI

/// I giocatori da mostrare in questo momento (consigliata, stile e modulo scelti, oppure modifica a mano).
struct VistaFormazione {
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let modulo: String
    let punti: Double
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

    /// Giornata a cui si riferisce la modifica a mano: se cambia, si riparte da zero.
    private var giornata: Int?
    /// Numera le valutazioni inviate: una risposta arrivata in ritardo (fuori ordine) viene ignorata.
    private var contatore = 0

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

    /// Se avevi salvato una scelta a mano per questa giornata, riparte da lì (solo per la propria squadra).
    private func caricaScelta(_ f: Formazione) async {
        // Un'altra giornata: la modifica a mano della vecchia non vale più.
        if giornata != f.giornata {
            azzeraManuale()
            giornata = f.giornata
        }
        guard squadraVista == nil, manuale == nil else { return }   // c'è già una modifica in corso: non si sovrascrive
        let salvata: SceltaSalvata? = try? await server.get("/api/scelta?giornata=\(f.giornata)")
        guard let salvata, manuale == nil, squadraVista == nil else { return }
        // Una scelta che non vale più (rosa cambiata: non sono 11 giocatori della rosa) si cancella, come fa la web app.
        let rosa = f.schede ?? [:]
        let valida = salvata.titolari.count == 11 && salvata.titolari.allSatisfy { rosa[String($0)] != nil }
        guard valida else {
            try? await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
            return
        }
        manuale = salvata.titolari
        await valuta(salva: false)
        if let m = messaggio, m.contains("Servono 11") {
            try? await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
            azzeraManuale()
        }
    }

    private func azzeraManuale() {
        manuale = nil
        valutazione = nil
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
            let ids = valutazione?.panchina ?? f.panchina.map(\.id).filter { !manuale.contains($0) }
            return VistaFormazione(titolari: titolari, panchina: ids.compactMap { schede[String($0)] },
                                   modulo: valutazione?.modulo ?? f.modulo, punti: valutazione?.punteggioAtteso ?? f.punteggioAtteso)
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
        if manuale != nil { return IntervalloPunti.frase(valutazione?.intervallo, dev: valutazione?.dev) }
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
        return TestoFormazione.crea(giornata: f.giornata, modulo: v.modulo, titolari: v.titolari, panchina: v.panchina)
    }

    func copiaTesto(_ f: Formazione) {
        UIPasteboard.general.string = testo(f)
        messaggio = "Formazione copiata: incollala dove vuoi."
        Haptics.esito(riuscito: true)
    }

    /// Disegna la formazione come immagine (campo con i titolari e la panchina) e apre l'anteprima con il pulsante Condividi.
    func preparaImmagine(_ f: Formazione) {
        let v = vista(f)
        let disegno = ImmagineFormazione(giornata: f.giornata, squadra: f.squadra ?? "", modulo: v.modulo, punti: v.punti,
                                         titolari: v.titolari, panchina: v.panchina)
        let renderer = ImageRenderer(content: disegno)
        renderer.scale = 3   // 360 x 490 punti → 1080 x 1470 pixel
        if let immagine = renderer.uiImage {
            anteprimaImmagine = ImmagineCondivisa(immagine: immagine, titolo: "Formazione giornata \(f.giornata)")
        } else {
            messaggio = "Non riesco a creare l'immagine."
        }
    }

    // MARK: modifica a mano

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

    /// Chiede al server i punti della formazione scelta a mano (e, se `salva`, la salva: solo per la propria squadra).
    /// Se nel frattempo la scelta è cambiata, la risposta (arrivata in ritardo) viene ignorata.
    func valuta(salva: Bool) async {
        guard let m = manuale else { return }
        contatore += 1
        let numero = contatore
        let salvaDavvero = salva && squadraVista == nil
        do {
            let richiesta = RichiestaValutazione(titolari: m, salva: salvaDavvero, squadra: squadraVista, giornata: formazione?.giornata)
            let v: ValutazioneManuale = try await server.posta("POST", "/api/formazione/valuta", richiesta)
            guard numero == contatore, manuale == m else { return }
            valutazione = v
            messaggio = nil
            if salvaDavvero {
                messaggio = "Salvata come la tua scelta per questa giornata."
                Haptics.esito(riuscito: true)
            }
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            guard numero == contatore, manuale == m else { return }
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }

    func tornaAllaConsigliata(_ f: Formazione) async {
        // La scelta salvata esiste solo per la propria squadra.
        guard squadraVista == nil else { azzeraManuale(); return }
        do {
            try await server.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
            azzeraManuale()
        } catch {
            // Se il server non cancella la scelta salvata, resta com'è e lo si dice.
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
