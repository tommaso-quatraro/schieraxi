import Foundation

/// Una modifica degli avvisi che il server non ha ancora: com'erano le impostazioni (`da`) e come le voleva l'utente (`a`).
/// Dopo un salvataggio non riuscito «Riprova» la rimanda sopra le impostazioni di adesso, così non disfa ciò che
/// l'utente ha cambiato e salvato nel frattempo.
struct ModificaAvvisi: Equatable {
    let da: ImpostazioniAvvisi
    let a: ImpostazioniAvvisi

    /// Le stesse scelte sopra altre impostazioni: cambiano solo i campi che l'utente aveva toccato.
    func applicata(a altre: ImpostazioniAvvisi) -> ImpostazioniAvvisi {
        var risultato = altre
        for porta in Self.campi { porta(&risultato, da, a) }
        return risultato
    }

    /// `altre` ha già tutte queste scelte (per esempio perché un salvataggio riuscito le conteneva).
    func contenuta(in altre: ImpostazioniAvvisi) -> Bool { applicata(a: altre) == altre }

    /// Quanti campi degli avvisi si portano: un test controlla che siano tutti quelli di `ImpostazioniAvvisi`.
    static var campiPortati: Int { campi.count }

    private typealias Porta = (inout ImpostazioniAvvisi, ImpostazioniAvvisi, ImpostazioniAvvisi) -> Void

    private static let campi: [Porta] = [
        porta(\.cambi), porta(\.promemoria_60), porta(\.promemoria_15), porta(\.riepilogo), porta(\.copertura),
        porta(\.app_nativa), porta(\.silenzio), porta(\.silenzio_da), porta(\.silenzio_a), porta(\.avviso_prima),
    ]

    private static func porta<T: Equatable>(_ campo: WritableKeyPath<ImpostazioniAvvisi, T>) -> Porta {
        { risultato, da, a in
            if a[keyPath: campo] != da[keyPath: campo] { risultato[keyPath: campo] = a[keyPath: campo] }
        }
    }
}
