import Foundation

/// L'esito di un salvataggio delle rose con dati INVENTATI, solo per le fotografie del simulatore:
/// `-DEMO_SCHERMATA lega-importa-salvate` (con un avviso da controllare) e `lega-importa-salvate-ok` (tutto in ordine).
/// Squadre e giocatori sono quelli della lega della demo (`LegaDemo`): chi si muove esiste e nessun avviso lo contraddice.
/// Per le altre schermate, e fuori dalla demo (`Demo.schermata` vuota), non c'è nessun esito.
enum DemoEsitoRose {
    static func esito(_ schermata: String?) -> EsitoImportazione? {
        guard schermata == "lega-importa-salvate" || schermata == "lega-importa-salvate-ok" else { return nil }
        // un nome che nella demo non esiste (il test di fumo, FumoUITests, cerca questo avviso)
        let avvisi = schermata == "lega-importa-salvate" ? #"["Real Madrink: «Bastrini» non è nel listone."]"# : "[]"
        let json = #"""
        {"squadre_importate": ["\#(LegaDemo.nomeMia)", "Real Madrink", "Dinamo Pizza"], "totale_squadre": 8,
         "avvisi": \#(avvisi), "mia_squadra": "\#(LegaDemo.nomeMia)",
         "differenze": {"scambi": [{"squadre": ["Real Madrink", "Dinamo Pizza"], "da_a": [{"id": 325, "nome": "Kaan Yurdız", "ruolo": "A"}],
                                    "da_b": [{"id": 321, "nome": "Sandy McTarran", "ruolo": "C"}]}],
           "svincolati_presi": [{"squadra": "Dinamo Pizza", "giocatori": [{"id": 204, "nome": "Nenad Krslić", "ruolo": "A"}]}], "tagliati": [],
           "crediti": [{"squadra": "Dinamo Pizza", "prima": 33, "dopo": 25}]}}
        """#
        do {
            let esito: EsitoImportazione = try Decodifica.decodifica(Data(json.utf8))
            return esito
        } catch {
            // dati scritti qui sopra: se non si leggono è un errore di chi li ha cambiati, da vedere subito in debug
            assertionFailure("DemoEsitoRose: il JSON dell'esito finto non si legge: \(error)")
            return nil
        }
    }
}
