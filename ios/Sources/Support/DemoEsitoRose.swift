import Foundation

/// L'esito di un salvataggio delle rose con dati INVENTATI, solo per le fotografie del simulatore:
/// `-DEMO_SCHERMATA lega-importa-salvate` (con un avviso da controllare) e `lega-importa-salvate-ok` (tutto in ordine).
/// Per le altre schermate, e fuori dalla demo (`Demo.schermata` vuota), non c'è nessun esito.
enum DemoEsitoRose {
    static func esito(_ schermata: String?) -> EsitoImportazione? {
        guard schermata == "lega-importa-salvate" || schermata == "lega-importa-salvate-ok" else { return nil }
        let avvisi = schermata == "lega-importa-salvate" ? #"["Real Mandrake: «Bastrani» non è nel listone."]"# : "[]"
        let json = #"""
        {"squadre_importate": ["Gli Amici del Bar Sport Centrale", "Real Mandrake", "Atletico Divano"], "totale_squadre": 3,
         "avvisi": \#(avvisi), "mia_squadra": "Gli Amici del Bar Sport Centrale",
         "differenze": {"scambi": [{"squadre": ["Real Mandrake", "Atletico Divano"], "da_a": [{"nome": "Sorvani"}], "da_b": [{"nome": "Marténi"}]}],
           "svincolati_presi": [{"squadra": "Atletico Divano", "giocatori": [{"nome": "Bastrani"}]}], "tagliati": [],
           "crediti": [{"squadra": "Real Mandrake", "prima": 120, "dopo": 95}]}}
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
