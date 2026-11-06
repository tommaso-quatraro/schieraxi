import Foundation

// «Chi schierare?» della demo, calcolato come il server (`confronto`, `spiega`, `_frase_perche` e `_in_formazione` di
// fanta/consigli.py) dai numeri della lega inventata (`LegaDemo`): le barre sommano la differenza dei punti attesi, la frase dice
// chi è avanti con quei numeri e il posto nella formazione è quello della Formazione (#246). Le frasi sono quelle del catalogo
// del server (`confronto.*` e `posto.*` di fanta/frasi.py).

extension LegaDemo {
    /// I bonus delle regole della demo che servono a scomporre il fantavoto atteso (gli stessi di `/api/regole`).
    static let bonus = (gol: 3.0, assist: 1.0, rigoreSegnato: 3.0, rigoreSbagliato: -3.0, golSubito: -1.0, imbattuto: 1.0)
    /// Quante sostituzioni ammette la lega della demo (`panchina.max_sostituzioni` delle regole).
    static let maxSostituzioni = 5
    /// Rigori attesi a partita di chi li tira (`rigoristi`) e quanti ne segna (`conversione_rigori` del modello).
    static let rigoriAttesi = 0.15
    static let conversioneRigori = 0.75
    /// Gol subiti attesi e probabilità di porta inviolata dei portieri (`gol_avversario` e `porta_inviolata` delle schede).
    static let golSubitiAttesi = 1.2
    static let portaInviolata = 0.34

    private static let etichetteFattori = ["giocare": "Probabilità di giocare", "voto": "Voto in pagella atteso", "gol": "Gol attesi",
                                           "assist": "Assist attesi", "rigori": "Rigori", "porta": "Porta (gol subiti, imbattibilità)",
                                           "altro": "Cartellini e altro"]
    private static let piuAlto = ["voto": "voto in pagella atteso", "gol": "gol attesi", "assist": "assist attesi", "rigori": "rigori",
                                  "porta": "porta (gol subiti, imbattibilità)", "altro": "cartellini e altro"]

    /// Una causa della differenza: chiave, valori dei due ed effetto in punti attesi (positivo: verso il primo).
    private struct Fattore {
        let chiave: String
        let a: Double
        let b: Double
        let effetto: Double
    }

    /// Chi schierare tra due giocatori, come `da_schierare` di fanta/consigli.py: se la formazione del sistema (`titolari`; nil = non
    /// si sa) ne schiera uno solo è lui, anche con meno punti attesi da solo; altrimenti chi ha più punti attesi. La stessa regola
    /// per «consigliato» del confronto e per il cambio di «Da fare» (#305).
    static func daSchierare(_ a: CalciatoreDemo, _ b: CalciatoreDemo, titolari: [Int]?) -> CalciatoreDemo {
        if let titolari {
            let dentro = [a, b].filter { titolari.contains($0.id) }
            if dentro.count == 1, let solo = dentro.first { return solo }
        }
        return a.puntiAttesi >= b.puntiAttesi ? a : b
    }

    /// Scelta, cause, frase e posto nella formazione del confronto tra `a` e `b` (senza i due giocatori, che aggiunge chi chiama).
    static func confrontoCalcolato(_ a: CalciatoreDemo, _ b: CalciatoreDemo, modulo: String?) -> [String: Any] {
        let fattori = spiega(a, b)
        let differenza = a.puntiAttesi - b.puntiAttesi
        let formazione = inFormazione(a, b, modulo: modulo)
        // come il server: il più atteso, ma se nella formazione del modulo uno solo dei due è titolare si schiera lui
        let titolari: [Int]? = formazione == nil ? nil : (moduli.first(where: { $0.nome == modulo }) ?? moduli[0]).titolari
        let consigliato = daSchierare(a, b, titolari: titolari)
        let arrotonda: (Double) -> Double = { ($0 * 1000).rounded() / 1000 }
        return [
            "consigliato": consigliato.id,
            "margine": (abs(differenza) * 100).rounded() / 100,
            "fattori": fattori.map { f -> [String: Any] in
                ["chiave": f.chiave, "etichetta": etichetteFattori[f.chiave] ?? f.chiave, "a": arrotonda(f.a), "b": arrotonda(f.b),
                 "effetto": arrotonda(f.effetto), "percentuale": f.chiave == "giocare"]
            },
            "perche": frasePerche(a, b, fattori, differenza: differenza),
            "formazione": formazione.map { $0 as Any } ?? NSNull(),
        ]
    }

