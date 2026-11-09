// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/sd.json, chiavi elencate in ios/testi/sd.txt.

extension Catalogo {
    enum Sd {
        /// `sd.reg_titolo`
        static let regTitolo = "Registro delle giornate"

        /// `sd.reg_spiega`
        static let regSpiega = "Prima di ogni giornata l'app salva i numeri che mostra per tutta la Serie A e, a giornata finita, li confronta con com'è andata."

        /// `sd.reg_nessuna`
        static let regNessuna = "Ancora nessuna giornata misurata: i numeri arrivano il giorno dopo la fine della prima giornata salvata."

        /// `sd.reg_media.one`, `sd.reg_media.other`
        static func regMedia(_ n: Int) -> String {
            n == 1 ? "Media di \(n) giornata misurata." : "Media delle ultime \(n) giornate misurate."
        }

        /// `sd.reg_perse`
        static let regPerse = "Giornate perse"

        /// `sd.reg_perse_spiega`
        static let regPerseSpiega = "Non salvate prima della prima partita: non si possono più misurare."

        /// `sd.reg_i1`
        static let regI1 = "Errore del fantavoto atteso contro la fantamedia"

        /// `sd.reg_i2`
        static let regI2 = "«Gioca N%» contro chi ha giocato davvero"

        /// `sd.reg_i3`
        static let regI3 = "Punti veri dentro la fascia «8 volte su 10»"

        /// `sd.reg_i1_riga`
        static func regI1Riga(f: String, m: String, s: String, v: String) -> String {
            "\(v) (deve stare a \(s) o meno) · errore \(m) contro \(f)"
        }

        /// `sd.reg_i2_riga`
        static func regI2Riga(b: String, c: String, sb: String, sc: String) -> String {
            "scarto \(c) (al massimo \(sc)) · punteggio di Brier \(b) (al massimo \(sb))"
        }

        /// `sd.reg_i3_riga`
        static func regI3Riga(max: String, min: String, v: String) -> String {
            "\(v) (deve stare tra \(min) e \(max))"
        }

        /// `sd.reg_regge`
        static let regRegge = "regge"

        /// `sd.reg_non_regge`
        static let regNonRegge = "non regge"

        /// `sd.reg_servono.one`, `sd.reg_servono.other`
        static func regServono(_ n: Int) -> String {
            n == 1 ? "serve ancora \(n) giornata" : "servono ancora \(n) giornate"
        }

        /// `sd.reg_giornata`
        static func regGiornata(g: String, s: String) -> String {
            "\(g) · \(s)"
        }

        /// `sd.nessun_dato`
        static let nessunDato = "ancora nessun dato"

        /// `sd.nos_titolo`
        static let nosTitolo = "Gol attesi nostri (senza Understat)"

        /// `sd.nos_spiega`
        static let nosSpiega = "Prima di ogni giornata l'app salva anche i numeri calcolati solo con i voti di Fantacalcio.it e, a giornata finita, li confronta con quelli mostrati. Se le tre misure reggono per 8 giornate, si può fare a meno di Understat."

        /// `sd.nos_insieme`
        static let nosInsieme = "Le tre misure insieme"

        /// `sd.nos_per_giornata`
        static let nosPerGiornata = "Giornata per giornata"

        /// `sd.nos_media.one`, `sd.nos_media.other`
        static func nosMedia(_ n: Int, v: String) -> String {
            n == 1 ? "Media di \(n) giornata misurata, versione \(v) del calcolo." : "Media delle ultime \(n) giornate misurate, versione \(v) del calcolo."
        }

        /// `sd.nos_nessuna`
        static let nosNessuna = "Ancora nessuna giornata misurata: i numeri arrivano il giorno dopo la fine della prima giornata salvata."

        /// `sd.nos_errore`
        static let nosErrore = "Errore del fantavoto atteso contro i numeri mostrati"

        /// `sd.nos_punti`
        static let nosPunti = "Punti veri della formazione migliore contro i numeri mostrati"

        /// `sd.nos_gol`
        static let nosGol = "Gol attesi contro gol veri, per fasce"

        /// `sd.nos_reggono`
        static let nosReggono = "reggono"

        /// `sd.nos_non_reggono`
        static let nosNonReggono = "non reggono"

        /// `sd.nos_errore_riga`
        static func nosErroreRiga(s: String, v: String) -> String {
            "\(v) (deve stare a \(s) o meno)"
        }

        /// `sd.nos_punti_riga`
        static func nosPuntiRiga(s: String, v: String) -> String {
            "\(v) punti a rosa e giornata (deve stare a \(s) o più)"
        }

        /// `sd.nos_gol_riga`
        static func nosGolRiga(g: String, m: String, s: String, v: String) -> String {
            "scarto più grande \(v) gol a giocatore (al massimo \(s)) · gol attesi su veri \(g), con i numeri mostrati \(m)"
        }

        /// `sd.nos_g_misurata`
        static func nosGMisurata(e: String, g: String, p: String) -> String {
            "errore \(e) · punti \(p) · gol attesi su veri \(g)"
        }

        /// `sd.nos_g_versione`
        static func nosGVersione(v: String) -> String {
            "versione \(v), non conta"
        }

        /// `sd.nos_g_vuota`
        static let nosGVuota = "misurata, ma senza giocatori da confrontare"

        /// `sd.nos_g_da_misurare.one`, `sd.nos_g_da_misurare.other`
        static func nosGDaMisurare(_ n: Int) -> String {
            n == 1 ? "salvati i numeri di \(n) giocatore, da misurare a giornata finita" : "salvati i numeri di \(n) giocatori, da misurare a giornata finita"
        }

