import Foundation

/// I testi italiani della web che le prove di parità confrontano con quelli dell'app: una copia ferma di `fanta/web/testi.js`
/// presa il 12/11/2026, prima del rifacimento della web (spec `2026-11-12-revisione-generale-design`). Prima il file si leggeva
/// dal repository; ora la web cambia per conto suo e l'app resta com'è finché il proprietario non decide, quindi le prove
/// controllano che l'app dica queste parole senza seguire la web (e una modifica alla web non fa partire i Mac).
/// Solo per le chiavi che l'iPhone NON elenca in `ios/testi/`: quelle elencate si confrontano con le costanti generate
/// `Catalogo.…` (#556). Una chiave che manca qui fa fallire la prova che la chiede: si aggiunge con il suo testo.
struct TestiWeb {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    init() throws {}

    /// Il testo italiano di una chiave.
    func italiano(_ chiave: String) throws -> String {
        guard let testo = Self.testi[chiave] else {
            throw Errore(description: "nella copia dei testi della web (TestiWeb) manca la chiave \(chiave)")
        }
        return testo
    }

    /// Chiave e testo italiano, come erano in `fanta/web/testi.js` il 12/11/2026.
    private static let testi: [String: String] = [
        "avv.diario_riga": "Giornata per giornata: la formazione che hai schierato contro la consigliata.",
        "confronto.fattore_voto": "Voto in pagella atteso",
        "diff.1": "Facile",
        "diff.2": "Abbordabile",
        "diff.3": "Normale",
        "diff.4": "Dura",
        "diff.5": "Molto dura",
        "err.formazione_chiusa": "La giornata è già iniziata: la formazione non si può più cambiare.",
        "err.giocatore_bloccato": "{1} gioca in una partita già cominciata: non si può più spostare.",
        "formazione.fv_preso": "fantavoto {fv}",
        "frase.giornata.lega": "Giornata {n} · {a}ª di Serie A",
        "frase.giornata.serie_a": "{a}ª giornata di Serie A",
        "frase.scelta.piu_punti": "Preferito a {altro}: con lui la formazione fa più punti attesi ({attuale} contro {invertita}).",
        "giocatore.gioca": "gioca {p}",
        "lega.n_crediti.one": "{n} credito",
        "lega.n_crediti.other": "{n} crediti",
        "mercato.assist": "assist",
        "mercato.atteso_ponderato": "Atteso ponderato (con la probabilità di giocare)",
        "mercato.avversario": "Avversario",
        "mercato.fantavoto_atteso": "Fantavoto atteso",
        "mercato.fantavoto_atteso_riga": "Fantavoto atteso",
        "mercato.giallo": "giallo",
        "mercato.gioca_riga": "Gioca",
        "mercato.indice": "Indice",
        "mercato.panchina_n": "Panchina {n}",
        "mercato.parte_a_volte": "a volte titolare",
        "mercato.parte_di_rado": "di solito entra dopo",
        "mercato.parte_quasi_sempre": "quasi sempre titolare",
        "mercato.parte_titolare": "Quando gioca",
        "mercato.partita": "Partita",
        "mercato.posto_fuori": "Non schierato",
        "mercato.posto_titolare": "Titolare",
        "mercato.segna": "segna",
        "oggi.dubbio": "In dubbio · gioca {p}",
        "scambio.bozza": "Ciao! Ti propongo uno scambio: io ti do {do}, tu mi dai {ricevo}. Secondo i miei calcoli conviene a tutti e due ({quanto}). Che ne dici?",
        "scambio.bozza_e": " e ",
        "scambio.bozza_punti": "tu {loro} punti attesi in stagione, io {mio}",
        "scambio.bozza_uguale": "più o meno uguale",
        "sd.f_taratura": "Taratura di «gioca N%»",
        "sd.n_giocatori.one": "{n} giocatore",
        "sd.n_giocatori.other": "{n} giocatori",
        "sd.reg_punti.one": "{n} punto",
        "sd.reg_punti.other": "{n} punti",
        "tit.ballottaggio": "In ballottaggio",
        "tit.improbabile": "Improbabile",
        "tit.panchina": "Probabile panchina",
    ]
}
