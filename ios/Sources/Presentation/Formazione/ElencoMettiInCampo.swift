import Foundation

/// L'elenco di «Metti in campo» aperto (#778), come quello di `apriMettiInCampo` della web: chi entra e cosa ha risposto il server.
/// Lo prepara `FormazioneViewModel.mettiInCampo`; lo mostra `SceltaChiEsce`.
struct ElencoMettiInCampo: Identifiable {
    /// Cresce a ogni elenco aperto: la risposta di un elenco già chiuso, o sostituito da un altro, non vale.
    let id: Int
    /// Chi entra: la sua scheda nella Formazione.
    let entra: Giocatore
    /// Gli 11 in campo quando l'elenco si è aperto: se una rilettura ne porta altri, l'elenco si chiude
    /// (`FormazioneViewModel.chiudiElenchiSuperati`, come `chiudiSostituzione` della web).
    var titolari: [Int] = []
    var stato: Stato = .carico

    enum Stato {
        /// La domanda è partita: «Carico…».
        case carico
        /// Chi può lasciargli il posto, nell'ordine del server (vuoto: nessun titolare può lasciargli il posto).
        case uscite([Riga])
        /// Una frase del server da dire come informazione, non come guasto (`giocatore_bloccato`: la sua partita è cominciata).
        case informazione(String)
        /// La domanda non è riuscita: il motivo.
        case errore(String)
    }

    /// Una riga: il titolare che esce (la sua scheda nella Formazione) e i numeri del server per quel cambio.
    struct Riga: Identifiable {
        let esce: Giocatore
        /// Il modulo dopo il cambio («5-3-2»).
        let modulo: String?
        /// Il modulo dopo il cambio è diverso da quello di adesso: «Si passa al …».
        let cambiaModulo: Bool
        /// I punti attesi della formazione dopo il cambio meno quelli di adesso; nil se il server non li manda (niente numero).
        let differenza: Double?

        var id: Int { esce.id }
    }
}
