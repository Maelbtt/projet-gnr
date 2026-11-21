"""Construction du portefeuille : scores -> alphas -> écarts de poids optimisés sous contraintes.

Méthode (Grinold & Kahn) :
  z_i     = score standardisé sur les valeurs notées (moyenne 0, écart type 1)
  alpha_i = IC x vol_residuelle_i x z_i
  max  alpha' wa - lambda x wa' S wa      (wa = poids portefeuille - poids indice)
  lambda est ajusté pour que l'écart de suivi ex ante soit proche de la cible.

Contraintes (note de cadrage) :
  - pas de vente à découvert, somme des poids = 100 %
  - ±3 pts de poids actif par titre, ±10 pts par secteur S&P
  - écarts sectoriels fixés par les avis (cibles_secteur, ±0,5 pt) : les scores choisissent les sociétés dans chaque secteur
  - 30 à 35 lignes
  - 10 % maximum par ligne et règle 5/10/40
  - seules les valeurs notées peuvent être détenues ; les autres sont à 0 %.
    Une valeur qui pèse plus de 3 % de l'indice doit donc être notée.

Usage :
  python scripts/optimiseur.py <indice_secteurs.csv> <cours_quotidiens.csv> <scores.csv> <sortie.csv>
  scores.csv : colonnes RIC;score (score entier de -2 à +2 ; ligne absente ou vide = non détenue)
"""
import json, sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from risque import lire_cours_lseg, rendements, ledoit_wolf, vol_residuelle, risque_ex_ante

PARAM = {
    "ic": 0.05,               # qualité supposée des scores (corrélation scores / surperformance)
    "te_cible": 0.035,        # écart de suivi ex ante visé : 3,5 % (à 5 %, presque pas plus d alpha attendu)
    "ecart_titre": 0.03,      # ±3 pts
    "ecart_secteur": 0.10,    # ±10 pts
    "max_ligne": 0.10,        # UCITS : 10 % maximum par ligne
    "seuil_5_40": (0.05, 0.40),
    "poids_min_detenu": 0.002,
    "nb_titres": (30, 35),  # en dessous de 0,2 %, une ligne est considérée comme non détenue
    # Écarts sectoriels décidés à part (avis sectoriels) : les scores ne choisissent plus que les
    # sociétés à l'intérieur de chaque secteur. None = les secteurs découlent des scores.
    "cibles_secteur": {"Énergie": -0.02, "Métaux et mines": 0.04, "Agriculture": -0.02},
    "bande_secteur": 0.005,   # tolérance autour de chaque cible : ±0,5 pt
    # Une valeur notée -1 ou plus reste en portefeuille (au moins au poids minimal de détention) :
    # -1 = sous-pondérer, -2 = sortir.
    "note_min_detenue": None,
}


def optimiser(w_b, cov, alpha, eligibles, secteurs, lam, plafonds_extra=None, p=PARAM):
    n = len(w_b)
    bas = np.where(eligibles, np.maximum(w_b - p["ecart_titre"], 0.0), 0.0)
    # Valeur > 3 % de l'indice : poids minimal positif, porté au seuil de détention pour ne pas
    # créer une ligne résiduelle qu'on supprimerait ensuite (ce qui dépasserait les -3 pts).
    bas = np.where(bas > 0, np.maximum(bas, p["poids_min_detenu"]), bas)
    haut = np.where(eligibles, np.minimum(w_b + p["ecart_titre"], p["max_ligne"]), 0.0)
    if plafonds_extra is not None:
        haut = np.minimum(haut, plafonds_extra)
    if p.get("plancher") is not None:
        bas = np.where(haut > 0, np.maximum(bas, np.minimum(p["plancher"], haut)), bas)
    s = cov.values
    a = alpha.values

    def f(w):
        wa = w - w_b
        return -(a @ wa) + lam * wa @ s @ wa

    def g(w):
        wa = w - w_b
        return -a + 2 * lam * s @ wa

    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)}]
    for sec in secteurs.unique():
        m = (secteurs.values == sec).astype(float)
        cible = m @ w_b
        cons.append({"type": "ineq", "fun": lambda w, m=m, c=cible: p["ecart_secteur"] - (m @ w - c), "jac": lambda w, m=m: -m})
        cons.append({"type": "ineq", "fun": lambda w, m=m, c=cible: p["ecart_secteur"] + (m @ w - c), "jac": lambda w, m=m: m})
        if p.get("cibles_secteur") and sec in p["cibles_secteur"]:
            c2, b = cible + p["cibles_secteur"][sec], p["bande_secteur"]
            cons.append({"type": "ineq", "fun": lambda w, m=m, c=c2, b=b: b - (m @ w - c), "jac": lambda w, m=m: -m})
            cons.append({"type": "ineq", "fun": lambda w, m=m, c=c2, b=b: b + (m @ w - c), "jac": lambda w, m=m: m})

    x0 = np.clip(w_b, bas, haut)
    x0 = x0 / x0.sum()
    res = minimize(f, x0, jac=g, bounds=list(zip(bas, haut)), constraints=cons, method="SLSQP",
                   options={"maxiter": 500, "ftol": 1e-12})
    if not res.success:
        raise RuntimeError(f"Optimisation impossible : {res.message}")
    return res.x


