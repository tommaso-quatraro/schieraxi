import Foundation
import Testing
@testable import Schieraxi

/// Dopo «troppi tentativi» (429) l'attesa vale solo nel passo in cui è nata, come la web: lì, cambiando scheda, il modulo si
/// ridisegna e il conto si ferma (`contaAttesa` in `fanta/web/app.js`), e il server conta a parte accesso e recupero. Prima
/// l'iPhone la teneva anche cambiando passo: «Password dimenticata», «Registrati» e «Continua con Google» restavano spenti con
/// «Riprova tra N minuti».
@Suite("Accesso: l'attesa dopo «troppi tentativi» vale solo nel suo passo")
struct AccessoAttesaPerPassoTests {
    private let fine = Date(timeIntervalSince1970: 2_000_000_000)

    @Test("Nel passo in cui è nata il pulsante conta")
    func nelSuoPasso() {
        var m = ModuloAccesso(scheda: .accedi)
        m.aspetta(fino: fine)
        #expect(m.attesaFinoA == fine)
    }

    @Test("Cambiando scheda l'attesa si azzera, e tornando non riprende", arguments: [
        SchermataAccesso.Scheda.registrati, .recupera,
    ])
    func cambiandoSchedaSiAzzera(verso: SchermataAccesso.Scheda) {
        var m = ModuloAccesso(scheda: .accedi)
        m.aspetta(fino: fine)
        m.vai(verso, modo: .invito)
        #expect(m.attesaFinoA == nil, "un altro passo non aspetta")
        m.vai(.accedi, modo: .invito)
        #expect(m.attesaFinoA == nil, "come la web: tornando all'accesso il conto non riprende")
    }

    @Test("Anche dal recupero e dalla registrazione verso l'accesso", arguments: [
        SchermataAccesso.Scheda.recupera, .registrati,
    ])
    func versoLAccesso(da: SchermataAccesso.Scheda) {
        var m = ModuloAccesso(scheda: da)
        m.aspetta(fino: fine)
        m.vai(.accedi, modo: .aperta)
        #expect(m.attesaFinoA == nil)
    }

    @Test("Un altro passo della stessa scheda non aspetta: «Ricomincia» dopo il codice per posta, l'altro modo di recupero")
    func altroPassoStessaScheda() {
        var registrazione = ModuloAccesso(scheda: .registrati)
        registrazione.iscrizione = IscrizioneInAttesa(email: "nome@example.invalid", iscrizione: "segreto-finto")
        registrazione.aspetta(fino: fine)
        #expect(registrazione.attesaFinoA == fine)
        registrazione.iscrizione = nil
        #expect(registrazione.attesaFinoA == nil, "di nuovo il modulo di Registrati")

        var recupero = ModuloAccesso(scheda: .recupera)
        recupero.metodo = .email
        recupero.aspetta(fino: fine)
        recupero.metodo = .codice
        #expect(recupero.attesaFinoA == nil, "con il codice di recupero")
    }
}
