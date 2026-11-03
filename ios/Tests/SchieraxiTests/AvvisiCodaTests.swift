import Foundation
import Testing
@testable import Schieraxi

/// Avvisi: i salvataggi vanno uno alla volta, un errore non fa perdere le modifiche dell'utente
/// e i promemoria locali seguono gli interruttori.
@MainActor
@Suite("Avvisi: salvataggi in coda e promemoria")
struct AvvisiCodaTests {
    @Test("Il secondo tocco a salvataggio in corso parte dopo il primo, con tutte e due le modifiche", .timeLimit(.minutes(1)))
    func secondoToccoASalvataggioInCorso() async throws {
        let prova = ProvaAvvisi(erroreDellaPrima: nil)
        let vm = prova.modello()
        await vm.carica()
        let riepilogo = try #require(vm.impostazioni?.riepilogo)
        let cambi = try #require(vm.impostazioni?.cambi)

        vm.impostazioni?.riepilogo = !riepilogo
        let primo = Task { await vm.salva() }
        await prova.aspettaPrimaPut()
        vm.impostazioni?.cambi = !cambi   // il secondo tocco arriva mentre la prima PUT è ancora ferma sul server
        let secondo = Task { await vm.salva() }
        try await Task.sleep(for: .milliseconds(200))
        #expect(prova.server.quante("PUT /api/avvisi") == 1, "il secondo salvataggio aspetta che finisca il primo")
        prova.lasciaAndare()
        await primo.value
        await secondo.value

        let corpi = try prova.corpi()
        try #require(corpi.count == 2)
        #expect(corpi[0].riepilogo == !riepilogo)
        #expect(corpi[0].cambi == cambi, "la prima PUT è partita prima del secondo tocco")
        #expect(corpi[1].riepilogo == !riepilogo)
        #expect(corpi[1].cambi == !cambi)
        #expect(prova.registro.massimoInsieme == 1, "mai due PUT in viaggio insieme")
        #expect(vm.erroreSalvataggio == nil)
    }

    @Test("Primo salvataggio senza rete: l'errore resta e «Riprova» manda tutte e due le modifiche", .timeLimit(.minutes(1)))
    func erroreDiReteConUnSecondoToccoInCoda() async throws {
        let prova = ProvaAvvisi(erroreDellaPrima: .rete("spento"))
        let vm = prova.modello()
        await vm.carica()
        let riepilogo = try #require(vm.impostazioni?.riepilogo)
        let cambi = try #require(vm.impostazioni?.cambi)

        vm.impostazioni?.riepilogo = !riepilogo
        let primo = Task { await vm.salva() }
        await prova.aspettaPrimaPut()
        vm.impostazioni?.cambi = !cambi
        let secondo = Task { await vm.salva() }
        prova.lasciaAndare()
        await primo.value
        await secondo.value

        #expect(prova.server.quante("PUT /api/avvisi") == 1, "nessuna PUT con gli interruttori tornati indietro")
        #expect(vm.erroreSalvataggio == "Non ho salvato la modifica. " + ErroreApi.testoNonRaggiungibile)
        #expect(vm.puoRiprovare)
        #expect(vm.impostazioni?.riepilogo == riepilogo, "gli interruttori mostrano ciò che ha il server")
        #expect(vm.impostazioni?.cambi == cambi)

        await vm.riprova()
        let corpi = try prova.corpi()
        try #require(corpi.count == 2)
        #expect(corpi[1].riepilogo == !riepilogo, "«Riprova» manda il primo tocco")
        #expect(corpi[1].cambi == !cambi, "… e anche il secondo")
        #expect(vm.erroreSalvataggio == nil)
        #expect(!vm.puoRiprovare)
        #expect(vm.impostazioni?.riepilogo == !riepilogo)
        #expect(vm.impostazioni?.cambi == !cambi)
    }

