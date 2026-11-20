"""Tri chiffré des valeurs de l'indice : un score de -2 à +2 par valeur, au sein de son secteur S&P.

C'est un point de départ pour les scores, pas un score final : à corriger avec l'analyse
(fiches sectorielles), surtout pour les valeurs notées +2 ou -2 et les 6 valeurs obligatoires.

Critères (chacun classé en centile DANS LE SECTEUR, de 0 à 1) :
  valorisation : rendement bénéficiaire (1/PER attendu), rendement EBITDA (1/VE-EBITDA attendu),
                 rendement du dividende -> moyenne des trois
  révisions    : variation de la prévision moyenne de BPA sur 3 mois
  surprise     : écart SmartEstimate / prévision moyenne
  momentum     : performance sur 6 mois, hors dernier mois (convention 6-1 : le dernier mois a tendance à se retourner)
Score composite = moyenne pondérée des critères disponibles, puis découpé en quintiles dans le secteur : -2 .. +2.

Usage :
  python scripts/tri_chiffre.py <valorisation.xlsx|csv> <cours_quotidiens.csv> <indice_secteurs.csv> <sortie.csv> [bpa_3m.xlsx|csv]
  Le BPA à 3 mois peut être dans le même fichier (deuxième formule LSEG, à droite de la première).
"""
import sys
import numpy as np
import pandas as pd
from risque import lire_cours_lseg

POIDS = {"valorisation": 0.35, "revisions": 0.25, "surprise": 0.15, "momentum": 0.25}
# Valeurs dont les prévisions de BPA ne sont pas comparables (scission récente) : la révision sur 3 mois
# et l'écart SmartEstimate / moyenne mesurent le changement de périmètre (analystes plus ou moins à jour),
# pas un vrai changement d'avis. Ces deux critères sont neutralisés.
REVISIONS_NEUTRALISEES = {"CTVA.N": "scission de Vylor", "UPM.HE": "scission de Wisa"}


def lire_brut(chemin):
    if str(chemin).endswith(".xlsx"):
        df = pd.read_excel(chemin, sheet_name=None)
        return next(d for d in df.values() if d.shape[1] >= 2 and len(d) > 5)
    return pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str)


def lire_lseg_tableau(chemin, noms, bloc=0):
    """Export LSEG large (une ligne par instrument). Le RIC est pris dans la colonne « Updated at… »
    remplie par LSEG. bloc = 0 pour la première formule de la feuille, 1 pour la deuxième, etc."""
    df = lire_brut(chemin)
    debuts = [i for i, c in enumerate(df.columns) if str(c).startswith("Updated at")]
    debut = debuts[bloc] if len(debuts) > bloc else 1
    df = df.iloc[:, debut:debut + len(noms)]
    df.columns = noms
    df = df.dropna(subset=["RIC"]).drop_duplicates("RIC").set_index("RIC")
    return df.apply(lambda c: pd.to_numeric(c.astype(str).str.replace(",", "."), errors="coerce"))


def centile_secteur(x, secteur):
    """Rang en centile (0 à 1) au sein du secteur, valeurs manquantes conservées."""
    return x.groupby(secteur).rank(pct=True)


