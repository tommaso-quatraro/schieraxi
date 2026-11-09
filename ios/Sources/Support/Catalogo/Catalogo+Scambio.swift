// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/scambio.json, chiavi elencate in ios/testi/scambio.txt.

extension Catalogo {
    enum Scambio {
        /// `scambio.cosa_vuoi_fare`
        static let cosaVuoiFare = "Cosa vuoi fare"

        /// `scambio.trova_per`
        static let trovaPer = "Trova per me"

        /// `scambio.costruisci`
        static let costruisci = "Costruisci"

        /// `scambio.valuta_offerta`
        static let valutaOfferta = "Valuta un'offerta"

        /// `scambio.scambi_cui_guadagnate`
        static let scambiCuiGuadagnate = "Scambi in cui guadagnate punti tutti e due: l'altro li può accettare."

        /// `scambio.con_quale_squadra`
        static let conQualeSquadra = "Con quale squadra"

        /// `scambio.tutte_squadre`
        static let tutteSquadre = "Tutte le squadre"

        /// `scambio.quanti_giocatori_per`
        static let quantiGiocatoriPer = "Quanti giocatori per parte"

        /// `scambio.uno_contro_uno`
        static let unoControUno = "1 contro 1"

        /// `scambio.fino_a_2`
        static let finoA2 = "Fino a 2"

        /// `scambio.fino_a_3`
        static let finoA3 = "Fino a 3"

        /// `scambio.fino_a_4`
        static let finoA4 = "Fino a 4"

        /// `scambio.per_gli_scambi`
        static let perGliScambi = "Per gli scambi più grandi scegli una squadra: si cercano una alla volta e ci vogliono alcuni secondi."

        /// `scambio.cerca_scambi`
        static let cercaScambi = "Cerca scambi"

        /// `scambio.cerco_gli_scambi`
        static let cercoGliScambi = "Cerco gli scambi…"

        /// `scambio.nessuno_scambio_che`
        static let nessunoScambioChe = "Nessuno scambio che convenga a tutti e due."

        /// `scambio.servono_altre`
        static let servonoAltre = "Per gli scambi servono le rose delle altre squadre. Aggiungile quando vuoi: formazione e consigli funzionano già."

        /// `scambio.con`
        static let con = "con"

        /// `scambio.copia_bozza_del`
        static let copiaBozzaDel = "Copia bozza del messaggio"

        /// `scambio.chi_accetta_piu`
        static let chiAccettaPiu = "Chi accetta più volentieri"

        /// `scambio.squadre_che_guadagnano`
        static let squadreCheGuadagnano = "Le squadre che guadagnano di più dagli scambi qui sotto, e il reparto che ne beneficia di più."

        /// `scambio.n_scambi.one`, `scambio.n_scambi.other`
        static func nScambi(_ n: Int) -> String {
            n == 1 ? "\(n) scambio" : "\(n) scambi"
        }

        /// `scambio.migliora`
        static func migliora(p: String, reparto: String) -> String {
            "migliora i \(reparto) di \(p)%"
        }

        /// `scambio.archivio`
        static func archivio(n: String) -> String {
            "Archivio (\(n))"
        }

        /// `scambio.gli_ultimi_scambi`
        static let gliUltimiScambi = "Gli ultimi scambi che hai analizzato."

        /// `scambio.incolla_messaggio_che`
        static let incollaMessaggioChe = "Incolla il messaggio che hai ricevuto (basta che ci siano i cognomi): trovo chi dai e chi ricevi e ti dico se conviene."

        /// `scambio.messaggio_dell_offerta`
        static let messaggioDellOfferta = "Messaggio dell'offerta"

        /// `scambio.valuta_offerta_2`
        static let valutaOfferta2 = "Valuta l'offerta"

        /// `scambio.incolla_prima_messaggio`
        static let incollaPrimaMessaggio = "Incolla prima il messaggio"

        /// `scambio.leggo_messaggio`
        static let leggoMessaggio = "Leggo il messaggio…"

        /// `scambio.riga_con`
        static let rigaCon = "Con"

