import Foundation

/// Cosa mostra «Il tuo account» nelle Impostazioni: un solo nome e un'email, senza voci doppie.
enum ProfiloAccount {
    /// L'email da mostrare: quella dell'account; se manca, quella di Google (se Google è collegato);
    /// se manca anche quella, l'indirizzo ancora da verificare. nil = nessuna email.
    static func email(account: String?, inAttesa: String?, google: String?) -> String? {
        if let a = pulita(account) { return a }
        if let g = pulita(google) { return g }
        if let i = pulita(inAttesa) { return "\(i) (da verificare)" }
        return nil
    }

    /// La voce per aggiungere o cambiare l'email serve solo a chi NON ha Google collegato:
    /// con Google l'email c'è già e si entra senza password da recuperare.
    static func mostraVoceEmail(googleCollegato: Bool) -> Bool {
        !googleCollegato
    }

    /// Posta spenta sul server e nessuna email (né dell'account né di Google): nessun codice può arrivare, quindi non se ne può
    /// collegare una. Come la web (`htmlEmailAccount`), al posto della riga e della voce dell'email c'è solo `TestiAccount.emailSpenta`.
    /// Con un'email già collegata resta tutto: si può ancora toglierla.
    static func soloPostaSpenta(postaAccesa: Bool, account: String?, google: String?) -> Bool {
        !postaAccesa && pulita(account) == nil && pulita(google) == nil
    }

    private static func pulita(_ testo: String?) -> String? {
        guard let t = testo?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else { return nil }
        return t
    }
}

/// Le scelte dell'aspetto che l'app non offre più (colore principale, densità, sezione iniziale): si tolgono dal telefono
/// una volta, così chi le aveva cambiate torna ai valori normali e non resta bloccato su una scelta che non può più vedere.
/// Con loro i dati tenuti sul telefono dalle funzioni tolte il 12/11/2026 (#634).
enum OpzioniTolte {
    /// L'archivio degli scambi analizzati e «legenda del campo già vista»: le loro schermate non ci sono più.
    static let chiaviFunzioni = ["archivioScambi", "legendaCampoVista"]
    /// `promemoria_60` e `promemoria_15`: le scelte per singolo promemoria, sostituite da «Avvisi su questo dispositivo» (#673 passo 3).
    static let chiavi = ["accento", "densita", "sezioneAvvio", "promemoria_60", "promemoria_15"] + chiaviFunzioni
    /// Il segno che le voci dei giocatori seguiti sono già state tolte dalla ricerca di iOS (Spotlight): si fa una volta sola.
    static let chiaveSpotlightSvuotato = "spotlightSeguitiSvuotato"

    static func pulisci(_ memoria: UserDefaults = .standard) {
        for chiave in chiavi where memoria.object(forKey: chiave) != nil {
            memoria.removeObject(forKey: chiave)
        }
    }
}
