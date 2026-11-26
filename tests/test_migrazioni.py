"""Le migrazioni del database degli account: mai modificare una già rilasciata (vedi il commento sopra MIGRAZIONI)."""
import contextlib
import sqlite3
from datetime import datetime, timezone

from fanta import account, percorsi
from tests.test_social import PASSWORD, SFIDA, cliente, scena, utente_con_password  # noqa: F401  (scena è una fixture)

COLONNA = ",\n        sessione_hash TEXT"
INDICE_FLUSSI = next(n for n, v in enumerate(account.MIGRAZIONI) if isinstance(v, str) and "CREATE TABLE IF NOT EXISTS flussi_social" in v)
INDICE_RIPARAZIONE = account.MIGRAZIONI.index(account._riparazione_sessione_hash)


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
    for n, voce in enumerate(account.MIGRAZIONI[:INDICE_RIPARAZIONE]):
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


def test_i_token_del_widget_di_prima_restano_senza_legame(tmp_path):
    """#814: un archivio di prima riceve token_widget.sessione_id; il token già emesso resta e vale, senza sessione (fino al rinnovo)."""
    indice = next(n for n, v in enumerate(account.MIGRAZIONI) if isinstance(v, str) and "token_widget ADD COLUMN sessione_id" in v)
    f = tmp_path / "account.sqlite"
    db = sqlite3.connect(f)
    for n, voce in enumerate(account.MIGRAZIONI[:indice]):
        _applica(db, voce, n)
    token = account.PREFISSO_TOKEN_WIDGET + "a" * 43
    db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('vecchio', 'h', 'r', '2026-01-01T00:00:00+00:00')")
    db.execute("INSERT INTO token_widget (utente_id, token_hash, creato, scade, ultimo_uso) VALUES (1, ?, ?, ?, ?)",
               (account._hash_token(token), "2026-11-01T00:00:00+00:00", "2027-01-30T00:00:00+00:00", "2026-11-01T00:00:00+00:00"))
    db.commit()
    db.close()
    with contextlib.closing(account.apri(f)) as db, contextlib.closing(_riferimento(tmp_path / "ref.sqlite")) as ref:
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
        assert _schema(db) == _schema(ref)
        assert tuple(db.execute("SELECT utente_id, sessione_id FROM token_widget").fetchone()) == (1, None)
        assert account.utente_da_token_widget(db, token, datetime(2026, 11, 20, tzinfo=timezone.utc)).nome_utente == "vecchio"
    assert list((tmp_path / "backup").glob("*prima-della-migrazione-*"))


def test_i_token_del_widget_di_prima_restano_e_ora_sono_uno_per_dispositivo(tmp_path):
    """26/11/2026: i token del widget passano da uno per utente a uno per sessione (iPhone e iPad dello stesso account). Un archivio
    di prima tiene i suoi token, con e senza legame, che valgono come prima; dopo, due sessioni dello stesso utente hanno due token
    e l'eliminazione dell'account li toglie ancora tutti."""
    indice = next(n for n, v in enumerate(account.MIGRAZIONI) if isinstance(v, str) and "token_widget_nuova" in v)
    f = tmp_path / "account.sqlite"
    db = sqlite3.connect(f)
    for n, voce in enumerate(account.MIGRAZIONI[:indice]):
        _applica(db, voce, n)
    legato, libero = account.PREFISSO_TOKEN_WIDGET + "a" * 43, account.PREFISSO_TOKEN_WIDGET + "b" * 43
    date = ("2026-11-01T00:00:00+00:00", "2027-01-30T00:00:00+00:00", "2026-11-01T00:00:00+00:00")
    for nome in ("uno", "due"):
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES (?, 'h', 'r', '2026-01-01T00:00:00+00:00')",
                   (nome,))
    db.execute("INSERT INTO sessioni (utente_id, token_hash, creata, scade, ultimo_uso) VALUES (1, 'sessione-finta', ?, ?, ?)", date)
    db.execute("INSERT INTO token_widget (utente_id, token_hash, creato, scade, ultimo_uso, sessione_id) VALUES (1, ?, ?, ?, ?, 1)",
               (account._hash_token(legato), *date))
    db.execute("INSERT INTO token_widget (utente_id, token_hash, creato, scade, ultimo_uso) VALUES (2, ?, ?, ?, ?)",
               (account._hash_token(libero), *date))
    db.commit()
    db.close()
    adesso = datetime(2026, 11, 26, tzinfo=timezone.utc)
    with contextlib.closing(account.apri(f)) as db, contextlib.closing(_riferimento(tmp_path / "ref.sqlite")) as ref:
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
        assert _schema(db) == _schema(ref)
        assert sorted(tuple(r) for r in db.execute("SELECT utente_id, sessione_id FROM token_widget")) == [(1, 1), (2, None)]
        assert account.utente_da_token_widget(db, legato, adesso).nome_utente == "uno"
        assert account.utente_da_token_widget(db, libero, adesso).nome_utente == "due"
        iphone = account._apri_sessione(db, 1, "iphone", adesso)
        ipad = account._apri_sessione(db, 1, "ipad", adesso)
        t1, _ = account.crea_token_widget(db, 1, adesso, sessione=iphone)
        t2, _ = account.crea_token_widget(db, 1, adesso, sessione=ipad)
        for t in (legato, t1, t2):
            assert account.utente_da_token_widget(db, t, adesso).nome_utente == "uno"
        db.execute("DELETE FROM utenti WHERE id = 1")
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM token_widget WHERE utente_id = 1").fetchone()[0] == 0
    assert list((tmp_path / "backup").glob("*prima-della-migrazione-*"))


def test_google_inizia_su_un_database_migrato_passo_per_passo(scena):     # noqa: F811
    _server_prima_del_tampone(percorsi.cartella_account() / "account.sqlite")
    c = cliente()
    r = c.post("/api/account/social/google/inizia", json={"scopo": "accedi", "sfida": SFIDA, "piattaforma": "web"})
    assert r.status_code == 200, r.text
    utente_con_password(c)
    r = c.post("/api/account/social/google/inizia", json={"scopo": "collega", "sfida": SFIDA, "piattaforma": "web", "password": PASSWORD})
    assert r.status_code == 200, r.text
