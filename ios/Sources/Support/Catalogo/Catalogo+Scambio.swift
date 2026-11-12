// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/scambio.json, chiavi elencate in ios/testi/scambio.txt.

extension Catalogo {
    enum Scambio {
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
