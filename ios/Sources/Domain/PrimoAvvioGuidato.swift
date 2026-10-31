import Foundation

// Configurazione guidata («Primo avvio»): pochi passi che si possono saltare, ricordati sul server (GET/PUT /api/primo-avvio)
// così si riprende anche da un altro dispositivo. Questa app gestisce rose, squadra, stemma e maglia, widget e avvisi; gli altri
// passi del server (server, accesso, pwa) li segnano altri client: qui si lasciano come sono.

/// Cosa il server ricorda del percorso guidato.
struct AvanzamentoPrimoAvvio: Decodable, Equatable {
    var fatti: [String] = []
    var saltati: [String] = []
    var chiuso: Bool = false
    var aggiornato: String?

    init(fatti: [String] = [], saltati: [String] = [], chiuso: Bool = false, aggiornato: String? = nil) {
        self.fatti = fatti; self.saltati = saltati; self.chiuso = chiuso; self.aggiornato = aggiornato
    }

    private enum Chiavi: String, CodingKey { case fatti, saltati, chiuso, aggiornato }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        fatti = (try? k.decodeIfPresent([String].self, forKey: .fatti)) ?? []
        saltati = (try? k.decodeIfPresent([String].self, forKey: .saltati)) ?? []
        chiuso = (try? k.decodeIfPresent(Bool.self, forKey: .chiuso)) ?? false
        aggiornato = (try? k.decodeIfPresent(String.self, forKey: .aggiornato)) ?? nil
    }
}

/// `GET /api/primo-avvio`. `primoAvvio` nil = non l'ha mai iniziato.
struct PrimoAvvioRisposta: Decodable, Equatable {
    var primoAvvio: AvanzamentoPrimoAvvio?
    var passi: [String] = []

    init(primoAvvio: AvanzamentoPrimoAvvio? = nil, passi: [String] = []) { self.primoAvvio = primoAvvio; self.passi = passi }

    private enum Chiavi: String, CodingKey { case primoAvvio, passi }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        primoAvvio = (try? k.decodeIfPresent(AvanzamentoPrimoAvvio.self, forKey: .primoAvvio)) ?? nil
        passi = (try? k.decodeIfPresent([String].self, forKey: .passi)) ?? []
    }
}

/// `PUT /api/primo-avvio`.
struct CorpoPrimoAvvio: Codable, Equatable {
    var fatti: [String]
    var saltati: [String]
    var chiuso: Bool
}

/// I passi che gestisce questa app, nell'ordine in cui si propongono.
enum PassoGuidato: String, CaseIterable, Identifiable {
    case rose, squadra, stemma, widget, avvisi
    var id: String { rawValue }

    var titolo: String {
        switch self {
        case .rose: return "Carica le rose"
        case .squadra: return "Scegli la tua squadra"
        case .stemma: return "Stemma e maglia"
        case .widget: return "Aggiungi il widget"
        case .avvisi: return "Attiva gli avvisi"
        }
    }

    var spiegazione: String {
        switch self {
        case .rose:
            return "Servono le rose di tutte le squadre della lega. Importa il file della tua lega (Excel, CSV o testo): ci vuole un minuto."
        case .squadra:
            return "Indica quale delle squadre è la tua: i consigli di formazione e di scambio sono per lei."
        case .stemma:
            return "Scegli lo stemma e la maglia della tua squadra dalle tue foto. Compaiono in Oggi e nella formazione."
        case .widget:
            return "Tieni premuto sulla Home, tocca + e cerca SchieraXI. Poi in «Modifica widget» scrivi l'indirizzo del server e il codice di collegamento che crei nelle Impostazioni."
        case .avvisi:
            return "Ti avvisiamo prima della partita se un titolare è in dubbio e quando la formazione consigliata cambia."
        }
    }

    var icona: String {
        switch self {
        case .rose: return "square.and.arrow.down"
        case .squadra: return "person.3"
        case .stemma: return "shield.lefthalf.filled"
        case .widget: return "rectangle.on.rectangle"
        case .avvisi: return "bell.badge"
        }
    }

    /// Il testo del pulsante principale.
    var azione: String {
        switch self {
        case .rose: return "Importa le rose"
        case .squadra: return "Scegli la squadra"
        case .stemma: return "Scegli stemma e maglia"
        case .widget: return "Apri le Impostazioni"
        case .avvisi: return "Attiva le notifiche"
        }
    }

