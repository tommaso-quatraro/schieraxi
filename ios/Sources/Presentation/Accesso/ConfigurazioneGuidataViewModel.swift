import SwiftUI

/// Dove porta un passo della configurazione guidata (la schermata si chiude, poi l'app va lì). Lasciata la pagina (o chiuso il
/// foglio del widget) a cui porta un passo, la guida si riapre da quel passo (`RitornoAllaGuida`, #880).
enum AzioneGuida: Equatable {
    /// «Importa le rose».
    case importaRose
    /// «Scegli la squadra»: l'elenco delle squadre, dove si sceglie la propria.
    case scegliSquadra
    case impostazioni
    /// «Tutto pronto»: «Vai alla Formazione» e il collegamento a Regole e scadenza della frase sui punteggi (#880).
    case formazione
    case regole
    /// «Collega il widget»: apre la schermata; al tocco su «Collega» lo collega (App Group o Keychain condiviso) e solo se non va
    /// copia il codice.
    case collegaWidget
}

/// Quello che serve della lega per sapere cosa è già fatto (`GET /api/stato`).
private struct StatoLega: Decodable {
    var roseImportate: Bool?
    var miaSquadra: String?

    private enum Chiavi: String, CodingKey { case roseImportate, miaSquadra }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        roseImportate = (try? k.decodeIfPresent(Bool.self, forKey: .roseImportate)) ?? nil
        miaSquadra = (try? k.decodeIfPresent(String.self, forKey: .miaSquadra)) ?? nil
    }
}

/// Logica della configurazione guidata: carica cosa è già fatto, propone i passi, salva quelli fatti o saltati sul server.
@MainActor
final class ConfigurazioneGuidataViewModel: ViewModelBase {
    enum Fase: Equatable { case carica, pronta, errore(String) }

    @Published private(set) var fase: Fase = .carica
    /// I passi da proporre (quelli non ancora fatti).
    @Published private(set) var passi: [PassoGuidato] = []
    /// Il passo mostrato; uguale a `passi.count` = il riepilogo finale.
    @Published private(set) var indice = 0
    @Published private(set) var avanzamento: AvanzamentoPrimoAvvio?
    @Published private(set) var stato = StatoConfigurazione()
    @Published private(set) var fattiOra: Set<PassoGuidato> = []
    @Published private(set) var saltatiOra: Set<PassoGuidato> = []
    /// Un messaggio dopo un'azione che non è andata (notifiche rifiutate, salvataggio non riuscito).
    @Published var avviso: String?
    @Published private(set) var inCorso = false
    /// «I tempi della lega» (#931): i due menu, con i valori più comuni finché le regole della lega non si leggono, come la web. Un
    /// cambio che non viene dalla lettura delle regole è una scelta dell'utente e la lettura non lo tocca più.
    @Published var scadenza = TempiGuida.partenza.scadenza {
        didSet { if !applicoLettura, scadenza != oldValue { scadenzaScelta = true } }
    }
    @Published var prima = TempiGuida.partenza.prima {
        didSet { if !applicoLettura, prima != oldValue { primaScelta = true } }
    }
    /// Le voci del menu della scadenza: le più comuni più quella salvata, se è diversa.
    @Published private(set) var scadenzeScelte = TempiGuida.scadenze
    /// Le regole della lega sono state lette: solo allora «Salva» le scrive (come la web, #801: altrimenti i valori di partenza
    /// andrebbero sopra quelli veri).
    private(set) var tempiLetti = false
    private var scadenzaScelta = false
    private var primaScelta = false
    /// Vero mentre i menu prendono i valori letti dal server (quel cambio non è una scelta dell'utente).
    private var applicoLettura = false
    /// La lettura delle regole in corso, che chi arriva dopo aspetta invece di farne un'altra.
    private var letturaTempi: Task<Bool, Never>?

    /// Come la web (`pav.non_sono_riuscito`); il salvataggio si ritenta da solo al passo dopo.
    static let erroreSalvataggio = Catalogo.Pav.nonSonoRiuscito

