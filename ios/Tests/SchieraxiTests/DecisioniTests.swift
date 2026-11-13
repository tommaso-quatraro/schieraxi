import Foundation
import Testing
@testable import Schieraxi

/// Le decisioni in cima alla Formazione (#673, decisione 1 del proprietario): quali voci di «Da fare» e in che ordine lo segna il
/// server con il campo `decisione`; l'app ne mostra al massimo due, quelle che hanno ancora senso con la formazione in pagina, come
/// `vale` e `dfDecisioni` della web: un cambio già fatto non si propone più, «la consigliata è cambiata» vale finché in campo c'è una
/// tua scelta diversa da lei. Più i punti attesi del cambio e cosa fa il pulsante. Dati inventati.
@Suite("Decisioni in cima alla Formazione, come la web")
struct DecisioniTests {
    /// La formazione in pagina: titolari 1…11, aperta, senza scelta salvata, uguale alla consigliata.
    static var pagina: Decisioni.Pagina {
        Decisioni.Pagina(titolari: Array(1...11), chiusa: false, conScelta: false, diversi: 0, tecniche: false)
    }

    /// Una voce di «Da fare» come la manda il server (decodificata, come nell'app).
    static func voce(_ json: String) throws -> DaFareVoce {
        try Decodifica.decodifica(Data(json.utf8))
    }

    /// `"decisione": N,` nel JSON di una voce; vuoto senza.
    static func campoDecisione(_ n: Int?) -> String {
        guard let n else { return "" }
        return "\"decisione\": \(n),"
    }

