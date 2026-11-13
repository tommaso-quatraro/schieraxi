// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/formazione.json, chiavi elencate in ios/testi/formazione.txt.

extension Catalogo {
    enum Formazione {
        /// `formazione.stato_e_consigliata`
        static let statoEConsigliata = "È la consigliata."

        /// `formazione.stato_cambiata.one`, `formazione.stato_cambiata.other`
        static func statoCambiata(_ n: Int, d: String) -> String {
            n == 1 ? "L'hai cambiata tu: \(n) titolare diverso dalla consigliata\(d)." : "L'hai cambiata tu: \(n) titolari diversi dalla consigliata\(d)."
        }

        /// `formazione.stato_superata.one`, `formazione.stato_superata.other`
        static func statoSuperata(_ n: Int, d: String) -> String {
            n == 1 ? "La consigliata è cambiata da quando l'hai salvata: \(n) titolare diverso\(d)." : "La consigliata è cambiata da quando l'hai salvata: \(n) titolari diversi\(d)."
        }

        /// `formazione.stato_punti`
        static func statoPunti(d: String) -> String {
            "\(d) punti attesi"
        }

        /// `formazione.stato_non_valida_ora`
        static let statoNonValidaOra = "La formazione che avevi salvato non è più valida: vale la consigliata."

        /// `formazione.stato_chiusa`
        static let statoChiusa = "Giornata iniziata: la formazione è chiusa"

        /// `formazione.stato_chiusa_tua`
        static let statoChiusaTua = "Giornata iniziata: la formazione è chiusa · vale quella che hai salvato"

        /// `formazione.stato_chiusa_non_valida`
        static let statoChiusaNonValida = "Giornata iniziata: la formazione è chiusa · vale la consigliata, la tua non è più valida"

        /// `formazione.torna_alla_consigliata`
        static let tornaAllaConsigliata = "Torna alla consigliata"

        /// `formazione.scelta_non_letta`
        static let sceltaNonLetta = "Non riesco a leggere la formazione che hai salvato: finché non la leggo non si può cambiare niente."

        /// `formazione.copia_ferma`
        static let copiaFerma = "Finché non arrivano quelli nuovi la formazione non si può cambiare."

        /// `formazione.sto_ancora_ricalcolando`
        static let stoAncoraRicalcolando = "Sto ancora ricalcolando: un attimo"

        /// `formazione.si_chiude`
        static func siChiude(quando: String) -> String {
            "Si chiude \(quando)"
        }

        /// `formazione.fra`
        static func fra(tempo: String) -> String {
            "fra \(tempo)"
        }

        /// `formazione.chiusa_breve`
        static let chiusaBreve = "Formazione chiusa"

        /// `formazione.in_corso`
        static let inCorso = "in corso"

        /// `formazione.punti_finora`
        static let puntiFinora = "punti finora"

        /// `formazione.circa_fine`
        static func circaFine(n: String) -> String {
            "circa \(n) a fine giornata"
        }

        /// `formazione.punti_e_attesi`
        static func puntiEAttesi(n: String) -> String {
            "punti (attesi \(n))"
        }

        /// `formazione.punti`
        static let punti = "punti"

        /// `formazione.come_andata`
        static let comeAndata = "Com'è andata"

        /// `formazione.per_la_prossima`
        static func perLaProssima(g: String, m: String) -> String {
            "\(g): è già iniziata. Questa è la formazione per la \(m)."
        }

        /// `formazione.modulo`
        static let modulo = "Modulo"

        /// `formazione.opzione_consigliato`
        static func opzioneConsigliato(modulo: String, punti: String) -> String {
            "\(modulo) · \(punti) punti · consigliato"
        }

        /// `formazione.opzione_modulo`
        static func opzioneModulo(modulo: String, punti: String) -> String {
            "\(modulo) · \(punti) punti"
        }

        /// `formazione.punti_attesi`
        static let puntiAttesi = "punti attesi"

        /// `formazione.di_solito`
        static func diSolito(a: String, b: String) -> String {
            "di solito fra \(a) e \(b)"
        }

        /// `formazione.oscilla`
        static func oscilla(n: String) -> String {
            "oscilla di ±\(n)"
        }

        /// `formazione.calcolo`
        static let calcolo = "Calcolo la formazione migliore…"

