// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/giornate.json, chiavi elencate in ios/testi/giornate.txt.

extension Catalogo {
    enum Giornate {
        /// `giornate.carico`
        static let carico = "Carico le giornate…"

        /// `giornate.precisione`
        static func precisione(e: String) -> String {
            "Finora il fantavoto atteso sbaglia in media di \(e) punti a giocatore."
        }

        /// `giornate.dettagli`
        static let dettagli = "Dettagli"

        /// `giornate.elenco`
        static let elenco = "Giornate finite"

        /// `giornate.hai_consigliata`
        static let haiConsigliata = "Hai schierato la consigliata."

        /// `giornate.cambi.one`, `giornate.cambi.other`
        static func cambi(_ n: Int, d: String) -> String {
            n == 1 ? "1 cambio tuo: \(d) punti rispetto alla consigliata." : "\(n) cambi tuoi: \(d) punti rispetto alla consigliata."
        }

        /// `giornate.cambi_pari.one`, `giornate.cambi_pari.other`
        static func cambiPari(_ n: Int) -> String {
            n == 1 ? "1 cambio tuo: gli stessi punti della consigliata." : "\(n) cambi tuoi: gli stessi punti della consigliata."
        }

        /// `giornate.tua`
        static let tua = "La tua formazione."

        /// `giornate.automatica`
        static let automatica = "Non l'avevi cambiata: sono i punti della consigliata alla scadenza."

        /// `giornate.non_salvata`
        static let nonSalvata = "Formazione non salvata: sono i punti della consigliata."

        /// `giornate.formazione_tua`
        static func formazioneTua(modulo: String) -> String {
            "La tua formazione (\(modulo))"
        }

        /// `giornate.formazione_automatica`
        static func formazioneAutomatica(modulo: String) -> String {
            "La consigliata alla scadenza (\(modulo))"
        }

        /// `giornate.formazione_consigliata`
        static func formazioneConsigliata(modulo: String) -> String {
            "La consigliata (\(modulo))"
        }

        /// `giornate.formazione_rifatta`
        static func formazioneRifatta(modulo: String) -> String {
            "La consigliata rifatta a giornata finita (\(modulo))"
        }

        /// `giornate.rifatta_nota`
        static let rifattaNota = "Quella mostrata prima della scadenza non era stata salvata: questa è rifatta con i dati di allora."

        /// `giornate.tabella`
        static let tabella = "Fantavoto atteso e fantavoto preso dei titolari"

        /// `giornate.col_giocatore`
        static let colGiocatore = "Giocatore"

        /// `giornate.col_atteso`
        static let colAtteso = "Atteso"

        /// `giornate.col_preso`
        static let colPreso = "Preso"

        /// `giornate.senza_voto`
        static let senzaVoto = "senza voto"

        /// `giornate.al_posto`
        static func alPosto(dentro: String, fuori: String) -> String {
            "Al posto di \(fuori) hai messo \(dentro)."
        }

        /// `giornate.senza_confronto`
        static let senzaConfronto = "Qui il confronto con la consigliata non c'è: quella mostrata prima della scadenza non era stata salvata."

        /// `giornate.correggi`
        static let correggi = "Non è quello che ho schierato"

        /// `giornate.vuoto`
        static let vuoto = "Ancora niente: le giornate compaiono qui dopo la prima finita."

        /// `giornate.vuoto_squadra`
        static func vuotoSquadra(voce: String) -> String {
            "Ancora niente: manca la tua squadra. Indicala in Impostazioni, alla voce \(voce)."
        }

        /// `giornate.vuoto_giornate`
        static let vuotoGiornate = "Ancora niente: nella tua lega non è ancora finita nessuna giornata."

        /// `giornate.vuoto_calcolo`
        static let vuotoCalcolo = "Ancora niente: le giornate finite non sono ancora state calcolate. Succede da solo al prossimo aggiornamento dei dati."
    }
}
