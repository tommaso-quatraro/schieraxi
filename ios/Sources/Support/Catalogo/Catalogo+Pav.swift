// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/pav.json, chiavi elencate in ios/testi/pav.txt.

extension Catalogo {
    enum Pav {
        /// `pav.primo_avvio`
        static let primoAvvio = "Primo avvio"

        /// `pav.salta`
        static let salta = "Salta"

        /// `pav.tutto_pronto_mister`
        static let tuttoProntoMister = "Tutto pronto, Mister"

        /// `pav.hai_finito`
        static let haiFinito = "Hai finito la configurazione."

        /// `pav.non_sono_riuscito`
        static let nonSonoRiuscito = "Non sono riuscito a ricordare a che punto sei: puoi continuare lo stesso"

        /// `pav.permesso_negato_abilita`
        static let permessoNegatoAbilita = "Permesso negato: abilita gli avvisi per l'app nelle impostazioni del telefono"

        /// `pav.regole_comuni`
        static func regoleComuni(regole: String) -> String {
            "I fantavoti attesi usano i punteggi più comuni delle leghe classic (gol 3, assist 1, ammonizione −0,5), finché non metti quelli della tua lega in \(regole)."
        }

        /// `pav.vai_formazione`
        static let vaiFormazione = "Vai alla Formazione"

        /// `pav.avvisi_spiega`
        static let avvisiSpiega = "Un promemoria prima della scadenza, se non hai spuntato «L'ho messa»."

        /// `pav.scegli_file`
        static let scegliFile = "Scegli il file (Excel o CSV)"

        /// `pav.incolla_testo_delle`
        static let incollaTestoDelle = "Esporta le rose da Leghe (Excel, CSV o testo copiato), poi incolla qui il testo o scegli il file. Per cominciare basta anche solo la tua squadra."

        /// `pav.quale_squadra_tua`
        static let qualeSquadraTua = "Quale squadra è la tua?"

        /// `pav.questa_mia`
        static let questaMia = "Questa è la mia"
    }
}