    private let server: any ServerClient
    private var passiServer: [String] = []
    /// «Più tardi», un passo che porta altrove o «Fine» hanno già salvato come si è usciti: la chiusura del foglio non risalva.
    private var lasciata = false
    /// Il server da cui è stata letta la guida: se nel frattempo è cambiato (Impostazioni > Server, spostamento automatico),
    /// alla chiusura non si scrive niente.
    private var indirizzoLetto: String?
    /// Riaperta dopo una pagina in cui l'aveva portata un passo: riparte da quel passo, o dal primo dopo se è fatto (#880).
    private let riprendiDa: PassoGuidato?
    /// Il passo fatto in quella pagina e che l'app non vede dai dati della lega (il widget collegato da «Collega il widget»): si
    /// segna fatto da solo, senza «L'ho già fatto» (#880).
    private let passoFatto: PassoGuidato?

    init(server: any ServerClient, riprendiDa: PassoGuidato? = nil, passoFatto: PassoGuidato? = nil) {
        self.server = server
        self.riprendiDa = riprendiDa
        self.passoFatto = passoFatto
        super.init()
    }

    var passoCorrente: PassoGuidato? { indice < passi.count ? passi[indice] : nil }
    var eRiepilogo: Bool { fase == .pronta && indice >= passi.count }
    /// «Passo 2 di 5» sopra i puntini (la web scrive i nomi dei passi, che sull'iPhone non ci stanno in una riga).
    var testoAvanzamento: String { Catalogo.Pav.passoDi(n: String(min(indice + 1, passi.count)), tot: String(passi.count)) }

    func esito(_ passo: PassoGuidato) -> EsitoPasso {
        if fattiOra.contains(passo) { return .fatto }
        return PrimoAvvioLogica.esito(passo, avanzamento: avanzamento, stato: stato, saltatiOra: saltatiOra)
    }

    /// La frase di «Tutto pronto», come la web: finito, o i passi non fatti per nome con dove ritrovarli.
    var frasePronto: String {
        PrimoAvvioLogica.frasePronto(nonFatti: PassoGuidato.allCases.filter { esito($0) != .fatto },
                                     roseImportate: stato.roseImportate == true)
    }

    // MARK: caricamento

    /// Legge lo stato della configurazione e quello della lega.
    func carica() async {
        fase = .carica
        do {
            let indirizzo = server.indirizzo
            let risposta: PrimoAvvioRisposta = try await server.get("/api/primo-avvio")
            avanzamento = risposta.primoAvvio
            passiServer = risposta.passi
            indirizzoLetto = indirizzo
        } catch {
            fase = .errore(error.localizedDescription)
            return
        }
        stato = await Self.leggiStato(server)
        if let passoFatto {
            fattiOra.insert(passoFatto)
            saltatiOra.remove(passoFatto)
        }
        let fattiDaDire = stato.fattiDaiDati.union(fattiOra)
        passi = PrimoAvvioLogica.daFare(avanzamento, stato: stato).filter { !fattiOra.contains($0) }
        indice = PrimoAvvioLogica.inizio(passi, riprendiDa: riprendiDa)
        fase = .pronta
        // Chi ha già cominciato e nel frattempo ha fatto dei passi (le rose, la squadra, il widget collegato): il server lo viene a
        // sapere.
        let ricordati = Set((avanzamento?.fatti ?? []).compactMap(PassoGuidato.init(rawValue:)))
        if avanzamento != nil || passoFatto != nil, !fattiDaDire.isSubset(of: ricordati) {
            await salva(fatti: fattiDaDire, saltati: [], chiuso: avanzamento?.chiuso ?? false)
        }
    }

    /// Cosa sa già l'app della lega: rose e mia squadra.
    static func leggiStato(_ server: any ServerClient) async -> StatoConfigurazione {
        let lega: StatoLega? = try? await server.get("/api/stato")
        return StatoConfigurazione(roseImportate: lega?.roseImportate, miaSquadra: lega?.miaSquadra)
    }

