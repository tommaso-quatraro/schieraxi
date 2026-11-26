import Foundation

// Configurazione guidata («Primo avvio»): pochi passi che si possono saltare, ricordati sul server (GET/PUT /api/primo-avvio)
// così si riprende anche da un altro dispositivo. I passi sono quelli della web (rose, squadra, tempi della lega, #931) più widget e
// avvisi, che ha solo l'iPhone; gli altri passi del server (server, accesso, stemma, pwa) li segnano altri client o versioni di
// prima: qui si lasciano come sono.

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

/// La vecchia procedura guidata degli account (`GET /api/onboarding`, solo con gli account): conta solo com'è finita.
struct ProceduraVecchia: Decodable, Equatable {
    var stato: String?

    init(stato: String? = nil) { self.stato = stato }

    private enum Chiavi: String, CodingKey { case stato }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        stato = (try? k.decodeIfPresent(String.self, forKey: .stato)) ?? nil
    }

    /// Completata o saltata: chi l'ha già fatta (o lasciata) non rivede la guida da sola, come la web (`paControllaAvvio`).
    var finita: Bool { stato == "completato" || stato == "saltato" }
}

/// `PUT /api/primo-avvio`.
struct CorpoPrimoAvvio: Codable, Equatable {
    var fatti: [String]
    var saltati: [String]
    var chiuso: Bool
}

/// I passi che gestisce questa app, nell'ordine in cui si propongono: i tre della web (`PA_PASSI` di primoavvio.js), poi widget e
/// avvisi, che la web non ha (differenza ammessa, #931). Lo stemma non è un passo: «Tutto pronto» dice che sta in Impostazioni.
enum PassoGuidato: String, CaseIterable, Identifiable {
    case rose, squadra, tempi, widget, avvisi
    var id: String { rawValue }

    /// Il nome del passo, come `PA_NOMI` della web («Le rose», «La tua squadra», «I tempi della lega»).
    var titolo: String {
        switch self {
        case .rose: return Catalogo.Pav.nRose
        case .squadra: return Catalogo.Pav.nSquadra
        case .tempi: return Catalogo.Pav.nTempi
        case .widget: return Catalogo.Pav.nWidget
        case .avvisi: return Catalogo.Pav.nAvvisi
        }
    }

    /// La frase sotto il nome. Rose e squadra si fanno poi nella loro pagina (sulla web dentro la guida), i tempi qui sotto.
    var spiegazione: String {
        switch self {
        case .rose: return Catalogo.Pav.roseSpiega
        case .squadra: return Catalogo.Pav.qualeSquadraTua
        case .tempi: return Catalogo.Pav.tempiSpiega
        case .widget: return Catalogo.Pav.widgetSpiega
        // solo ciò che fanno i promemoria dell'app (#906): l'avviso quando cambia la formazione lo manda il server alla web
        case .avvisi: return Catalogo.Pav.avvisiSpiega
        }
    }

    var icona: String {
        switch self {
        case .rose: return "square.and.arrow.down"
        case .squadra: return "person.3"
        case .tempi: return "clock"
        case .widget: return "rectangle.on.rectangle"
        case .avvisi: return "bell.badge"
        }
    }

    /// Il testo del pulsante principale; per gli avvisi quello di «Tutto pronto» della web.
    var azione: String {
        switch self {
        case .rose: return Catalogo.Comune.importaRose
        case .squadra: return Catalogo.Pav.scegliSquadra
        case .tempi: return Catalogo.Pav.tempiSalva
        case .widget: return Catalogo.Pav.collegaWidget
        case .avvisi: return Catalogo.Onb.attivaGliAvvisiB
        }
    }

    /// Widget e avvisi dipendono dal telefono e l'app non li vede fatti dai dati della lega: si segnano anche con «L'ho già fatto».
    var siSegnaAMano: Bool { self == .widget || self == .avvisi }

    /// Il nome usato dal server.
    var nomeServer: String { rawValue }
}

/// Quello che l'app sa già di per sé (dalla lega): serve a saltare i passi già fatti.
struct StatoConfigurazione: Equatable {
    var roseImportate: Bool?
    var miaSquadra: String?

    /// Passi che risultano fatti dai dati della lega, come `paGiaFatti` della web (i tempi li ricorda il server; widget e avvisi
    /// dipendono dal telefono: si segnano a mano).
    var fattiDaiDati: Set<PassoGuidato> {
        var fatti = Set<PassoGuidato>()
        if roseImportate == true { fatti.insert(.rose) }
        if let s = miaSquadra, !s.isEmpty { fatti.insert(.squadra) }
        return fatti
    }
}

enum PrimoAvvioLogica {
    /// Quanti passi al massimo il server accetta in una lista.
    static let massimoVoci = 12

