r"""Gli indizi che usa Algo (forma, rendimento contro l'avversario, casa/fuori, fortuna) migliorano il nostro fantavoto atteso?

Per ogni giornata passata: previsione del modello (solo dati precedenti) + gli indizi, calcolati anch'essi solo sul passato.
Si stima quanto ogni indizio corregge l'errore del modello sul 2025-26 e si controlla se la correzione aiuta sul 2026-27.
Uso: .venv\Scripts\python.exe prove\prova_spunti.py
"""
import sys; sys.stdout.reconfigure(encoding="utf-8"); sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from fanta import archivio, modello
from fanta.punteggio import COLONNA_VOTO, fantavoto
from fanta.regole import carica as carica_regole
from fanta.percorsi import CARTELLA_LEGA

R = carica_regole(CARTELLA_LEGA / "regole.json"); col = COLONNA_VOTO[R.fonte_voto]
d = modello.carica(archivio.apri())
V = d.voti[d.voti[col].notna() & d.voti["data"].notna()].copy()
V["fv"] = [fantavoto(r._asdict(), r.ruolo, R) for r in V.itertuples()]
# avversario di ogni voto
avv = pd.concat([d.partite[["stagione", "giornata", "casa", "trasferta"]].rename(columns={"casa": "squadra", "trasferta": "avv"}),
                 d.partite[["stagione", "giornata", "trasferta", "casa"]].rename(columns={"trasferta": "squadra", "casa": "avv"})])
V = V.merge(avv.drop_duplicates(["stagione", "giornata", "squadra"]), on=["stagione", "giornata", "squadra"], how="left")
V = V.sort_values("data")
per_g = {k: x for k, x in V.groupby("calciatore_id")}

giornate = [("2025-26", g) for g in range(5, 39)] + [("2026-27", g) for g in range(2, 9)]
righe = []
for st, g in giornate:
    p = modello.previsioni(d, st, g, R)
    data0 = d.inizio(st, g)
    veri = V[(V.stagione == st) & (V.giornata == g)].drop_duplicates("calciatore_id").set_index("calciatore_id")["fv"]
    for x in p.itertuples():
        if x.id not in veri.index:
            continue
        storia = per_g.get(x.id)
        storia = storia[storia["data"] < data0] if storia is not None else None
        n = 0 if storia is None else len(storia)
        ult = storia.tail(4)["fv"] if n else pd.Series(dtype=float)
        st_corr = storia[storia.stagione == st]["fv"] if n else pd.Series(dtype=float)
        vs = storia[storia["avv"] == x.avversario]["fv"] if n else pd.Series(dtype=float)
        media = storia["fv"].mean() if n else np.nan
        righe.append({
            "stagione": st, "giornata": g, "ruolo": x.ruolo, "mu": x.mu, "vero": veri[x.id],
            # forma: ultime 4 rispetto alla previsione (tirata verso 0 se sono poche)
            "forma": (ult.sum() - len(ult) * x.mu) / (len(ult) + 2) if len(ult) else 0.0,
            # fantamedia della stagione rispetto alla previsione
            "fm_stagione": (st_corr.sum() - len(st_corr) * x.mu) / (len(st_corr) + 4) if len(st_corr) else 0.0,
            # contro questo avversario rispetto alla sua media (FMvs di Algo)
            "vs_avversario": (vs.sum() - len(vs) * media) / (len(vs) + 2) if len(vs) and not np.isnan(media) else 0.0,
            "n_vs": len(vs),
            "casa": 1.0 if x.in_casa else -1.0,
        })
    print(st, g, len(righe), flush=True)

df = pd.DataFrame(righe)
df["errore"] = df["vero"] - df["mu"]
tara, ctrl = df[df.stagione == "2025-26"], df[df.stagione == "2026-27"]
rmse = lambda e: float(np.sqrt(np.mean(np.square(e))))  # noqa: E731
print(f"\nrighe: taratura {len(tara)}, controllo {len(ctrl)}")
print(f"modello attuale: taratura {rmse(tara.errore):.4f}  controllo {rmse(ctrl.errore):.4f}")
for indizi in (["forma"], ["fm_stagione"], ["vs_avversario"], ["casa"], ["forma", "fm_stagione", "vs_avversario", "casa"]):
    X = tara[indizi].to_numpy()
    coef, *_ = np.linalg.lstsq(X, tara.errore.to_numpy(), rcond=None)
    e_t = tara.errore - X @ coef
    e_c = ctrl.errore - ctrl[indizi].to_numpy() @ coef
    print(f"{'+'.join(indizi):45s} coeff {np.round(coef, 3)}  taratura {rmse(e_t):.4f}  controllo {rmse(e_c):.4f}"
          f"  (controllo {rmse(ctrl.errore) - rmse(e_c):+.4f})")
# chi ha almeno una partita contro quell'avversario
sub = df[df.n_vs > 0]
print(f"\ncon precedenti contro l'avversario: {len(sub)} righe, correlazione indizio/errore "
      f"{np.corrcoef(sub.vs_avversario, sub.errore)[0, 1]:.3f}")
print("errore medio per casa/fuori:", df.groupby("casa")["errore"].mean().round(3).to_dict())
print("errore medio per ruolo e casa/fuori:", df.groupby(["ruolo", "casa"])["errore"].mean().round(3).to_dict())
