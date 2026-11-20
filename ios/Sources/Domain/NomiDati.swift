import Foundation

/// Le righe di «Ultimi aggiornamenti» in Stato dei dati: il nome lo scrive il server (campo `etichetta`, come la web); i nomi
/// grezzi dei dati («dati-extra», «crediti-giocatore 2026-10») si traducono qui solo per un server di prima, senza il campo.
enum NomiDati {
    private static let noti: [String: String] = [
        "aggiornamento": "Aggiornamento generale",
        "dati-extra": "Dati extra delle partite",
        "voti": "Voti delle giornate",
        "calendario": "Calendario",
        "listone": "Elenco dei calciatori",
        "probabili": "Probabili formazioni",
        "understat": "Statistiche delle partite",
        // la riga scritta a ogni cambio della taratura di «gioca N%» (#379), come `sd.f_taratura` della web
        "taratura-probabili": "Taratura di «gioca N%»",
    ]

    /// Voci di server vecchi che l'app non mostra più (fonti di dati non più usate).
    static func daNascondere(_ cosa: String) -> Bool {
        cosa.lowercased().hasPrefix("quote")
    }

    /// Il nome di una riga di «Ultimi aggiornamenti», come la web (#808): il campo `etichetta` del server («Listone e quotazioni»);
    /// un server di prima, senza il campo, ha i nomi dell'app (`leggibile`).
    static func nome(_ a: AggiornamentoDati) -> String {
        if let etichetta = a.etichetta?.trimmingCharacters(in: .whitespacesAndNewlines), !etichetta.isEmpty { return etichetta }
        return leggibile(a.cosa)
    }

    /// Quando è riuscito l'ultima volta; per un passo mai riuscito (senza `quando`) «mai», come la web (`sd.mai`).
    static func quando(_ a: AggiornamentoDati) -> String {
        guard let quando = a.quando?.trimmingCharacters(in: .whitespacesAndNewlines), !quando.isEmpty else { return Catalogo.Sd.mai }
        return Quando.leggibile(quando.replacingOccurrences(of: "T", with: " "))
    }

    static func leggibile(_ cosa: String) -> String {
        let t = cosa.trimmingCharacters(in: .whitespaces)
        let minuscolo = t.lowercased()
        if let n = noti[minuscolo] { return n }
        // «crediti-giocatore 2026-10» -> «Crediti dei giocatori»
        if minuscolo.hasPrefix("crediti-giocatore") { return "Crediti dei giocatori" }
        let parole = minuscolo.replacingOccurrences(of: "-", with: " ").replacingOccurrences(of: "_", with: " ")
        return parole.prefix(1).uppercased() + parole.dropFirst()
    }

    /// Il numero dopo una «g» alla fine («... g10»).
    private static func giornata(in testo: String) -> Int? {
        guard let ultima = testo.split(separator: " ").last, ultima.hasPrefix("g"), let n = Int(ultima.dropFirst()) else { return nil }
        return n
    }
}