    /// All'apertura dell'app, senza rose: parte se non è mai stata iniziata, si riprende se era stata lasciata prima delle rose
    /// (`PrimoAvvioLogica.daAvviare`). Mai iniziata e con gli account (`conAccount`), prima si guarda la vecchia procedura
    /// (`GET /api/onboarding`) come `paControllaAvvio` della web: completata o saltata non parte, e se non risponde nemmeno (si
    /// riprova alla prossima apertura). Mai se l'app è stata aperta con un file o un'immagine da un'altra app (Condividi, «Apri
    /// con»): la guida non prende il posto di quella schermata. `apertaDaFuori` si guarda anche dopo le risposte del server,
    /// perché il file può arrivare mentre si aspettano.
    static func devePartire(server: any ServerClient, conAccount: Bool = false, apertaDaFuori: () -> Bool = { false }) async -> Bool {
        guard !apertaDaFuori(), let risposta: PrimoAvvioRisposta = try? await server.get("/api/primo-avvio") else { return false }
        let lega: StatoLega? = try? await server.get("/api/stato")
        var procedura: ProceduraVecchia?
        if conAccount, risposta.primoAvvio == nil, lega?.roseImportate == false {
            guard let vecchia: ProceduraVecchia = try? await server.get("/api/onboarding") else { return false }
            procedura = vecchia
        }
        return !apertaDaFuori() && PrimoAvvioLogica.daAvviare(risposta, roseImportate: lega?.roseImportate, procedura: procedura)
    }

    // MARK: azioni

    func segnaFatto(_ passo: PassoGuidato) async {
        fattiOra.insert(passo)
        saltatiOra.remove(passo)
        await salva(fatti: [passo], saltati: [], chiuso: false)
        avanza()
    }

    /// «L'ho già fatto» di widget e avvisi: come `segnaFatto`, ma non mentre un'altra azione è in corso (il pulsante è spento).
    func giaFatto(_ passo: PassoGuidato) async {
        guard !inCorso else { return }
        await segnaFatto(passo)
    }

    /// «Salta». Mentre un'azione è in corso (per esempio «Salva» dei tempi) non vale: il passo avanzerebbe due volte.
    func salta(_ passo: PassoGuidato) async {
        guard !inCorso else { return }
        saltatiOra.insert(passo)
        await salva(fatti: [], saltati: [passo], chiuso: false)
        avanza()
    }

    /// Le notifiche: si chiede il permesso; se arriva il passo è fatto, altrimenti si spiega dove cambiare.
    func attivaNotifiche() async {
        inCorso = true
        defer { inCorso = false }
        if await Notifiche.chiediPermesso() {
            avviso = nil
            await segnaFatto(.avvisi)
        } else {
            avviso = Catalogo.Pav.permessoNegatoAbilita
        }
    }

    /// Si esce a metà («Più tardi», oppure un passo che porta in un'altra schermata): i passi non fatti diventano saltati, così la
    /// guida non si riapre da sola (come la ✕ della web); si ritrovano in «Da fare» di Oggi.
    func piuTardi() async {
        lasciata = true
        let restanti = Set(passi.filter { esito($0) != .fatto })
        await salva(fatti: [], saltati: restanti, chiuso: false)
    }

    /// «Importa le rose»: la guida si chiude per la pagina delle rose e si riapre quando la pagina si lascia (`RitornoAllaGuida`),
    /// come la web che dopo le rose continua con i passi che restano (#880). Niente diventa saltato e la chiusura del foglio non
    /// salva: se l'app si chiude prima, all'apertura la guida si riprende dalle rose (`PrimoAvvioLogica.daRiprendere`).
    func versoLeRose() async {
        lasciata = true
    }

    // MARK: i tempi della lega

    /// All'apertura del passo «I tempi della lega» i menu prendono i valori salvati della lega, come `paTempiLeggi` della web. Un
    /// menu scelto a mano (`scadenzaScelta`, `primaScelta`, come `data-scelto` della web) la lettura non lo tocca, anche se arriva
    /// dopo. Una lettura alla volta: chi chiama mentre ce n'è una in corso la aspetta (`letturaTempi`); a lettura riuscita non si
    /// rilegge più. Vero se le regole sono lette; se non si leggono i menu restano come sono e «Salva» non li scrive (#801).
    @discardableResult
    func caricaTempi() async -> Bool {
        if tempiLetti { return true }
        if let giaPartita = letturaTempi { return await giaPartita.value }
        let lettura = Task { await leggiTempi() }
        letturaTempi = lettura
        let letti = await lettura.value
        letturaTempi = nil
        return letti
    }

