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

    /// `@Sendable`: `campi` è una costante condivisa (`static let`) e con Swift 6 deve poter passare da un thread all'altro.
    /// Le closure non catturano niente (il campo si scrive dentro), così non serve che il key path sia `Sendable`.
    private typealias Porta = @Sendable (inout ImpostazioniAvvisi, ImpostazioniAvvisi, ImpostazioniAvvisi) -> Void

    private static let campi: [Porta] = [
        { porta(\.cambi, &$0, $1, $2) }, { porta(\.promemoria_60, &$0, $1, $2) }, { porta(\.promemoria_15, &$0, $1, $2) },
        { porta(\.riepilogo, &$0, $1, $2) }, { porta(\.copertura, &$0, $1, $2) }, { porta(\.app_nativa, &$0, $1, $2) },
        { porta(\.silenzio, &$0, $1, $2) }, { porta(\.silenzio_da, &$0, $1, $2) }, { porta(\.silenzio_a, &$0, $1, $2) },
        { porta(\.avviso_prima, &$0, $1, $2) },
    ]

    /// Porta il campo in `risultato` solo se l'utente l'aveva cambiato (da `da` ad `a`).
    private static func porta<T: Equatable>(_ campo: WritableKeyPath<ImpostazioniAvvisi, T>, _ risultato: inout ImpostazioniAvvisi,
                                           _ da: ImpostazioniAvvisi, _ a: ImpostazioniAvvisi) {
        if a[keyPath: campo] != da[keyPath: campo] { risultato[keyPath: campo] = a[keyPath: campo] }
    }
}
