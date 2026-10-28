import SwiftUI

/// I giocatori da mostrare in questo momento (consigliata, stile e modulo scelti, oppure modifica a mano).
struct VistaFormazione {
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let modulo: String
    let punti: Double
}

/// Logica della schermata Formazione: stile e modulo, modifica a mano, salvataggio della scelta.
/// Vive nell'`AppModel`, quindi cambiando sezione (barra laterale dell'iPad) la modifica a mano non si perde.
@MainActor
final class FormazioneViewModel: ViewModelBase {
    let caricatore: Caricatore<Formazione>
    private let server: any ServerClient

    @Published var rischio = 0
    @Published var moduloScelto: String?
    /// Id dei titolari scelti a mano; nil = si usa la formazione consigliata.
    @Published var manuale: [Int]?
    @Published var valutazione: ValutazioneManuale?
    @Published var messaggio: String?
    /// Testo pronto da condividere (ShareLink).
    @Published var testoDaCondividere: String?

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

    func carica() async {
        await caricatore.ricarica()
        await caricaTesto()
        if let f = caricatore.dato { await caricaScelta(f) }
    }

    private func caricaTesto() async {
        testoDaCondividere = try? await server.testo("/api/formazione/testo")
    }

    /// Se avevi salvato una scelta a mano per questa giornata, riparte da lì.
    private func caricaScelta(_ f: Formazione) async {
        // Un'altra giornata: la modifica a mano della vecchia non vale più.
        if giornata != f.giornata {
            azzeraManuale()
            giornata = f.giornata
        }
        guard manuale == nil else { return }   // c'è già una modifica in corso: non si sovrascrive
        let salvata: SceltaSalvata? = try? await server.get("/api/scelta?giornata=\(f.giornata)")
        if let salvata, manuale == nil, salvata.titolari.count == 11 {
            manuale = salvata.titolari
            await valuta(salva: false)
        }
    }

    private func azzeraManuale() {
        manuale = nil
        valutazione = nil
        messaggio = nil
        contatore += 1
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

    /// Il modulo attivo per lo stile corrente (serve per evidenziare il chip giusto).
    func moduloAttivo(_ livello: LivelloRischio) -> String { moduloScelto ?? livello.modulo }

    func cambiaStile() {
        moduloScelto = nil
        Haptics.selezione()
    }

    func scegliModulo(_ modulo: String) {
        moduloScelto = modulo
        Haptics.selezione()
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

    /// Chiede al server i punti della formazione scelta a mano (e, se `salva`, la salva).
    /// Se nel frattempo la scelta è cambiata, la risposta (arrivata in ritardo) viene ignorata.
    func valuta(salva: Bool) async {
        guard let m = manuale else { return }
        contatore += 1
        let numero = contatore
        do {
            let v: ValutazioneManuale = try await server.posta("POST", "/api/formazione/valuta", RichiestaValutazione(titolari: m, salva: salva))
            guard numero == contatore, manuale == m else { return }
            valutazione = v
            messaggio = nil
            if salva {
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