        /// `sd.cons_titolo`
        static let consTitolo = "Consiglio di formazione"

        /// `sd.cons_spiega`
        static let consSpiega = "Dopo ogni giornata l'app misura la consigliata mostrata prima della scadenza, nei Diari di tutti. La scelta semplice è quella di chi non ha l'app: schiera chi ha preso voto la giornata prima e ha la fantamedia più alta."

        /// `sd.cons_nessuna`
        static let consNessuna = "Ancora nessuna giornata misurata: i numeri arrivano dopo la fine della prima giornata."

        /// `sd.cons_formazioni.one`, `sd.cons_formazioni.other`
        static func consFormazioni(_ n: Int) -> String {
            n == 1 ? "\(n) formazione" : "\(n) formazioni"
        }

        /// `sd.cons_media.one`, `sd.cons_media.other`
        static func consMedia(_ n: Int, f: String) -> String {
            n == 1 ? "Media di \(n) giornata, su \(f)." : "Media delle ultime \(n) giornate, su \(f)."
        }

        /// `sd.cons_c1`
        static let consC1 = "Punti in più della consigliata rispetto alla scelta semplice"

        /// `sd.cons_c2`
        static let consC2 = "Cambi della consigliata nelle 24 ore prima della scadenza"

        /// `sd.cons_c3`
        static let consC3 = "Titolari che rischiano di non giocare"

        /// `sd.cons_c4`
        static let consC4 = "Scelte strane senza un motivo detto"

        /// `sd.cons_c1_riga`
        static func consC1Riga(s: String, v: String) -> String {
            "\(v) punti a giornata (deve stare a \(s) o più)"
        }

        /// `sd.cons_c1_schierata`
        static func consC1Schierata(w: String) -> String {
            "\(w) rispetto alla formazione schierata, quando è diversa"
        }

        /// `sd.cons_c2_riga`
        static func consC2Riga(c: String, n: String, s: String) -> String {
            "\(c) a formazione, in media · per meno di 1 punto atteso, senza un titolare diventato fuori o improbabile: \(n) (devono essere \(s))"
        }

        /// `sd.cons_c3_riga`
        static func consC3Riga(i: String, n: String, s: String) -> String {
            "sotto il 20% o fuori: \(i) · con un compagno di ruolo al 50% o più tra gli esclusi: \(n) (devono essere \(s))"
        }

        /// `sd.cons_c4_riga`
        static func consC4Riga(s: String, sp: String, st: String, v: String) -> String {
            "spiegate \(sp) su \(st) (devono essere tutte) · titolari senza un motivo loro in «Perché questo numero»: \(v) (al massimo \(s))"
        }

        /// `sd.tar_riga`
        static func tarRiga(s: String) -> String {
            "Taratura con le probabili: \(s)"
        }

        /// `sd.tar_in_attesa.one`, `sd.tar_in_attesa.other`
        static func tarInAttesa(_ n: Int) -> String {
            n == 1 ? "in attesa · \(n) giornata" : "in attesa · \(n) giornate"
        }

        /// `sd.tar_in_attesa_su.one`, `sd.tar_in_attesa_su.other`
        static func tarInAttesaSu(_ n: Int, m: String) -> String {
            n == 1 ? "in attesa · \(n) giornata su \(m)" : "in attesa · \(n) giornate su \(m)"
        }

        /// `sd.tar_attiva_dal`
        static func tarAttivaDal(d: String, v: String) -> String {
            "attiva dal \(d) (versione \(v))"
        }

        /// `sd.tar_attiva`
        static func tarAttiva(v: String) -> String {
            "attiva (versione \(v))"
        }

        /// `sd.tar_prova.one`, `sd.tar_prova.other`
        static func tarProva(_ n: Int, b: String, c: String, p: String) -> String {
            n == 1 ? "nell'ultima giornata Brier \(b) invece di \(p), scarto \(c)" : "nelle ultime \(n) giornate Brier \(b) invece di \(p), scarto \(c)"
        }

        /// `sd.tar_non_attiva`
        static let tarNonAttiva = "non attiva"

        /// `sd.tar_spenta`
        static let tarSpenta = "spenta a mano"

        /// `sd.tar_m_non_migliora`
        static let tarMNonMigliora = "non sbaglia meno dei numeri di partenza"

        /// `sd.tar_m_poche_giornate`
        static func tarMPocheGiornate(n: String) -> String {
            "la prova passa, si accende con 8 giornate (ora \(n))"
        }

        /// `sd.tar_m_fuori_soglia`
        static let tarMFuoriSoglia = "fuori dalle soglie di scarto o di Brier"

        /// `sd.tar_m_incoerente`
        static let tarMIncoerente = "i numeri tarati non sono validi"

        /// `sd.tar_m_peggiorata`
        static let tarMPeggiorata = "tornata ai numeri di partenza: sbagliava di più nelle ultime giornate"

        /// `sd.tar_m_scadenza_vicina`
        static let tarMScadenzaVicina = "cambio rimandato: la prima partita è tra meno di 24 ore"

        /// `sd.tar_m_spenta_a_mano`
        static let tarMSpentaAMano = "spenta a mano"

        /// `sd.giornate_giocate`
        static func giornateGiocate(n: String) -> String {
            "Giornate già giocate con le probabili raccolte: \(n)."
        }

        /// `sd.appena_finisce`
        static let appenaFinisce = "Appena finisce una giornata, qui si confronta chi era dato titolare con chi ha davvero preso voto."

        /// `sd.pochi_dati`
        static let pochiDati = " (pochi dati)"
    }
}
