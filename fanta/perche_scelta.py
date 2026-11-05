"""Il perché della scelta in una riga (#356, lavoro L3 di #166).

A volte la consigliata sembra storta: un titolare ha meno punti attesi di un escluso dello stesso ruolo (in panchina o fuori). Per
quei titolari, e per i titolari incerti con una riserva sicura (`consigli.incerti`, che avevano già la loro nota), il server scrive il
motivo vero della scelta in una riga, come `Frase`. Gli altri titolari non hanno riga: il loro perché sta al tocco sul giocatore.

Il conto è quello del Confronto (`consigli._in_formazione`): la formazione com'è contro la stessa con i due scambiati di posto e la
panchina rifatta dal sistema, sulle stesse simulazioni, e la riga non dice mai il contrario del Confronto. I motivi, in quest'ordine:
1. l'altro quasi certamente non gioca e il titolare sì (la regola dei titolari che giocano, #329 e #341);
se scambiarli varrebbe di più (il Confronto dice «invertendoli varrebbe di più»): solo con la consigliata già mostrata e tenuta
(#335) una riga, perché il cambio vale meno della soglia; altrimenti nessuna riga (meglio niente che una scusa: succede con gli
stili prudenti o rischiosi e con un modulo diverso da quello proposto, che costano punti apposta);
2. titolare anche se incerto: se non gioca entra la riserva, e insieme valgono di più;
3. con lui la formazione fa più punti attesi;
se le due formazioni valgono lo stesso (come per il Confronto, o con lo stesso numero a schermo):
4. gioca più sicuro dell'altro;
5. ha il fantavoto atteso (quello «se gioca») più alto;
6. il primo motivo proprio a favore del suo «perché questo numero»;
7. con l'uno o con l'altro la formazione vale quasi lo stesso.

Campo `perche_scelta` di ogni modulo della risposta di `GET /api/formazione`: [{titolare, altro, testo, frase}] (contratto in
docs/API.md). Non cambia nessun numero né nessuna scelta.
"""
from __future__ import annotations

from . import formazione as fz
from .frasi import F, Frase, da_json
from .notifiche import SOGLIA_AVVISO_PUNTI

PARI = 0.04          # come il Confronto (`consigli._in_formazione`): sotto questa differenza le due formazioni valgono lo stesso
SOGLIA_TENUTA = SOGLIA_AVVISO_PUNTI    # = `consigli.SOGLIA_CAMBIO_PUNTI`: sotto, la consigliata già mostrata non cambia (il testo dice «1 punto»)
NON_PROPRI = ("gioca", "partita", "altro", "rinvio")     # motivi del «perché questo numero» che non parlano del giocatore


def _uno(x: float) -> float:
    """Il numero come si legge a schermo, con un decimale."""
    return float(f"{x:.1f}")


def _motivo_proprio(perche_numero) -> str | None:
    """Il primo motivo del «perché questo numero» che parla del giocatore e va a suo favore (testo o `Frase`), se c'è."""
    for m in perche_numero or []:
        if not isinstance(m, dict) or m.get("chiave") in NON_PROPRI or not isinstance(m.get("effetto"), (int, float)):
            continue
        if m["effetto"] > 0 and m.get("testo"):
            return da_json(m.get("frase")) or str(m["testo"])
    return None


def motivo(t: fz.Giocatore, altro: fz.Giocatore, attuale: float, invertita: float, riserva: fz.Giocatore | None = None,
           perche_numero=(), tenuta: bool = False) -> Frase | None:
    """Perché `t` è titolare e `altro` (stesso ruolo) no. `attuale` e `invertita` = punti attesi della formazione com'è e con i due
    scambiati (`conto`); `riserva` = la riserva sicura se `t` è un titolare incerto; `perche_numero` = il «perché questo numero» di
    `t`; `tenuta` = è la consigliata già mostrata, tenuta perché la migliore non valeva abbastanza di più (#335). None = nessun
    motivo da dire."""
    diff = attuale - invertita
    if diff < -PARI:              # scambiarli varrebbe di più: il Confronto dice «esito_peggio» (o «titolare_che_gioca»)
        if t.p >= fz.COMPAGNO_ALMENO and altro.p < fz.IMPROBABILE_SOTTO:
            return F("scelta.titolare_che_gioca", altro=altro.nome, p=round(altro.p * 100))
        if tenuta and invertita - attuale < SOGLIA_TENUTA:
            return F("scelta.stabile", altro=altro.nome, attuale=attuale, invertita=invertita)
        return None               # un altro motivo contraddirebbe il Confronto (stile o modulo che costano punti)
    if riserva is not None:
        return F("scelta.incerto", p=round(t.p * 100), riserva=riserva.nome)
    if diff > PARI and _uno(attuale) > _uno(invertita):
        return F("scelta.piu_punti", altro=altro.nome, attuale=attuale, invertita=invertita)
    proprio = _motivo_proprio(perche_numero)
    if round(t.p * 100) > round(altro.p * 100):
        return F("scelta.piu_sicuro", altro=altro.nome, pt=round(t.p * 100), pa=round(altro.p * 100))
    if _uno(t.mu) > _uno(altro.mu):
        return F("scelta.fantavoto_piu_alto", altro=altro.nome, mu_t=t.mu, mu_a=altro.mu)
    if proprio:
        return F("scelta.motivo", altro=altro.nome, motivo=proprio)
    return F("scelta.pari", altro=altro.nome, attuale=attuale, invertita=invertita)


