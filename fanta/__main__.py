"""Comandi da terminale. Uso:  .venv\\Scripts\\python.exe -m fanta <comando>

  listone [--aggiorna]            scarica/mostra il listone dei calciatori
  regole                          mostra le regole della lega
  regole --imposta CHIAVE VALORE  cambia una regola (es. bonus.assist 1.5, bonus.gol.D 4.5)
  importa-rose FILE               importa le rose da Excel/CSV/testo (FILE = "appunti" per il copia-incolla)
  importa-formazioni FILE         importa formazioni schierate e calendario delle giornate passate (file JSON, vedi formazioni_lega.py)
  mia-squadra NOME                indica qual è la tua squadra
  rosa [NOME]                     mostra una rosa (senza nome: la tua)
  squadre                         elenca le squadre della lega
  aggiorna [--storico]            scarica i dati nuovi (voti, probabili, xG...)
  giocatore NOME [--squadra SQ]   scheda di un giocatore
  formazione [--squadra NOME]     formazione consigliata per la prossima giornata
  verifica                        prova il modello sulle giornate già giocate
  oracolo                         guadagno massimo di sapere presenze, gol veri, rigorista (solo misura)
  scambio --con SQ --do X --ricevo Y   analizza uno scambio
  scambi [--con SQ] [--due]       propone scambi vantaggiosi per tutti e due
  server                          avvia l'app (http://127.0.0.1:8000)
  cambi                           avvisa se sono cambiate le probabili dei tuoi giocatori (usato sul server)
  promemoria                      promemoria prima della scadenza della formazione (usato sul server)
  affidabilita [--forza] [--minuti N]   prova il modello sulle ultime giornate e aggiorna il diario (con gli account: di ogni utente, al massimo N minuti, di norma 10)
  affidabilita --pubblico [--file F]   scrive il riassunto anonimo «Quanto ci abbiamo preso» per il sito (non lo pubblica)
  backup [--tieni N]              copia dei dati della lega in dati/backup, ne tiene le ultime N (usato sul server, di sera)
  salute                          controlla che l'app risponda e che i dati siano freschi (usato sul server)
  sentinella [--minuti N] [--senza-invio]   rifà in sola lettura le risposte dell'app per ogni utente e controlla che tornino (usato sul server, ogni ora)
  riepilogo                       riepilogo a giornata finita: punti fatti, attesi e massimo possibile (usato sul server)
  avviso [--prova]                testo dell'avviso "formazione pronta", se è il momento (usato sul server)
  taratura-probabili [--prova]    misura se «gioca N%» con le probabili sbaglia meno ritarato sulle giornate giocate (usato sul server;
                                  --prova stampa i numeri e non scrive niente)
  invito --etichetta NOME [--admin | --usi N]   codice d'invito (7 giorni) per un nuovo account, per N amici (solo con FANTA_MULTIUTENTE=1)
  utente-nome --utente NOME --nome Nome   cambia le maiuscole del nome mostrato di un account
  utente-ruolo --utente NOME --ruolo admin|normale   promuove o declassa un account (non lascia il server senza amministratori)
  importa-per-conto-di --utente NOME FILE     importa le rose di un amico che lo ha chiesto, nel suo archivio (multiutente)
  multiutente-migra --utente NOME [--forza]   COPIA la lega di oggi (lega/ e i file personali di dati/) nella cartella di un account
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import lega, listone, movimenti, nomi, regole, rose
from .percorsi import CARTELLA_LEGA

FILE_REGOLE = CARTELLA_LEGA / "regole.json"
FILE_ROSE = CARTELLA_LEGA / "rose.json"
FILE_MOVIMENTI = CARTELLA_LEGA / "movimenti.json"
NOMI_RUOLO = {"P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"}


def _leggi_appunti() -> str:
    import tkinter
    finestra = tkinter.Tk()
    finestra.withdraw()
    try:
        return finestra.clipboard_get()
    finally:
        finestra.destroy()


def cmd_momento_libero(a) -> None:
    """Per lo script che installa le versioni nuove: esce con 0 se adesso si può riavviare il servizio, 3 se no (vedi libero.py)."""
    from . import libero
    sys.exit(libero.main())


def cmd_listone(a) -> None:
    calciatori, quando = listone.carica(aggiorna=a.aggiorna)
    per_ruolo = {r: sum(c.ruolo == r for c in calciatori) for r in regole.RUOLI}
    print(f"Listone: {len(calciatori)} calciatori (aggiornato {quando}) - {per_ruolo}")


def cmd_regole(a) -> None:
    r = regole.carica(FILE_REGOLE)
    if a.imposta:
        r = regole.imposta(r, a.imposta[0], a.imposta[1])
        regole.salva(r, FILE_REGOLE)
        print(f"Impostato {a.imposta[0]} = {a.imposta[1]}")
    elif not FILE_REGOLE.exists():
        regole.salva(r, FILE_REGOLE)
        print(f"Create le regole predefinite in {FILE_REGOLE}")
    print(json.dumps(asdict(r), ensure_ascii=False, indent=2))


def cmd_importa(a) -> None:
    r = regole.carica(FILE_REGOLE)
    calciatori, quando = listone.carica()
    indice = nomi.Indice(calciatori)
    if a.file.lower() == "appunti":
        griglie = [("testo", rose.griglia_da_testo(_leggi_appunti()))]
    else:
        percorso = Path(a.file)
        if not percorso.exists():
            sys.exit(f"File non trovato: {percorso}")
        griglie = rose.leggi_griglie(percorso)
    avvisi_lettura: list[str] = []
    lette = rose.estrai(griglie, indice, r.rosa, avvisi_lettura)
    if not lette:
        sys.exit(rose.NESSUNA_ROSA)
    precedenti = lega.carica(FILE_ROSE)
    lega.nomi_rinominati(lette, precedenti)
    nuove = lega.da_import(lette, precedenti, sostituisci_tutto=a.sostituisci_tutto)
    lega.salva(nuove, FILE_ROSE, copia_di_riserva=True)
    diff = movimenti.differenze(precedenti, nuove)
    movimenti.registra(FILE_MOVIMENTI, diff)
    print(f"Importate {len(lette)} squadre (listone del {quando}):")
    for letta in lette:
        s = nuove.squadra(letta.nome)
        speso = sum(g.costo or 0 for g in s.giocatori)
        controllo = f" (nel file: {letta.totale_speso})" if letta.totale_speso is not None else ""
        print(f"  {s.nome:<25} {len(s.giocatori):>2} giocatori, spesi {speso}{controllo}")
    print("\nCosa è cambiato:\n" + diff["testo"])
    rimaste = len(nuove.squadre) - len(lette)
    if rimaste > 0:
        print(f"Altre {rimaste} squadre non erano nel file e sono rimaste com'erano "
              "(per toglierle: --sostituisci-tutto).")
    if precedenti:
        print(f"Versione precedente salvata in {FILE_ROSE.name}.bak")
    for x in avvisi_lettura:
        print("  ! ", x)
    _stampa_avvisi(nuove, r)
    if not nuove.mia_squadra:
        print('\nOra indica la tua squadra:  python -m fanta mia-squadra "Nome squadra"')


def _stampa_avvisi(r_ose: lega.Rose, r: regole.Regole) -> None:
    avvisi = lega.controlla(r_ose, r)
    if avvisi:
        print("\nDa controllare:")
        for x in avvisi:
            print("  -", x)
    else:
        print("\nTutto in ordine: rose complete e tutti i giocatori riconosciuti.")


def _rose_o_esci() -> lega.Rose:
    r = lega.carica(FILE_ROSE)
    if not r:
        sys.exit("Nessuna rosa importata. Usa prima:  python -m fanta importa-rose FILE")
    return r


def cmd_importa_formazioni(a) -> None:
    from pathlib import Path
    from . import formazioni_lega
    esito = formazioni_lega.importa_file(Path(a.file), sovrascrivi_scelte=a.sovrascrivi)
    print(f"Tue formazioni salvate: {esito['scelte']}; altre squadre: {esito['altre_squadre']}; partite del calendario: {esito['partite']}")
    if esito["scelte_gia_presenti"]:
        print("Giornate dove avevi già una scelta (lasciata com'era; usa --sovrascrivi per cambiarla):",
              ", ".join(map(str, esito["scelte_gia_presenti"])))


def cmd_mia(a) -> None:
    r = _rose_o_esci()
    s = r.squadra(a.nome)
    if not s:
        sys.exit(f"Squadra non trovata: {a.nome}. Squadre: {', '.join(x.nome for x in r.squadre)}")
    r.mia_squadra = s.nome
    lega.salva(r, FILE_ROSE)
    print(f"La tua squadra è: {s.nome}")


def cmd_squadre(a) -> None:
    r = _rose_o_esci()
    for s in r.squadre:
        segno = "  <- la tua" if s.nome == r.mia_squadra else ""
        print(f"  {s.nome}{segno}")


def cmd_rosa(a) -> None:
    r = _rose_o_esci()
    nome = a.nome or r.mia_squadra
    if not nome:
        sys.exit('Indica una squadra, oppure imposta la tua con:  python -m fanta mia-squadra "Nome"')
    s = r.squadra(nome)
    if not s:
        sys.exit(f"Squadra non trovata: {nome}")
    calciatori = {c.id: c for c in listone.carica()[0]}
    print(f"{s.nome}  (rose aggiornate il {r.aggiornato[:10]})")
    for ruolo in regole.RUOLI:
        gruppo = [g for g in s.giocatori if g.ruolo == ruolo]
        print(f"\n{NOMI_RUOLO[ruolo]} ({len(gruppo)})")
        for g in gruppo:
            c = calciatori.get(g.id)
            quot = f"quot. {c.quotazione:>3}" if c else "non nel listone"
            print(f"  {g.nome:<22} {g.squadra or '':<4} costo {g.costo if g.costo is not None else '-':>3}   {quot}")
    altri = [g for g in s.giocatori if g.ruolo not in regole.RUOLI]
    for g in altri:
        print(f"  ? {g.nome} (ruolo sconosciuto)")


def cmd_aggiorna(a) -> None:
    from . import aggiorna
    errori = aggiorna.esegui(storico=a.storico, stagioni_storiche=a.stagioni)
    if errori:
        sys.exit(1)


def cmd_giocatore(a) -> None:
    from . import archivio, scheda
    from .aggiorna import Stagione
    from datetime import date
    db = archivio.apri()
    calciatori = [listone.Calciatore(**{k: r[k] for k in r.keys() if k != "aggiornato"})
                  for r in db.execute("SELECT * FROM calciatori")]
    if not calciatori:
        sys.exit("Archivio vuoto: lancia prima  python -m fanta aggiorna")
    esito = nomi.Indice(calciatori).cerca(a.nome, a.squadra)
    if not esito.trovato:
        alternative = ", ".join(f"{c.nome} ({c.squadra})" for c in esito.alternative)
        sys.exit(f"Giocatore non trovato: {a.nome}" + (f". Forse: {alternative}" if alternative else ""))
    r = regole.carica(FILE_REGOLE)
    s = scheda.scheda(db, esito.calciatore.id, Stagione.di(date.today()).codice, r.fonte_voto)
    _stampa_scheda(s)


def _stampa_scheda(s: dict) -> None:
    c, st, av = s["calciatore"], s["stagione"], s["avanzate"]
    print(f"{c['nome']}  ({NOMI_RUOLO.get(c['ruolo'], c['ruolo'])}, {c['squadra']})  quotazione {c['quotazione']}")
    print(f"\nStagione: {st['presenze']} presenze su {st['giornate_giocate_serie_a']} giornate "
          f"({st['con_voto']} con voto, {st['titolare']} da titolare)")
    print(f"  media voto {st['media_voto']}   fantamedia {st['fantamedia']}")
    print(f"  gol {st['gol']}  assist {st['assist']}  ammonizioni {st['ammonizioni']}  espulsioni {st['espulsioni']}"
          + (f"  gol subiti {st['gol_subiti']}  rigori parati {st['rig_parati']}" if c["ruolo"] == "P" else "")
          + f"  rigori {st['rig_segnati']} segnati / {st['rig_sbagliati']} sbagliati")
    print("  ultimi fantavoti:", " ".join("sv" if v is None else f"{v:g}" for v in st["ultime_5_fv"]) or "-")
    if av and av.get("minuti"):
        p90 = av.get("per_90", {})
        print(f"\nStatistiche avanzate (Understat, '{av['nome_understat']}'): {av['minuti']} minuti in {av['partite']} partite")
        print(f"  xG {av['xg']}  xA {av['xa']}  tiri {av['tiri']}  passaggi chiave {av['passaggi_chiave']}")
        print(f"  ogni 90 minuti: xG {p90.get('xg')}  xA {p90.get('xa')}  tiri {p90.get('tiri')}")
        print(f"  rigori calciati {av['rigori_calciati']} (segnati {av['rigori_segnati']}), punizioni tirate {av['punizioni']}")
        for prec in av["stagioni_precedenti"]:
            print(f"  stagione {prec['stagione']}: {prec['minuti']} min, {prec['gol']} gol (xG {prec['xg']:.1f}), "
                  f"{prec['assist']} assist (xA {prec['xa']:.1f})")
    elif av is None:
        print("\nStatistiche avanzate: giocatore non abbinato a Understat")
    pp, pr = s["prossima_partita"], s["probabile"]
    if pp:
        dove = "in casa" if pp["casa"] == c["squadra_slug"] else "in trasferta"
        avv = pp["trasferta"] if pp["casa"] == c["squadra_slug"] else pp["casa"]
        print(f"\nProssima: giornata {pp['giornata']}, {pp['data']}, contro {avv} {dove}")
    if pr:
        extra = (" - IN DUBBIO" if pr["in_dubbio"] else "") + (" - diffidato" if pr["diffidato"] else "")
        perc = f" {pr['percentuale']:g}%" if pr["percentuale"] is not None else ""
        print(f"Probabili (giornata {pr['giornata']}): {pr['stato']}{perc}{extra}")
        if pr["nota"]:
            print(f"  {pr['nota']}")
    elif pp:
        print("Probabili: non citato (fuori dai convocati previsti)")


def cmd_formazione(a) -> None:
    from . import archivio, consigli
    r_ose = _rose_o_esci()
    r = regole.carica(FILE_REGOLE)
    f = consigli.formazione(archivio.apri(), r, r_ose, a.squadra, a.giornata, a.simulazioni)
    if not f["con_probabili"]:
        print(f"Attenzione: niente probabili formazioni per la giornata {f['giornata']}: uso le presenze recenti.")
    print(f"{f['squadra']} - giornata {f['giornata']}: modulo {f['modulo']}, punteggio atteso {f['punteggio_atteso']}")
    print("  (altri moduli: " + ", ".join(f"{x['modulo']} {x['punteggio_atteso']}" for x in f["alternative"][:3]) + ")")

    def riga(x, numero):
        dove = "casa" if x["in_casa"] else "fuori"
        return (f"  {numero:>2}. {x['ruolo']} {x['nome']:<20} {x['squadra'][:3].upper()} vs {x['avversario'][:3].upper()}"
                f" ({dove})  gioca {x['p_voto'] * 100:>3.0f}%  fantavoto atteso {x['fv_atteso']:4.1f}"
                + (f"  [{'; '.join(x['motivi'])}]" if x["motivi"] else ""))
    print("\nTitolari")
    for i, x in enumerate(f["titolari"], 1):
        print(riga(x, i))
    print("\nPanchina (in quest'ordine)")
    for i, x in enumerate(f["panchina"], 1):
        print(riga(x, i))
    if f["fuori"] or f["senza_dati"]:
        print("\nFuori: " + ", ".join([f"{x['nome']} ({', '.join(x['motivi'][:1]) or 'poco utile'})" for x in f["fuori"]]
                                     + f["senza_dati"]))


def _trova_in_rosa(s: lega.Squadra, nomi_testo: str) -> list[int]:
    ids = []
    for nome in [x.strip() for x in nomi_testo.split(",") if x.strip()]:
        n = nomi.normalizza(nome)
        trovati = [g for g in s.giocatori if g.id and (nomi.normalizza(g.nome) == n or nomi.normalizza(g.nome).startswith(n))]
        if len(trovati) != 1:
            sys.exit(f"'{nome}' non trovato (o ambiguo) nella rosa di {s.nome}")
        ids.append(trovati[0].id)
    return ids


def _stampa_scambio(d: dict) -> None:
    do = ", ".join(x["nome"] for x in d["do"])
    ricevo = ", ".join(x["nome"] for x in d["ricevo"])
    print(f"  con {d['altra']}: dai {do} (quot. {d['quotazione_do']}) e ricevi {ricevo} (quot. {d['quotazione_ricevo']})")
    print(f"     punti attesi in stagione: tu {d['guadagno_mio']:+.1f}, loro {d['guadagno_loro']:+.1f}"
          f"   (giornate {d['giornate'][0]}-{d['giornate'][-1]}: tu {d['breve_mio']:+.2f}, loro {d['breve_loro']:+.2f})")


def cmd_scambio(a) -> None:
    from . import archivio, consigli, scambi
    r_ose, r = _rose_o_esci(), regole.carica(FILE_REGOLE)
    if not r_ose.mia_squadra:
        sys.exit('Indica prima la tua squadra:  python -m fanta mia-squadra "Nome"')
    altra = r_ose.squadra(a.con)
    if not altra:
        sys.exit(f"Squadra non trovata: {a.con}")
    do = _trova_in_rosa(r_ose.squadra(r_ose.mia_squadra), a.do)
    ricevo = _trova_in_rosa(altra, a.ricevo)
    v = consigli.valori_scambi(archivio.apri(), r)
    d = scambi.analizza(v, r, r_ose, r_ose.mia_squadra, altra.nome, do, ricevo).come_dict(v)
    _stampa_scambio(d)
    print("  per giornata (tu): " + ", ".join(f"g{g} {x:+.2f}" for g, x in zip(d["giornate"], d["per_giornata_mio"])))
    if d["guadagno_mio"] >= scambi.SOGLIA and d["guadagno_loro"] >= scambi.SOGLIA:
        print("  Conviene a tutti e due: proponilo.")
    elif d["guadagno_mio"] >= scambi.SOGLIA:
        print("  Conviene a te ma non a loro: difficile che accettino.")
    else:
        print("  Non ti conviene.")


def cmd_scambi(a) -> None:
    from . import archivio, consigli, scambi
    r_ose, r = _rose_o_esci(), regole.carica(FILE_REGOLE)
    if not r_ose.mia_squadra:
        sys.exit('Indica prima la tua squadra:  python -m fanta mia-squadra "Nome"')
    if a.due and not a.con:
        sys.exit("Con --due indica anche la squadra (--con): la ricerca 2 contro 2 è lunga")
    v = consigli.valori_scambi(archivio.apri(), r)
    proposte = scambi.proponi(v, r, r_ose, r_ose.mia_squadra, a.con, anche_due=a.due)
    if not proposte:
        print("Nessuno scambio vantaggioso per tutti e due trovato.")
    for s in proposte:
        _stampa_scambio(s.come_dict(v))


def cmd_server(a) -> None:
    from . import server
    server.avvia(a.host, a.porta)


def cmd_foto(a) -> None:
    from . import archivio, foto
    db = archivio.apri()
    try:
        r = lega.carica(FILE_ROSE)
        prioritari = [g.id for s in (r.squadre if r else []) for g in s.giocatori if g.id is not None]
        print(foto.scarica_mancanti(db, prioritari, 100000 if a.tutti else a.max,
                                    durata_massima=a.minuti * 60 if a.minuti else None))
    finally:
        db.close()


def _avvisi_per_utente(funzione: str) -> None:
    """Con gli account: gli avvisi di ogni utente attivo, con i suoi file (vedi avvisi_utenti.py). Nel log solo i numeri."""
    from . import archivio, avvisi_utenti
    db = archivio.apri()
    try:
        esiti, errori = avvisi_utenti.esegui(funzione, db)
    finally:
        db.close()
    # «pronta» è il comando di cui lo script del server manda l'uscita su ntfy (il canale del proprietario): qui deve uscire vuota
    uscita = sys.stderr if funzione == "pronta" else sys.stdout
    for nome, righe in esiti.items():
        if righe:
            print(f"{nome}: {len(righe)} avvisi ({funzione})", file=uscita)
    for nome, errore in errori.items():
        print(f"{nome}: errore negli avvisi ({funzione}): {errore}", file=uscita)


def _avvisi_telefono(funzione: str) -> None:
    from . import account
    if account.multiutente():
        return _avvisi_per_utente(funzione)
    from . import archivio, notifiche
    r_ose = lega.carica(FILE_ROSE)
    if not r_ose or not r_ose.mia_squadra:
        sys.exit("Indica prima la tua squadra e importa le rose.")
    db = archivio.apri()
    try:
        reg = regole.carica(FILE_REGOLE)
        righe = []
        if funzione == "promemoria":               # prima l'avviso «cambia la formazione»: se parte, il promemoria non fa il doppione
            try:
                righe = notifiche.avviso_scadenza(db, reg, r_ose)
            except Exception as e:                 # noqa: BLE001  (i promemoria partono comunque)
                print(f"avviso prima della scadenza non controllato: {type(e).__name__}")
        righe += getattr(notifiche, funzione)(db, reg, r_ose)
        if funzione == "cambi":                    # stesso giro dei cambi: reparti della rosa scoperti (una volta sola ciascuno)
            try:
                righe += notifiche.copertura(db, reg, r_ose)
            except Exception as e:                 # noqa: BLE001  (i cambi sono già partiti)
                print(f"copertura non controllata: {type(e).__name__}")
    finally:
        db.close()
    for riga in righe:
        print(riga)


def cmd_cambi(a) -> None:
    _avvisi_telefono("cambi")


def cmd_promemoria(a) -> None:
    _avvisi_telefono("promemoria")


def cmd_riepilogo(a) -> None:
    _avvisi_telefono("riepilogo")


def cmd_affidabilita(a) -> None:
    from . import account, affidabilita, archivio, diario
    if a.pubblico:
        return _affidabilita_pubblica(a.file)
    import time
    scadenza = time.monotonic() + 60 * a.minuti        # il diario di tutti in tempo limitato: il blocco degli aggiornamenti non resta preso a lungo
    db = archivio.apri()
    try:
        regole_, rose_ = regole.carica(FILE_REGOLE), lega.carica(FILE_ROSE)
        fatto = affidabilita.aggiorna_se_serve(db, regole_, rose_, forza=a.forza)
        nuove = diario.aggiorna(db, regole_, rose_, scadenza=scadenza)
        utenti = _diario_per_utente(db, scadenza) if account.multiutente() else None
    finally:
        db.close()
    print("prova del modello rifatta" if fatto else "prova del modello già aggiornata")
    print(f"diario delle giornate: {nuove} nuove voci")
    if utenti is not None:
        voci, fatti, saltati, errori = utenti
        print(f"diario degli utenti: {voci} voci nuove o completate per {fatti} utenti"
              + (f", {saltati} rimandati al prossimo giro (tempo finito)" if saltati else ""))
        for uid, tipo in errori:                # solo il numero dell'utente e il tipo di errore: niente nomi né contenuti
            print(f"diario dell'utente {uid}: errore {tipo}")
    _indicatori_consiglio()


def _indicatori_consiglio() -> None:
    """Dopo il Diario di tutti: i totali degli indicatori del consiglio per «Stato dei dati» e, se una media resta fuori soglia,
    l'avviso al proprietario (`indicatori_consiglio.giro`). Un errore non ferma il comando: nel log solo il tipo."""
    from . import indicatori_consiglio, sentinella
    try:
        esito = indicatori_consiglio.giro(sentinella.manda_ntfy)
    except Exception as e:  # noqa: BLE001 - si rifà al prossimo giro del cron
        print(f"indicatori del consiglio: non aggiornati (errore {type(e).__name__})")
        return
    print(f"indicatori del consiglio: {esito['giornate']} giornate"
          + (f", fuori soglia {', '.join(esito['fuori'])}" if esito["fuori"] else "")
          + (f", avviso mandato ({', '.join(esito['avvisato'])})" if esito["avvisato"] else ""))


