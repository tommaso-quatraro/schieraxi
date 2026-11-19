// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/avv.json, chiavi elencate in ios/testi/avv.txt.

extension Catalogo {
    enum Avv {
        /// `avv.ore_tranq`
        static let oreTranq = "Ore tranquille"

        /// `avv.avevi_scelto_ore`
        static let aveviSceltoOre = "Avevi scelto le ore tranquille con inizio e fine alla stessa ora: non valgono, le ho spente. Se le riaccendi valgono dalle 23 alle 7."

        /// `avv.permesso_negato_abilita`
        static let permessoNegatoAbilita = "Permesso negato: abilita le notifiche per l'app nelle impostazioni del telefono"

        /// `avv.notifiche_disattivate_questo`
        static let notificheDisattivateQuesto = "Notifiche disattivate su questo dispositivo"

        /// `avv.nativa`
        static let nativa = "Avvisi anche per l'app nativa"

        /// `avv.nativa_aiuto`
        static let nativaAiuto = "Arrivano con l'app ntfy e il tocco apre l'app iOS nativa. Con «Avvisi su questo dispositivo» acceso potresti riceverli doppi"

        /// `avv.nome_del_giocatore`
        static let nomeDelGiocatore = "Nome del giocatore"

        /// `avv.scrivi_almeno_due`
        static let scriviAlmenoDue = "Scrivi almeno due lettere."

        /// `avv.nessun_giocatore_trovato`
        static let nessunGiocatoreTrovato = "Nessun giocatore trovato."

        /// `avv.quot`
        static func quot(n: String) -> String {
            "quotazione \(n)"
        }

        /// `avv.n_di_11`
        static func nDi11(n: String) -> String {
            "\(n) di 11"
        }
    }
}
