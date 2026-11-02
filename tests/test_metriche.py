"""Metriche della squadra (script/ci/metriche.py): solo le parti pure, senza gh né rete."""
import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path

_f = Path(__file__).resolve().parent.parent / "script" / "ci" / "metriche.py"
_spec = importlib.util.spec_from_file_location("metriche", _f)
metriche = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metriche)


def t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_lunedi_della_settimana_in_ora_italiana():
    # domenica 1/11 alle 23:30 italiane = 22:30 UTC: settimana del 26/10
    assert metriche.lunedi(t("2026-11-01T22:30:00Z")) == date(2026, 10, 26)
    # lunedì 2/11 alle 00:30 italiane = domenica 23:30 UTC: settimana del 2/11
    assert metriche.lunedi(t("2026-11-01T23:30:00Z")) == date(2026, 11, 2)


def test_mediana_e_novantesimo():
    assert metriche.mediana([]) is None
    assert metriche.mediana([3.0, 1.0, 2.0]) == 2.0
    assert metriche.mediana([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert metriche.percentile([float(i) for i in range(1, 11)], 90) == 9.0


def test_pr_ios_da_repository_o_file():
    assert metriche.e_ios("tommaso-quatraro/schieraxi-ios", [])
    assert metriche.e_ios("x/schieraxi", ["ios/SchieraXI/Oggi.swift", "docs/API.md"])
    assert not metriche.e_ios("x/schieraxi", ["fanta/server.py"])


def test_riepilogo_di_una_settimana():
    lun = date(2026, 10, 26)
    pr = [
        {"repo": "x/a", "creata": t("2026-10-26T08:00:00Z"), "unita": t("2026-10-26T10:00:00Z"), "etichette": [], "ios": False},
        {"repo": "x/a", "creata": t("2026-10-27T08:00:00Z"), "unita": t("2026-10-27T12:00:00Z"), "etichette": ["fuori-piano"], "ios": True},
        {"repo": "x/a", "creata": t("2026-11-03T08:00:00Z"), "unita": t("2026-11-03T09:00:00Z"), "etichette": [], "ios": False},
    ]
    issue = [
        {"creata": t("2026-10-28T08:00:00Z"), "chiusa": t("2026-10-28T14:00:00Z"), "etichette": ["regressione", "bug"]},
        {"creata": t("2026-10-29T08:00:00Z"), "chiusa": None, "etichette": ["bug", "dall-utente"]},
        {"creata": t("2026-10-30T08:00:00Z"), "chiusa": None, "etichette": ["bug"]},
        {"creata": t("2026-10-30T08:00:00Z"), "chiusa": None, "etichette": ["enhancement"]},
    ]
    versioni = [t("2026-10-26T10:05:00Z"), t("2026-10-27T12:05:00Z"), t("2026-11-03T09:05:00Z")]
    r = metriche.riepilogo(lun, pr, issue, versioni)
    assert r["versioni"] == 2
    assert r["pr_unite"] == 2
    assert r["ore_pr_mediana"] == 3.0                # 2 h e 4 h
    assert r["regressioni"] == 1 and r["guasti_su_unioni"] == 0.5
    assert r["ore_rimedio_mediana"] == 6.0 and r["regressioni_aperte"] == 0
    assert r["difetti"] == 3 and r["dall_utente"] == 1
    assert abs(r["quota_dall_utente"] - 1 / 3) < 1e-9
    assert r["fuori_piano"] == 1
    assert r["pr_ios"] == 1 and r["ore_ios_mediana"] == 4.0