def _diario_per_utente(db, scadenza: float | None = None) -> tuple[int, int, int, list[tuple[int, str]]]:
    """Con gli account: il diario di ogni utente nella sua cartella, con le sue regole, la sua rosa e le sue scelte.
    Prima chi ha il diario più vecchio (o non ce l'ha), così con il tempo finito tocca agli altri al giro dopo. Un utente con un
    file rovinato non ferma gli altri. Restituisce (voci scritte, utenti fatti, utenti rimandati, [(id, tipo di errore)])."""
    import contextlib
    import time
    from . import account, diario
    from .contesto import Contesto
    with contextlib.closing(account.apri()) as adb:
        ids = [u["id"] for u in account.elenco(adb)]
    contesti = [c for c in (Contesto.per_utente(i) for i in ids) if c.rose.exists()]
    contesti.sort(key=lambda c: c.diario.stat().st_mtime if c.diario.exists() else 0.0)
    voci = fatti = 0
    errori: list[tuple[int, str]] = []
    for n, ctx in enumerate(contesti):
        if scadenza is not None and time.monotonic() > scadenza:
            return voci, fatti, len(contesti) - n, errori
        try:
            voci += diario.aggiorna(db, regole.carica(ctx.regole), lega.carica(ctx.rose), ctx.diario, file_scelte=ctx.scelte,
                                    scadenza=scadenza)
            fatti += 1
        except Exception as e:              # noqa: BLE001 - un utente non deve fermare gli altri
            errori.append((ctx.utente_id, type(e).__name__))
    return voci, fatti, 0, errori


