// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/imp.json, chiavi elencate in ios/testi/imp.txt.

extension Catalogo {
    enum Imp {
        /// `imp.sez_avvisi`
        static let sezAvvisi = "Avvisi"

        /// `imp.avvisi_qui`
        static let avvisiQui = "Avvisi su questo dispositivo"

        /// `imp.avvisi_qui_aiuto_app`
        static let avvisiQuiAiutoApp = "Un promemoria prima della scadenza, se non hai spuntato «L'ho messa»"

        /// `imp.avvisi_qui_aiuto_web`
        static let avvisiQuiAiutoWeb = "Il promemoria arriva anche dalla web app sulla Home: se ti arriva due volte, spegni gli avvisi qui o nella web app"

        /// `imp.ore_tranquille_aiuto`
        static func oreTranquilleAiuto(a: String, da: String) -> String {
            "Niente avvisi dalle \(da) alle \(a)"
        }

        /// `imp.ore_tranquille_spente`
        static func oreTranquilleSpente(a: String, da: String) -> String {
            "Spente. Se le accendi: niente avvisi dalle \(da) alle \(a)"
        }

        /// `imp.lega`
        static let lega = "La mia lega"

        /// `imp.regole`
        static let regole = "Regole e scadenza"

        /// `imp.regole_sub`
        static let regoleSub = "Punteggi, moduli e quando si chiude la formazione"

        /// `imp.mia_squadra_nessuna`
        static let miaSquadraNessuna = "Non l'hai ancora scelta"

        /// `imp.altre_squadre`
        static let altreSquadre = "Le altre squadre"

        /// `imp.account`
        static let account = "Il tuo account"

        /// `imp.aspetto`
        static let aspetto = "Aspetto"

        /// `imp.informazioni`
        static let informazioni = "Informazioni"

        /// `imp.informazioni_sub`
        static let informazioniSub = "Novità, privacy, termini, crediti e versione"

        /// `imp.gestione`
        static let gestione = "Gestione"

        /// `imp.aggiorna_spiega`
        static let aggiornaSpiega = "Scarica adesso listone, voti e probabili formazioni dalle fonti accese. Di solito succede da solo."

        /// `imp.avanzate`
        static let avanzate = "Avanzate"
    }
}