    /// «Rossi è in dubbio: meglio Bianchi», con il cambio proposto.
    static func dubbio(esce: Int = 4, entra: Int = 40, decisione: Int? = 1, priorita: Int = 1) throws -> DaFareVoce {
        let campo = campoDecisione(decisione)
        return try voce(#"""
        {"id": "dubbio:\#(esce)", "tipo": "dubbio", "testo": "Rossi è in dubbio (45% di giocare). Meglio Bianchi.", "priorita": \#(priorita),
         "azione": "Sostituisci", \#(campo)
         "giocatore": {"id": \#(esce), "nome": "Rossi"},
         "alternativa": {"id": \#(entra), "nome": "Bianchi", "ruolo": "D", "punti_attesi": 6.4}}
        """#)
    }

    static func rose(decisione: Int? = 2) throws -> DaFareVoce {
        let campo = campoDecisione(decisione)
        return try voce(#"""
        {"id": "rose", "tipo": "rose", "testo": "Le rose non sono aggiornate da 5 giorni.", "priorita": 2, "azione": "Aggiorna le rose",
         \#(campo) "destinazione": {"sezione": "lega", "link": "schieraxi://lega"}}
        """#)
    }

    static func consigliataCambiata() throws -> DaFareVoce {
        try voce(#"""
        {"id": "consigliata:9", "tipo": "formazione", "testo": "La consigliata è cambiata da quando l'hai salvata.", "priorita": 2,
         "decisione": 1, "azione": "Vedi"}
        """#)
    }

    // MARK: quali e in che ordine

    @Test("Solo le voci con `decisione`, nel suo ordine (a pari numero quello del server), al massimo due")
    func ordineEMassimo() throws {
        let terza = try Self.voce(#"{"id": "diario", "tipo": "diario", "testo": "Dimmi cosa hai schierato.", "priorita": 3, "decisione": 3}"#)
        let senza = try Self.voce(#"{"id": "info", "tipo": "server", "testo": "Dati di ieri.", "priorita": 1}"#)
        let voci = [terza, try Self.rose(decisione: 2), senza, try Self.dubbio(decisione: 1)]
        #expect(Decisioni.prime(voci, pagina: Self.pagina).map(\.id) == ["dubbio:4", "rose"])
        #expect(Decisioni.massimo == 2)
        let pari = [try Self.rose(decisione: 1), try Self.dubbio(decisione: 1)]
        #expect(Decisioni.prime(pari, pagina: Self.pagina).map(\.id) == ["rose", "dubbio:4"], "a pari numero l'ordine del server")
    }

    @Test("Un server vecchio (senza `decisione`): in cima non c'è niente; una voce senza testo non si mostra")
    func serverVecchio() throws {
        #expect(Decisioni.prime([try Self.dubbio(decisione: nil), try Self.rose(decisione: nil)], pagina: Self.pagina).isEmpty)
        let vuota = try Self.voce(#"{"id": "x", "tipo": "rose", "testo": "", "decisione": 1}"#)
        #expect(Decisioni.prime([vuota], pagina: Self.pagina).isEmpty)
    }

    @Test("Un campo `decisione` di forma strana vale «niente», la voce resta")
    func campoStrano() throws {
        let v = try Self.voce(#"{"id": "rose", "tipo": "rose", "testo": "Aggiorna.", "decisione": "prima"}"#)
        #expect(v.decisione == nil)
        #expect(v.testo == "Aggiorna.")
    }

    // MARK: ancora sensate con la formazione in pagina

    @Test("Il cambio proposto vale solo se chi esce è in campo e chi entra no; mai a giornata chiusa")
    func dubbioSensato() throws {
        let d = try Self.dubbio(esce: 4, entra: 40)
        #expect(Decisioni.vale(d, Self.pagina))
        var fatto = Self.pagina
        fatto.titolari = Array(1...3) + [40] + Array(5...11)
        #expect(!Decisioni.vale(d, fatto), "il cambio è già fatto")
        var uscito = Self.pagina
        uscito.titolari = Array(1...3) + [50] + Array(5...11)
        #expect(!Decisioni.vale(d, uscito), "chi esce non è più in campo")
        var chiusa = Self.pagina
        chiusa.chiusa = true
        #expect(!Decisioni.vale(d, chiusa))
        let senzaAlternativa = try Self.voce(#"{"id": "dubbio:4", "tipo": "dubbio", "testo": "Rossi è in dubbio.", "decisione": 1, "giocatore": {"id": 4, "nome": "Rossi"}}"#)
        #expect(!Decisioni.vale(senzaAlternativa, Self.pagina), "senza un'alternativa non c'è niente da decidere")
    }

    @Test("«La consigliata è cambiata» vale finché in campo c'è una tua scelta salvata diversa da lei")
    func consigliataCambiataSensata() throws {
        let v = try Self.consigliataCambiata()
        #expect(v.consigliataCambiata)
        #expect(!Decisioni.vale(v, Self.pagina), "in campo la consigliata: niente da decidere")
        var tua = Self.pagina
        tua.conScelta = true
        tua.diversi = 2
        #expect(Decisioni.vale(v, tua))
        tua.chiusa = true
        #expect(!Decisioni.vale(v, tua))
    }

    @Test("Le voci tecniche solo per chi gestisce l'app; la copia di sicurezza mai; le altre sempre")
    func tecnicheEAltre() throws {
        let certificato = try Self.voce(#"{"id": "cert", "tipo": "certificato", "testo": "Rinnova l'app.", "decisione": 1}"#)
        let backup = try Self.voce(#"{"id": "backup", "tipo": "backup", "testo": "Fai la copia.", "decisione": 1}"#)
        #expect(!Decisioni.vale(certificato, Self.pagina))
        var gestore = Self.pagina
        gestore.tecniche = true
        #expect(Decisioni.vale(certificato, gestore))
        #expect(!Decisioni.vale(backup, gestore))
        #expect(Decisioni.vale(try Self.rose(), Self.pagina))
        var chiusa = Self.pagina
        chiusa.chiusa = true
        #expect(Decisioni.vale(try Self.rose(), chiusa), "aggiornare le rose ha senso anche a giornata chiusa")
    }

    @Test("Un cambio già fatto lascia il posto alla decisione dopo")
    func scorre() throws {
        var fatto = Self.pagina
        fatto.titolari = Array(1...3) + [40] + Array(5...11)
        let voci = [try Self.dubbio(decisione: 1), try Self.rose(decisione: 2)]
        #expect(Decisioni.prime(voci, pagina: fatto).map(\.id) == ["rose"])
    }

    // MARK: cosa dice e cosa fa

    @Test("«+0,9 punti attesi.»: quanto vale in più il sostituto, solo da 0,05 in su e con i due numeri")
    func guadagno() throws {
        let d = try Self.dubbio()
        #expect(Decisioni.guadagno(d, puntiTitolare: 5.5) == "+0,9 punti attesi.")
        #expect(Decisioni.guadagno(d, puntiTitolare: 5.5) == Catalogo.Formazione.decisionePunti(d: "+0,9"))
        #expect(Decisioni.guadagno(d, puntiTitolare: 6.38) == nil, "meno di 0,05")
        #expect(Decisioni.guadagno(d, puntiTitolare: 7) == nil, "il sostituto vale meno")
        #expect(Decisioni.guadagno(d, puntiTitolare: nil) == nil)
        #expect(Decisioni.guadagno(try Self.rose(), puntiTitolare: 5) == nil)
    }

    @Test("Il pulsante: quello del server, «Usa la consigliata» per la consigliata cambiata; urgente lo dice a parole")
    func pulsanteEUrgente() throws {
        let d = try Self.dubbio(priorita: 1)
        #expect(d.testoPulsante == "Sostituisci")
        #expect(d.urgente)
        #expect(d.cambio?.esce == 4 && d.cambio?.entra == 40)
        #expect(d.scrive)
        let c = try Self.consigliataCambiata()
        #expect(c.testoPulsante == Catalogo.Formazione.usaConsigliata)
        #expect(c.scrive && c.cambio == nil)
        let r = try Self.rose()
        #expect(!r.urgente && !r.scrive)
        #expect(r.testoPulsante == "Aggiorna le rose")
        #expect(r.destinazione?.destinazione == .sezione(.altro), "«lega» è Altro")
    }

    // MARK: dalla Formazione

    @Test("La Formazione passa a `Decisioni` gli 11 in campo: con la consigliata il cambio proposto c'è, per un'altra squadra no")
    @MainActor
    func dallaFormazione() async throws {
        let f: Formazione = try Fixture.decodifica("formazione")
        let titolare = 6523, riserva = 6994          // un difensore titolare incerto e uno della rosa
        let oggi: Oggi = try Decodifica.decodifica(Data(#"""
        {"giornata": 9, "da_fare": [
          {"id": "dubbio:6523", "tipo": "dubbio", "testo": "Barucci è in dubbio.", "priorita": 1, "azione": "Sostituisci", "decisione": 1,
           "giocatore": {"id": \#(titolare), "nome": "Barucci"}, "alternativa": {"id": \#(riserva), "nome": "Altro", "punti_attesi": 5.64}}]}
        """#.utf8))
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        let decisioni = vm.decisioni(oggi, tecniche: false)
        #expect(decisioni.map(\.id) == ["dubbio:6523"])
        let barucci = try #require(f.schede?[String(titolare)]?.puntiAttesi)
        let prima = try #require(decisioni.first)
        #expect(vm.guadagno(prima) == Decisioni.guadagno(prima, puntiTitolare: barucci))
        #expect(vm.guadagno(prima) == "+1,9 punti attesi.")
        vm.vediSquadra("Gli Amici")
        #expect(vm.decisioni(oggi, tecniche: false).isEmpty)
    }
}
