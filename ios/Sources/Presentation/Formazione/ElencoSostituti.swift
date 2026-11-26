import Foundation

/// L'elenco di «Sostituisci» aperto, come quello di `apriSostituzione` della web: chi esce e cosa ha risposto il server
/// (`POST /api/formazione/sostituisci`). Lo prepara `FormazioneViewModel.sostituisci`; lo mostra `SceltaSostituto`.
struct ElencoSostituti: Identifiable {
    /// Cresce a ogni elenco aperto: la risposta di un elenco già chiuso, o sostituito da un altro, non vale.
    let id: Int
    /// Chi esce: la sua scheda nella Formazione.
    let uscente: Giocatore
    var stato: Stato = .carico

    enum Stato {
        /// La domanda è partita: «Carico…».
        case carico
        /// Chi può prendere il suo posto, nell'ordine del server (vuoto: nessun altro giocatore di questo ruolo in rosa).
        case entrate([Riga])
        /// Una frase del server da dire come informazione, non come guasto (`giocatore_bloccato`: la sua partita è cominciata).
        case informazione(String)
        /// La domanda non è riuscita: il motivo.
        case errore(String)
    }

    /// Una riga: chi entra (la sua scheda nella Formazione), il numero del server per quel cambio e dove sta adesso.
    struct Riga: Identifiable {
        let entra: Giocatore
        /// I punti attesi della formazione dopo il cambio meno quelli di adesso; nil se il server non li manda (niente numero).
        let differenza: Double?
        /// Dove sta chi entra nella formazione in campo: «Panchina 2», «Non schierato» (`PostoInFormazione`, come la web).
        var posto: String? = nil

        var id: Int { entra.id }
    }
}
