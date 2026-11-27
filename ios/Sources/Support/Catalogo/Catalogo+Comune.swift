// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/comune.json, chiavi elencate in ios/testi/comune.txt.

extension Catalogo {
    enum Comune {
        /// `comune.importa_rose`
        static let importaRose = "Importa le rose"

        /// `comune.riprova`
        static let riprova = "Riprova"

        /// `comune.cambiato_ricarico`
        static let cambiatoRicarico = "Questi dati sono stati cambiati da un altro dispositivo. Sto ricaricando la versione nuova…"

        /// `comune.cambiato_altrove`
        static let cambiatoAltrove = "Questi dati sono stati cambiati da un altro dispositivo."

        /// `comune.prima_rose`
        static let primaRose = "Prima le tue rose"

        /// `comune.importa_spiega`
        static let importaSpiega = "Importa le rose della tua lega: poi ti dico ogni giornata chi schierare. Ci vuole un minuto."

        /// `comune.carico`
        static let carico = "Carico…"

        /// `comune.rete_no`
        static let reteNo = "Non riesco a collegarmi: controlla internet e riprova"

        /// `comune.server_non_risponde`
        static let serverNonRisponde = "Il server non risponde: riprova fra poco"

        /// `comune.calcolo_attesa`
        static let calcoloAttesa = "Un attimo, mister: ci sto lavorando."

        /// `comune.calcolo_lungo`
        static let calcoloLungo = "Il calcolo sta durando più del previsto: riprova tra poco."

        /// `comune.cache_errore`
        static func cacheErrore(errore: String, giorno: String, ora: String) -> String {
            "\(errore) (dati salvati il \(giorno) alle \(ora), potrebbero non essere aggiornati)."
        }

        /// `comune.cache_offline`
        static func cacheOffline(giorno: String, ora: String) -> String {
            "Non riesco a collegarmi: questi sono i dati salvati il \(giorno) alle \(ora)."
        }

        /// `comune.attesa_secondi.one`, `comune.attesa_secondi.other`
        static func attesaSecondi(_ n: Int) -> String {
            n == 1 ? "\(n) secondo" : "\(n) secondi"
        }

        /// `comune.attesa_minuti`
        static func attesaMinuti(n: String) -> String {
            "\(n) minuti"
        }

        /// `comune.attesa_ora`
        static func attesaOra(n: String) -> String {
            "circa \(n) ora"
        }

        /// `comune.attesa_ore`
        static func attesaOre(n: String) -> String {
            "circa \(n) ore"
        }
    }
}
