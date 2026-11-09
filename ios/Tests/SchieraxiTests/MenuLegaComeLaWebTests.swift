import Foundation
import Testing
@testable import Schieraxi

// Issue #304. I menu Squadra e Altro dell'iPhone sono quelli della web: stesse voci, stesso ordine, stessi testi e stesse
// condizioni di `VOCI_LEGA` in `fanta/web/app.js` (nomi e righe sotto dal catalogo comune, #496). La pagina Calendario ha il
// titolo e la spiegazione della web (`tabCalendario`: `mercato.calendario_difficolta`, `mercato.cal_spiega` dal catalogo,
// legenda `diff.1` e `diff.4` da `fanta/web/testi.js`, pallino verde sulle squadre dei tuoi giocatori). I file della web si
// leggono dal repository.

/// Le chiavi che `VOCI_LEGA` usa per nomi e righe sotto, con il loro testo nel catalogo (`ios/testi/lega.txt`). Una voce nuova
/// della web con una chiave che non è qui fa fallire il test: va aggiunta qui e in `ios/testi/lega.txt`.
private let testiDelleVoci: [String: String] = [
    "lega.voce_squadre": Catalogo.Lega.voceSquadre, "lega.voce_squadre_sub": Catalogo.Lega.voceSquadreSub,
    "lega.voce_miasquadra": Catalogo.Lega.voceMiasquadra, "lega.voce_miasquadra_sub": Catalogo.Lega.voceMiasquadraSub,
    "lega.voce_consigli": Catalogo.Lega.voceConsigli, "lega.voce_consigli_sub": Catalogo.Lega.voceConsigliSub,
    "lega.voce_osservati": Catalogo.Lega.voceOsservati, "lega.voce_osservati_sub": Catalogo.Lega.voceOsservatiSub,
    "lega.voce_giocatori": Catalogo.Lega.voceGiocatori, "lega.voce_giocatori_sub": Catalogo.Lega.voceGiocatoriSub,
    "lega.voce_calendario": Catalogo.Lega.voceCalendario, "lega.voce_calendario_sub": Catalogo.Lega.voceCalendarioSub,
    "lega.voce_importa": Catalogo.Lega.voceImporta, "lega.voce_importa_sub": Catalogo.Lega.voceImportaSub,
    "lega.voce_scambi": Catalogo.Lega.voceScambi, "lega.voce_scambi_sub": Catalogo.Lega.voceScambiSub,
    "lega.voce_diario": Catalogo.Lega.voceDiario, "lega.voce_diario_sub": Catalogo.Lega.voceDiarioSub,
    "lega.voce_regole": Catalogo.Lega.voceRegole, "lega.voce_regole_sub": Catalogo.Lega.voceRegoleSub,
    "lega.voce_movimenti": Catalogo.Lega.voceMovimenti, "lega.voce_movimenti_sub": Catalogo.Lega.voceMovimentiSub,
    "lega.voce_crediti": Catalogo.Lega.voceCrediti, "lega.voce_crediti_sub": Catalogo.Lega.voceCreditiSub,
    "lega.voce_stagione": Catalogo.Lega.voceStagione, "lega.voce_stagione_sub": Catalogo.Lega.voceStagioneSub,
    "lega.voce_novita": Catalogo.Lega.voceNovita, "lega.voce_novita_sub": Catalogo.Lega.voceNovitaSub,
]

/// Tutte le funzioni del server accese, o tutte spente, tranne quelle di `eccezioni` (che hanno il valore opposto).
private func funzioni(_ web: VociLegaWeb, accese: Bool, tranne eccezioni: [String] = []) -> StatoFunzioni {
    var scelte = Dictionary(uniqueKeysWithValues: web.funzioniServer.map { ($0, accese) })
    for f in eccezioni { scelte[f] = !accese }
    return StatoFunzioni(scelte: scelte)
}

@Suite("Menu Squadra e Altro come la web (#304)")
struct MenuLegaComeLaWebTests {
    @Test("Stesse voci e stesso ordine di VOCI_LEGA, con tutte le funzioni accese", arguments: [Sezione.squadra, .altro])
    func stesseVociStessoOrdine(scheda: Sezione) throws {
        let web = try VociLegaWeb()
        let ios = VoceMenuLega.voci(scheda, funzioni: funzioni(web, accese: true)).map(\.id)
        #expect(ios == web.voci(scheda.rawValue).map(\.id))
    }