    private func leggiTempi() async -> Bool {
        guard let regole: JSONValue = try? await server.get("/api/regole", snake: false) else { return false }
        let salvati = TempiGuida.valori(regole)
        scadenzeScelte = TempiGuida.sceltaScadenze(salvata: salvati.scadenza)
        applicoLettura = true
        if !scadenzaScelta { scadenza = salvati.scadenza }
        if !primaScelta { prima = salvati.prima }
        applicoLettura = false
        // una scadenza scelta a mano resta fra le voci anche dopo che il menu ha preso quelle della lega
        if !scadenzeScelte.contains(scadenza) { scadenzeScelte.append(scadenza) }
        tempiLetti = true
        return true
    }

    /// «Salva» del passo «I tempi della lega», come `paTempiSalva` della web: aspetta la lettura delle regole (quella in corso, o una
    /// nuova se la prima non è riuscita); se non riesce non scrive niente e lo dice; altrimenti rilegge le regole e le salva tutte,
    /// cambiando solo i due valori dei menu, e il passo è fatto.
    func salvaTempi() async {
        guard !inCorso else { return }
        inCorso = true
        defer { inCorso = false }
        guard await caricaTempi() else {
            avviso = Catalogo.Pav.tempiNonLetti
            return
        }
        do {
            let lette: JSONValue = try await server.get("/api/regole", snake: false)
            let nuove = TempiGuida.regole(lette, scadenza: scadenza, prima: prima)
            let _: JSONValue = try await server.posta("PUT", "/api/regole", nuove, snake: false)
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            avviso = error.localizedDescription
            return
        }
        if avviso == Catalogo.Pav.tempiNonLetti { avviso = nil }
        // la giornata della lega cambia subito anche nelle altre schermate (la web rilegge la testata)
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        await segnaFatto(.tempi)
    }

    /// Fine del percorso: non si riapre più da solo.
    func termina() async {
        lasciata = true
        await salva(fatti: [], saltati: [], chiuso: true)
    }

    /// Il foglio si è chiuso: se è stato trascinato giù (o toccato fuori sull'iPad) senza «Più tardi» né «Fine», vale come
    /// «Più tardi», come la web quando si chiude la guida con la ✕ (`paOsservaChiusura`). Non si salva niente a guida finita
    /// (riepilogo), prima che sia pronta, se l'ha chiusa l'app e non l'utente (`dallApp`: sessione finita, un file arrivato da
    /// fuori) o se nel frattempo è cambiato il server: i passi restano come erano.
    func chiusa(dallApp: Bool = false) async {
        guard !dallApp, !lasciata, fase == .pronta, !eRiepilogo, server.indirizzo == indirizzoLetto else { return }
        await piuTardi()
    }

    private func avanza() { indice = min(indice + 1, passi.count) }

    private func salva(fatti: Set<PassoGuidato>, saltati: Set<PassoGuidato>, chiuso: Bool) async {
        // Si manda tutto quello deciso finora, così un salvataggio fallito si recupera al passo dopo.
        let corpo = PrimoAvvioLogica.corpo(precedente: avanzamento, passiAmmessi: passiServer,
                                           fatti: fatti.union(fattiOra), saltati: saltati.union(saltatiOra), chiuso: chiuso)
        do {
            _ = try await server.corpoJSON("PUT", "/api/primo-avvio", corpo)
            avanzamento = AvanzamentoPrimoAvvio(fatti: corpo.fatti, saltati: corpo.saltati, chiuso: corpo.chiuso, aggiornato: avanzamento?.aggiornato)
            if avviso == Self.erroreSalvataggio { avviso = nil }
        } catch {
            // Non si blocca il percorso: il passo resta fatto o saltato qui e si ritenta al prossimo salvataggio.
            avviso = Self.erroreSalvataggio
        }
    }
}