def _affidabilita_pubblica(file: str | None) -> None:
    """Il riassunto anonimo per il sito, in un file JSON (di norma dati/affidabilita-pubblica.json). Non va online da solo."""
    import contextlib
    from . import account, archivio, diario, percorsi, precisione
    from .contesto import Contesto
    diari = []
    if account.multiutente():
        with contextlib.closing(account.apri()) as adb:
            ids = [u["id"] for u in account.elenco(adb)]
        diari = [list(diario.carica(Contesto.per_utente(i).diario)["giornate"].values()) for i in ids]
    else:
        diari = [list(diario.carica()["giornate"].values())]
    db = archivio.apri()
    try:
        r = precisione.pubblico(db, diari)
    finally:
        db.close()
    dove = Path(file) if file else percorsi.RADICE / "dati" / "affidabilita-pubblica.json"
    percorsi.scrivi_sicuro(dove, json.dumps(r, ensure_ascii=False, indent=1))
    fv = r.get("fantavoto") or {}
    print(f"riassunto pubblico scritto in {dove}: {r['giornate']} giornate, errore medio sul fantavoto "
          f"{fv.get('errore_medio', '–')} su {fv.get('voti', 0)} voti")


def cmd_backup(a) -> None:
    from . import account, backup
    if account.multiutente():
        return _backup_per_utente(a.tieni)
    file = backup.salva_copia(tieni=a.tieni)
    print(f"copia salvata: {file}" if file else "niente da salvare")