        /// `formazione.mancano_probabili_formazioni`
        static let mancanoProbabiliFormazioni = "Le probabili formazioni di questa giornata non sono ancora uscite: per ora uso le presenze recenti. Il consiglio si aggiorna da solo quando escono."

        /// `formazione.stai_guardando_formazione`
        static let staiGuardandoFormazione = "Stai guardando la formazione di"

        /// `formazione.torna_alla_tua`
        static let tornaAllaTua = "Torna alla tua"

        /// `formazione.chiusa`
        static let chiusa = "La formazione di questa giornata è chiusa: le partite sono cominciate."

        /// `formazione.bloccati`
        static let bloccati = "Chi gioca in una partita già cominciata non si può più spostare."

        /// `formazione.copia_lega`
        static let copiaLega = "Copia per l'app della lega"

        /// `formazione.copiata_lega`
        static let copiataLega = "Formazione copiata: ora mettila nell'app della lega"

        /// `formazione.non_copio`
        static let nonCopio = "Non riesco a copiare: tieni premuto sul testo"

        /// `formazione.messa`
        static let messa = "L'ho messa"

        /// `formazione.decisione_punti`
        static func decisionePunti(d: String) -> String {
            "\(d) punti attesi."
        }

        /// `formazione.usa_consigliata`
        static let usaConsigliata = "Usa la consigliata"

        /// `formazione.quest_ordine_entra`
        static let questOrdineEntra = "Entra il primo che può sostituire chi resta senza voto."

        /// `formazione.non_schierati`
        static func nonSchierati(n: String) -> String {
            "Non schierati (\(n))"
        }

        /// `formazione.indisponibili`
        static func indisponibili(n: String) -> String {
            "Infortunati e squalificati (\(n))"
        }

        /// `formazione.senza_dati`
        static func senzaDati(nomi: String) -> String {
            "Senza dati per questa giornata: \(nomi)"
        }

        /// `formazione.voce_fv`
        static func voceFv(fv: String) -> String {
            "fantavoto atteso \(fv)"
        }

        /// `formazione.voce_gioca`
        static func voceGioca(p: String) -> String {
            "gioca al \(p) per cento"
        }

        /// `formazione.voce_gioca_v`
        static func voceGiocaV(p: String) -> String {
            "gioca all'\(p) per cento"
        }

        /// `formazione.sostituisci`
        static let sostituisci = "Sostituisci"

        /// `formazione.al_posto_di`
        static func alPostoDi(nome: String) -> String {
            "Al posto di \(nome)"
        }

        /// `formazione.sost_spiega`
        static func sostSpiega(nome: String) -> String {
            "Stesso ruolo, dalla tua rosa. Il numero grande sono i punti attesi in più o in meno rispetto a \(nome)."
        }

        /// `formazione.punti_rispetto`
        static func puntiRispetto(nome: String) -> String {
            "punti attesi rispetto a \(nome)"
        }

        /// `formazione.fv_atteso_breve`
        static func fvAttesoBreve(fv: String) -> String {
            "atteso \(fv)"
        }

        /// `formazione.nessun_altro_giocatore`
        static let nessunAltroGiocatore = "Nessun altro giocatore di questo ruolo in rosa."

        /// `formazione.partita_casa`
        static func partitaCasa(avv: String, quando: String) -> String {
            "In casa contro \(avv) · \(quando)"
        }

        /// `formazione.partita_fuori`
        static func partitaFuori(avv: String, quando: String) -> String {
            "In trasferta contro \(avv) · \(quando)"
        }

        /// `formazione.se_gioca`
        static let seGioca = "se gioca"

        /// `formazione.perche_titolare`
        static let percheTitolare = "Perché è titolare"

        /// `formazione.incerto`
        static func incerto(p: String, riserva: String) -> String {
            "Titolare anche se incerto (gioca \(p)): se non gioca, in panchina c'è \(riserva) che gioca quasi di sicuro, e insieme valgono di più."
        }

        /// `formazione.ultimi_voti`
        static let ultimiVoti = "Ultimi voti"

        /// `formazione.tutti_numeri`
        static let tuttiNumeri = "Tutti i numeri"

        /// `formazione.questa_partita`
        static let questaPartita = "Questa partita"
    }
}
