"""Archivio locale (SQLite, un file solo: dati/fanta.sqlite). Si può cancellare: si ricostruisce con `aggiorna`, TRANNE il registro
delle giornate (tabelle `registro_*`, `registro_giornate.py`): i numeri mostrati prima di una giornata non si rifanno dopo.

Ogni giocatore è identificato dal codice di Fantacalcio.it (calciatore_id); le altre fonti vi vengono abbinate.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .percorsi import RADICE

FILE = RADICE / "dati" / "fanta.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS calciatori (
    id INTEGER PRIMARY KEY, nome TEXT, ruolo TEXT, ruolo_mantra TEXT, squadra TEXT, squadra_slug TEXT,
    quotazione INTEGER, quotazione_iniziale INTEGER, fvm INTEGER, aggiornato TEXT
);
-- calendario di Serie A (codici partita di Fantacalcio.it)
CREATE TABLE IF NOT EXISTS partite (
    id INTEGER PRIMARY KEY, stagione TEXT, giornata INTEGER, data TEXT,
    casa TEXT, trasferta TEXT, gol_casa INTEGER, gol_trasferta INTEGER, giocata INTEGER,
    understat_id INTEGER
);
CREATE INDEX IF NOT EXISTS partite_giornata ON partite(stagione, giornata);
-- voti e bonus/malus per giornata (voto NULL = senza voto). ATTENZIONE: "gol" esclude i rigori (sono in rig_segnati)
CREATE TABLE IF NOT EXISTS voti (
    stagione TEXT, giornata INTEGER, calciatore_id INTEGER, nome TEXT, squadra TEXT, ruolo TEXT,
    voto_red REAL, fv_red REAL, voto_stat REAL, fv_stat REAL, voto_ita REAL, fv_ita REAL,
    gol INTEGER, gol_subiti INTEGER, autogol INTEGER, rig_segnati INTEGER, rig_sbagliati INTEGER,
    rig_parati INTEGER, assist INTEGER, mvp INTEGER, ammonizioni INTEGER, espulsioni INTEGER,
    subentrato INTEGER, sostituito INTEGER,
    PRIMARY KEY (stagione, giornata, calciatore_id)
);
-- giocatori di Understat e loro abbinamento al listone
CREATE TABLE IF NOT EXISTS understat_giocatori (
    id INTEGER PRIMARY KEY, nome TEXT, squadre TEXT, posizione TEXT, calciatore_id INTEGER, abbinamento TEXT
);
-- statistiche avanzate partita per partita (Understat)
CREATE TABLE IF NOT EXISTS prestazioni (
    understat_partita INTEGER, understat_giocatore INTEGER, squadra TEXT, posizione TEXT,
    minuti INTEGER, gol INTEGER, autogol INTEGER, tiri INTEGER, xg REAL, xa REAL, assist INTEGER,
    passaggi_chiave INTEGER, xg_chain REAL, xg_buildup REAL, gialli INTEGER, rossi INTEGER,
    rigori_calciati INTEGER, rigori_segnati INTEGER, punizioni INTEGER,
    entrato INTEGER, uscito INTEGER,
    PRIMARY KEY (understat_partita, understat_giocatore)
);
-- totali di stagione Understat (anche delle stagioni passate, per chi ha giocato poco quest'anno)
CREATE TABLE IF NOT EXISTS understat_stagione (
    stagione TEXT, understat_giocatore INTEGER, squadre TEXT, posizione TEXT, partite INTEGER, minuti INTEGER,
    gol INTEGER, npgol INTEGER, xg REAL, npxg REAL, assist INTEGER, xa REAL, tiri INTEGER,
    passaggi_chiave INTEGER, gialli INTEGER, rossi INTEGER, xg_chain REAL, xg_buildup REAL,
    PRIMARY KEY (stagione, understat_giocatore)
);
CREATE TABLE IF NOT EXISTS partite_understat (
    id INTEGER PRIMARY KEY, stagione TEXT, data TEXT, casa TEXT, trasferta TEXT,
    gol_casa INTEGER, gol_trasferta INTEGER, xg_casa REAL, xg_trasferta REAL, giocata INTEGER, scaricata INTEGER
);
-- probabili formazioni e indisponibili (l'ultima rilevazione per fonte e giornata)
CREATE TABLE IF NOT EXISTS probabili (
    stagione TEXT, giornata INTEGER, fonte TEXT, calciatore_id INTEGER, squadra TEXT, partita_id INTEGER,
    stato TEXT,            -- titolare, panchina, infortunato, squalificato, non_convocato
    percentuale REAL,      -- probabilità di giocare titolare (0-100) se la fonte la dà
    in_dubbio INTEGER, diffidato INTEGER, nota TEXT, rilevato TEXT,
    PRIMARY KEY (stagione, giornata, fonte, calciatore_id)
);
-- ogni rilevazione delle probabili, con l'ora (solo si aggiunge, non si cancella): serve a vedere come cambiano
-- le probabili avvicinandosi alla partita e a tarare il modello. Stesse colonne di "probabili".
CREATE TABLE IF NOT EXISTS probabili_storia (
    stagione TEXT, giornata INTEGER, fonte TEXT, calciatore_id INTEGER, squadra TEXT, partita_id INTEGER,
    stato TEXT, percentuale REAL, in_dubbio INTEGER, diffidato INTEGER, nota TEXT, rilevato TEXT,
    PRIMARY KEY (stagione, giornata, fonte, calciatore_id, rilevato)
);
-- colonne in più di football-data.co.uk (xG di squadra, tiri, angoli, falli, cartellini): MODALITÀ OMBRA,
-- il modello non le legge; servono agli esperimenti di `verifica --fonti`
CREATE TABLE IF NOT EXISTS partite_extra (
    stagione TEXT, data TEXT, casa TEXT, trasferta TEXT,
    xg_casa REAL, xg_trasferta REAL, tiri_casa REAL, tiri_trasferta REAL, in_porta_casa REAL, in_porta_trasferta REAL,
    angoli_casa REAL, angoli_trasferta REAL, falli_casa REAL, falli_trasferta REAL,
    gialli_casa REAL, gialli_trasferta REAL, rossi_casa REAL, rossi_trasferta REAL,
    rilevato TEXT,
    PRIMARY KEY (stagione, casa, trasferta)
);
-- seconda fonte di probabili (feed RSS di Sosfanta): MODALITÀ OMBRA, il modello non la legge. Un segnale per giocatore, giornata
-- e articolo; titolare = 1 (titolare), 0 (fuori), NULL (dubbio). Dei testi si conserva solo il link. pubblicato = ora dell'articolo.
CREATE TABLE IF NOT EXISTS probabili_fonte2 (
    stagione TEXT, giornata INTEGER, fonte TEXT, calciatore_id INTEGER, squadra TEXT, titolare INTEGER, percentuale REAL,
    segnale TEXT, link TEXT, pubblicato TEXT, rilevato TEXT,
    PRIMARY KEY (stagione, giornata, fonte, calciatore_id, link)
);
-- quotazioni di Fantacalcio.it per stagione (qi = iniziale, fissata prima del campionato: buona stima di partenza)
CREATE TABLE IF NOT EXISTS quotazioni (
    stagione TEXT, calciatore_id INTEGER, nome TEXT, ruolo TEXT, squadra TEXT, qi INTEGER, qa INTEGER, fvm INTEGER,
    PRIMARY KEY (stagione, calciatore_id)
);
-- esito dei controlli di coerenza (fanta/controlli.py): l'ultimo per stagione e controllo
CREATE TABLE IF NOT EXISTS controlli (
    stagione TEXT, nome TEXT, esito TEXT,   -- ok, avviso, errore
    valore REAL, dettaglio TEXT, controllato TEXT,
    PRIMARY KEY (stagione, nome)
);
CREATE TABLE IF NOT EXISTS aggiornamenti (cosa TEXT PRIMARY KEY, quando TEXT, dettaglio TEXT);
-- registro delle giornate (fanta/registro_giornate.py): i numeri MOSTRATI poco prima della prima partita, per ogni giocatore della
-- Serie A, con le regole classiche. Solo id e numeri, niente dati personali. NON si ricostruisce: una giornata persa è persa.
CREATE TABLE IF NOT EXISTS registro_giocatori (
    stagione TEXT, giornata INTEGER, calciatore_id INTEGER, ruolo TEXT, squadra TEXT, partita_id INTEGER,
    p_voto REAL, mu REAL, mu_voto REAL, e_gol REAL, e_assist REAL, minuti REAL,
    stato TEXT, percentuale REAL, dubbio INTEGER,     -- probabili formazioni mostrate allora (stato NULL = non citato)
    fantamedia REAL,                                  -- con le regole classiche, giornate di prima; NULL = nessun voto
    PRIMARY KEY (stagione, giornata, calciatore_id)
);
-- una riga per giornata: quando è stata salvata e, a giornata finita, i pezzi delle misure I1-I3 (sommati poi sulla finestra)
CREATE TABLE IF NOT EXISTS registro_giornate (
    stagione TEXT, giornata INTEGER, salvato TEXT, giocatori INTEGER, con_probabili INTEGER,
    misurato TEXT, voti INTEGER, sq_modello REAL, sq_fantamedia REAL,   -- I1: chi ha preso voto, somme dei quadrati degli errori
    presenze INTEGER, brier_somma REAL, fasce TEXT,                     -- I2: giocatori delle partite giocate, fasce di 10 punti (JSON)
    fascia_casi INTEGER, fascia_dentro INTEGER,                         -- I3: rose estratte a sorte, punti veri dentro la fascia
    fuori TEXT, da_avvisare TEXT, avvisati TEXT,                        -- indicatori fuori soglia e avvisi al proprietario (JSON)
    persa TEXT,                     -- motivo in breve se la giornata non è stata salvata prima della prima partita (salvato NULL)
    PRIMARY KEY (stagione, giornata)
);
-- numeri «nostri» (solo Fantacalcio.it, fanta/registro_nostri.py) degli stessi giocatori di registro_giocatori, salvati subito dopo i
-- mostrati, con la versione dei nostri (`nostri.VERSIONE`). Tabelle a sé (e non colonne in più nel registro): gli archivi che hanno
-- già il registro le ricevono con CREATE TABLE IF NOT EXISTS, senza toccare le tabelle che ci sono. NON si ricostruiscono.
CREATE TABLE IF NOT EXISTS registro_nostri (
    stagione TEXT, giornata INTEGER, calciatore_id INTEGER, versione TEXT,
    p_voto REAL, mu REAL, mu_voto REAL, e_gol REAL, e_rigori REAL, e_assist REAL, minuti REAL,
    e_rigori_mostrati REAL,                           -- rigori attesi MOSTRATI (registro_giocatori non li ha), per le fasce dei mostrati
    PRIMARY KEY (stagione, giornata, calciatore_id)
);
-- I4 dal vivo, una riga per giornata: nostri contro mostrati sugli stessi giocatori (somme, sommate poi sulla finestra)
CREATE TABLE IF NOT EXISTS registro_i4 (
    stagione TEXT, giornata INTEGER, versione TEXT, misurato TEXT,
    voti INTEGER, sq_nostri REAL, sq_mostrati REAL,                     -- chi ha preso voto: somme dei quadrati degli errori
    rose INTEGER, punti_nostri REAL, punti_mostrati REAL,              -- rose di I3: punti veri della migliore con gli uni e gli altri
    fasce TEXT, fasce_mostrati TEXT,                                    -- gol attesi per fasce: [casi, somma attesi, somma veri] (JSON)
    tentativi INTEGER,              -- misure non riuscite (qui e non in memoria: contano anche dopo un riavvio)
    persa TEXT,                     -- motivo in breve se i nostri non si sono salvati prima della prima partita o non si misurano
    avvisato INTEGER,               -- 1 = avviso partito (giornata persa, o 8 giornate entro soglia per la sua versione)
    PRIMARY KEY (stagione, giornata)
);
"""