def _backup_per_utente(tieni: int) -> None:
    """Con gli account: una copia dei dati di ogni utente nella sua cartella (le ultime 3) e una del database degli account."""
    import contextlib
    from . import account, backup, percorsi
    from .contesto import Contesto
    with contextlib.closing(account.apri()) as db:
        ids = [u["id"] for u in account.elenco(db)]
    fatte = 0
    for i in ids:
        ctx = Contesto.per_utente(i)
        if backup.salva_copia(cartella=ctx.cartella / "backup", tieni=min(tieni, 3), file_utente=ctx.file_backup):
            fatte += 1
    conti = backup.copia_account(percorsi.cartella_account() / "backup", percorsi.cartella_account() / "account.sqlite", tieni)
    print(f"copie salvate: {fatte} utenti su {len(ids)}; database degli account: {'copiato' if conti else 'niente da copiare'}")


def cmd_salute(a) -> None:
    from . import archivio, salute
    db = archivio.apri()
    try:
        for p in salute.controlla(db):
            print(p)
    finally:
        db.close()


def cmd_sentinella(a) -> None:
    from . import sentinella
    esito = sentinella.giro(minuti=a.minuti, manda=None if a.senza_invio else sentinella.manda_ntfy)
    if any(sentinella.INVARIANTI[r.invariante][0] == "errore" for r in esito["rotture"]):
        sys.exit(2)                       # per chi la lancia a mano: qualcosa che l'utente vede sbagliato