    /// Da cosa è fatto il fantavoto atteso se gioca (`_componenti`): voto, gol, assist, rigori, porta e il resto (somma = fantavoto).
    private static func componenti(_ p: CalciatoreDemo) -> [String: Double] {
        guard !p.assente else { return ["voto": 0, "gol": 0, "assist": 0, "rigori": 0, "porta": 0, "altro": 0] }
        let rigori = rigoristi.contains(p.id)
            ? rigoriAttesi * (conversioneRigori * bonus.rigoreSegnato + (1 - conversioneRigori) * bonus.rigoreSbagliato) : 0
        let porta = p.ruolo == "P" ? bonus.golSubito * golSubitiAttesi + bonus.imbattuto * portaInviolata : 0
        let voto = p.votoAtteso, gol = bonus.gol * p.golAttesi, assist = bonus.assist * p.assistAttesi
        return ["voto": voto, "gol": gol, "assist": assist, "rigori": rigori, "porta": porta,
                "altro": p.fvAtteso - voto - gol - assist - rigori - porta]
    }

    /// Perché il sistema preferisce uno dei due (`spiega`): la differenza dei punti attesi (gioca × fantavoto) si scompone in
    /// (gioca A − gioca B) × fantavoto medio, più gioca medio × la differenza di ogni parte del fantavoto.
    private static func spiega(_ a: CalciatoreDemo, _ b: CalciatoreDemo) -> [Fattore] {
        let pa = a.assente ? 0 : a.pVoto, pb = b.assente ? 0 : b.pVoto
        let ca = componenti(a), cb = componenti(b)
        let pMedio = (pa + pb) / 2
        var fattori = [Fattore(chiave: "giocare", a: pa, b: pb, effetto: (pa - pb) * (a.fvAtteso + b.fvAtteso) / 2)]
        for k in ["voto", "gol", "assist", "rigori", "porta", "altro"] {
            if k == "porta" && a.ruolo != "P" && b.ruolo != "P" { continue }
            let va = ca[k] ?? 0, vb = cb[k] ?? 0
            fattori.append(Fattore(chiave: k, a: va, b: vb, effetto: pMedio * (va - vb)))
        }
        return fattori
    }

    /// La frase «da soli» (`_frase_perche`): chi è avanti, di quanto e per quali cause, dalle più pesanti.
    private static func frasePerche(_ a: CalciatoreDemo, _ b: CalciatoreDemo, _ fattori: [Fattore], differenza: Double) -> String {
        if abs(differenza) < 0.15 {
            return "\(a.nome) e \(b.nome) sono quasi alla pari: la differenza è sotto 0,2 punti attesi."
        }
        let (primo, secondo) = differenza > 0 ? (a, b) : (b, a)
        let segno: Double = differenza > 0 ? 1 : -1
        let motivi = fattori.filter { $0.effetto * segno > 0.05 }.sorted { $0.effetto * segno > $1.effetto * segno }.prefix(3)
        let punti = Formato.punti(abs(differenza))
        if motivi.isEmpty {
            return "\(primo.nome) è avanti di \(punti) punti attesi, con piccoli vantaggi sparsi."
        }
        let parti = motivi.map { f -> String in
            let peso = Formato.punti(abs(f.effetto))
            if f.chiave == "giocare" {
                let (pp, ps) = segno > 0 ? (f.a, f.b) : (f.b, f.a)
                return "gioca di più (\(percento(pp))% contro \(percento(ps))%: +\(peso))"
            }
            return "\(piuAlto[f.chiave] ?? f.chiave) più alto (+\(peso))"
        }
        return "\(primo.nome) è avanti di \(punti) punti attesi su \(secondo.nome): \(parti.joined(separator: "; "))."
    }

    /// Una probabilità come percentuale intera, arrotondata come `round` di Python.
    private static func percento(_ p: Double) -> Int { Int((p * 100).rounded(.toNearestOrEven)) }

