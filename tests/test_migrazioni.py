"""Le migrazioni del database degli account: mai modificare una già rilasciata (vedi il commento sopra MIGRAZIONI)."""
import contextlib
import sqlite3

from fanta import account, percorsi
from tests.test_social import PASSWORD, SFIDA, cliente, scena, utente_con_password  # noqa: F401  (scena è una fixture)

COLONNA = ",\n        sessione_hash TEXT"
INDICE_FLUSSI = next(n for n, v in enumerate(account.MIGRAZIONI) if isinstance(v, str) and "CREATE TABLE IF NOT EXISTS flussi_social" in v)


def _applica(db, voce, numero):
    if callable(voce):
        db.execute("BEGIN IMMEDIATE")
        voce(db)
        db.execute(f"PRAGMA user_version = {numero + 1}")
        db.execute("COMMIT")
    else:
        db.executescript("BEGIN IMMEDIATE;" + voce + f"PRAGMA user_version = {numero + 1}; COMMIT;")


def _schema(db):
    """Per ogni tabella e indice: colonne (nome, tipo, non null, predefinito, chiave) e definizione degli indici."""
    out = {}
    for nome, tipo in db.execute("SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        if tipo == "table":
            out[nome] = sorted(tuple(r[1:]) for r in db.execute(f"PRAGMA table_info({nome})"))
        elif tipo == "index":
            out[nome] = [tuple(r[1:]) for r in db.execute(f"PRAGMA index_xinfo({nome})")]
    return out


def _server_prima_del_tampone(percorso):
    """Come un server già installato: migrazioni fino ai termini già fatte, flussi_social creata SENZA sessione_hash."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(percorso)
    assert COLONNA in account.MIGRAZIONI[INDICE_FLUSSI]
    for n, voce in enumerate(account.MIGRAZIONI[:-1]):
        _applica(db, voce.replace(COLONNA, "") if n == INDICE_FLUSSI else voce, n)
    assert "sessione_hash" not in [r[1] for r in db.execute("PRAGMA table_info(flussi_social)")]
    db.close()


def _riferimento(percorso):
    ref = sqlite3.connect(percorso)
    for n, voce in enumerate(account.MIGRAZIONI):
        _applica(ref, voce, n)
    return ref


def test_incrementale_e_finale_hanno_lo_stesso_schema(tmp_path):
    with contextlib.closing(_riferimento(tmp_path / "inc.sqlite")) as inc, contextlib.closing(account.apri(tmp_path / "fin.sqlite")) as fin:
        assert _schema(inc) == _schema(fin)
        assert fin.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)


def test_un_database_vecchio_senza_la_colonna_la_riceve(tmp_path):
    f = tmp_path / "account.sqlite"
    _server_prima_del_tampone(f)
    with contextlib.closing(account.apri(f)) as db, contextlib.closing(_riferimento(tmp_path / "ref.sqlite")) as ref:
        assert "sessione_hash" in [r[1] for r in db.execute("PRAGMA table_info(flussi_social)")]
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
        assert _schema(db) == _schema(ref)
    assert list((tmp_path / "backup").glob("*prima-della-migrazione-*"))


def test_un_database_gia_sistemato_a_mano_non_si_rompe(tmp_path):
    f = tmp_path / "account.sqlite"
    _server_prima_del_tampone(f)
    db = sqlite3.connect(f)
    db.execute("ALTER TABLE flussi_social ADD COLUMN sessione_hash TEXT")      # il tampone fatto a mano sul server
    db.commit()
    db.close()
    with contextlib.closing(account.apri(f)) as db:
        colonne = [r[1] for r in db.execute("PRAGMA table_info(flussi_social)")]
        assert colonne.count("sessione_hash") == 1
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)


def test_google_inizia_su_un_database_migrato_passo_per_passo(scena):     # noqa: F811
    _server_prima_del_tampone(percorsi.cartella_account() / "account.sqlite")
    c = cliente()
    r = c.post("/api/account/social/google/inizia", json={"scopo": "accedi", "sfida": SFIDA, "piattaforma": "web"})
    assert r.status_code == 200, r.text
    utente_con_password(c)
    r = c.post("/api/account/social/google/inizia", json={"scopo": "collega", "sfida": SFIDA, "piattaforma": "web", "password": PASSWORD})
    assert r.status_code == 200, r.text
