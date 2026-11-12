// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/formazione.json, chiavi elencate in ios/testi/formazione.txt.

extension Catalogo {
    enum Formazione {
        /// `formazione.la_tua_scelta`
        static let laTuaScelta = "la tua scelta"

        /// `formazione.modulo_consigliato`
        static let moduloConsigliato = "modulo consigliato"

        /// `formazione.modulo_scelto`
        static let moduloScelto = "modulo scelto"

        /// `formazione.alle`
        static func alle(ora: String) -> String {
            "alle \(ora)"
        }

        /// `formazione.giorno_alle`
        static func giornoAlle(giorno: String, ora: String) -> String {
            "\(giorno) alle \(ora)"
        }

        /// `formazione.stato_consigliata`
        static let statoConsigliata = "Stai vedendo la consigliata: non hai salvato una tua formazione."

        /// `formazione.stato_altro_modulo`
        static let statoAltroModulo = "Stai vedendo un altro modulo, non quello consigliato: non l'hai salvato."

        /// `formazione.stato_salvata`
        static let statoSalvata = "La tua formazione è salvata"

        /// `formazione.stato_salvata_quando`
        static func statoSalvataQuando(quando: String) -> String {
            "La tua formazione è salvata (\(quando))"
        }

        /// `formazione.stato_modificata`
        static let statoModificata = "Modifiche non salvate"

        /// `formazione.stato_modificata_quando`
        static func statoModificataQuando(quando: String) -> String {
            "Modifiche non salvate · salvata \(quando)"
        }

        /// `formazione.stato_mano`
        static let statoMano = "Modifica a mano non ancora salvata"

        /// `formazione.stato_non_valida`
        static let statoNonValida = "La formazione salvata non è più valida: rifalla o torna alla consigliata."

        /// `formazione.stato_chiusa`
        static let statoChiusa = "Giornata iniziata: la formazione è chiusa"

        /// `formazione.stato_chiusa_tua`
        static let statoChiusaTua = "Giornata iniziata: la formazione è chiusa · vale quella che hai salvato"

        /// `formazione.stato_chiusa_non_valida`
        static let statoChiusaNonValida = "Giornata iniziata: la formazione è chiusa · vale la consigliata, la tua non è più valida"

        /// `formazione.calcolo`
        static let calcolo = "Calcolo la formazione migliore…"

        /// `formazione.punti_attesi`
        static let puntiAttesi = "punti attesi"

        /// `formazione.mancano_probabili_formazioni`
        static let mancanoProbabiliFormazioni = "Le probabili formazioni di questa giornata non sono ancora uscite: per ora uso le presenze recenti. Il consiglio si aggiorna da solo quando escono."

        /// `formazione.stai_guardando_formazione`
        static let staiGuardandoFormazione = "Stai guardando la formazione di"

        /// `formazione.torna_alla_tua`
        static let tornaAllaTua = "Torna alla tua"

        /// `formazione.titolari`
        static let titolari = "Titolari"

        /// `formazione.tocca_sostituire`
        static let toccaSostituire = "Tocca ✎ per sostituire un titolare: i punti attesi si ricalcolano."

        /// `formazione.ballottaggio_alternative_vic`
        static let ballottaggioAlternativeVic = "In ballottaggio con"

        /// `formazione.quasi_pari`
        static let quasiPari = "quasi pari"

        /// `formazione.quest_ordine_entra`
        static let questOrdineEntra = "Entra il primo che può sostituire chi resta senza voto."

        /// `formazione.fuori_dalla`
        static func fuoriDalla(n: String) -> String {
            "Fuori dalla formazione (\(n))"
        }

        /// `formazione.senza_dati`
        static func senzaDati(nomi: String) -> String {
            "Senza dati per questa giornata: \(nomi)"
        }

        /// `formazione.copia_formazione`
        static let copiaFormazione = "Copia il testo"

        /// `formazione.modifica_mano`
        static let modificaMano = "Modifica a mano"

        /// `formazione.rispetto`
        static func rispetto(d: String, n: String) -> String {
            "\(d) rispetto alla consigliata con lo stesso modulo (\(n))."
        }

        /// `formazione.salva_come_mia`
        static let salvaComeMia = "Salva come mia scelta"

        /// `formazione.salva_modifiche`
        static let salvaModifiche = "Salva le modifiche"

        /// `formazione.giocatori_dello_stesso`
        static let giocatoriDelloStesso = "Giocatori dello stesso ruolo della tua rosa. Per cambiare ruolo scegli un altro modulo."

        /// `formazione.nessun_altro_giocatore`
        static let nessunAltroGiocatore = "Nessun altro giocatore di questo ruolo in rosa."

        /// `formazione.al_posto_di`
        static func alPostoDi(nome: String) -> String {
            "Al posto di \(nome)"
        }

        /// `formazione.salva_questa`
        static let salvaQuesta = "Salva questa"

        /// `formazione.annulla_modifiche`
        static let annullaModifiche = "Annulla modifiche"

        /// `formazione.torna_alla_consigliata`
        static let tornaAllaConsigliata = "Torna alla consigliata"

        /// `formazione.chiusa`
        static let chiusa = "La formazione di questa giornata è chiusa: le partite sono cominciate."

        /// `formazione.bloccati`
        static let bloccati = "Chi gioca in una partita già cominciata non si può più spostare."

        /// `formazione.copiata`
        static let copiata = "Formazione copiata: incollala dove vuoi"

        /// `formazione.salvata_come_tua`
        static let salvataComeTua = "Salvata come tua scelta"
    }
}
