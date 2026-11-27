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
        let cala = try rendimento(#"{"sovra_rendimento": -0.5, "tendenza": "cala"}"#)
        #expect(LetturaScheda.tendenza(cala) == .cala)
        let inLinea = try rendimento(#"{"sovra_rendimento": 0.9, "tendenza": "in_linea"}"#)
        #expect(LetturaScheda.tendenza(inLinea) == .inLinea)
    }

    @Test("Un server di prima, senza codice né frase: la soglia 0,3 sul numero e la frase del catalogo")
    func ripiego() throws {
        let cala = try rendimento(#"{"sovra_rendimento": 0.31}"#)
        #expect(LetturaScheda.tendenza(cala) == .cala)
        #expect(LetturaScheda.fraseRendimento(cala) == Catalogo.Mercato.rendCala)
        let sblocca = try rendimento(#"{"sovra_rendimento": -0.31}"#)
        #expect(LetturaScheda.tendenza(sblocca) == .sblocca)
        #expect(LetturaScheda.fraseRendimento(sblocca) == Catalogo.Mercato.rendSblocca)
        let soglia = try rendimento(#"{"sovra_rendimento": 0.3}"#)
        #expect(LetturaScheda.tendenza(soglia) == .inLinea)
        let sogliaSotto = try rendimento(#"{"sovra_rendimento": -0.3}"#)
        #expect(LetturaScheda.fraseRendimento(sogliaSotto) == Catalogo.Mercato.rendLinea)
        let sconosciuto = try rendimento(#"{"sovra_rendimento": 0.5, "tendenza": "boh"}"#)
        #expect(LetturaScheda.tendenza(sconosciuto) == .cala, "un codice che non conosciamo vale come un server di prima")
        let vuoto = try rendimento("{}")
        #expect(LetturaScheda.tendenza(vuoto) == nil, "senza numero né codice niente blocco")
    }

    @Test("I gol con i rigori sono il numero del server; senza il campo, la somma di gol e rigori segnati")
    func gol() throws {
        let nuovo: StagioneGiocatore = try Decodifica.decodifica(Data(#"{"gol": 4, "rig_segnati": 1, "gol_con_rigori": 9}"#.utf8))
        #expect(LetturaScheda.golConRigori(nuovo) == 9)
        let vecchio: StagioneGiocatore = try Decodifica.decodifica(Data(#"{"gol": 4, "rig_segnati": 1}"#.utf8))
        #expect(LetturaScheda.golConRigori(vecchio) == 5)
    }

    @Test("Nella Rosa chi è uscito dal listone lo dice il server (`fuori_listone`), non la quotazione vuota")
    func fuoriListoneDalServer() throws {
        let fuori = try rosa(#"{"id": 7, "nome": "Paolo Esempio", "ruolo": "C", "quotazione": 14, "fuori_listone": true}"#)
        let dentro = try rosa(#"{"id": 8, "nome": "Mauro Retalli", "ruolo": "A", "quotazione": null, "fuori_listone": false}"#)
        let senzaCodice = try rosa(#"{"nome": "Sconosciuto", "ruolo": "A", "fuori_listone": true}"#)
        #expect(RigaRosa.fuoriListone(fuori))
        #expect(RigaRosa.fuoriListone(dentro) == false, "nel listone senza quotazione: la scheda si apre")
        #expect(RigaRosa.fuoriListone(senzaCodice) == false, "senza codice la riga resta spenta")
    }

    @Test("Un server di prima, senza `fuori_listone`: chi non ha la quotazione è uscito dal listone, il tocco dice la frase")
    func fuoriListone() throws {
        let fuori = try rosa(#"{"id": 7, "nome": "Paolo Esempio", "ruolo": "C", "quotazione": null}"#)
        let dentro = try rosa(#"{"id": 8, "nome": "Mauro Retalli", "ruolo": "A", "quotazione": 14}"#)
        let senzaCodice = try rosa(#"{"nome": "Sconosciuto", "ruolo": "A"}"#)
        #expect(RigaRosa.fuoriListone(fuori))
        #expect(RigaRosa.fuoriListone(dentro) == false)
        #expect(RigaRosa.fuoriListone(senzaCodice) == false, "senza codice la riga resta spenta, come prima")
        #expect(Catalogo.Err.fuoriListone == "Questo giocatore non è più nel listone di Serie A.", "la frase del 404 del server")
    }
}