def _toglie_tabella_dismessa(db: sqlite3.Connection) -> None:
    """Una tabella dismessa non si raccoglie più: negli archivi vecchi si toglie (una volta sola, senza scrivere se non c'è)."""
    if db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'quote'").fetchone():
        try:
            db.execute("DROP TABLE quote")
            db.execute("DELETE FROM aggiornamenti WHERE cosa LIKE 'quote%'")
            db.commit()
        except sqlite3.OperationalError:     # archivio occupato da un altro processo: si riprova alla prossima apertura
            db.rollback()


def apri(percorso: Path = FILE) -> sqlite3.Connection:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(percorso, timeout=30)   # attende se un altro processo (es. l'aggiornamento automatico) sta scrivendo
    db.execute("PRAGMA busy_timeout = 30000")    # esplicito, oltre a timeout=30 sopra
    db.execute("PRAGMA journal_mode=WAL")        # chi legge non blocca chi scrive
    db.execute("PRAGMA synchronous = NORMAL")    # in WAL è sicuro; l'archivio si ricostruisce comunque, e ogni conferma non aspetta il disco
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    _toglie_tabella_dismessa(db)
    return db


def inserisci(db: sqlite3.Connection, tabella: str, righe: list[dict]) -> int:
    """INSERT OR REPLACE di più righe (dizionari con le stesse chiavi)."""
    if not righe:
        return 0
    colonne = list(righe[0])
    sql = f"INSERT OR REPLACE INTO {tabella} ({', '.join(colonne)}) VALUES ({', '.join('?' * len(colonne))})"
    db.executemany(sql, [tuple(r[c] for c in colonne) for r in righe])
    return len(righe)


def segna(db: sqlite3.Connection, cosa: str, quando: str, dettaglio: str = "") -> None:
    db.execute("INSERT OR REPLACE INTO aggiornamenti VALUES (?, ?, ?)", (cosa, quando, dettaglio))