    /// Il nome usato dal server.
    var nomeServer: String { rawValue }
}

/// Quello che l'app sa già di per sé (dalla lega): serve a saltare i passi già fatti.
struct StatoConfigurazione: Equatable {
    var roseImportate: Bool?
    var miaSquadra: String?
    var stemmaEMaglia: Bool?

    /// Passi che risultano fatti dai dati della lega (widget e avvisi dipendono dal telefono: si segnano a mano).
    var fattiDaiDati: Set<PassoGuidato> {
        var fatti = Set<PassoGuidato>()
        if roseImportate == true { fatti.insert(.rose) }
        if let s = miaSquadra, !s.isEmpty { fatti.insert(.squadra) }
        if stemmaEMaglia == true { fatti.insert(.stemma) }
        return fatti
    }
}

enum PrimoAvvioLogica {
    /// Quanti passi al massimo il server accetta in una lista.
    static let massimoVoci = 12

    /// Si avvia da solo solo se non l'ha mai iniziato E mancano le rose (chi ha già la lega non lo vede mai).
    static func daAvviare(_ risposta: PrimoAvvioRisposta?, roseImportate: Bool?) -> Bool {
        guard let risposta, risposta.primoAvvio == nil else { return false }
        return roseImportate == false
    }

    /// I passi fatti: quelli ricordati dal server più quelli che i dati della lega mostrano già fatti.
    static func fatti(_ avanzamento: AvanzamentoPrimoAvvio?, stato: StatoConfigurazione) -> Set<PassoGuidato> {
        let ricordati = Set((avanzamento?.fatti ?? []).compactMap(PassoGuidato.init(rawValue:)))
        return ricordati.union(stato.fattiDaiDati)
    }

    /// I passi da proporre, nell'ordine: tutti tranne quelli già fatti (anche quelli saltati si ripropongono).
    static func daFare(_ avanzamento: AvanzamentoPrimoAvvio?, stato: StatoConfigurazione) -> [PassoGuidato] {
        let gia = fatti(avanzamento, stato: stato)
        return PassoGuidato.allCases.filter { !gia.contains($0) }
    }

    /// Il corpo del PUT: si parte da quello che il server ricorda (anche i passi di altri dispositivi) e si aggiunge il nuovo.
    /// Un passo non sta mai in «fatti» e «saltati» insieme; i nomi che il server non conosce non si mandano (darebbero errore).
    static func corpo(precedente: AvanzamentoPrimoAvvio?, passiAmmessi: [String], fatti nuoviFatti: Set<PassoGuidato>,
                      saltati nuoviSaltati: Set<PassoGuidato>, chiuso: Bool) -> CorpoPrimoAvvio {
        let ammessi = passiAmmessi.isEmpty ? Set(["server", "accesso", "rose", "squadra", "stemma", "pwa", "widget", "avvisi"]) : Set(passiAmmessi)
        let ordine = passiAmmessi.isEmpty ? PassoGuidato.allCases.map(\.nomeServer) : passiAmmessi
        var fatti = Set(precedente?.fatti ?? []).union(nuoviFatti.map(\.nomeServer))
        var saltati = Set(precedente?.saltati ?? []).union(nuoviSaltati.map(\.nomeServer))
        saltati.subtract(fatti)
        fatti.formIntersection(ammessi)
        saltati.formIntersection(ammessi)
        func ordinati(_ s: Set<String>) -> [String] {
            let primi = ordine.filter { s.contains($0) }
            return Array(primi.prefix(massimoVoci))
        }
        return CorpoPrimoAvvio(fatti: ordinati(fatti), saltati: ordinati(saltati), chiuso: chiuso)
    }

    /// Una riga per ogni passo, per il riepilogo: «Fatto», «Saltato», «Da fare».
    static func esito(_ passo: PassoGuidato, avanzamento: AvanzamentoPrimoAvvio?, stato: StatoConfigurazione, saltatiOra: Set<PassoGuidato> = []) -> EsitoPasso {
        if fatti(avanzamento, stato: stato).contains(passo) { return .fatto }
        if saltatiOra.contains(passo) || (avanzamento?.saltati ?? []).contains(passo.nomeServer) { return .saltato }
        return .daFare
    }
}

enum EsitoPasso: Equatable {
    case fatto, saltato, daFare

    var testo: String {
        switch self {
        case .fatto: return "Fatto"
        case .saltato: return "Saltato"
        case .daFare: return "Da fare"
        }
    }
}
