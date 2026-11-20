"""Écrit les JSON publiés par le site (docs/data/) et l'index des contenus (docs/contenu/).

Usage : python scripts/build_site_data.py data_brute/indice_secteurs_20261031.csv 2026-10-31

Ne publie que des résultats du projet (poids de l'indice reconstitués, par valeur et agrégés).
Aucun cours, nombre d'actions ou série brute LSEG n'est écrit dans docs/.
"""
import json, sys
from pathlib import Path
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
DOCS = RACINE / "docs"
ORDRE_SECTEURS = ["Énergie", "Agriculture", "Métaux et mines"]
# Noms d'affichage (le fichier SSGA est en majuscules). Les autres valeurs : mise en forme automatique.
NOMS = {"SHELL PLC": "Shell", "EXXONMOBIL HOLDINGS CORP": "ExxonMobil", "NUTRIEN LTD": "Nutrien",
        "BHP GROUP LTD DI": "BHP", "TOTALENERGIES SE": "TotalEnergies", "CHEVRON CORP": "Chevron",
        "UPM KYMMENE OYJ": "UPM-Kymmene", "NEWMONT CORP": "Newmont", "BP PLC": "BP", "VYLOR INC": "Vylor",
        "AGNICO EAGLE MINES LTD": "Agnico Eagle", "CANADIAN NATURAL RESOURCES": "Canadian Natural Resources",
        "FREEPORT MCMORAN INC": "Freeport-McMoRan", "ARCHER DANIELS MIDLAND CO": "Archer-Daniels-Midland",
        "SUNCOR ENERGY INC": "Suncor", "GLENCORE PLC": "Glencore", "BARRICK MINING CORP": "Barrick",
        "RIO TINTO LTD": "Rio Tinto", "ANGLO AMERICAN PLC": "Anglo American", "ENI SPA": "Eni",
        "MOSAIC CO/THE": "Mosaic", "FMC CORP": "FMC", "ZIJIN MINING GROUP CO LTD H": "Zijin Mining",
        "SVENSKA CELLULOSA AB SCA B": "SCA (Svenska Cellulosa)", "CONOCOPHILLIPS": "ConocoPhillips",
        "PETROLEO BRASILEIRO SPON ADR": "Petrobras", "ARCELORMITTAL": "ArcelorMittal",
        "ANGLOGOLD ASHANTI PLC": "AngloGold Ashanti", "PACKAGING CORP OF AMERICA": "Packaging Corp of America",
        "FRANCO NEVADA CORP": "Franco-Nevada", "SCOTTS MIRACLE GRO CO": "Scotts Miracle-Gro",
        "ZIJIN GOLD INTERNATIONAL CO": "Zijin Gold", "STORA ENSO OYJ R SHS": "Stora Enso",
        "SUZANO SA  SPON ADR": "Suzano", "WEST FRASER TIMBER CO LTD": "West Fraser",
        "TECK RESOURCES LTD CLS B": "Teck Resources", "BHP GROUP LTD DI": "BHP"}


SUFFIXES = [" SPONSORED ADR", " SPONS ADR", " SPON ADR", " SP ADR", " ADR", " CLS B", " R SHS", " DI", " REG S GDR",
            " HOLDINGS", " GROUP", " LTD", " INC", " PLC", " CORP", " CORPORATION", " CO", " SA", " SE", " SPA",
            " ASA", " OYJ", " AB", " AG", " NV", " LIMITED", " /THE", " B"]
MAJUSCULES = {"BP", "ADM", "CF", "ICL", "SIG", "SLB", "EOG", "EQT", "POSCO", "UPM", "SCA", "INPEX"}


def nom_affiche(nom):
    """Nom lisible à partir du nom SSGA en majuscules ("FREEPORT MCMORAN INC" -> "Freeport Mcmoran")."""
    if nom in NOMS:
        return NOMS[nom]
    n = nom.strip()
    retire = True
    while retire:
        retire = False
        for suf in SUFFIXES:
            if n.endswith(suf) and len(n) > len(suf) + 2:
                n, retire = n[: -len(suf)].strip(), True
    return " ".join(m if m in MAJUSCULES else m.capitalize() for m in n.split())


def indice_json(csv, date):
    w = pd.read_csv(csv, sep=";", decimal=",", encoding="utf-8-sig")
    w = w[w.poids_3110 > 0]
    sect = (w.groupby("secteur").agg(poids=("poids_3110", "sum"), n=("RIC", "size"))
              .reindex(ORDRE_SECTEURS).reset_index())
    sous = (w.groupby(["secteur", "sous_secteur"]).agg(poids=("poids_3110", "sum"), n=("RIC", "size"))
              .reset_index())
    sous["ordre"] = sous.secteur.map({s: i for i, s in enumerate(ORDRE_SECTEURS)})
    sous = sous.sort_values(["ordre", "poids"], ascending=[True, False]).drop(columns="ordre")
    valeurs = {k: g.sort_values("poids_3110", ascending=False)
               for k, g in w.groupby(["secteur", "sous_secteur"])}
    top = w.nlargest(10, "poids_3110")[["Name", "secteur", "sous_secteur", "poids_3110"]]
    r = lambda x: round(float(x), 2)
    return {
        "date": date,
        "indice": "S&P Global Natural Resources Index (Net TR, USD)",
        "nb_valeurs": int(len(w)),
        "plafond_secteur": 33.33,
        "secteurs": [{"nom": s.secteur, "poids": r(s.poids), "n": int(s.n)} for s in sect.itertuples()],
        "sous_secteurs": [{"secteur": s.secteur, "nom": s.sous_secteur, "poids": r(s.poids), "n": int(s.n),
                           "valeurs": [{"nom": nom_affiche(v.Name), "poids": r(v.poids_3110)}
                                       for v in valeurs[(s.secteur, s.sous_secteur)].itertuples()]}
                          for s in sous.itertuples()],
        "top10": [{"nom": nom_affiche(t.Name), "secteur": t.secteur, "sous_secteur": t.sous_secteur,
                   "poids": r(t.poids_3110)} for t in top.itertuples()],
    }


def index_contenus():
    """Liste les .md de chaque rubrique : lettres et hebdo du plus récent au plus ancien,
    fiches sectorielles dans l'ordre de leur préfixe (1-, 2-, 3-)."""
    out = {}
    for rub in ["lettres", "hebdo", "secteurs"]:
        fichiers = sorted((DOCS / "contenu" / rub).glob("*.md"), reverse=(rub != "secteurs"))
        items = []
        for f in fichiers:
            titre = next((l.lstrip("# ").strip() for l in f.read_text(encoding="utf-8").splitlines()
                          if l.startswith("# ")), f.stem)
            items.append({"fichier": f"contenu/{rub}/{f.name}", "titre": titre})
        out[rub] = items
    return out


if __name__ == "__main__":
    csv, date = sys.argv[1], sys.argv[2]
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    (DOCS / "data" / "indice.json").write_text(
        json.dumps(indice_json(csv, date), ensure_ascii=False, indent=1), encoding="utf-8")
    (DOCS / "contenu" / "index.json").write_text(
        json.dumps(index_contenus(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK : docs/data/indice.json, docs/contenu/index.json")
