import SwiftUI

/// Dove porta un passo della configurazione guidata (la schermata si chiude, poi l'app va lì).
enum AzioneGuida: Equatable {
    case importaRose
    case squadre(nome: String?)
    case impostazioni
    /// «Collega il widget»: lo collega da solo (App Group o Keychain condiviso); solo se non va copia il codice.
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

    static let erroreSalvataggio = "Non sono riuscito a salvare i progressi sul server. Riprovo al prossimo passo."

    private let server: any ServerClient
    private var passiServer: [String] = []

    init(server: any ServerClient) {
        self.server = server
        super.init()
    }

    var passoCorrente: PassoGuidato? { indice < passi.count ? passi[indice] : nil }
    var eRiepilogo: Bool { fase == .pronta && indice >= passi.count }
    var testoAvanzamento: String { "Passo \(min(indice + 1, passi.count)) di \(passi.count)" }

    func esito(_ passo: PassoGuidato) -> EsitoPasso {
        if fattiOra.contains(passo) { return .fatto }
        return PrimoAvvioLogica.esito(passo, avanzamento: avanzamento, stato: stato, saltatiOra: saltatiOra)
    }

    // MARK: caricamento

    /// Legge lo stato della configurazione e quello della lega.
    func carica() async {
        fase = .carica
        do {
            let risposta: PrimoAvvioRisposta = try await server.get("/api/primo-avvio")
            avanzamento = risposta.primoAvvio
            passiServer = risposta.passi
        } catch {
            fase = .errore(error.localizedDescription)
            return
        }
        stato = await Self.leggiStato(server)
        let fattiOraDaiDati = stato.fattiDaiDati
        passi = PrimoAvvioLogica.daFare(avanzamento, stato: stato)
        indice = 0
        fase = .pronta
        // Chi ha già cominciato e nel frattempo ha fatto dei passi (le rose, la squadra): il server lo viene a sapere.
        if let a = avanzamento, !fattiOraDaiDati.isSubset(of: Set(a.fatti.compactMap(PassoGuidato.init(rawValue:)))) {
            await salva(fatti: fattiOraDaiDati, saltati: [], chiuso: a.chiuso)
        }
    }

    /// Cosa sa già l'app della lega: rose, mia squadra, stemma e maglia.
    static func leggiStato(_ server: any ServerClient) async -> StatoConfigurazione {
        var s = StatoConfigurazione()
        let lega: StatoLega? = try? await server.get("/api/stato")
        s.roseImportate = lega?.roseImportate
        s.miaSquadra = lega?.miaSquadra
        if let squadre: [SquadraLega] = try? await server.get("/api/squadre"),
           let mia = squadre.first(where: { $0.mia == true }) {
            s.stemmaEMaglia = mia.immagini?.stemma == true && mia.immagini?.maglia == true
        }
        return s
    }

    /// All'apertura dell'app: parte da sola solo se non l'ha mai iniziato E mancano le rose.
    static func devePartire(server: any ServerClient) async -> Bool {
        guard let risposta: PrimoAvvioRisposta = try? await server.get("/api/primo-avvio") else { return false }
        let lega: StatoLega? = try? await server.get("/api/stato")
        return PrimoAvvioLogica.daAvviare(risposta, roseImportate: lega?.roseImportate)
    }

    // MARK: azioni

    func segnaFatto(_ passo: PassoGuidato) async {
        fattiOra.insert(passo)
        saltatiOra.remove(passo)
        await salva(fatti: [passo], saltati: [], chiuso: false)
        avanza()
    }

    func salta(_ passo: PassoGuidato) async {
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
            avviso = "Le notifiche non sono attive. Puoi accenderle in Impostazioni del telefono, nella voce di SchieraXI, e poi scegliere quali avvisi ricevere nelle Impostazioni di SchieraXI."
        }
    }

    /// Si esce a metà (X, oppure un passo che porta in un'altra schermata): i passi non fatti restano da riprendere.
    func piuTardi() async {
        let restanti = Set(passi.filter { esito($0) != .fatto })
        await salva(fatti: [], saltati: restanti, chiuso: false)
    }

    /// Fine del percorso: non si riapre più da solo.
    func termina() async {
        await salva(fatti: [], saltati: [], chiuso: true)
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
