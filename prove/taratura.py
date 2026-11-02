r"""Taratura dei parametri del modello (errore quadratico medio del fantavoto previsto): si tara sul 2025-26, si controlla sul 2026-27.

Uso: .venv\Scripts\python.exe prove\taratura.py  (qualche minuto). Poi riportare i valori in fanta/modello.py (Parametri)
e confrontare `python -m fanta verifica` prima e dopo.
"""
import sys, time; sys.stdout.reconfigure(encoding="utf-8"); sys.path.insert(0,".")
from dataclasses import replace
import numpy as np
from fanta import archivio, modello
from fanta.punteggio import COLONNA_VOTO, fantavoto
from fanta.regole import carica as carica_regole
from fanta.percorsi import CARTELLA_LEGA
R=carica_regole(CARTELLA_LEGA/"regole.json"); col=COLONNA_VOTO[R.fonte_voto]
d=modello.carica(archivio.apri())
def giornate(st,a,b): return [(st,g) for g in range(a,b+1)]
TARA=giornate("2025-26",5,38)[::2]; CONTROLLO=giornate("2026-27",2,8)
reali={}
for st,g in TARA+CONTROLLO+giornate("2025-26",5,38):
    v=d.voti[(d.voti.stagione==st)&(d.voti.giornata==g)&d.voti[col].notna()]
    reali[(st,g)]={r.calciatore_id: fantavoto(r._asdict(), r.ruolo, R) for r in v.itertuples()}
def errore(par, gg):
    e=[]
    for st,g in gg:
        p=modello.previsioni(d,st,g,R,par)
        fv=reali[(st,g)]
        e += [(m-fv[i])**2 for i,m in zip(p.id,p.mu) if i in fv]
    # errore QUADRATICO: è minimo quando la previsione è il valore MEDIO atteso (quello che serve per scegliere);
    # l'errore assoluto premierebbe il valore tipico e schiaccerebbe i bomber verso la media
    return float(np.sqrt(np.mean(e)))
par=modello.Parametri()
t=time.time(); base=errore(par,TARA); print(f"base {base:.4f} controllo {errore(par,CONTROLLO):.4f} ({time.time()-t:.0f}s)")
griglia={"decadimento":[0.88,0.92,0.94,0.96,0.98],"peso_stagione_prec":[0.3,0.5,0.8],"k_voto":[2,5,10,20,40],
         "k_90":[2,4,8,16,24],"peso_xg":[0.3,0.6,0.8,1.0],"peso_xa":[0.3,0.5,0.8],"beta_voto":[0,0.1,0.2,0.3],
         "k_squadre":[3,6,12]}
for giro in range(2):
    for nome,valori in griglia.items():
        risultati={v: errore(replace(par,**{nome:v}),TARA) for v in valori}
        v=min(risultati,key=risultati.get); par=replace(par,**{nome:v})
        print(f"  {nome}: {v}  ({', '.join(f'{k}={x:.4f}' for k,x in risultati.items())})", flush=True)
print("tarati:",par)
print(f"taratura {errore(par,TARA):.4f} (base {base:.4f}) | controllo 2026-27 {errore(par,CONTROLLO):.4f} (base {errore(modello.Parametri(),CONTROLLO):.4f})")