    /// Come stanno i due nella formazione del sistema per quel modulo (`_in_formazione`): titolare, panchina N o fuori, e quanto
    /// cambierebbe invertirli. Nil se uno dei due non è nella mia rosa.
    private static func inFormazione(_ a: CalciatoreDemo, _ b: CalciatoreDemo, modulo: String?) -> [String: Any]? {
        guard miaRosa.contains(where: { $0.id == a.id }), miaRosa.contains(where: { $0.id == b.id }) else { return nil }
        let m = moduli.first { $0.nome == modulo } ?? moduli[0]
        let banco = panchina(per: m.titolari)
        func posto(_ id: Int) -> String {
            if m.titolari.contains(id) { return "titolare" }
            if let i = banco.firstIndex(of: id) { return "panchina \(i + 1)" }
            return "fuori"
        }
        let pa = posto(a.id), pb = posto(b.id)
        var base: [String: Any] = ["modulo": m.nome, "posto_a": pa, "posto_b": pb, "attuale": NSNull(), "invertita": NSNull(),
                                   "differenza": NSNull()]
        if pa == "titolare" && pb == "titolare" {
            base["testo"] = "\(a.nome) e \(b.nome) sono tutti e due titolari nel \(m.nome): giocano insieme, non si tolgono il posto."
            return base
        }
        if pa != "titolare" && pb != "titolare" {
            base["testo"] = pa != "fuori" && pb != "fuori"
                ? "\(a.nome) e \(b.nome) non sono titolari nel \(m.nome) (\(pa) e \(pb)): entra per primo chi sta più in alto in panchina, se il ruolo serve."
                : "\(a.nome) e \(b.nome) non sono titolari nel \(m.nome) (\(pa) e \(pb)): chi è fuori non entra."
            return base
        }
        let (titolare, altro, postoAltro) = pa == "titolare" ? (a, b, pb) : (b, a, pa)
        if titolare.ruolo != altro.ruolo {
            base["testo"] = "\(titolare.nome) è titolare, \(altro.nome) è \(postoAltro), ma sono di ruoli diversi: non si sostituiscono tra loro (a meno di un cambio di modulo durante le sostituzioni)."
            return base
        }
        // Quanto vale la formazione con i due al loro posto (i punti attesi della Formazione) e invertiti. Se il titolare non
        // prende voto entra l'altro dalla panchina: tenere titolare chi vale di più quando gioca rende gioca A × gioca B × (fantavoto
        // A − fantavoto B); se l'altro è fuori, o la lega non ha sostituzioni, conta solo chi gioca.
        let pt = titolare.assente ? 0 : titolare.pVoto, po = altro.assente ? 0 : altro.pVoto
        let conCambio = postoAltro != "fuori" && maxSostituzioni > 0
        let guadagno = conCambio ? pt * po * (titolare.fvAtteso - altro.fvAtteso) : titolare.puntiAttesi - altro.puntiAttesi
        let attuale = punteggio(m.titolari), invertita = attuale - guadagno
        base["attuale"] = (attuale * 100).rounded() / 100
        base["invertita"] = (invertita * 100).rounded() / 100
        base["differenza"] = (guadagno * 100).rounded() / 100
        let entrata: String
        if postoAltro == "fuori" {
            entrata = "\(altro.nome) resta fuori: in panchina ci sono giocatori più utili al punteggio."
        } else if maxSostituzioni <= 0 {
            entrata = "Nella tua lega non sono ammesse sostituzioni: \(altro.nome) (\(postoAltro)) non può entrare al posto di \(titolare.nome)."
        } else {
            entrata = "Se \(titolare.nome) non prende voto (\(percento(1 - pt))% di probabilità), al suo posto può entrare \(altro.nome) (\(postoAltro))."
        }
        let esito: String
        if guadagno > 0.04 {
            esito = "Con \(titolare.nome) titolare la formazione vale \(Formato.punti(attuale)) punti attesi; con i due invertiti \(Formato.punti(invertita)) (\(Formato.punti(-guadagno)))."
        } else if guadagno < -0.04 {
            esito = "Invertendoli la formazione varrebbe \(Formato.punti(invertita)) invece di \(Formato.punti(attuale)) (\(Formato.punti(-guadagno))): con il modulo \(m.nome) (non il migliore) la scelta non è la più conveniente."
        } else {
            esito = "Le due soluzioni valgono praticamente lo stesso (\(Formato.punti(attuale)) contro \(Formato.punti(invertita)))."
        }
        base["testo"] = "Il sistema schiera \(titolare.nome) come titolare. \(entrata) \(esito) Conta quanto vale ciascuno quando gioca (\(titolare.nome) \(Formato.punti(titolare.fvAtteso)) contro \(altro.nome) \(Formato.punti(altro.fvAtteso))), non solo se gioca."
        return base
    }
}
