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

    private static func pulita(_ testo: String?) -> String? {
        guard let t = testo?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else { return nil }
        return t
    }
}

/// Le scelte dell'aspetto che l'app non offre più (colore principale, densità, sezione iniziale): si tolgono dal telefono
/// una volta, così chi le aveva cambiate torna ai valori normali e non resta bloccato su una scelta che non può più vedere.
enum OpzioniTolte {
    static let chiavi = ["accento", "densita", "sezioneAvvio"]

    static func pulisci(_ memoria: UserDefaults = .standard) {
        for chiave in chiavi where memoria.object(forKey: chiave) != nil {
            memoria.removeObject(forKey: chiave)
        }
    }
}
