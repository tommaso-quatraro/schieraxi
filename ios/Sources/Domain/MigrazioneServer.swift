import Foundation

/// Chi aggiorna da una versione vecchia può avere salvato l'indirizzo di un server che non c'è più (un indirizzo privato di prova).
/// Qui si decide quando lasciarlo e passare al server predefinito. Nessun indirizzo vero sta nel codice: si riconosce solo
/// il tipo generico «.<dominio privato>» (indirizzi di rete privata) e il caso «non risponde mentre il predefinito sì».
enum MigrazioneServer {
    static let chiaveIndirizzo = "indirizzo"
    /// true dopo uno spostamento, finché la persona non ha rifatto l'accesso: serve a mostrare il messaggio nella schermata Accedi.
    static let chiaveSpostato = "migrazione.spostato"

    static let messaggio = "Abbiamo spostato SchieraXI su un nuovo server: accedi di nuovo."

    static func pulito(_ testo: String) -> String {
        var t = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        while t.hasSuffix("/") { t.removeLast() }
        return t
    }

    /// L'indirizzo salvato dall'utente se è diverso dal predefinito (altrimenti `nil`).
    static func salvatoDiverso(_ memoria: UserDefaults) -> String? {
        let s = pulito(memoria.string(forKey: chiaveIndirizzo) ?? "")
        if s.isEmpty || s.lowercased() == pulito(Config.indirizzoPredefinito).lowercased() { return nil }
        return s
    }

    /// Indirizzi di rete privata («*.<dominio privato>»): non esistono per chi non è nella stessa rete, quindi non vanno tenuti.
    static func eReteprivata(_ indirizzo: String) -> Bool {
        guard let host = URL(string: indirizzo)?.host?.lowercased() else { return false }
        return host == "ts.net" || host.hasSuffix(".ts.net")
    }

    /// Passo sincrono, all'avvio: se l'indirizzo salvato è di rete privata lo toglie (da lì in poi vale il predefinito)
    /// e restituisce il vecchio, così chi chiama butta anche la sessione legata a quel server.
    static func migraSubito(_ memoria: UserDefaults = .standard) -> String? {
        guard !Demo.attivo, let vecchio = salvatoDiverso(memoria), eReteprivata(vecchio) else { return nil }
        sposta(memoria)
        return vecchio
    }

    /// Passo con la rete: il predefinito risponde e quello salvato no per due prove di fila → si torna al predefinito.
    /// (Se non risponde nemmeno il predefinito, il problema è il telefono offline: non si tocca niente.)
    /// Restituisce `true` se ha cambiato l'indirizzo.
    static func migraSeIrraggiungibile(_ memoria: UserDefaults = .standard,
                                       prova: (String) async -> EsitoConnessione) async -> Bool {
        guard !Demo.attivo, let vecchio = salvatoDiverso(memoria) else { return false }
        guard await prova(pulito(Config.indirizzoPredefinito)).raggiunto else { return false }
        for _ in 0..<2 {
            let esito = await prova(vecchio)
            if esito.raggiunto || !eFallitoDiConnessione(esito) { return false }
        }
        sposta(memoria)
        return true
    }

    /// Il server non c'è (non risponde, tempo scaduto, certificato): non conta un server che risponde con un errore suo.
    static func eFallitoDiConnessione(_ esito: EsitoConnessione) -> Bool {
        switch esito {
        case .nonRaggiungibile, .timeout, .certificato: return true
        default: return false
        }
    }

    private static func sposta(_ memoria: UserDefaults) {
        memoria.removeObject(forKey: chiaveIndirizzo)
        memoria.set(true, forKey: chiaveSpostato)
    }
}