if __name__ == "__main__":
    f_val, f_cours, f_ind, f_sortie = sys.argv[1:5]
    f_bpa3m = sys.argv[5] if len(sys.argv) > 5 else None

    ind = pd.read_csv(f_ind, sep=";", decimal=",", encoding="utf-8-sig").set_index("RIC")
    ind = ind[ind.poids_3110 > 0]
    v = lire_lseg_tableau(f_val, ["RIC", "per", "ve_ebitda", "rdt_div", "bpa_smart", "bpa_moy"]).reindex(ind.index)
    sect = ind.secteur

    # Valorisation : on passe en rendements (inverse des multiples) pour que « plus haut = moins cher ».
    # Multiples négatifs ou aberrants (> 100) : non significatifs.
    rdt_benef = 1 / v.per.where((v.per > 0) & (v.per < 100))
    rdt_ebitda = 1 / v.ve_ebitda.where((v.ve_ebitda > 0) & (v.ve_ebitda < 100))
    val = pd.concat([centile_secteur(rdt_benef, sect), centile_secteur(rdt_ebitda, sect),
                     centile_secteur(v.rdt_div, sect)], axis=1).mean(axis=1)

    # Surprise attendue : seulement si le BPA moyen est positif et pas proche de zéro
    surprise = (v.bpa_smart / v.bpa_moy - 1).where(v.bpa_moy > 0.05)
    surprise[surprise.index.isin(list(REVISIONS_NEUTRALISEES))] = np.nan

    # Révisions sur 3 mois
    # BPA à 3 mois : fichier séparé, ou deuxième formule dans le même fichier
    deux_blocs = sum(str(c).startswith("Updated at") for c in lire_brut(f_val).columns) >= 2
    if f_bpa3m or deux_blocs:
        b3 = lire_lseg_tableau(f_bpa3m or f_val, ["RIC", "bpa_moy_3m"], bloc=0 if f_bpa3m else 1)
        b3 = b3.reindex(ind.index).bpa_moy_3m
        revisions = ((v.bpa_moy - b3) / b3.abs()).where(b3.abs() > 0.05).clip(-1, 1)
        revisions[revisions.index.isin(list(REVISIONS_NEUTRALISEES))] = np.nan
    else:
        revisions = pd.Series(np.nan, index=ind.index)

    # Momentum 6-1 mois sur les cours en USD
    c = lire_cours_lseg(f_cours)
    fin = c.index.max()
    p_1m = c[c.index <= fin - pd.DateOffset(months=1)].ffill().iloc[-1]
    p_7m = c[c.index <= fin - pd.DateOffset(months=7)].ffill().iloc[-1]
    momentum = (p_1m / p_7m - 1).reindex(ind.index)

    crit = pd.DataFrame({
        "valorisation": val,
        "revisions": centile_secteur(revisions, sect),
        "surprise": centile_secteur(surprise, sect),
        "momentum": centile_secteur(momentum, sect),
    })
    poids = pd.Series(POIDS)
    dispo = crit.notna()
    composite = (crit.fillna(0) * poids).sum(axis=1) / (dispo * poids).sum(axis=1)
    composite[dispo.sum(axis=1) < 2] = np.nan          # moins de 2 critères : pas de score
    # Quintiles dans le secteur -> -2 .. +2
    score = composite.groupby(sect).transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=[-2, -1, 0, 1, 2]) if x.notna().sum() >= 5 else np.nan)

    out = pd.DataFrame({
        "nom": ind.Name, "secteur": sect, "sous_secteur": ind.sous_secteur, "poids_indice": ind.poids_3110,
        "score_chiffre": pd.to_numeric(score, errors="coerce"), "composite": composite,
        "per": v.per, "ve_ebitda": v.ve_ebitda, "rdt_div": v.rdt_div,
        "revision_bpa_3m_pct": revisions * 100, "surprise_pct": surprise * 100, "momentum_6_1m_pct": momentum * 100,
        "nb_criteres": dispo.sum(axis=1),
    }).sort_values(["secteur", "composite"], ascending=[True, False])
    out.to_csv(f_sortie, sep=";", decimal=",", encoding="utf-8-sig", float_format="%.3f")
    print(out.groupby(["secteur", "score_chiffre"]).size().unstack(fill_value=0))
    print("Sans score (moins de 2 critères) :", out.index[out.score_chiffre.isna()].tolist())
    print("Révisions neutralisées :", REVISIONS_NEUTRALISEES)
    if not (f_bpa3m or deux_blocs):
        print("Attention : révisions de BPA absentes (fichier BPA à 3 mois non fourni).")