def cmd_avviso(a) -> None:
    """Stampa il testo dell'avviso "formazione pronta" se è il momento (e lo segna come mandato), altrimenti niente."""
    from datetime import datetime
    from . import account, archivio, avvisi, consigli, notifiche
    if account.multiutente():              # ogni utente riceve il suo avviso direttamente (il canale ntfy dello script non è degli utenti)
        return _avvisi_per_utente("pronta")
    if not a.prova and notifiche.in_silenzio(datetime.now(), notifiche.impostazioni()):
        return                                     # ore tranquille: non lo segno come mandato, riprova al giro dopo
    db = archivio.apri()
    try:
        st = consigli.stagione_corrente()
        r = regole.carica(FILE_REGOLE)
        avviso = avvisi.da_mandare(db, st, consigli.giornata_da_giocare(db, st, r), datetime.now(), segna=not a.prova, regole=r)
    finally:
        db.close()
    if avviso:
        print(avviso["testo"])


def cmd_taratura_probabili(a) -> None:
    """Un giro della taratura di «gioca N%» con le probabili (una riga per il log di aggiorna.sh), o con --prova i numeri senza
    scrivere niente. Senza --prova un errore dà una riga sola con il tipo d'errore (mai il messaggio, che può contenere dati) e
    l'uscita 1: aggiorna.sh lo scrive nel log e va avanti. Con --prova lo lancia una persona a mano: tutta la traccia e l'uscita 1."""
    import time
    import traceback
    from datetime import datetime
    from . import archivio, taratura_probabili
    inizio = time.monotonic()
    try:
        db = archivio.apri(archivio.FILE)
        try:
            righe = taratura_probabili.rapporto(db) if a.prova else [taratura_probabili.esegui(db, datetime.now())]
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001 - qualunque errore: una riga nel log, mai la traccia con i dati
        if a.prova:
            traceback.print_exc()          # a mano: la traccia intera (anche per ValueError, che `main` ridurrebbe a una riga)
        else:
            print(f"{taratura_probabili.NOME}: non riuscita ({type(e).__name__})", file=sys.stderr)
        sys.exit(1)
    for riga in righe:
        print(riga)
    if a.prova:
        print(f"Secondi: {time.monotonic() - inizio:.1f}")


