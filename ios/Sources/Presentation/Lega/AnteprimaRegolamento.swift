import Foundation

/// I valori dell'anteprima del regolamento incollato dopo «Riconosci le regole», come la web (#889, dopo la #884: `vistaRegole`
/// in `fanta/web/app.js`): sotto «Riconosciuto» i valori di `modifiche`, gli unici che «Applica ai campi» mette nei campi; sotto
/// «Non applicato» quelli di `non_applicabili`, che con le regole di adesso non si possono salvare così come sono, ognuno con il
/// perché del server (`motivo`, il testo italiano di `motivo_frase`). I valori si scrivono con le parole della pagina: l'ordine dei
/// cambi «Per ruolo» o «Libera», i posti per ruolo «2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti». Valori, motivi e
/// righe sono del server: qui si scelgono solo i testi. Le righe da controllare a mano sono in `RegolamentoDaControllare`.
/// Logica pura: la provano i test.
struct AnteprimaRegolamento: Equatable, Sendable {
    /// Un valore letto nel regolamento.
    struct Valore: Equatable, Sendable, Identifiable {
        /// Il posto nell'elenco: due valori possono avere la stessa chiave.
        let id: Int
        /// «Ordine dei cambi: Per ruolo».
        let testo: String
        /// Solo per i valori non applicati: il perché del server; nil se non lo manda.
        let motivo: String?
        /// «da: «Panchina: 12 giocatori»»; nil se il server non dice da quale riga viene.
        let daRiga: String?
    }

    let riconosciuti: [Valore]
    let nonApplicati: [Valore]

    /// Niente da mostrare: al loro posto «Non ho riconosciuto nessuna regola…», come la web.
    var vuota: Bool { riconosciuti.isEmpty && nonApplicati.isEmpty }
    /// «Applica ai campi» c'è solo con qualcosa da applicare, come «Salva queste regole» della web.
    var siApplica: Bool { !riconosciuti.isEmpty }

    init(_ esito: RiconoscimentoRegole) {
        riconosciuti = esito.modifiche.enumerated().map { voce in
            let m = voce.element
            return Valore(id: voce.offset, testo: Self.testo(m.etichetta, chiave: m.chiave, valore: m.valore), motivo: nil,
                          daRiga: Self.daRiga(m.riga))
        }
        // un valore senza etichetta né chiave non si saprebbe di che regola è: non si mostra
        nonApplicati = (esito.nonApplicabili ?? []).compactMap { n -> (ValoreNonApplicabile, String)? in
            guard let nome = n.etichetta ?? n.chiave else { return nil }
            return (n, nome)
        }
        .enumerated().map { voce in
            let (n, nome) = voce.element
            let motivo = n.motivo?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return Valore(id: voce.offset, testo: Self.testo(nome, chiave: n.chiave ?? "", valore: n.valore),
                          motivo: motivo.isEmpty ? nil : motivo, daRiga: Self.daRiga(n.riga))
        }
    }

    /// Come si scrive un valore letto, con le parole della pagina come la web (`vedi` in `vistaRegole`): l'ordine dei cambi come i
    /// suoi pulsanti («Per ruolo», «Libera»), i posti per ruolo per esteso, con il plurale giusto; il resto come prima
    /// (`RegoleLogica.descrivi`).
    static func valore(chiave: String, _ valore: JSONValue) -> String {
        switch (chiave, valore) {
        case ("panchina.tipo", .testo("per_ruolo")):
            return Catalogo.Regole.perRuolo
        case ("panchina.tipo", .testo("libera")):
            return Catalogo.Regole.libera
        case ("panchina.posti", .oggetto(let posti)):
            let ruoli: [(String, (Int) -> String)] = [("P", Catalogo.Frase.rosePortieri), ("D", Catalogo.Frase.roseDifensori),
                                                      ("C", Catalogo.Frase.roseCentrocampisti), ("A", Catalogo.Frase.roseAttaccanti)]
            return ruoli.map { ruolo, frase in frase(quanti(posti[ruolo])) }.joined(separator: ", ")
        default:
            return RegoleLogica.descrivi(valore)
        }
    }

    /// «etichetta: valore», o la sola etichetta se il server non manda il valore.
    private static func testo(_ etichetta: String, chiave: String, valore: JSONValue?) -> String {
        guard let valore else { return etichetta }
        return "\(etichetta): \(Self.valore(chiave: chiave, valore))"
    }

    private static func daRiga(_ riga: String?) -> String? {
        riga.map { Catalogo.Regole.daRiga(r: $0) }
    }

    /// I posti di un ruolo come numero intero (0 se mancano), come `Number(m.valore[x] ?? 0)` della web.
    private static func quanti(_ valore: JSONValue?) -> Int {
        guard let n = valore?.numero, n.isFinite, abs(n) < 1_000_000 else { return 0 }
        return Int(n.rounded())
    }
}