    @Test("Nomi e righe sotto sono quelli delle chiavi di VOCI_LEGA nel catalogo, nello stesso ordine", arguments: [Sezione.squadra, .altro])
    func testiComeLaWeb(scheda: Sezione) throws {
        let web = try VociLegaWeb()
        let attese = try web.voci(scheda.rawValue).map { v in
            [v.id, try #require(testiDelleVoci[v.chiaveNome], "\(v.chiaveNome) manca in testiDelleVoci"),
             try #require(testiDelleVoci[v.chiaveDettaglio], "\(v.chiaveDettaglio) manca in testiDelleVoci")]
        }
        #expect(VoceMenuLega.tutte(scheda).map { [$0.id, $0.nome, $0.dettaglio] } == attese)
    }

    @Test("Ogni voce si vede con la sola sua funzione accesa e sparisce se la sua funzione è spenta, come la web")
    func condizioniComeLaWeb() throws {
        let web = try VociLegaWeb()
        for voce in web.voci {
            let scheda = try #require(Sezione(rawValue: voce.ambito), "scheda sconosciuta: \(voce.ambito)")
            let sola = funzioni(web, accese: false, tranne: voce.funzione.map { [$0] } ?? [])
            let quando = voce.funzione ?? "nessuna funzione"
            #expect(VoceMenuLega.voci(scheda, funzioni: sola).map(\.id).contains(voce.id),
                    "«\(voce.id)» deve vedersi con le funzioni spente tranne «\(quando)»")
            if let f = voce.funzione {
                #expect(!VoceMenuLega.voci(scheda, funzioni: funzioni(web, accese: true, tranne: [f])).map(\.id).contains(voce.id),
                        "«\(voce.id)» non deve vedersi con «\(f)» spenta")
            }
        }
    }

    @Test("Senza «Squadre della lega» la prima voce di Squadra è «La mia squadra e rosa», come la web")
    func laMiaSquadra() throws {
        let web = try VociLegaWeb()
        let nome = Catalogo.Lega.voceMiasquadra
        let sotto = Catalogo.Lega.voceMiasquadraSub
        let prima = try #require(VoceMenuLega.voci(.squadra, funzioni: funzioni(web, accese: true, tranne: [Funzione.squadreAltrui])).first)
        #expect(prima.id == "squadre")
        #expect(prima.nome == nome)
        #expect(prima.dettaglio == sotto)
    }
}

@MainActor
@Suite("Pagina Calendario come la web (#304)")
struct CalendarioComeLaWebTests {
    @Test("Il titolo è quello della web (`mercato.calendario_difficolta`)")
    func titolo() {
        #expect(CalendarioView.titolo == Catalogo.Mercato.calendarioDifficolta)
    }

    @Test("La spiegazione dice quante giornate, con il plurale della web (`mercato.cal_spiega`)", arguments: [1, 2, 5])
    func spiegazione(giornate: Int) {
        #expect(CalendarioView.spiegazione(giornate: giornate) == Catalogo.Mercato.calSpiega(giornate))
        let dove = giornate == 1 ? "nella prossima giornata" : "nelle prossime \(giornate) giornate"
        #expect(CalendarioView.spiegazione(giornate: giornate).contains(dove))
    }

    @Test("La legenda dei colori va da «Facile» a «Dura», come la web (`diff.1` e `diff.4`)")
    func legenda() throws {
        let testi = try TestiWeb()
        let facile = try testi.italiano("diff.1")
        let dura = try testi.italiano("diff.4")
        #expect(CalendarioView.legenda.facile == facile)
        #expect(CalendarioView.legenda.difficile == dura)
    }

    @Test("Il pallino verde va sulle squadre di Serie A dei tuoi giocatori; senza la rosa, su nessuna")
    func squadreMie() throws {
        let rosa: Rosa = try Decodifica.decodifica(Data(#"""
        {"nome": "Squadra Prova", "mia": true, "giocatori": [
          {"id": 1, "nome": "Rossi", "ruolo": "P", "squadra": "LAZ", "squadra_slug": "lazio"},
          {"id": 2, "nome": "Bianchi", "ruolo": "D", "squadra_slug": "lazio"},
          {"id": 3, "nome": "Verdi", "ruolo": "C", "squadra_slug": "como"},
          {"id": 4, "nome": "Neri", "ruolo": "A"}]}
        """#.utf8))
        #expect(CalendarioView.squadreMie(rosa) == ["lazio", "como"])
        #expect(CalendarioView.squadreMie(nil).isEmpty)
    }
}
