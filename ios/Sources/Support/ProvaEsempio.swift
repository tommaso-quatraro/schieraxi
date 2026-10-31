import Foundation

/// «Prova con dati di esempio»: l'app si apre con una lega inventata, senza server, senza account e senza rete.
/// Serve a chi vuole vedere com'è fatta prima di collegare il suo server, e a chi deve controllare l'app (la revisione di Apple).
///
/// Sicurezza: nessuna password, nessun token e nessun indirizzo vero. I dati sono quelli finti già dentro l'app (`FinteServer.demo`),
/// niente esce dal telefono, non si registrano lavori in background né si programmano notifiche (le protezioni della modalità demo).
/// Si esce da Impostazioni > «Esci dalla prova»: i dati di esempio si cancellano e l'app torna a chiedere l'indirizzo del server.
enum ProvaEsempio {
    static let chiave = "provaConDatiDiEsempio"

    /// Vero mentre la prova è accesa (resta anche dopo aver chiuso l'app).
    nonisolated static var attiva: Bool { UserDefaults.standard.bool(forKey: chiave) }

    @MainActor
    static func avvia() {
        // prima il server finto, poi l'interruttore: le schermate nascono già con i dati di esempio
        ServerCorrente.condiviso = FinteServer.demo
        UserDefaults.standard.set(true, forKey: chiave)
    }

    @MainActor
    static func esci() {
        ServerCorrente.condiviso = ServerHTTP()
        UserDefaults.standard.removeObject(forKey: chiave)
        DatiLocali.svuota()
    }
}
