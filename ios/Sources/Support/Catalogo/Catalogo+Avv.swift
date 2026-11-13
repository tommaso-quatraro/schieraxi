// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/avv.json, chiavi elencate in ios/testi/avv.txt.

extension Catalogo {
    enum Avv {
        /// `avv.ore_tranq`
        static let oreTranq = "Ore tranquille"

        /// `avv.avevi_scelto_ore`
        static let aveviSceltoOre = "Avevi scelto le ore tranquille con inizio e fine alla stessa ora: non valgono, le ho spente. Riaccendile scegliendo due ore diverse (per esempio dalle 23 alle 7)."

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

        /// `avv.per_ogni_giornata`
        static let perOgniGiornata = "Per ogni giornata finita: i punti fatti (e quelli previsti prima) dalla formazione che hai schierato e dalla consigliata che SchieraXI ti ha mostrato prima della scadenza, con in evidenza i giocatori che hai cambiato. Il confronto conta le giornate in cui hai schierato undici diversi dalla consigliata. Se la consigliata di allora non era stata salvata, SchieraXI la ricostruisce con i dati di allora e la rosa di oggi: i suoi punti si vedono, ma quella giornata non entra nel confronto. Se non conosciamo la tua panchina la sceglie SchieraXI; con gli stessi titolari della consigliata, è la sua. Si aggiorna da solo dopo ogni giornata."

        /// `avv.n_di_11`
        static func nDi11(n: String) -> String {
            "\(n) di 11"
        }

        /// `avv.cambi`
        static let cambi = "Cambi di formazione e probabili"

        /// `avv.cambi_aiuto`
        static let cambiAiuto = "Infortunati, squalificati, titolari in panchina, forti cali"

        /// `avv.prima`
        static let prima = "Avviso se il consiglio cambia"

        /// `avv.prima_aiuto`
        static let primaAiuto = "Prima della scadenza, solo se le ultime notizie cambiano la formazione da schierare (per esempio un titolare non gioca): ti dice chi mettere. Al massimo due per giornata"

        /// `avv.prima_0`
        static let prima0 = "Spento"

        /// `avv.prima_30`
        static let prima30 = "30 minuti prima"

        /// `avv.prima_60`
        static let prima60 = "1 ora prima"

        /// `avv.prima_90`
        static let prima90 = "1 ora e mezza prima"

        /// `avv.prom_60`
        static let prom60 = "Promemoria un'ora prima"

        /// `avv.prom_60_aiuto`
        static let prom60Aiuto = "Con la formazione consigliata e i giocatori da controllare"

        /// `avv.prom_15`
        static let prom15 = "Promemoria 15 minuti prima"

        /// `avv.riepilogo`
        static let riepilogo = "Riepilogo a giornata finita"

        /// `avv.riepilogo_aiuto`
        static let riepilogoAiuto = "Punti fatti, attesi e massimo possibile con la tua rosa"

        /// `avv.copertura`
        static let copertura = "Reparto della rosa scoperto"

        /// `avv.copertura_aiuto`
        static let coperturaAiuto = "Ti avvisa se in un reparto hai pochi giocatori disponibili (infortunati, squalificati, diffidati)"

        /// `avv.ore_tranq_aiuto`
        static let oreTranqAiuto = "Niente avvisi nella fascia scelta: cambi e riepilogo arrivano appena finisce. Un promemoria che cade lì non viene mandato"

        /// `avv.dalle`
        static let dalle = "Dalle"

        /// `avv.alle`
        static let alle = "Alle"

        /// `avv.manda_avviso_prova`
        static let mandaAvvisoProva = "Manda un avviso di prova"
    }
}