    /// All'apertura dell'app si apre da sola solo se mancano le rose (chi ha già la lega non la vede mai da sola), come
    /// `primoAvvioSeServe` della web: si riprende se è da riprendere (`daRiprendere`); se non è mai stata iniziata parte, tranne
    /// quando la vecchia procedura degli account (`procedura`, nil senza account) è già completata o saltata.
    static func daAvviare(_ risposta: PrimoAvvioRisposta?, roseImportate: Bool?, procedura: ProceduraVecchia? = nil) -> Bool {
        guard let risposta, roseImportate == false else { return false }
        guard let avanzamento = risposta.primoAvvio else { return !(procedura?.finita ?? false) }
        return daRiprendere(avanzamento)
    }

    /// Cominciata (anche sulla web o su un altro dispositivo) e lasciata prima delle rose: non chiusa, passo «rose» né fatto né
    /// saltato. Stessa regola di `paDaRiprendere` della web. «Più tardi» (e la ✕ della web) segna saltati i passi rimasti, rose
    /// comprese: così chi la chiude non la rivede da sola.
    static func daRiprendere(_ avanzamento: AvanzamentoPrimoAvvio?) -> Bool {
        guard let avanzamento else { return false }
        let rose = PassoGuidato.rose.nomeServer
        return !avanzamento.chiuso && !avanzamento.fatti.contains(rose) && !avanzamento.saltati.contains(rose)
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

    /// Da quale dei `passi` parte la guida. Aperta da sola o da «Da fare» (`riprendiDa` nil), dal primo. Riaperta dopo una pagina in
    /// cui l'aveva portata un passo (#880), da quel passo se è ancora da fare (il widget, che l'app non sa se è collegato, si
    /// segna con «L'ho già fatto»), altrimenti dal primo dopo: i passi prima, già decisi, non si ripropongono. Nessuno dopo:
    /// `passi.count`, cioè «Tutto pronto».
    static func inizio(_ passi: [PassoGuidato], riprendiDa: PassoGuidato?) -> Int {
        let ordine = PassoGuidato.allCases
        guard let riprendiDa, let soglia = ordine.firstIndex(of: riprendiDa) else { return 0 }
        return passi.firstIndex { (ordine.firstIndex(of: $0) ?? 0) >= soglia } ?? passi.count
    }

    /// Il corpo del PUT: si parte da quello che il server ricorda (anche i passi di altri dispositivi) e si aggiunge il nuovo.
    /// Un passo non sta mai in «fatti» e «saltati» insieme; i nomi che il server non conosce non si mandano (darebbero errore).
    static func corpo(precedente: AvanzamentoPrimoAvvio?, passiAmmessi: [String], fatti nuoviFatti: Set<PassoGuidato>,
                      saltati nuoviSaltati: Set<PassoGuidato>, chiuso: Bool) -> CorpoPrimoAvvio {
        let ammessi = passiAmmessi.isEmpty ? Set(["server", "accesso", "rose", "stemma", "squadra", "tempi", "pwa", "widget", "avvisi"])
                                           : Set(passiAmmessi)
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

    /// Una riga per ogni passo, per il riepilogo: fatto, saltato o da fare.
    static func esito(_ passo: PassoGuidato, avanzamento: AvanzamentoPrimoAvvio?, stato: StatoConfigurazione, saltatiOra: Set<PassoGuidato> = []) -> EsitoPasso {
        if fatti(avanzamento, stato: stato).contains(passo) { return .fatto }
        if saltatiOra.contains(passo) || (avanzamento?.saltati ?? []).contains(passo.nomeServer) { return .saltato }
        return .daFare
    }

    /// La frase di «Tutto pronto», come `paFine` della web: «Hai finito la configurazione.» o i passi non fatti per nome, con dove
    /// ritrovarli (dalla Formazione; senza rose con «Importa le rose» della Formazione, che riapre la guida).
    static func frasePronto(nonFatti: [PassoGuidato], roseImportate: Bool) -> String {
        guard !nonFatti.isEmpty else { return Catalogo.Pav.haiFinito }
        let nomi = nonFatti.map(\.titolo).joined(separator: ", ")
        return roseImportate ? Catalogo.Pav.haiSaltato(nomi: nomi) : Catalogo.Pav.haiSaltatoSenzaRose(nomi: nomi)
    }
}

enum EsitoPasso: Equatable {
    case fatto, saltato, daFare

    /// Accanto al nome del passo nel riepilogo, come l'indicatore dei passi della web: «Le rose (fatto)», «Il widget (saltato)».
    var suffisso: String {
        switch self {
        case .fatto: return Catalogo.Pav.fattoPar
        case .saltato: return Catalogo.Pav.saltatoPar
        case .daFare: return ""
        }
    }
}
