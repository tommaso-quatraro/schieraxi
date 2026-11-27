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

        /// `avv.certificato_titolo`
        static let certificatoTitolo = "SchieraXI · Da rinnovare"

        /// `avv.certificato_ore.one`, `avv.certificato_ore.other`
        static func certificatoOre(_ n: Int) -> String {
            n == 1 ? "Tra circa un'ora l'app smette di aprirsi. Rinnovala dall'app con cui l'hai installata." : "Tra circa \(n) ore l'app smette di aprirsi. Rinnovala dall'app con cui l'hai installata."
        }

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

        /// `avv.prova_su.one`, `avv.prova_su.other`
        static func provaSu(_ n: Int) -> String {
            n == 1 ? "Prova sull'ultima giornata giocata, usando solo i dati che c'erano prima. «Da fantamedia» è la formazione scelta con la fantamedia dei giocatori e la loro probabilità di giocare; per chi ha pochi voti la fantamedia si avvicina a quella del suo ruolo." : "Prova sulle ultime \(n) giornate giocate, usando per ognuna solo i dati che c'erano prima. «Da fantamedia» è la formazione scelta con la fantamedia dei giocatori e la loro probabilità di giocare; per chi ha pochi voti la fantamedia si avvicina a quella del suo ruolo."
        }

        /// `avv.errore_sui_fantavoti`
        static let erroreSuiFantavoti = "errore sui fantavoti (modello)"

        /// `avv.errore_fantamedia`
        static let erroreFantamedia = "errore (da fantamedia)"

        /// `avv.punti_formazione_modello`
        static let puntiFormazioneModello = "punti formazione (modello)"

        /// `avv.punti_medi`
        static func puntiMedi(f: String, m: String, p: String) -> String {
            "Punti medi per giornata: modello \(m), da fantamedia \(f), massimo possibile \(p). Errore più basso e punti più alti sono meglio."
        }

        /// `avv.mancano_probabili`
        static let mancanoProbabili = "Nelle giornate passate mancano le probabili formazioni, quindi dal vivo il modello va un po' meglio."

        /// `avv.prova_sola_dopo`
        static let provaSolaDopo = "La prova si fa da sola dopo gli aggiornamenti, appena c'è almeno una giornata finita."

        /// `avv.punti_delle_formazioni`
        static let puntiDelleFormazioni = "Punti delle formazioni giornata per giornata: modello, fantamedia e massimo possibile"

        /// `avv.modello_nbsp`
        static let modelloNbsp = "modello &nbsp;"

        /// `avv.fantamedia_nbsp`
        static let fantamediaNbsp = "da fantamedia &nbsp;"

        /// `avv.max_possibile`
        static let maxPossibile = "massimo possibile"

        /// `avv.giornate_da_a`
        static func giornateDaA(a: String, b: String) -> String {
            "dalla \(a)ª alla \(b)ª giornata di Serie A"
        }
    }
}