    @Test("Dopo un 412 il messaggio resta anche con un altro tocco in coda", .timeLimit(.minutes(1)))
    func conflittoConUnSecondoToccoInCoda() async throws {
        let prova = ProvaAvvisi(erroreDellaPrima: .conflitto)
        let vm = prova.modello()
        await vm.carica()
        let cambi = try #require(vm.impostazioni?.cambi)

        vm.impostazioni?.riepilogo.toggle()
        let primo = Task { await vm.salva() }
        await prova.aspettaPrimaPut()
        vm.impostazioni?.cambi = !cambi
        let secondo = Task { await vm.salva() }
        prova.lasciaAndare()
        await primo.value
        await secondo.value

        #expect(vm.erroreSalvataggio == "Non ho salvato la modifica. " + (ErroreApi.conflitto.errorDescription ?? ""))
        #expect(!vm.puoRiprovare, "dopo un conflitto si vedono già i dati nuovi del server")
        #expect(prova.server.quante("GET /api/avvisi") == 2, "si rilegge")
        #expect(prova.server.quante("PUT /api/avvisi") == 1, "niente PUT che copre il conflitto con i dati appena riletti")
    }

    @Test("Un'altra modifica salvata dopo un errore non cancella quella da riprovare, e «Riprova» non la disfa")
    func altraModificaDopoUnErrore() async throws {
        let rotto = Scatola<Bool>()
        rotto.valore = true
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", rotto.valore == true { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/avvisi") { return try Fixture.dati("avvisi") }
            return Data("{}".utf8)
        }
        let vm = AvvisiServerViewModel(server: s, promemoria: PromemoriaAnnotati().telefono)
        await vm.carica()
        let riepilogo = try #require(vm.impostazioni?.riepilogo)
        let cambi = try #require(vm.impostazioni?.cambi)

        vm.impostazioni?.riepilogo = !riepilogo
        await vm.salva()
        #expect(vm.puoRiprovare)

        rotto.valore = false
        vm.impostazioni?.cambi = !cambi
        await vm.salva()
        #expect(vm.erroreSalvataggio != nil, "il riepilogo non è ancora salvato: l'errore resta")
        #expect(vm.puoRiprovare)

        await vm.riprova()
        let ultimo = try #require(try ProvaAvvisi.decodifica(s).last)
        #expect(ultimo.riepilogo == !riepilogo)
        #expect(ultimo.cambi == !cambi, "«Riprova» non disfa la modifica salvata dopo")
        #expect(vm.erroreSalvataggio == nil)
        #expect(!vm.puoRiprovare)
    }

    @Test("Spegnere un promemoria lo toglie dal telefono, riaccenderlo lo rimette in programma")
    func interruttoriEPromemoriaDelTelefono() async throws {
        let annotati = PromemoriaAnnotati()
        let vm = AvvisiServerViewModel(server: ServerDiProva.conFixture(["/api/avvisi": "avvisi"]), promemoria: annotati.telefono)
        await vm.carica()
        #expect(annotati.ricordate.last?.promemoriaAccesi == Set([60, 15]), "letti dal server, si ricordano sul telefono")

        vm.impostazioni?.promemoria_60 = false
        await vm.salva()
        #expect(annotati.ricordate.last?.promemoriaAccesi == Set([15]))
        #expect(annotati.accesiQuandoSiTolgono.last == Set([15]), "quello di un'ora si toglie subito dal telefono")
        #expect(annotati.riprogrammati == 0)

        vm.impostazioni?.promemoria_60 = true
        await vm.salva()
        #expect(annotati.ricordate.last?.promemoriaAccesi == Set([60, 15]))
        #expect(annotati.riprogrammati == 1, "riacceso: torna in programma con l'ultima giornata salvata")

        vm.impostazioni?.riepilogo.toggle()
        await vm.salva()
        #expect(annotati.riprogrammati == 1, "un altro interruttore non riprogramma niente")
    }

    @Test("Cambiare le ore tranquille rimette subito in programma i promemoria, con le ore nuove già sul telefono",
          .bug("https://github.com/tommaso-quatraro/schieraxi/issues/175"))
    func oreTranquilleRiprogrammanoIPromemoria() async throws {
        let annotati = PromemoriaAnnotati()
        let vm = AvvisiServerViewModel(server: ServerDiProva.conFixture(["/api/avvisi": "avvisi"]), promemoria: annotati.telefono)
        await vm.carica()
        try #require(vm.impostazioni?.silenzio != true, "la lettura parte con le ore tranquille spente")
        #expect(annotati.riprogrammati == 0)

        // accese come fa l'interruttore della schermata (con le ore di partenza)
        vm.impostazioni?.silenzio = true
        vm.impostazioni?.silenzio_da = 22
        vm.impostazioni?.silenzio_a = 7
        await vm.salva()
        let accese: [OreTranquille?] = [OreTranquille(attive: true, da: 22, a: 7)]
        #expect(annotati.oreQuandoSiRiprogramma == accese,
                "i promemoria che ora cadono nel silenzio spariscono subito, non alla prossima lettura di Oggi")

        vm.impostazioni?.silenzio_a = 8   // la fine si sposta di un'ora
        await vm.salva()
        vm.impostazioni?.silenzio = false   // spente: quelli saltati tornano
        await vm.salva()
        let tutte: [OreTranquille?] = [OreTranquille(attive: true, da: 22, a: 7), OreTranquille(attive: true, da: 22, a: 8),
                                       OreTranquille(attive: false, da: 22, a: 8)]
        #expect(annotati.oreQuandoSiRiprogramma == tutte,
                "ogni cambio delle ore riprogramma, e lo fa con le ore nuove già ricordate sul telefono")
    }

    @Test("Dopo un salvataggio il telefono ricorda ciò che è stato salvato, non il tocco ancora in coda", .timeLimit(.minutes(1)))
    func siRicordaIlSalvato() async throws {
        let prova = ProvaAvvisi(erroreDellaPrima: nil)
        let vm = prova.modello()
        await vm.carica()

        vm.impostazioni?.promemoria_60 = false
        let primo = Task { await vm.salva() }
        await prova.aspettaPrimaPut()
        vm.impostazioni?.promemoria_15 = false   // non ancora salvato quando finisce la prima PUT
        let secondo = Task { await vm.salva() }
        prova.lasciaAndare()
        await primo.value
        await secondo.value

        let atteso: [Set<Int>] = [[60, 15], [15], []]   // lettura, primo salvataggio, secondo salvataggio
        #expect(prova.annotati.ricordate.map(\.promemoriaAccesi) == atteso)
        #expect(prova.annotati.accesiQuandoSiTolgono == atteso)
        #expect(prova.annotati.riprogrammati == 0)
    }

    @Test("Una modifica da riprovare porta ogni campo degli avvisi, e solo quelli toccati")
    func modificaDaRiprovare() {
        let base = ImpostazioniAvvisi(cambi: true, promemoria_60: true, promemoria_15: true, riepilogo: true, copertura: true,
                                      app_nativa: false, silenzio: false, silenzio_da: 23, silenzio_a: 7, avviso_prima: 60)
        let tutta = ImpostazioniAvvisi(cambi: false, promemoria_60: false, promemoria_15: false, riepilogo: false, copertura: false,
                                       app_nativa: true, silenzio: true, silenzio_da: 22, silenzio_a: 6, avviso_prima: 30)
        #expect(ModificaAvvisi(da: base, a: tutta).applicata(a: base) == tutta)
        #expect(Mirror(reflecting: base).children.count == ModificaAvvisi.campiPortati, "un campo nuovo degli avvisi va portato anche qui")

        var soloRiepilogo = base
        soloRiepilogo.riepilogo = false
        var salvataDopo = base
        salvataDopo.cambi = false
        let modifica = ModificaAvvisi(da: base, a: soloRiepilogo)
        let rimandata = modifica.applicata(a: salvataDopo)
        #expect(rimandata.riepilogo == false)
        #expect(rimandata.cambi == false, "la modifica salvata dopo resta")
        #expect(modifica.contenuta(in: rimandata))
        #expect(!modifica.contenuta(in: salvataDopo))
    }

    @Test("La nota su cosa arriva al telefono compare solo con gli account e non contraddice il riquadro sopra")
    func notaSoloConGliAccount() throws {
        #expect(AvvisiServerView.notaQualiAvvisi(multiutente: false) == nil)
        let nota = try #require(AvvisiServerView.notaQualiAvvisi(multiutente: true))
        #expect(nota.contains("web app"))
        #expect(nota.contains("formazione consigliata"), "anche l'avviso dell'app quando cambia la consigliata arriva sul telefono")
        #expect(!nota.contains("solo i promemoria"))
    }

    @Test("I promemoria locali accesi si ricordano sul telefono e si filtrano")
    func archivioPromemoria() throws {
        let memoria = try #require(UserDefaults(suiteName: "prova-promemoria-\(UUID().uuidString)"))
        #expect(ArchivioPromemoria.minutiAttivi(memoria) == [60, 15], "senza scelta: tutti e due, come prima")
        ArchivioPromemoria.salva(sessanta: false, quindici: true, memoria)
        #expect(ArchivioPromemoria.minutiAttivi(memoria) == [15])
        ArchivioPromemoria.salva(sessanta: false, quindici: false, memoria)
        #expect(ArchivioPromemoria.minutiAttivi(memoria).isEmpty)

        let adesso = Date(timeIntervalSince1970: 1_793_500_000)
        let inizio = adesso.addingTimeInterval(5 * 3600)
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, adesso: adesso).map(\.minuti) == [60, 15])
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [15], adesso: adesso).map(\.minuti) == [15],
                "«Promemoria un'ora prima» spento: il telefono non lo manda")
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [], adesso: adesso).isEmpty)
    }
}

