import Foundation

/// L'anteprima delle rose della modalità demo (`POST /api/rose/anteprima` e `/anteprima/file`): squadre e giocatori INVENTATI,
/// come il resto della demo. Tre squadre: la mia con due dubbi (un nome simile e uno ambiguo), una con un portiere in meno e due
/// nomi non trovati, una nuova completa. Serve alle fotografie (`-DEMO_SCHERMATA lega-importa-csv`) e alle anteprime di Xcode.
enum DemoAnteprimaRose {
    private static func sicuro(_ testo: String, _ id: Int, _ nome: String, _ ruolo: String, _ squadra: String, _ costo: Int) -> String {
        #"{"testo": "\#(testo)", "stato": "sicuro", "metodo": "esatto", "id": \#(id), "nome": "\#(nome)", "ruolo": "\#(ruolo)", "squadra": "\#(squadra)", "costo": \#(costo), "avviso": "", "alternative": []}"#
    }

    static let json: String = #"""
    {"squadre": [
      {"nome": "Schiera FC", "nuova": false, "crediti_residui": 12, "sicuri": 23, "da_controllare": 2, "non_trovati": 0,
       "totale": 25, "attesi": 25, "ruoli": {"P": 3, "D": 8, "C": 8, "A": 6}, "mancano": {}, "in_piu": {}, "senza_ruolo": 0,
       "completa": true, "avvisi": [], "giocatori": [
        \#(sicuro("Sorvani", 101, "Ivo Sorvani", "P", "inter", 12)),
        \#(sicuro("Magrenti", 102, "Milo Magrenti", "P", "milan", 22)),
        \#(sicuro("Bastrani A.", 104, "Alvise Bastrani", "D", "inter", 28)),
        \#(sicuro("Dimarzi", 105, "Fabio Dimarzi", "D", "inter", 31)),
        \#(sicuro("Barlesi", 112, "Nestore Barlesi", "C", "inter", 34)),
        \#(sicuro("Thorvan", 121, "Marvin Thorvan", "A", "inter", 52)),
        {"testo": "Marteni", "stato": "da_controllare", "metodo": "simile", "id": 120, "nome": "Leonel Marténi", "ruolo": "A",
         "squadra": "inter", "costo": 80, "avviso": "", "alternative": [{"id": 120, "nome": "Leonel Marténi", "ruolo": "A", "squadra": "inter"}]},
        {"testo": "Kervan", "stato": "da_controllare", "metodo": "ambiguo", "id": null, "nome": null, "ruolo": "A", "squadra": null,
         "costo": 18, "avviso": "", "alternative": [{"id": 125, "nome": "Mosè Kervan", "ruolo": "A", "squadra": "fiorentina"},
                                                    {"id": 338, "nome": "Ilian Kervan", "ruolo": "C", "squadra": "torino"}]}
      ]},
      {"nome": "Dinamo Pizza", "nuova": false, "crediti_residui": 7, "sicuri": 22, "da_controllare": 0, "non_trovati": 2,
       "totale": 24, "attesi": 25, "ruoli": {"P": 2, "D": 8, "C": 8, "A": 6}, "mancano": {"P": 1}, "in_piu": {}, "senza_ruolo": 0,
       "completa": false, "avvisi": ["24 giocatori su 25", "mancano 1 portiere"], "giocatori": [
        \#(sicuro("Yurdiz", 325, "Kaan Yurdız", "A", "juventus", 33)),
        \#(sicuro("McTarran", 321, "Sandy McTarran", "C", "napoli", 25)),
        \#(sicuro("Krslic", 204, "Nenad Krslić", "A", "lecce", 5)),
        {"testo": "Rossignoli", "stato": "non_trovato", "metodo": "non trovato", "id": null, "nome": null, "ruolo": "D", "squadra": null,
         "costo": 3, "avviso": "", "alternative": []},
        {"testo": "Zanardelli", "stato": "non_trovato", "metodo": "non trovato", "id": null, "nome": null, "ruolo": "C", "squadra": null,
         "costo": 1, "avviso": "", "alternative": []}
      ]},
      {"nome": "Atletico Divano", "nuova": true, "crediti_residui": 25, "sicuri": 25, "da_controllare": 0, "non_trovati": 0,
       "totale": 25, "attesi": 25, "ruoli": {"P": 3, "D": 8, "C": 8, "A": 6}, "mancano": {}, "in_piu": {}, "senza_ruolo": 0,
       "completa": true, "avvisi": [], "giocatori": [
        \#(sicuro("Falcherini", 301, "Walter Falcherini", "P", "lecce", 9)),
        \#(sicuro("Morlani", 305, "Nelson Morlani", "D", "atalanta", 14)),
        \#(sicuro("de Valk", 313, "Mats de Valk", "C", "atalanta", 21)),
        \#(sicuro("Lumbaku", 327, "Rolando Lumbaku", "A", "napoli", 47))
      ]}
    ],
    "avvisi": ["Dinamo Pizza: 24 giocatori su 25", "Dinamo Pizza: mancano 1 portiere"],
    "mia_squadra": "Schiera FC", "totale_squadre": 8, "sicuri": 70, "da_controllare": 2, "non_trovati": 2,
    "differenze": {"prima_importazione": false, "nessuna_differenza": false, "scambi": [],
      "svincolati_presi": [{"squadra": "Dinamo Pizza", "giocatori": [{"id": 204, "nome": "Nenad Krslić", "ruolo": "A", "squadra": "lecce", "costo": 5}]}],
      "tagliati": [], "crediti": [{"squadra": "Dinamo Pizza", "prima": 12, "dopo": 7}], "testo": "Dinamo Pizza prende Nenad Krslić"},
    "riepilogo": "Dinamo Pizza prende Nenad Krslić"}
    """#

    /// Le squadre della lega con la sola mia rosa (fotografia `scambi-una-rosa`: Scambi spiega che servono le rose degli altri).
    static let unaSquadra = #"[{"nome": "Schiera FC", "mia": true, "giocatori": 25, "crediti_residui": 12}]"#
}
