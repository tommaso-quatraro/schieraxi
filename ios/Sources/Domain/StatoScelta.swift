import Foundation

/// La riga dello stato della scelta sotto il campo, come `rigaStato` di `mostraFormazione` della web (#616, #673): cinque stati
/// («È la consigliata.», «L'hai cambiata tu: …», «La consigliata è cambiata da quando l'hai salvata: …», la scelta che non vale
/// più, la giornata chiusa con le sue tre frasi) e la scelta che non si è letta. Si confrontano gli 11 in campo con quelli della
/// consigliata; la scelta salvata (`GET /api/scelta`) dice se la consigliata era sua. Logica pura, provata in `StatoSceltaTests`.
enum StatoScelta: Equatable {
    /// Non si dice niente: la formazione di un'altra squadra, o la copia sul telefono mentre arrivano i dati nuovi.
    case nessuno
    /// La scelta salvata non si è letta: un errore con «Riprova», e i comandi che scrivono restano spenti (si scriverebbe sopra una
    /// scelta che non si è vista). Anche sulla copia e a giornata chiusa se il server dice che ce n'è una: in campo c'è la
    /// consigliata, e non va presa per la tua.
    case nonLetta
    /// Gli 11 in campo sono quelli della consigliata.
    case consigliata
    /// Gli 11 in campo non sono quelli della consigliata e li hai cambiati tu: quanti sono diversi e i punti attesi in più o in
    /// meno rispetto a lei (nil se manca uno dei due numeri).
    case cambiata(diversi: Int, punti: Double?)
    /// Avevi salvato la consigliata (`era_consigliata`) ed è lei a essere cambiata dopo.
    case superata(diversi: Int, punti: Double?)
    /// La scelta salvata non si può più schierare: vale la consigliata, finché non torni alla consigliata o la cambi.
    case nonValida
    /// Giornata chiusa (scadenza passata): niente più da cambiare.
    case chiusa(Chiusura)

    /// Le tre frasi della giornata chiusa.
    enum Chiusura: Equatable, Sendable {
        /// Nessuna scelta salvata: vale la consigliata.
        case senzaScelta
        /// Vale quella che hai salvato.
        case tua
        /// La tua non si può schierare: vale la consigliata.
        case nonValida
    }

    /// - Parameters:
    ///   - mia: si guarda la propria formazione (per un'altra squadra non si dice niente).
    ///   - letta: la scelta della giornata è stata letta dal server (anche «nessuna»).
    ///   - copia: si vedono i dati salvati sul telefono, non ancora quelli nuovi.
    ///   - chiusa: la giornata è chiusa (viene prima di tutto il resto, come sulla web).
    ///   - salvata: la scelta salvata (nil = nessuna).
    ///   - nonValida: la scelta salvata non si può più schierare.
    ///   - titolari: gli 11 in campo; `consigliati`: quelli della consigliata. L'ordine non conta.
    ///   - punti, puntiConsigliata: i punti attesi degli 11 in campo e della consigliata.
    ///   - salvataNonLetta: il server dice che c'è una scelta salvata che vale (`stato_scelta` «valida») e non si è letta: in campo
    ///     non c'è la formazione che conta, e lo si dice anche sulla copia e a giornata chiusa.
    static func calcola(mia: Bool, letta: Bool, copia: Bool, chiusa: Bool, salvata: SceltaSalvata?, nonValida: Bool,
                        titolari: [Int], consigliati: [Int], punti: Double?, puntiConsigliata: Double?,
                        salvataNonLetta: Bool = false) -> StatoScelta {
        guard mia else { return .nessuno }
        // non letta: lo si dice, tranne sulla copia del telefono (i dati nuovi stanno arrivando) e a giornata chiusa, se non si sa
        // che c'è una scelta salvata
        guard letta else { return (chiusa || copia) && !salvataNonLetta ? .nessuno : .nonLetta }
        if chiusa { return .chiusa(nonValida ? .nonValida : salvata != nil ? .tua : .senzaScelta) }
        if nonValida { return .nonValida }
        let dentro = Set(consigliati)
        let diversi = Set(titolari).filter { !dentro.contains($0) }.count
        guard diversi > 0 else { return .consigliata }
        var differenza: Double?
        if let punti, let puntiConsigliata, punti.isFinite, puntiConsigliata.isFinite { differenza = punti - puntiConsigliata }
        return salvata?.eraConsigliata == true ? .superata(diversi: diversi, punti: differenza)
                                                : .cambiata(diversi: diversi, punti: differenza)
    }

