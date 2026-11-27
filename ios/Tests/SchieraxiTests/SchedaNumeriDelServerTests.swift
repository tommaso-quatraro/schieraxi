import Foundation
import Testing
@testable import Schieraxi

/// La scheda del giocatore e la Rosa con quello che decide il server (27/11/2026), come la web (`riempiScheda` e `vistaRosa` di
/// app.js): tendenza e frase di «Gol e assist rispetto alle occasioni», gol con i rigori, riga della Rosa di chi è uscito dal
/// listone. Con un server di prima, senza i campi nuovi, il ripiego di prima. Dati inventati.
@Suite("Scheda e Rosa con i numeri del server")
struct SchedaNumeriDelServerTests {
    private func rendimento(_ json: String) throws -> Rendimento {
        try Decodifica.decodifica(Data(json.utf8))
    }

    private func rosa(_ json: String) throws -> GiocatoreRosa {
        try Decodifica.decodifica(Data(json.utf8))
    }

    @Test("Tendenza e frase sono quelle del server, anche se il numero direbbe altro")
    func tendenzaDelServer() throws {
        let r = try rendimento(#"{"sovra_rendimento": 0.5, "gol_meno_xg": 1.2, "assist_meno_xa": 0.1, "tendenza": "sblocca", "testo": "Crea più di quanto segna: è probabile che si sblocchi."}"#)
        #expect(LetturaScheda.tendenza(r) == .sblocca)
        #expect(LetturaScheda.fraseRendimento(r) == "Crea più di quanto segna: è probabile che si sblocchi.")
        #expect(LetturaScheda.tendenza(try rendimento(#"{"sovra_rendimento": -0.5, "tendenza": "cala"}"#)) == .cala)
        #expect(LetturaScheda.tendenza(try rendimento(#"{"sovra_rendimento": 0.9, "tendenza": "in_linea"}"#)) == .inLinea)
    }

    @Test("Un server di prima, senza codice né frase: la soglia 0,3 sul numero e la frase del catalogo")
    func ripiego() throws {
        let cala = try rendimento(#"{"sovra_rendimento": 0.31}"#)
        #expect(LetturaScheda.tendenza(cala) == .cala)
        #expect(LetturaScheda.fraseRendimento(cala) == Catalogo.Mercato.rendCala)
        let sblocca = try rendimento(#"{"sovra_rendimento": -0.31}"#)
        #expect(LetturaScheda.tendenza(sblocca) == .sblocca)
        #expect(LetturaScheda.fraseRendimento(sblocca) == Catalogo.Mercato.rendSblocca)
        #expect(LetturaScheda.tendenza(try rendimento(#"{"sovra_rendimento": 0.3}"#)) == .inLinea)
        #expect(LetturaScheda.fraseRendimento(try rendimento(#"{"sovra_rendimento": -0.3}"#)) == Catalogo.Mercato.rendLinea)
        #expect(LetturaScheda.tendenza(try rendimento(#"{"sovra_rendimento": 0.5, "tendenza": "boh"}"#)) == .cala,
                "un codice che non conosciamo vale come un server di prima")
        #expect(LetturaScheda.tendenza(try rendimento("{}")) == nil, "senza numero né codice niente blocco")
    }

    @Test("I gol con i rigori sono il numero del server; senza il campo, la somma di gol e rigori segnati")
    func gol() throws {
        let nuovo: StagioneGiocatore = try Decodifica.decodifica(Data(#"{"gol": 4, "rig_segnati": 1, "gol_con_rigori": 9}"#.utf8))
        #expect(LetturaScheda.golConRigori(nuovo) == 9)
        let vecchio: StagioneGiocatore = try Decodifica.decodifica(Data(#"{"gol": 4, "rig_segnati": 1}"#.utf8))
        #expect(LetturaScheda.golConRigori(vecchio) == 5)
    }

    @Test("Nella Rosa chi non ha la quotazione è uscito dal listone: il tocco dice la frase del catalogo, non apre la scheda")
    func fuoriListone() throws {
        #expect(RigaRosa.fuoriListone(try rosa(#"{"id": 7, "nome": "Paolo Esempio", "ruolo": "C", "quotazione": null}"#)))
        #expect(!RigaRosa.fuoriListone(try rosa(#"{"id": 8, "nome": "Mauro Retalli", "ruolo": "A", "quotazione": 14}"#)))
        #expect(!RigaRosa.fuoriListone(try rosa(#"{"nome": "Sconosciuto", "ruolo": "A"}"#)), "senza codice la riga resta spenta, come prima")
        #expect(Catalogo.Err.fuoriListone == "Questo giocatore non è più nel listone di Serie A.", "la frase del 404 del server")
    }
}