        /// `scambio.ambigui`
        static func ambigui(nomi: String) -> String {
            "Più giocatori con lo stesso cognome: \(nomi). Scegli a mano in Costruisci."
        }

        /// `scambio.non_trovato_giocatori`
        static let nonTrovatoGiocatori = "Non ho trovato giocatori di tutte e due le squadre nel messaggio: controlla i cognomi, oppure scegli a mano in Costruisci."

        /// `scambio.scegli_mano_costruisci`
        static let scegliManoCostruisci = "Scegli a mano in Costruisci"

        /// `scambio.vedi_giudizio_completo`
        static let vediGiudizioCompleto = "Vedi il giudizio completo"

        /// `scambio.impatto_sulla_tua`
        static let impattoSullaTua = "Impatto sulla tua rosa"

        /// `scambio.conta_anche_resto`
        static let contaAncheResto = "Conta anche il resto della squadra: se il reparto è già forte, un nuovo arrivato fa meno differenza."

        /// `scambio.in_totale.one`, `scambio.in_totale.other`
        static func inTotale(_ n: Int) -> String {
            n == 1 ? "In totale (prossima giornata)" : "In totale (prossime \(n) giornate)"
        }

        /// `scambio.stemma`
        static let stemma = "Stemma"

        /// `scambio.maglia`
        static let maglia = "Maglia"

        /// `scambio.stemma_aggiornato`
        static let stemmaAggiornato = "Stemma aggiornato"

        /// `scambio.maglia_aggiornata`
        static let magliaAggiornata = "Maglia aggiornata"

        /// `scambio.cambia_tipo`
        static func cambiaTipo(tipo: String) -> String {
            "Cambia \(tipo)"
        }

        /// `scambio.carica_tipo`
        static func caricaTipo(tipo: String) -> String {
            "Carica \(tipo)"
        }

        /// `scambio.formazione_consigliata_per`
        static let formazioneConsigliataPer = "Formazione consigliata per loro"

        /// `scambio.cambia_nome`
        static let cambiaNome = "Cambia il nome"

        /// `scambio.nuovo_nome`
        static let nuovoNome = "Nuovo nome della squadra"

        /// `scambio.nome_aiuto`
        static let nomeAiuto = "Su Leghe può restare il nome vecchio: quando reimporti le rose, SchieraXI aggiorna questa squadra."

        /// `scambio.nome_non_valido`
        static let nomeNonValido = "Scrivi un nome da 1 a 60 caratteri."

        /// `scambio.nome_salvato`
        static let nomeSalvato = "Nome salvato"

        /// `scambio.crediti_residui`
        static let creditiResidui = "Crediti residui"

        /// `scambio.salva`
        static let salva = "Salva"

        /// `scambio.crediti_salvati`
        static let creditiSalvati = "Crediti salvati"

        /// `scambio.scrivi_crediti_come`
        static let scriviCreditiCome = "Scrivi i crediti come numero intero, anche 0"

        /// `scambio.senza_ruolo`
        static let senzaRuolo = "Senza ruolo (da controllare)"

        /// `scambio.rose_aggiornate`
        static func roseAggiornate(data: String) -> String {
            "Rose aggiornate il \(data)"
        }

        /// `scambio.non_gioca`
        static let nonGioca = "non gioca"

        /// `scambio.nessuna_differenza_rispetto`
        static let nessunaDifferenzaRispetto = "Nessuna differenza rispetto a prima."

        /// `scambio.scambio_b`
        static let scambioB = "Scambio"

        /// `scambio.passaggio_b`
        static let passaggioB = "Passaggio"

        /// `scambio.prende_svincolati`
        static func prendeSvincolati(nomi: String, squadra: String) -> String {
            "\(squadra) prende dagli svincolati: \(nomi)"
        }

        /// `scambio.lascia_liberi`
        static func lasciaLiberi(nomi: String, squadra: String) -> String {
            "\(squadra) lascia liberi: \(nomi)"
        }

        /// `scambio.ultimi_aggiornamenti`
        static let ultimiAggiornamenti = "Ultimi aggiornamenti"

        /// `scambio.probabili_formazioni_raccolt`
        static let probabiliFormazioniRaccolt = "Probabili formazioni raccolte"
    }
}