/// Conta le PUT: quante in tutto e quante al massimo in viaggio insieme.
/// `@unchecked Sendable`: ogni lettura e scrittura passa da `blocco`, mai attraverso un `await`.
private final class RegistroPut: @unchecked Sendable {
    private let blocco = NSLock()
    private var totale = 0
    private var inViaggio = 0
    private var massimo = 0

    /// Una PUT arriva al server: il suo numero d'ordine (1 = la prima).
    func entra() -> Int {
        blocco.lock(); defer { blocco.unlock() }
        totale += 1
        inViaggio += 1
        massimo = max(massimo, inViaggio)
        return totale
    }

    func esce() {
        blocco.lock(); defer { blocco.unlock() }
        inViaggio -= 1
    }

    var massimoInsieme: Int {
        blocco.lock(); defer { blocco.unlock() }
        return massimo
    }
}

/// Prende il posto dei promemoria del telefono (UserDefaults e centro notifiche) e annota cosa gli arriva.
@MainActor
private final class PromemoriaAnnotati {
    private(set) var ricordate: [ImpostazioniAvvisi] = []
    private(set) var accesiQuandoSiTolgono: [Set<Int>] = []
    /// A ogni riprogrammazione, le ore tranquille già ricordate sul telefono in quel momento (sono quelle che userà).
    private(set) var oreQuandoSiRiprogramma: [OreTranquille?] = []
    var riprogrammati: Int { oreQuandoSiRiprogramma.count }