def cmd_verifica(a) -> None:
    from . import archivio, modello, verifica
    r = regole.carica(FILE_REGOLE)
    db = archivio.apri()
    d = modello.carica(db)
    giornate = []
    for st in d.stagioni:
        giocate = sorted(d.partite.loc[(d.partite["stagione"] == st) & (d.partite["giocata"] == 1), "giornata"].unique())
        inizio = a.dalla if st == d.stagioni[0] else 2
        giornate += [(st, int(g)) for g in giocate if g >= inizio]
    r_ose = lega.carica(FILE_ROSE)
    rose_ids = [[g.id for g in s.giocatori if g.id] for s in r_ose.squadre] if r_ose else None
    print(f"Verifica su {len(giornate)} giornate" + (f" e {len(rose_ids)} rose" if rose_ids else ""))
    t = verifica.verifica(d, r, modello.Parametri(), giornate, rose_ids, a.simulazioni)
    print("\nRiepilogo per stagione (rmse = errore quadratico medio, la misura principale):")
    t["rmse_modello"], t["rmse_fantamedia"] = t["quadratico_modello"], t["quadratico_fantamedia"]
    colonne = [c for c in ("rmse_modello", "rmse_fantamedia", "errore_modello", "errore_fantamedia", "brier",
                           "punti_modello", "punti_fantamedia", "punti_perfetta") if c in t]
    riepilogo = t.groupby("stagione")[colonne].mean()
    for c in ("rmse_modello", "rmse_fantamedia"):
        riepilogo[c] = riepilogo[c] ** 0.5          # radice della media dei quadrati
    print(riepilogo.round(3).to_string())
    if a.incertezza:
        from . import incertezza
        print("\nIncertezza dei punti attesi (fascia 10-90%: dovrebbe contenere circa l'80% dei punti fatti):")
        incertezza.rapporto(incertezza.misura(d, r, modello.Parametri(), giornate, rose_ids, a.simulazioni))
    if a.pacchetti:
        from . import verifica_pacchetti as vp
        scelti = None if a.pacchetti == "tutti" else [x.strip() for x in a.pacchetti.split(",") if x.strip()]
        try:
            rose_prova = vp.rose_sintetiche(d, r, a.rose_sintetiche) if a.rose_sintetiche else rose_ids
            tab, note = vp.confronto(d, r, modello.Parametri(), giornate, rose_prova, a.simulazioni,
                                     vp.SCENARI if scelti is None else scelti)
        except ValueError as e:
            sys.exit(f"Errore: {e}")
        print("\nPacchetti di dati (ablazione; vs_completo = punti a giornata in meno o in più; il modello NON è cambiato):")
        print(tab.round(3).to_string(index=False))
        for nome, n in note.items():
            if n.get("errore_voto_stimato"):
                print(f"  {nome}: errore del voto stimato (radice dell'errore quadratico) "
                      + ", ".join(f"{s} {e:.3f}" for s, e in n["errore_voto_stimato"].items()))
    if a.fonti:
        from . import verifica_fonti
        from . import verifica_probabili_fonte2 as vf2
        richieste = [x.strip() for x in a.fonti.split(",") if x.strip()] if a.fonti != "tutte" else None
        con_fonte2 = richieste is None or vf2.NOME in richieste
        varianti = verifica_fonti.VARIANTI if richieste is None else tuple(x for x in richieste if x != vf2.NOME)
        if varianti:
            try:
                tab = verifica_fonti.confronto(d, r, modello.Parametri(), giornate, rose_ids, a.simulazioni, varianti)
            except ValueError as e:
                sys.exit(f"Errore: {e}")
            print("\nFonti in ombra (variazione negativa = meglio della verifica normale; il modello NON è cambiato):")
            print(tab.round(3).to_string(index=False))
            print()
            for v, testo in verifica_fonti.giudizio(tab).items():
                print(f"  {v}: {testo}")
        if con_fonte2:
            esito = vf2.misura(db)
            print("\nSeconda fonte di probabili (Sosfanta) contro quelle di Fantacalcio.it (variazione negativa = la fonte aiuta; il modello NON è cambiato):")
            if len(esito["tabella"]):
                print(esito["tabella"].round(3).to_string(index=False))
            print(f"  {vf2.NOME}: {esito['verdetto']}")
    if a.consiglio is not None:
        from . import consigli, verifica_consiglio
        print()
        if not r_ose or not r_ose.squadre:
            sys.exit("Errore: per misurare il consiglio servono le rose della lega.")
        verifica_consiglio.rapporto(verifica_consiglio.misura(d, db, r, r_ose, consigli.stagione_corrente(), a.consiglio or None))


def cmd_oracolo(a) -> None:
    """Quanto varrebbe sapere in anticipo chi gioca, i gol veri della squadra, il rigorista vero (solo misura)."""
    from . import archivio, modello, verifica
    r = regole.carica(FILE_REGOLE)
    db = archivio.apri()
    d = modello.carica(db)
    giornate = []
    for st in d.stagioni:
        giocate = sorted(d.partite.loc[(d.partite["stagione"] == st) & (d.partite["giocata"] == 1), "giornata"].unique())
        inizio = a.dalla if st == d.stagioni[0] else 2
        giornate += [(st, int(g)) for g in giocate if g >= inizio]
    r_ose = lega.carica(FILE_ROSE)
    rose_ids = [[g.id for g in s.giocatori if g.id] for s in r_ose.squadre] if r_ose else None
    print(f"Oracolo su {len(giornate)} giornate" + (f" e {len(rose_ids)} rose" if rose_ids else "")
          + " (dati futuri dati di proposito al modello: serve solo a misurare)")
    t = verifica.guadagno_oracoli(d, r, modello.Parametri(), giornate, rose_ids, a.simulazioni)
    print("\nGuadagno rispetto alla verifica normale (punti = per giornata e per rosa; sotto 0,3 la lacuna non vale una fonte):")
    print(t.round(3).to_string(index=False))


def cmd_invito(a) -> None:
    """Crea un codice d'invito per registrare un account. Il primo (--admin) serve a creare l'amministratore."""
    import contextlib
    from . import account
    try:
        with contextlib.closing(account.apri()) as db:
            if a.admin and a.usi != 1:
                sys.exit("Errore: un invito da amministratore si può usare una volta sola (togli --usi o --admin).")
            codice = account.crea_invito(db, a.etichetta, a.admin, usi_max=a.usi)
    except account.ErroreAccount as e:
        sys.exit(f"Errore: {e.messaggio}")
    print(f"Invito per «{a.etichetta}»{' (amministratore)' if a.admin else ''}, valido {account.DURATA_INVITO.days} giorni, {'una sola volta' if a.usi == 1 else f'fino a {a.usi} persone'}:\n\n  {codice}\n")
    print("Si usa dalla pagina di registrazione. Il codice non si può rivedere: se lo perdi, ne crei un altro.")


def cmd_utente_nome(a) -> None:
    """Cambia le maiuscole del nome mostrato di un account (le lettere devono restare le stesse; l'accesso non cambia)."""
    import contextlib
    from . import account
    try:
        with contextlib.closing(account.apri()) as db:
            riga = db.execute("SELECT id FROM utenti WHERE nome_utente = ?", (account.normalizza_nome(a.utente),)).fetchone()
            if riga is None:
                sys.exit(f"Errore: l'account «{a.utente}» non esiste.")
            nuovo = account.cambia_maiuscole(db, riga["id"], a.nome)
    except account.ErroreAccount as e:
        sys.exit(f"Errore: {e.messaggio}")
    print(f"Fatto: l'account «{nuovo.nome_utente}» ora si mostra come «{nuovo.nome_mostrato}». L'accesso funziona come prima.")


def cmd_utente_ruolo(a) -> None:
    """Promuove (admin) o declassa (normale) un account. Non lascia il server senza amministratori. Il ruolo cambia da subito."""
    import contextlib
    from . import account
    if not account.multiutente():
        sys.exit("Gli account non sono attivi: serve FANTA_MULTIUTENTE=1 nell'ambiente del servizio.")
    ruolo = {"admin": "amministratore", "normale": "utente"}[a.ruolo]
    try:
        with contextlib.closing(account.apri()) as db:
            nuovo = account.imposta_ruolo(db, a.utente, ruolo)
    except account.ErroreAccount as e:
        sys.exit(f"Errore: {e.messaggio}")
    print(f"Fatto: l'account «{nuovo.nome_utente}» è ora {'amministratore' if nuovo.amministratore else 'utente normale'}. "
          "I suoi dati non sono cambiati e le sue sessioni restano aperte.")