    /// La frase della riga, uguale alla web (`formazione.stato_*` del catalogo comune); vuota per `nessuno`.
    var frase: String {
        switch self {
        case .nessuno: return ""
        case .nonLetta: return Catalogo.Formazione.sceltaNonLetta
        case .consigliata: return Catalogo.Formazione.statoEConsigliata
        case .cambiata(let n, let punti): return Catalogo.Formazione.statoCambiata(n, d: Self.differenza(punti))
        case .superata(let n, let punti): return Catalogo.Formazione.statoSuperata(n, d: Self.differenza(punti))
        case .nonValida: return Catalogo.Formazione.statoNonValidaOra
        case .chiusa(.senzaScelta): return Catalogo.Formazione.statoChiusa
        case .chiusa(.tua): return Catalogo.Formazione.statoChiusaTua
        case .chiusa(.nonValida): return Catalogo.Formazione.statoChiusaNonValida
        }
    }

    /// « (−0,4 punti attesi)»: quanto vale la tua rispetto alla consigliata, con il nome del numero (`formazione.stato_punti`) e il
    /// segno come la web (`Formato.conSegno`). Vuota senza i due numeri.
    static func differenza(_ punti: Double?) -> String {
        guard let punti, punti.isFinite else { return "" }
        return " (" + Catalogo.Formazione.statoPunti(d: Formato.conSegno(punti)) + ")"
    }

    /// La stessa frase per VoiceOver: il «·» diventa una virgola (com'è, si sente il nome del simbolo).
    var voce: String { frase.replacingOccurrences(of: " · ", with: ", ") }

    /// «Torna alla consigliata» accanto alla frase: quando in campo c'è una tua scelta (cambiata o superata) o quella salvata non
    /// vale più. A giornata chiusa mai.
    var conTorna: Bool {
        switch self {
        case .cambiata, .superata, .nonValida: return true
        case .nessuno, .nonLetta, .consigliata, .chiusa: return false
        }
    }

    /// Simbolo SF della riga, oltre al colore: lo stato non si legge dal solo colore.
    var simbolo: String {
        switch self {
        case .nessuno: return ""
        case .nonLetta: return "exclamationmark.triangle.fill"
        case .consigliata: return "checkmark.circle"
        case .cambiata, .superata: return "pencil.circle"
        case .nonValida: return "exclamationmark.triangle.fill"
        case .chiusa: return "lock.fill"
        }
    }

    enum Tono: Equatable { case neutro, attenzione, malus }

    /// Il colore del segno: rosso per la scelta che non si legge o non vale più, arancio per la consigliata cambiata, grigio il resto.
    var tono: Tono {
        switch self {
        case .nonLetta, .nonValida: return .malus
        case .superata: return .attenzione
        case .nessuno, .consigliata, .cambiata, .chiusa: return .neutro
        }
    }
}

/// Il modulo («3-4-3») contato dai ruoli dei titolari: si sa subito, senza aspettare il server.
enum ModuloTitolari {
    static func modulo(ruoli: [String]) -> String {
        let conta = { (r: String) in ruoli.filter { $0.uppercased() == r }.count }
        return "\(conta("D"))-\(conta("C"))-\(conta("A"))"
    }
}

/// Una scelta salvata vale ancora? 11 titolari diversi, tutti della rosa. Senza rosa (scheda mancante o vuota) non si
/// giudica: la scelta NON si cancella.
enum ValiditaScelta {
    enum Esito: Equatable { case valida, nonValida, nonSiSa }

    static func controlla(titolari: [Int], rosa: [String: Giocatore]?) -> Esito {
        guard let rosa, !rosa.isEmpty else { return .nonSiSa }
        let diversi = Set(titolari)
        guard diversi.count == 11, titolari.count == 11, diversi.allSatisfy({ rosa[String($0)] != nil }) else { return .nonValida }
        return .valida
    }

    /// Il codice d'errore del server per una formazione che non si può valutare (non 11 della rosa, modulo non ammesso).
    static let codiceNonValida = "formazione_non_valida"
}