    var telefono: PromemoriaTelefono {
        PromemoriaTelefono(
            ricorda: { self.ricordate.append($0) },
            togliSpenti: { self.accesiQuandoSiTolgono.append($0) },
            riprogramma: { self.oreQuandoSiRiprogramma.append(self.ricordate.last?.oreTranquille) })
    }
}

/// Un server finto per gli avvisi: ferma la prima PUT finché il test non la lascia andare (poi riesce, o lancia
/// `erroreDellaPrima`) e annota le altre, che riescono subito. Le letture rispondono con la fixture `avvisi`.
/// I promemoria del telefono sono quelli annotati (`annotati`).
@MainActor
private struct ProvaAvvisi {
    let server: ServerDiProva
    let registro: RegistroPut
    let annotati: PromemoriaAnnotati
    private let arrivo: AsyncStream<Void>
    private let via: AsyncStream<Void>.Continuation

    init(erroreDellaPrima: ErroreApi?) {
        let (arrivo, segnalaArrivo) = AsyncStream<Void>.makeStream()
        let (attesa, via) = AsyncStream<Void>.makeStream()
        let registro = RegistroPut()
        self.registro = registro
        annotati = PromemoriaAnnotati()
        server = ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT" {
                let numero = registro.entra()
                defer { registro.esce() }
                if numero == 1 {
                    segnalaArrivo.yield()
                    for await _ in attesa { break }
                    if let erroreDellaPrima { throw erroreDellaPrima }
                }
            }
            if percorso.hasPrefix("/api/avvisi") { return try Fixture.dati("avvisi") }
            return Data("{}".utf8)
        }
        self.arrivo = arrivo
        self.via = via
    }

    func modello() -> AvvisiServerViewModel { AvvisiServerViewModel(server: server, promemoria: annotati.telefono) }

    /// Aspetta che la prima PUT sia arrivata al server (dove resta ferma).
    func aspettaPrimaPut() async {
        for await _ in arrivo { break }
    }

    func lasciaAndare() { via.yield() }

    /// Le impostazioni mandate con ogni PUT, nell'ordine.
    func corpi() throws -> [ImpostazioniAvvisi] { try Self.decodifica(server) }

    static func decodifica(_ server: ServerDiProva) throws -> [ImpostazioniAvvisi] {
        try server.corpiInviati(a: "PUT /api/avvisi").map { try JSONDecoder().decode(ImpostazioniAvvisi.self, from: $0) }
    }
}