def respecter_5_10_40(w_b, cov, alpha, eligibles, secteurs, lam, p=PARAM):
    """La règle 5/10/40 n'est pas convexe : on optimise, puis on plafonne à 5 % la ligne > 5 %
    la plus petite tant que le total des lignes > 5 % dépasse 40 %."""
    seuil, total = p["seuil_5_40"]
    plafonds = np.full(len(w_b), 1.0)
    for _ in range(len(w_b)):
        w = optimiser(w_b, cov, alpha, eligibles, secteurs, lam, plafonds, p)
        gros = w > seuil + 1e-9
        if w[gros].sum() <= total + 1e-9:
            return w
        i = np.where(gros)[0][np.argmin(w[gros])]
        plafonds[i] = seuil
    raise RuntimeError("Règle 5/10/40 impossible à respecter")


def standardiser(scores):
    """Moyenne 0 et écart type 1 sur les valeurs notées : des scores qui penchent tous du même côté
    ne doivent pas faire surpondérer tout ce qui est noté. Scores tous identiques : z = 0."""
    s = scores.dropna()
    if s.std(ddof=0) == 0:
        return scores * 0.0
    return (scores - s.mean()) / s.std(ddof=0)


def construire(w_b, cov, scores, secteurs, p=PARAM):
    """Cherche lambda pour viser l'écart de suivi cible. Renvoie (poids, lambda, risque)."""
    eligibles = scores.notna().values
    trop_gros = w_b.index[(~eligibles) & (w_b.values > p["ecart_titre"])].tolist()
    if trop_gros:
        raise ValueError("Ces valeurs pèsent plus de 3 % de l'indice et doivent être notées : " + ", ".join(trop_gros))
    if p.get("note_min_detenue") is not None:
        p = dict(p, plancher=np.where(scores.fillna(-99).values >= p["note_min_detenue"], p["poids_min_detenu"], 0.0))
    sigma_res, _ = vol_residuelle(cov, w_b.values)
    alpha = p["ic"] * sigma_res * standardiser(scores).fillna(0.0)

    te = lambda w: risque_ex_ante(w, w_b.values, cov)["ecart_suivi"]
    opt = lambda lam, el: respecter_5_10_40(w_b.values, cov, alpha, el, secteurs, lam, p)

    # Écart de suivi maximal atteignable sous les contraintes (lambda très faible).
    # Si la cible est hors d'atteinte, on vise 90 % de ce maximum : à lambda quasi nul,
    # l'optimiseur devient indifférent au risque et produit des poids arbitraires.
    if np.allclose(alpha.values, 0):
        # Aucune conviction : on minimise simplement l'écart de suivi avec les valeurs détenues.
        w = opt(1.0, eligibles)
        el2 = eligibles & ((w >= p["poids_min_detenu"]) | (w_b.values > p["ecart_titre"]))
        w = opt(1.0, el2); w[w < 1e-6] = 0.0
        risque = risque_ex_ante(w, w_b.values, cov, secteurs)
        risque.update(alpha_attendu=0.0, ratio_information_ex_ante=0.0, nb_titres=int((w > 0).sum()),
                      **{"lambda": 1.0, "ecart_suivi_max_atteignable": np.nan, "ecart_suivi_vise": np.nan})
        return pd.Series(w, index=w_b.index), alpha, risque
    te_max = te(opt(1e-4, eligibles))
    cible = min(p["te_cible"], 0.9 * te_max)
    lo, hi = 1e-4, 1000.0
    for _ in range(60):       # dichotomie sur une échelle logarithmique
        mid = np.sqrt(lo * hi)
        if te(opt(mid, eligibles)) > cible:
            lo = mid
        else:
            hi = mid
        if hi / lo < 1.01:
            break
    lam = hi
    w = opt(lam, eligibles)
    # Les lignes sous le poids minimal sont retirées puis on réoptimise, plutôt que de
    # redistribuer leur poids à la main (ce qui ferait sortir d'autres lignes des limites).
    el2 = eligibles & ((w >= p["poids_min_detenu"]) | (w_b.values > p["ecart_titre"]))
    if (el2 != eligibles).any():
        w = opt(lam, el2)
    w[w < 1e-6] = 0.0
    risque = risque_ex_ante(w, w_b.values, cov, secteurs)
    risque["alpha_attendu"] = float(alpha.values @ (w - w_b.values))
    risque["ratio_information_ex_ante"] = risque["alpha_attendu"] / risque["ecart_suivi"]
    risque["nb_titres"] = int((w > 0).sum())
    risque["lambda"] = float(lam)
    risque["ecart_suivi_max_atteignable"] = te_max
    risque["ecart_suivi_vise"] = cible
    return pd.Series(w, index=w_b.index), alpha, risque