def conto(val: fz.Valutatore, rosa: list[fz.Giocatore], titolari: list[fz.Giocatore], panchina: list[fz.Giocatore],
          titolare: fz.Giocatore, altro: fz.Giocatore, regole) -> tuple[float, float]:
    """(punti attesi della formazione com'è, punti attesi con `altro` al posto di `titolare` e la panchina rifatta dal sistema):
    lo stesso conto del Confronto (`consigli._in_formazione`), sulle simulazioni di `val`."""
    attuale = val.atteso(titolari, panchina)
    scambiati = [altro if g.id == titolare.id else g for g in titolari]
    return attuale, val.atteso(scambiati, fz._panchina(rosa, scambiati, regole))


def del_modulo(m: dict, schede: dict, rosa: list[fz.Giocatore], regole, val: fz.Valutatore, tenuta: bool = False) -> list[dict]:
    """Le righe di un modulo (`titolari`, `panchina`, `incerti` come in `consigli._moduli`), nell'ordine dei titolari.
    Scelta storta = un escluso dello stesso ruolo ha più punti attesi (`punti_attesi` delle schede, il numero che vede l'utente;
    senza, «gioca» per fantavoto atteso): l'altro è quello che ne ha di più. Per un titolare incerto l'altro è la sua riserva, quella
    che la riga nomina: il conto (e il Confronto) è sempre sulla coppia della riga."""
    per_id = {g.id: g for g in rosa}
    ids = [int(i) for i in m.get("titolari") or []]
    panchina_ids = [int(i) for i in m.get("panchina") or []]
    if not all(i in per_id for i in ids + panchina_ids):
        return []
    titolari, panchina = [per_id[i] for i in ids], [per_id[i] for i in panchina_ids]
    scelti = set(ids) | set(panchina_ids)
    # gli esclusi: prima la panchina nel suo ordine, poi gli altri della rosa (a pari punti vince il primo)
    esclusi = panchina_ids + [g.id for g in rosa if g.id not in scelti]
    riserve = {int(x["titolare"]): int(x["riserva"]) for x in m.get("incerti") or []}

    def punti(i: int) -> float:
        v = (schede.get(str(i)) or {}).get("punti_attesi")
        return float(v) if isinstance(v, (int, float)) else round(per_id[i].valore, 2)
    righe = []
    for t in titolari:
        rivali = [i for i in esclusi if per_id[i].ruolo == t.ruolo and punti(i) > punti(t.id)]
        riserva = per_id.get(riserve.get(t.id))
        if not rivali and riserva is None:
            continue
        altro = riserva if riserva is not None else per_id[max(rivali, key=punti)]
        attuale, invertita = conto(val, rosa, titolari, panchina, t, altro, regole)
        frase = motivo(t, altro, attuale, invertita, riserva, (schede.get(str(t.id)) or {}).get("perche_numero"), tenuta)
        if frase is not None:
            righe.append({"titolare": t.id, "altro": altro.id, "testo": frase, "frase": frase.json()})
    return righe


def aggiungi(f: dict, rosa: list[fz.Giocatore], regole, val: fz.Valutatore, tenuta: bool = False) -> dict:
    """Mette `perche_scelta` in ogni modulo della risposta di `consigli._calcola_formazione` (in cima e in ogni stile) che non l'ha
    ancora; le stesse formazioni si contano una volta sola. `tenuta`: la risposta è la consigliata già mostrata e tenuta
    (`consigli.stabile`). Restituisce `f`."""
    fatti: dict = {}
    moduli = list(f.get("moduli") or []) + [m for liv in f.get("livelli") or [] for m in liv.get("moduli") or []]
    for m in moduli:
        if "perche_scelta" in m:
            continue
        chiave = (tuple(m.get("titolari") or []), tuple(m.get("panchina") or []))
        if chiave not in fatti:
            fatti[chiave] = del_modulo(m, f.get("schede") or {}, rosa, regole, val, tenuta)
        m["perche_scelta"] = fatti[chiave]
    return f