def cmd_importa_per_conto_di(a) -> None:
    """Importa le rose di un amico che l'ha chiesto, nel SUO archivio (multiutente). Solo da chi ha accesso al server; resta
    una riga nel registro di sicurezza. Excel letto in un processo separato, come per le importazioni dall'app."""
    import contextlib
    from . import account, importa_sicuro, server
    percorso = Path(a.file)
    if not percorso.is_file():
        sys.exit(f"File non trovato: {percorso}")
    try:
        with contextlib.closing(account.apri()) as db:
            riga = db.execute("SELECT id FROM utenti WHERE nome_utente = ?", (account.normalizza_nome(a.utente),)).fetchone()
        if riga is None:
            sys.exit(f"Errore: l'account «{a.utente}» non esiste.")
        if percorso.suffix.lower() in (".xlsx", ".xlsm"):
            griglie = importa_sicuro.leggi_excel(percorso)
        else:
            testo = percorso.read_bytes()[:importa_sicuro.MAX_TESTO * 4].decode("utf-8", "replace")
            importa_sicuro.controlla_testo(testo)
            griglie = [("testo", rose.griglia_da_testo(testo))]
        r = server.importa_per_conto_di(riga["id"], griglie, a.sostituisci_tutto, None)
    except account.ErroreAccount as e:
        sys.exit(f"Errore: {e.messaggio}")
    except (ValueError, server.HTTPException) as e:
        sys.exit(f"Errore: {getattr(e, 'detail', e)}")
    print(f"Importate {len(r['squadre_importate'])} squadre per «{a.utente}»: {', '.join(r['squadre_importate'])}")


