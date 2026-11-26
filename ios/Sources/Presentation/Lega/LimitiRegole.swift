import Foundation

/// I limiti dei numeri delle regole (#889, dopo la #886): gli stessi con cui il server controlla le regole quando si salvano, dal
/// file `/limiti-regole.json` che legge anche la web (`leggiLimitiRegole` in `fanta/web/app.js`). I pulsanti − e + dell'editor si
/// fermano lì e «Salva le regole» controlla i campi con questi numeri (`CampiRegole.problema`). Con un server di prima, che non ha
/// il file, valgono i limiti di riserva: gli stessi del file (lo controlla `tests/test_limiti_regole_iphone.py`; se il file cambia,
/// si cambia anche `riserva`). I numeri sono del server: qui si leggono e basta. Logica pura: la provano i test.
struct LimitiRegole: Equatable, Sendable {
    /// Il numero più piccolo e quello più grande che il server accetta per un campo.
    struct Limite: Equatable, Sendable {
        let min: Double
        let max: Double
    }

    /// Per chiave, con i nomi dei campi delle regole («bonus.assist», «rosa.P», «modificatore_difesa.soglie.media»).
    let valori: [String: Limite]

    init(valori: [String: Limite]) {
        self.valori = valori
    }

    /// I limiti della risposta di `/limiti-regole.json` (`{chiave: {min, max}}`) e, per le chiavi che non ha, quelli di riserva.
    /// Una voce senza due numeri, o con il minimo sopra il massimo, non vale: per quella chiave resta il limite di riserva. nil se la
    /// risposta non è quel file (un server di prima risponde con un errore o con un'altra pagina): allora restano i limiti di riserva.
    init?(dati: Data) {
        guard let letto = try? JSONDecoder().decode(JSONValue.self, from: dati), case .oggetto(let voci) = letto else { return nil }
        var validi: [String: Limite] = [:]
        for (chiave, voce) in voci {
            guard case .oggetto(let campi) = voce, let minimo = campi["min"]?.numero, let massimo = campi["max"]?.numero,
                  minimo.isFinite, massimo.isFinite, minimo <= massimo else { continue }
            validi[chiave] = Limite(min: minimo, max: massimo)
        }
        guard !validi.isEmpty else { return nil }
        valori = Self.riserva.valori.merging(validi) { _, delServer in delServer }
    }

    /// I numeri ammessi per una chiave; per una chiave che manca, quelli di riserva (e, se manca anche lì, nessun limite).
    func intervallo(_ chiave: String) -> ClosedRange<Double> {
        guard let limite = valori[chiave] ?? Self.riserva.valori[chiave] else {
            return -Double.greatestFiniteMagnitude...Double.greatestFiniteMagnitude
        }
        return limite.min...limite.max
    }

    /// Gli stessi numeri di `fanta/web/limiti-regole.json`, chiave per chiave.
    static let riserva = LimitiRegole(valori: [
        "bonus.gol.P": Limite(min: 0, max: 20),
        "bonus.gol.D": Limite(min: 0, max: 20),
        "bonus.gol.C": Limite(min: 0, max: 20),
        "bonus.gol.A": Limite(min: 0, max: 20),
        "bonus.rigore_segnato": Limite(min: 0, max: 20),
        "bonus.assist": Limite(min: 0, max: 20),
        "bonus.rigore_parato": Limite(min: 0, max: 20),
        "bonus.portiere_imbattuto": Limite(min: 0, max: 20),
        "bonus.mvp": Limite(min: 0, max: 20),
        "bonus.rigore_sbagliato": Limite(min: -20, max: 0),
        "bonus.autogol": Limite(min: -20, max: 0),
        "bonus.gol_subito_portiere": Limite(min: -20, max: 0),
        "bonus.ammonizione": Limite(min: -20, max: 0),
        "bonus.espulsione": Limite(min: -20, max: 0),
        "rosa.P": Limite(min: 1, max: 30),
        "rosa.D": Limite(min: 1, max: 30),
        "rosa.C": Limite(min: 1, max: 30),
        "rosa.A": Limite(min: 1, max: 30),
        "crediti_iniziali": Limite(min: 0, max: 100_000),
        "panchina.numero": Limite(min: 1, max: 30),
        "panchina.max_sostituzioni": Limite(min: 0, max: 10),
        "panchina.posti.P": Limite(min: 0, max: 10),
        "panchina.posti.D": Limite(min: 0, max: 10),
        "panchina.posti.C": Limite(min: 0, max: 10),
        "panchina.posti.A": Limite(min: 0, max: 10),
        "voto_senza_sostituto": Limite(min: 0, max: 10),
        "voto_ufficio_rinviate": Limite(min: 0, max: 10),
        "modificatore_difesa.min_difensori": Limite(min: 3, max: 5),
        "modificatore_difesa.soglie.media": Limite(min: 0, max: 10),
        "modificatore_difesa.soglie.bonus": Limite(min: 0, max: 20),
        "fattore_campo": Limite(min: -100, max: 100),
        "soglia_primo_gol": Limite(min: 0, max: 200),
        "ampiezza_fascia_gol": Limite(min: 0, max: 100),
    ])
}