def controles(w, w_b, secteurs, p=PARAM):
    """Vérifie les règles de gestion sur le portefeuille final. Renvoie la liste des dépassements."""
    pb = []
    wa = w - w_b
    if (wa.abs() > p["ecart_titre"] + 1e-6).any():
        pb.append("écart titre > 3 pts : " + ", ".join(wa.index[wa.abs() > p["ecart_titre"] + 1e-6]))
    ws = wa.groupby(secteurs).sum()
    if (ws.abs() > p["ecart_secteur"] + 1e-6).any():
        pb.append("écart secteur > 10 pts : " + ", ".join(ws.index[ws.abs() > p["ecart_secteur"] + 1e-6]))
    if (w > p["max_ligne"] + 1e-6).any():
        pb.append("ligne > 10 %")
    if w[w > p["seuil_5_40"][0] + 1e-6].sum() > p["seuil_5_40"][1] + 1e-6:
        pb.append("règle 5/10/40")
    if (w < -1e-9).any():
        pb.append("poids négatif")
    n = int((w > 0).sum())
    if not p["nb_titres"][0] <= n <= p["nb_titres"][1]:
        pb.append(f"{n} titres détenus, hors de la fourchette {p['nb_titres'][0]}-{p['nb_titres'][1]} : "
                  "noter plus de valeurs (au moins 0) ou en retirer")
    return pb


if __name__ == "__main__":
    f_indice, f_cours, f_scores, f_sortie = sys.argv[1:5]
    frequence = sys.argv[5] if len(sys.argv) > 5 else "hebdo"      # "hebdo" (défaut) ou "quotidien"
    depuis = sys.argv[6] if len(sys.argv) > 6 else None            # ex. 2025-11-20 pour 1 an
    ind = pd.read_csv(f_indice, sep=";", decimal=",", encoding="utf-8-sig").set_index("RIC")
    ind = ind[ind.poids_3110 > 0]
    cours = lire_cours_lseg(f_cours)
    r, courtes = rendements(cours, min_obs=52 if frequence == "hebdo" else 120, frequence=frequence, depuis=depuis)
    univers = [x for x in ind.index if x in r.columns]
    exclues = [x for x in ind.index if x not in r.columns]
    if exclues:
        print("Historique insuffisant : gardées à leur poids d'indice, hors optimisation :", exclues)
    w_b_tot = ind.poids_3110 / 100
    # Poids de l'indice dérivés du 31/10 jusqu'à la dernière date de l'export, avec les cours :
    # l'optimisation part des poids du jour, pas de ceux d'il y a un mois.
    base = cours.loc[:"2026-10-31"]
    if len(base) and cours.index[-1] > base.index[-1]:
        rel = (cours.iloc[-1] / base.iloc[-1]).reindex(w_b_tot.index).fillna(1.0)
        w_b_tot = w_b_tot * rel / (w_b_tot * rel).sum()
        print(f"Poids de l'indice dérivés du 31/10 au {cours.index[-1].date()} avec les cours.")
    fixe = w_b_tot[exclues].sum()          # valeurs sans historique : gardées à leur poids d'indice
    w_b = w_b_tot[univers] / w_b_tot[univers].sum()
    cov, delta = ledoit_wolf(r[univers], periodes_an=52 if frequence == "hebdo" else 252)
    sc = pd.read_csv(f_scores, sep=";", encoding="utf-8-sig", dtype={"score": str}).set_index("RIC").score
    sc = pd.to_numeric(sc.str.strip().str.replace(",", ".", regex=False), errors="coerce")  # accepte 1,5 comme 1.5
    w, alpha, risque = construire(w_b, cov, sc.reindex(univers), ind.secteur[univers])
    # On revient aux poids de l'indice complet : la partie optimisée est réduite de la part fixe.
    # Les écarts restent dans les limites (ils sont multipliés par 1 - part fixe < 1).
    w_tot = pd.concat([w * (1 - fixe), w_b_tot[exclues]])
    for k in ("ecart_suivi", "alpha_attendu", "active_share"):
        risque[k] *= (1 - fixe)
    risque["contrib_te"] *= (1 - fixe)
    risque["contrib_te_secteur"] *= (1 - fixe)
    risque["nb_titres"] = int((w_tot > 0).sum())
    pb = controles(w_tot, w_b_tot[w_tot.index], ind.secteur[w_tot.index])

    idx = w_tot.index
    out = pd.DataFrame({"nom": ind.Name[idx], "secteur": ind.secteur[idx], "score": sc.reindex(idx),
                        "poids_indice": w_b_tot[idx] * 100, "poids_portefeuille": w_tot * 100,
                        "ecart": (w_tot - w_b_tot[idx]) * 100,
                        "alpha_attendu_pct": alpha.reindex(idx) * 100,
                        "contrib_te_pct": risque["contrib_te"].reindex(idx).fillna(0) * 100})
    out.sort_values("poids_portefeuille", ascending=False).to_csv(
        f_sortie, sep=";", decimal=",", encoding="utf-8-sig", float_format="%.4f")
    resume = {k: v for k, v in risque.items() if not isinstance(v, pd.Series)}
    resume["contrib_te_secteur"] = risque["contrib_te_secteur"].round(5).to_dict()
    resume["retrecissement_ledoit_wolf"] = delta
    resume["depassements"] = pb
    print(json.dumps(resume, ensure_ascii=False, indent=1, default=float))
