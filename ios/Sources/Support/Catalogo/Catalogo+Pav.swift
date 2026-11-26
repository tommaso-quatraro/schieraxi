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

        /// `pav.n_rose`
        static let nRose = "Le rose"

        /// `pav.n_squadra`
        static let nSquadra = "La tua squadra"

        /// `pav.n_tempi`
        static let nTempi = "I tempi della lega"

        /// `pav.n_widget`
        static let nWidget = "Il widget"

        /// `pav.n_avvisi`
        static let nAvvisi = "Gli avvisi"

        /// `pav.passo_di`
        static func passoDi(n: String, tot: String) -> String {
            "Passo \(n) di \(tot)"
        }

        /// `pav.piu_tardi`
        static let piuTardi = "Più tardi"

        /// `pav.piu_tardi_aiuto`
        static let piuTardiAiuto = "Chiude e ti ricorda i passi da fare"

        /// `pav.gia_fatto`
        static let giaFatto = "L'ho già fatto"

        /// `pav.rose_spiega`
        static let roseSpiega = "Esporta le rose da Leghe (Excel, CSV o testo copiato), poi incollale o scegli il file. Per cominciare basta anche solo la tua squadra."

        /// `pav.scegli_squadra`
        static let scegliSquadra = "Scegli la squadra"

        /// `pav.tempi_spiega`
        static let tempiSpiega = "Due domande, così i promemoria arrivano in tempo e le giornate hanno il numero giusto. Le risposte le trovi nelle impostazioni della tua lega su Leghe."

        /// `pav.scad_domanda`
        static let scadDomanda = "Quando si chiude la formazione?"

        /// `pav.scad_inizio`
        static let scadInizio = "All'inizio della prima partita"

        /// `pav.scad_minuti.one`, `pav.scad_minuti.other`
        static func scadMinuti(_ n: Int) -> String {
            n == 1 ? "\(n) minuto prima della prima partita" : "\(n) minuti prima della prima partita"
        }

        /// `pav.prima_domanda`
        static let primaDomanda = "Da quale giornata di Serie A è partita la lega?"

        /// `pav.prima_uno`
        static let primaUno = "Dalla 1ª, con il campionato"

        /// `pav.prima_n`
        static func primaN(n: String) -> String {
            "Dalla \(n)ª"
        }

        /// `pav.tempi_dove`
        static let tempiDove = "Puoi cambiarle quando vuoi in Impostazioni › Regole e scadenza."

        /// `pav.tempi_salva`
        static let tempiSalva = "Salva"

        /// `pav.tempi_non_letti`
        static let tempiNonLetti = "Non riesco a leggere i tempi salvati della tua lega, quindi non ho salvato niente: controlla i due valori e riprova."

        /// `pav.widget_spiega`
        static let widgetSpiega = "Tieni premuto sulla Home, tocca + e cerca SchieraXI. Il widget si collega da solo: se dice «Tocca per collegare», toccalo."

        /// `pav.collega_widget`
        static let collegaWidget = "Collega il widget"

        /// `pav.fatto_par`
        static let fattoPar = " (fatto)"

        /// `pav.saltato_par`
        static let saltatoPar = " (saltato)"

        /// `pav.hai_saltato`
        static func haiSaltato(nomi: String) -> String {
            "Hai saltato \(nomi): puoi riprenderli quando vuoi dalla Formazione."
        }

        /// `pav.hai_saltato_senza_rose`
        static func haiSaltatoSenzaRose(nomi: String) -> String {
            "Hai saltato \(nomi): li ritrovi toccando «Importa le rose» nella Formazione."
        }

        /// `pav.il_resto`
        static let ilResto = "In Impostazioni trovi anche gli avvisi e lo stemma della tua squadra."

        /// `pav.da_sistemare`
        static func daSistemare(n: String) -> String {
            "Giocatori da sistemare (\(n))"
        }

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