def cmd_migra(a) -> None:
    """Copia (non sposta) la lega di oggi nella cartella dell'account indicato: così il primo utente ritrova le sue rose e le sue scelte."""
    import contextlib
    from . import account, contesto
    with contextlib.closing(account.apri()) as db:
        riga = db.execute("SELECT id FROM utenti WHERE nome_utente = ?", (account.normalizza_nome(a.utente),)).fetchone()
    if riga is None:
        sys.exit(f"Errore: l'account «{a.utente}» non esiste. Crealo prima: python -m fanta invito --etichetta ... --admin, poi registrati dall'app.")
    copiati = contesto.migra(riga["id"], forza=a.forza)
    if not copiati:
        sys.exit("Niente da copiare: lega/ e dati/ non hanno i file della lega.")
    print(f"Copiati nella cartella di «{a.utente}» ({contesto.cartella_utente(riga['id'])}): {', '.join(copiati)}")
    print("I file originali sono rimasti dove erano.")


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m fanta", description="SchieraXI: la mia lega")
    sub = p.add_subparsers(dest="comando", required=True)
    x = sub.add_parser("momento-libero", help="0 se si può installare adesso una versione nuova, 3 se no (partite in corso o scadenza vicina)")
    x.set_defaults(f=cmd_momento_libero)
    x = sub.add_parser("listone", help="scarica o mostra il listone")
    x.add_argument("--aggiorna", action="store_true", help="scarica anche se la copia è recente")
    x.set_defaults(f=cmd_listone)
    x = sub.add_parser("regole", help="mostra o cambia le regole")
    x.add_argument("--imposta", nargs=2, metavar=("CHIAVE", "VALORE"))
    x.set_defaults(f=cmd_regole)
    x = sub.add_parser("importa-rose", help="importa le rose della lega")
    x.add_argument("file", help='file Excel/CSV/testo, oppure "appunti"')
    x.add_argument("--sostituisci-tutto", action="store_true",
                   help="toglie anche le squadre che non sono nel file (di norma restano com'erano)")
    x.set_defaults(f=cmd_importa)
    x = sub.add_parser("importa-formazioni", help="importa formazioni e calendario delle giornate passate da un file JSON")
    x.add_argument("file")
    x.add_argument("--sovrascrivi", action="store_true", help="sostituisce anche le tue scelte già salvate")
    x.set_defaults(f=cmd_importa_formazioni)
    x = sub.add_parser("mia-squadra", help="indica la tua squadra")
    x.add_argument("nome")
    x.set_defaults(f=cmd_mia)
    x = sub.add_parser("rosa", help="mostra una rosa")
    x.add_argument("nome", nargs="?")
    x.set_defaults(f=cmd_rosa)
    x = sub.add_parser("squadre", help="elenca le squadre")
    x.set_defaults(f=cmd_squadre)
    x = sub.add_parser("aggiorna", help="scarica i dati nuovi da tutte le fonti")
    x.add_argument("--storico", action="store_true", help="scarica anche la stagione scorsa (la prima volta)")
    x.add_argument("--stagioni", type=int, default=1, metavar="N",
                   help="con --storico: quante stagioni passate (default 1; ogni stagione in più sono circa 420 richieste, "
                        "meglio una volta sola)")
    x.set_defaults(f=cmd_aggiorna)
    x = sub.add_parser("server", help="avvia l'app (http://127.0.0.1:8000)")
    x.add_argument("--host", default="127.0.0.1", help="127.0.0.1 = solo questo PC")
    x.add_argument("--porta", type=int, default=8000)
    x.set_defaults(f=cmd_server)
    if importlib.util.find_spec("fanta.foto") is not None:      # solo nelle copie private: la versione pubblica non ha le foto (docs/AVATAR-DIRITTI.md)
        x = sub.add_parser("foto", help="scarica le foto dei calciatori (poche alla volta)")
        x.add_argument("--max", type=int, default=30, help="quante foto cercare in questo giro")
        x.add_argument("--minuti", type=float, default=None, help="fermati dopo questi minuti (il resto al giro dopo)")
        x.add_argument("--tutti", action="store_true", help="una tantum: cerca tutti i calciatori che non hanno ancora il ritaglio")
        x.set_defaults(f=cmd_foto)
    x = sub.add_parser("cambi", help="avvisa se sono cambiate le probabili dei tuoi giocatori")
    x.set_defaults(f=cmd_cambi)
    x = sub.add_parser("promemoria", help="promemoria prima della scadenza della formazione")
    x.set_defaults(f=cmd_promemoria)
    x = sub.add_parser("affidabilita", help="prova il modello sulle ultime giornate giocate")
    x.add_argument("--forza", action="store_true")
    x.add_argument("--pubblico", action="store_true", help="scrive solo il riassunto anonimo per il sito (non lo pubblica)")
    x.add_argument("--minuti", type=float, default=10, help="tempo massimo per i diari (di norma 10): il resto al giro dopo")
    x.add_argument("--file", default=None, help="con --pubblico: dove scriverlo (di norma dati/affidabilita-pubblica.json)")
    x.set_defaults(f=cmd_affidabilita)
    x = sub.add_parser("backup", help="salva una copia dei dati della lega in dati/backup (tiene le ultime N)")
    x.add_argument("--tieni", type=int, default=7)
    x.set_defaults(f=cmd_backup)
    x = sub.add_parser("salute", help="controlla che l'app risponda e che i dati siano freschi")
    x.set_defaults(f=cmd_salute)
    x = sub.add_parser("sentinella", help="controlla in sola lettura che le risposte dell'app tornino, per ogni utente")
    x.add_argument("--minuti", type=float, default=15, help="tempo massimo (di norma 15): gli utenti rimasti al giro dopo")
    x.add_argument("--senza-invio", action="store_true", help="stampa l'avviso invece di mandarlo e non segna niente")
    x.set_defaults(f=cmd_sentinella)
    x = sub.add_parser("riepilogo", help="riepilogo a giornata finita")
    x.set_defaults(f=cmd_riepilogo)
    x = sub.add_parser("avviso", help="stampa l'avviso 'formazione pronta' se è il momento (per le notifiche)")
    x.add_argument("--prova", action="store_true", help="non segnare l'avviso come mandato")
    x.set_defaults(f=cmd_avviso)
    x = sub.add_parser("taratura-probabili", help="misura se «gioca N%%» con le probabili sbaglia meno ritarato sulle giornate giocate")
    x.add_argument("--prova", action="store_true", help="stampa giornate, numeri e verdetto senza scrivere niente")
    x.set_defaults(f=cmd_taratura_probabili)
    x = sub.add_parser("invito", help="crea un codice d'invito per un nuovo account, monouso o per più amici con --usi (multiutente)")
    x.add_argument("--etichetta", required=True, help="per chi è (per ricordarlo)")
    x.add_argument("--admin", action="store_true", help="l'account creato con questo invito sarà amministratore")
    x.add_argument("--usi", type=int, default=1, help="quante persone possono entrare con lo stesso codice (1-30, predefinito 1; non con --admin)")
    x.set_defaults(f=cmd_invito)
    x = sub.add_parser("utente-nome", help="cambia le maiuscole del nome mostrato di un account (multiutente)")
    x.add_argument("--utente", required=True, help="nome utente dell'account (anche tutto minuscolo)")
    x.add_argument("--nome", required=True, help="lo stesso nome con le maiuscole volute, per esempio MarioRossi")
    x.set_defaults(f=cmd_utente_nome)
    x = sub.add_parser("utente-ruolo", help="promuove o declassa un account (multiutente, non lascia il server senza amministratori)")
    x.add_argument("--utente", required=True, help="nome utente dell'account")
    x.add_argument("--ruolo", required=True, choices=("admin", "normale"), help="admin = amministratore, normale = utente")
    x.set_defaults(f=cmd_utente_ruolo)
    x = sub.add_parser("importa-per-conto-di", help="importa le rose di un amico che lo ha chiesto, nel suo archivio (multiutente)")
    x.add_argument("--utente", required=True, help="nome utente dell'amico")
    x.add_argument("file", help="file Excel, CSV o di testo con le rose")
    x.add_argument("--sostituisci-tutto", action="store_true", help="toglie anche le sue squadre che non sono nel file")
    x.set_defaults(f=cmd_importa_per_conto_di)
    x = sub.add_parser("multiutente-migra", help="copia la lega di oggi nella cartella di un account (multiutente)")
    x.add_argument("--utente", required=True, help="nome utente dell'account (già registrato)")
    x.add_argument("--forza", action="store_true", help="sovrascrive i dati già presenti nella cartella dell'account")
    x.set_defaults(f=cmd_migra)
    x = sub.add_parser("formazione", help="formazione consigliata per la prossima giornata")
    x.add_argument("--squadra", help="un'altra squadra della lega (di norma la tua)")
    x.add_argument("--giornata", type=int)
    x.add_argument("--simulazioni", type=int, default=600)
    x.set_defaults(f=cmd_formazione)
    x = sub.add_parser("scambio", help="analizza uno scambio con un'altra squadra")
    x.add_argument("--con", required=True, help="squadra con cui scambiare")
    x.add_argument("--do", required=True, help='giocatori che dai, separati da virgola (es. "Bonny")')
    x.add_argument("--ricevo", required=True, help="giocatori che ricevi, separati da virgola")
    x.set_defaults(f=cmd_scambio)
    x = sub.add_parser("scambi", help="propone scambi vantaggiosi per tutti e due")
    x.add_argument("--con", help="solo con questa squadra")
    x.add_argument("--due", action="store_true", help="anche 2 contro 2 (serve --con)")
    x.set_defaults(f=cmd_scambi)
    x = sub.add_parser("verifica", help="verifica il modello sulle giornate già giocate")
    x.add_argument("--dalla", type=int, default=5, help="prima giornata della stagione più vecchia")
    x.add_argument("--simulazioni", type=int, default=300)
    x.add_argument("--fonti", nargs="?", const="tutte", default=None,
                   help="in più, prova le fonti in ombra (xg_fd, probabili_fonte2; senza valore tutte): lento, spento di default")
    x.add_argument("--pacchetti", nargs="?", const="tutti", default=None,
                   help="in più, misura quanto si perde con i dati di un solo fornitore (scenari separati da virgola; "
                        "senza valore tutti): lento, spento di default")
    x.add_argument("--rose-sintetiche", type=int, default=0,
                   help="con --pacchetti: invece delle rose della lega, tante rose estratte a sorte per stagione")
    x.add_argument("--incertezza", action="store_true",
                   help="in più, misura lo scarto vero tra punti attesi e fatti e la copertura della fascia mostrata (circa 2 minuti)")
    x.add_argument("--consiglio", nargs="?", type=int, const=0, default=None, metavar="GIORNATA",
                   help="in più, misura il consiglio di formazione in laboratorio (C1-C4: confronto con una scelta semplice, "
                        "titolari che non giocano, scelte storte, perché, stabilità; 600 simulazioni come l'app, semi fissi, "
                        "circa mezzo minuto). Con un numero, la giornata con le probabili da usare (senza: l'ultima che le ha)")
    x.set_defaults(f=cmd_verifica)
    x = sub.add_parser("oracolo", help="misura il guadagno massimo di sapere in anticipo presenze, gol, rigorista")
    x.add_argument("--dalla", type=int, default=5, help="prima giornata della stagione più vecchia")
    x.add_argument("--simulazioni", type=int, default=300)
    x.set_defaults(f=cmd_oracolo)
    x = sub.add_parser("giocatore", help="scheda di un giocatore")
    x.add_argument("nome")
    x.add_argument("--squadra", help="per distinguere gli omonimi")
    x.set_defaults(f=cmd_giocatore)
    a = p.parse_args(argv)
    try:
        a.f(a)
    except (ValueError, TypeError) as e:
        sys.exit(f"Errore: {e}")


if __name__ == "__main__":
    main()
