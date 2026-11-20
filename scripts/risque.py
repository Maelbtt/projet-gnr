"""Outils de risque : rendements, covariance (Ledoit-Wolf), risque ex ante, indicateurs réalisés.

Dépendances : numpy, pandas.
"""
import numpy as np
import pandas as pd

JOURS_AN = 252
SEMAINES_AN = 52


# ---------- Données ----------

def lire_cours_lseg(chemin):
    """Lit un export long LSEG (une ligne par RIC et par date) et renvoie une table date x RIC.

    Formule attendue dans Excel :
    =RDP.Data(A2:A93;"TR.PriceClose.date;TR.PriceClose";"SDate=... EDate=... Frq=D Curn=USD RH=IN CH=Fd")
    Les colonnes sont repérées par leur nom (RIC/Instrument, Date, Close).
    """
    df = pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str)
    cols = {c.lower(): c for c in df.columns}
    # Avec RH=IN, LSEG écrit l'instrument dans une colonne dont l'en-tête est « Updated at hh:mm:ss »
    # (ou « Instrument »). La colonne « RIC » est la liste collée à la main : elle n'est pas alignée.
    c_ric = next((cols[k] for k in cols if k.startswith("updated at") or k == "instrument"),
                 next(cols[k] for k in cols if k == "ric"))
    c_date = next(cols[k] for k in cols if "date" in k and "updated" not in k)
    c_px = next(cols[k] for k in cols if "close" in k)
    df[c_ric] = df[c_ric].ffill()  # LSEG n'écrit parfois le RIC que sur la première ligne
    df["px"] = pd.to_numeric(df[c_px].str.replace(",", "."), errors="coerce")
    df["date"] = pd.to_datetime(df[c_date], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["px", "date"])
    return df.pivot_table(index="date", columns=c_ric, values="px", aggfunc="last").sort_index()


def rendements(cours, min_obs=120, frequence="quotidien", depuis=None):
    """Rendements simples, quotidiens ou hebdomadaires (cours du vendredi).
    Les valeurs avec trop peu d'historique sont écartées (renvoyées à part)."""
    if depuis is not None:
        cours = cours[cours.index >= pd.Timestamp(depuis)]
    if frequence == "hebdo":
        cours = cours.resample("W-FRI").last()
    r = cours.pct_change(fill_method=None).iloc[1:]
    courtes = r.columns[r.notna().sum() < min_obs].tolist()
    r = r.drop(columns=courtes)
    return r.fillna(0.0), courtes  # jour sans cotation (férié local) = rendement nul


# ---------- Covariance ----------

def ledoit_wolf(r, periodes_an=JOURS_AN):
    """Covariance annualisée, rétrécie vers une cible diagonale de variance moyenne (Ledoit-Wolf 2004).

    Limite les erreurs d'estimation d'une matrice 91 x 91 estimée sur ~250 jours.
    Renvoie (matrice annualisée, intensité de rétrécissement entre 0 et 1).
    """
    x = r.values - r.values.mean(axis=0)
    t, n = x.shape
    s = x.T @ x / t
    mu = np.trace(s) / n
    cible = mu * np.eye(n)
    d2 = np.sum((s - cible) ** 2) / n
    b2 = sum(np.sum((np.outer(xi, xi) - s) ** 2) for xi in x) / n / t ** 2
    b2 = min(b2, d2)
    delta = b2 / d2 if d2 > 0 else 1.0
    cov = delta * cible + (1 - delta) * s
    return pd.DataFrame(cov * periodes_an, index=r.columns, columns=r.columns), delta


def vol_residuelle(cov, w_b):
    """Volatilité propre de chaque titre (hors indice) : variance totale - bêta² x variance de l'indice."""
    s = cov.values
    var_b = w_b @ s @ w_b
    beta = s @ w_b / var_b
    var_res = np.clip(np.diag(s) - beta ** 2 * var_b, 1e-8, None)
    return pd.Series(np.sqrt(var_res), index=cov.index), pd.Series(beta, index=cov.index)


# ---------- Risque ex ante ----------

def risque_ex_ante(w_p, w_b, cov, secteurs=None):
    """Indicateurs ex ante d'un portefeuille par rapport à l'indice (poids en fraction, somme 1)."""
    s = cov.values
    wa = w_p - w_b
    te = float(np.sqrt(wa @ s @ wa))
    contrib = wa * (s @ wa) / te if te > 0 else np.zeros_like(wa)  # somme = TE
    out = {
        "ecart_suivi": te,
        "vol_portefeuille": float(np.sqrt(w_p @ s @ w_p)),
        "vol_indice": float(np.sqrt(w_b @ s @ w_b)),
        "beta": float((w_p @ s @ w_b) / (w_b @ s @ w_b)),
        "active_share": float(0.5 * np.abs(wa).sum()),
        "contrib_te": pd.Series(contrib, index=cov.index),
    }
    if secteurs is not None:
        out["contrib_te_secteur"] = out["contrib_te"].groupby(secteurs.reindex(cov.index)).sum()
    return out


# ---------- Indicateurs réalisés (séries hebdomadaires) ----------

def indicateurs_realises(r_p, r_b, taux_sans_risque=0.0):
    """r_p, r_b : rendements hebdomadaires du portefeuille et de l'indice (pd.Series alignées)."""
    r_p, r_b = r_p.align(r_b, join="inner")
    actif = r_p - r_b
    n = len(r_p)
    ann = lambda r: (1 + r).prod() ** (SEMAINES_AN / n) - 1
    perf_p, perf_b = ann(r_p), ann(r_b)
    te = actif.std(ddof=1) * np.sqrt(SEMAINES_AN)
    vol_p = r_p.std(ddof=1) * np.sqrt(SEMAINES_AN)
    nav = (1 + r_p).cumprod()
    return {
        "nb_semaines": n,
        "perf_annualisee_portefeuille": perf_p,
        "perf_annualisee_indice": perf_b,
        "ecart_suivi_realise": te,
        "ratio_information": (perf_p - perf_b) / te if te > 0 else np.nan,
        "volatilite": vol_p,
        "sharpe": (perf_p - taux_sans_risque) / vol_p if vol_p > 0 else np.nan,
        "beta": float(np.cov(r_p, r_b)[0, 1] / np.var(r_b, ddof=1)),
        "perte_max": float((nav / nav.cummax() - 1).min()),
    }
