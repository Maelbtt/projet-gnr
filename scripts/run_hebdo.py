"""Valorisation hebdomadaire du portefeuille fictif contre l'indice (base 100 au lancement).

Deux commandes, lancées depuis la racine du projet :

  1) Lancement (une seule fois, vendredi 27/11/2026 à la clôture) :
     py -3.13 scripts\\run_hebdo.py lancer <portefeuille_optimiseur.csv> <cours.csv> <indice_secteurs.csv> [AAAA-MM-JJ]

  2) Chaque vendredi soir :
     py -3.13 scripts\\run_hebdo.py semaine <cours.csv> <indice_secteurs.csv> [dividendes=dividendes.csv] [poids=nouveaux_poids.csv]

  - cours.csv : export LSEG long (une ligne par RIC et par date), cours de clôture quotidiens EN USD
    de toutes les valeurs de l'indice + l'indice .SPGNRUN. Même formule que pour l'optimiseur :
    =RDP.Data(RICs;"TR.PriceClose.date;TR.PriceClose";"SDate=... EDate=... Frq=D Curn=USD RH=IN CH=Fd")
  - dividendes.csv (facultatif) : dividendes détachés dans la semaine, en USD par action :
    =RDP.Data(RICs;"TR.DivExDate;TR.DivUnadjustedGross(Curn=USD);TR.DivCurr(Curn=USD)";"SDate=... EDate=... RH=IN CH=Fd")
  - nouveaux_poids.csv : sortie de optimiseur.py pour le rééquilibrage du vendredi.

Règles (voir la méthodologie du site) :
  - capital fictif de 10 M$, nombres d'actions fictifs ; buy-and-hold entre deux vendredis ;
  - dividendes crédités à la date de détachement, nets d'une retenue forfaitaire de 15 %, réinvestis
    au rééquilibrage suivant ; frais de 10 points de base sur chaque achat ou vente au rééquilibrage ;
  - exécution au cours de clôture du vendredi.

État (non publié avec les cours) : portefeuille/positions.csv et portefeuille/historique.csv.
Sortie publiée : docs/data/performance.json (uniquement des résultats : base 100, poids, contributions).
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from risque import lire_cours_lseg  # noqa: E402
from build_site_data import nom_affiche  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parents[1]
ETAT = RACINE / "portefeuille"
F_POS, F_HIST, F_MOUV = ETAT / "positions.csv", ETAT / "historique.csv", ETAT / "mouvements.csv"
SORTIE = RACINE / "docs" / "data" / "performance.json"

CAPITAL = 10_000_000.0
FRAIS = 0.0010            # 10 points de base par transaction
RETENUE = 0.15            # retenue à la source forfaitaire sur les dividendes
INDICE = ".SPGNRUN"
SEMAINES_MIN_RISQUE = 12  # en dessous, les indicateurs de risque réalisés n'ont pas de sens


# ------------------------------------------------------------------ lecture
def lire_indice(chemin):
    ind = pd.read_csv(chemin, sep=";", decimal=",", encoding="utf-8-sig").set_index("RIC")
    return ind[ind.poids_3110 > 0]


def lire_poids(chemin):
    """Poids cibles en fraction (sortie de optimiseur.py, colonne poids_portefeuille en %)."""
    df = pd.read_csv(chemin, sep=";", decimal=",", encoding="utf-8-sig")
    df = df.set_index(df.columns[0])
    w = pd.to_numeric(df["poids_portefeuille"], errors="coerce").fillna(0) / 100
    w = w[w > 1e-6]
    if abs(w.sum() - 1) > 0.002:
        raise SystemExit(f"Les poids du portefeuille somment à {w.sum():.4f}, pas à 1.")
    return w / w.sum()


def lire_dividendes(chemin):
    """Renvoie une table (RIC, date, montant en USD par action). Ignore les lignes non USD."""
    df = pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str)
    cols = {c.lower(): c for c in df.columns}
    c_ric = next((cols[k] for k in cols if k.startswith("updated at") or k == "instrument"),
                 next(cols[k] for k in cols if k == "ric"))
    # La liste de RIC collée à côté peut contenir « Local Currency » : on privilégie les colonnes du dividende.
    c_date = next((cols[k] for k in cols if "ex" in k and "date" in k),
                  next(cols[k] for k in cols if "date" in k and "updated" not in k))
    c_mt = next(cols[k] for k in cols if "amount" in k or "gross" in k or "montant" in k)
    c_dev = next((cols[k] for k in cols if "div" in k and "curr" in k),
                 next((cols[k] for k in cols if ("curr" in k and "local" not in k) or "devise" in k), None))
    df[c_ric] = df[c_ric].ffill()
    out = pd.DataFrame({
        "ric": df[c_ric],
        "date": pd.to_datetime(df[c_date], dayfirst=True, errors="coerce"),
        "montant": pd.to_numeric(df[c_mt].str.replace(",", "."), errors="coerce"),
        "devise": df[c_dev].str.upper().str.strip() if c_dev else "USD",
    }).dropna(subset=["date", "montant"])
    hors_usd = out[out.devise != "USD"]
    if len(hors_usd):
        print("Attention : dividendes ignorés car pas en USD (ajoute Curn=USD) :", hors_usd.ric.unique().tolist())
    return out[out.devise == "USD"]


def cours_complets(chemin):
    c = lire_cours_lseg(chemin).ffill()  # jour férié local : on garde le dernier cours
    if INDICE not in c.columns:
        raise SystemExit(f"L'indice {INDICE} manque dans {chemin}.")
    return c


# ------------------------------------------------------------------ état
def lire_etat():
    if not F_POS.exists():
        raise SystemExit("Portefeuille non lancé : commence par « run_hebdo.py lancer ... ».")
    pos = pd.read_csv(F_POS, sep=";", decimal=",", encoding="utf-8-sig").set_index("RIC")
    hist = pd.read_csv(F_HIST, sep=";", decimal=",", encoding="utf-8-sig", parse_dates=["date"])
    return pos, hist


def ecrire_etat(actions, cash, hist):
    ETAT.mkdir(exist_ok=True)
    pos = pd.DataFrame({"actions": actions[actions > 0]})
    pos.loc["CASH_USD", "actions"] = cash
    pos.index.name = "RIC"
    pos.to_csv(F_POS, sep=";", decimal=",", encoding="utf-8-sig", float_format="%.6f")
    hist.to_csv(F_HIST, sep=";", decimal=",", encoding="utf-8-sig", index=False, float_format="%.6f",
                date_format="%Y-%m-%d")


def journal(lignes):
    ETAT.mkdir(exist_ok=True)
    df = pd.DataFrame(lignes)
    df.to_csv(F_MOUV, sep=";", decimal=",", encoding="utf-8-sig", index=False, float_format="%.4f",
              mode="a", header=not F_MOUV.exists(), date_format="%Y-%m-%d")


# ------------------------------------------------------------------ calculs
def reequilibrer(actions, cash, w, px, date):
    """Achète/vend au cours de clôture pour atteindre les poids w ; frais de 10 pb ; cash final ≈ 0."""
    actions = actions.reindex(actions.index.union(w.index), fill_value=0.0)
    manquants = [r for r in actions.index if r not in px.index or pd.isna(px[r])]
    if manquants:
        raise SystemExit(f"Cours manquant le {date.date()} pour : {manquants}")
    actuel = actions * px[actions.index]
    v = actuel.sum() + cash
    v_net = v
    for _ in range(5):  # les frais dépendent des montants échangés, qui dépendent des frais
        cible = w.reindex(actions.index, fill_value=0.0) * v_net
        frais = FRAIS * (cible - actuel).abs().sum()
        v_net = v - frais
    cible = w.reindex(actions.index, fill_value=0.0) * v_net
    echanges = cible - actuel
    nouvelles = cible / px[actions.index]
    journal([{"date": date, "RIC": r, "montant_usd": echanges[r], "frais_usd": FRAIS * abs(echanges[r])}
             for r in echanges.index if abs(echanges[r]) > 1])
    return nouvelles[nouvelles > 1e-9], 0.0, frais, (echanges.abs().sum() / 2) / v


def poids_indice_a(ind, cours, date):
    """Poids de l'indice dérivés depuis le 31/10 avec les cours (approximation entre deux rebalancements S&P)."""
    base = cours.loc[:pd.Timestamp("2026-10-31")].iloc[-1] if (cours.index <= "2026-10-31").any() else None
    w0 = ind.poids_3110 / 100
    if base is None:
        return w0 / w0.sum()
    px = cours.loc[:date].iloc[-1]
    rel = (px[w0.index] / base[w0.index]).fillna(1.0)
    w = w0 * rel
    return w / w.sum()


def indicateurs_risque(hist):
    h = hist.set_index("date")[["vl", "indice"]].resample("W-FRI").last().dropna()
    r = h.pct_change().dropna()
    if len(r) < SEMAINES_MIN_RISQUE:
        return {"nb_semaines": int(len(r)), "disponible": False}
    act = r.vl - r.indice
    te = act.std() * np.sqrt(52)
    beta = np.cov(r.vl, r.indice)[0, 1] / r.indice.var()
    return {"nb_semaines": int(len(r)), "disponible": True,
            "ecart_suivi": te, "ratio_information": act.mean() * 52 / te if te else None,
            "beta": beta, "vol_portefeuille": r.vl.std() * np.sqrt(52), "vol_indice": r.indice.std() * np.sqrt(52)}


def attribution(w_p, w_b, r_titres, secteurs):
    """Brinson par secteur sur la semaine : allocation + sélection (interaction incluse dans la sélection)."""
    titres = w_p.index.union(w_b.index)
    w_p, w_b = w_p.reindex(titres, fill_value=0), w_b.reindex(titres, fill_value=0)
    r = r_titres.reindex(titres).fillna(0)
    sec = secteurs.reindex(titres)
    rb_tot = (w_b * r).sum()
    lignes = []
    for s in sorted(sec.dropna().unique()):
        m = sec == s
        wp, wb = w_p[m].sum(), w_b[m].sum()
        rp = (w_p[m] * r[m]).sum() / wp if wp else 0.0
        rb = (w_b[m] * r[m]).sum() / wb if wb else 0.0
        lignes.append({"secteur": s, "poids_portefeuille": wp, "poids_indice": wb,
                       "rendement_portefeuille": rp, "rendement_indice": rb,
                       "allocation": (wp - wb) * (rb - rb_tot), "selection": wp * (rp - rb)})
    return lignes


# ------------------------------------------------------------------ publication
def publier(hist, actions, cash, cours, ind, info_semaine):
    date = hist.date.iloc[-1]
    px = cours.loc[:date].iloc[-1]
    val = actions * px[actions.index]
    v = val.sum() + cash
    w_p = val / v
    w_b = poids_indice_a(ind, cours, date)
    noms = ind.Name.map(nom_affiche)

    h = hist.copy()
    def perf(depuis):
        a = h[h.date <= depuis].iloc[-1] if (h.date <= depuis).any() else h.iloc[0]
        b = h.iloc[-1]
        p, i = b.vl / a.vl - 1, b.indice / a.indice - 1
        return {"depuis": a.date.strftime("%Y-%m-%d"), "portefeuille": p, "indice": i, "ecart": p - i}

    sect = []
    for s in ["Énergie", "Métaux et mines", "Agriculture"]:
        rics = ind.index[ind.secteur == s]
        sect.append({"secteur": s, "poids_portefeuille": float(w_p.reindex(rics).fillna(0).sum()),
                     "poids_indice": float(w_b.reindex(rics).fillna(0).sum())})
    # sous-secteurs et active share (pour le contrôle des risques)
    sous = []
    for ss in sorted(ind.sous_secteur.dropna().unique()):
        rics = ind.index[ind.sous_secteur == ss]
        sous.append({"sous_secteur": ss, "secteur": ind.secteur[rics[0]],
                     "poids_portefeuille": float(w_p.reindex(rics).fillna(0).sum()),
                     "poids_indice": float(w_b.reindex(rics).fillna(0).sum())})
    tous = w_p.index.union(w_b.index)
    active_share = float(0.5 * (w_p.reindex(tous).fillna(0) - w_b.reindex(tous).fillna(0)).abs().sum())
    lignes = pd.DataFrame({"poids_portefeuille": w_p, "poids_indice": w_b.reindex(w_p.index).fillna(0)})
    lignes["ecart"] = lignes.poids_portefeuille - lignes.poids_indice
    lignes = lignes.sort_values("poids_portefeuille", ascending=False)

    out = {
        "maj": date.strftime("%Y-%m-%d"),
        "lancement": h.date.iloc[0].strftime("%Y-%m-%d"),
        "vl": float(h.vl.iloc[-1]), "indice": float(h.indice.iloc[-1]),
        "historique": [[d.strftime("%Y-%m-%d"), round(float(a), 4), round(float(b), 4)]
                       for d, a, b in zip(h.date, h.vl, h.indice)],
        "performances": {
            "semaine": perf(date - pd.Timedelta(days=7)),
            "mois": perf(date - pd.DateOffset(months=1)),
            "lancement": perf(h.date.iloc[0]),
        },
        "nb_lignes": int((w_p > 0).sum()),
        "cash": float(cash / v),
        "secteurs": sect,
        "sous_secteurs": sous,
        "active_share": active_share,
        "positions": [{"nom": noms.get(r, r), "sous_secteur": ind.sous_secteur.get(r, ""), "secteur": ind.secteur.get(r, ""), "poids_portefeuille": float(x.poids_portefeuille),
                       "poids_indice": float(x.poids_indice), "ecart": float(x.ecart)} for r, x in lignes.iterrows()],
        "risque": indicateurs_risque(h),
        "semaine": info_semaine,
        "methode": "Capital fictif de 10 M$ ; dividendes nets d'une retenue forfaitaire de 15 % ; frais de 10 pb par "
                   "transaction ; exécution au cours de clôture du vendredi. Indice : S&P Global Natural Resources Net TR (USD).",
    }
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return out


# ------------------------------------------------------------------ commandes
def lancer(f_poids, f_cours, f_indice, date=None):
    if F_POS.exists():
        raise SystemExit("Le portefeuille est déjà lancé (portefeuille/positions.csv existe).")
    w, cours, ind = lire_poids(f_poids), cours_complets(f_cours), lire_indice(f_indice)
    date = pd.Timestamp(date) if date else cours.index[-1]
    px = cours.loc[:date].iloc[-1]
    manquants = [r for r in w.index if pd.isna(px.get(r))]
    if manquants:
        raise SystemExit(f"Cours manquant le {date.date()} pour : {manquants}")
    actions = CAPITAL * w / px[w.index]   # constitution sans frais : la base 100 part du portefeuille investi
    hist = pd.DataFrame({"date": [date], "vl": [100.0], "indice": [100.0], "niveau_indice": [px[INDICE]],
                         "valeur_usd": [CAPITAL]})
    journal([{"date": date, "RIC": r, "montant_usd": CAPITAL * w[r], "frais_usd": 0.0} for r in w.index])
    ecrire_etat(actions, 0.0, hist)
    out = publier(hist, actions, 0.0, cours, ind, None)
    print(f"Portefeuille lancé le {date.date()} : {out['nb_lignes']} lignes, base 100.")


def semaine(f_cours, f_indice, f_div=None, f_poids=None):
    pos, hist = lire_etat()
    cours, ind = cours_complets(f_cours), lire_indice(f_indice)
    cash = float(pos.actions.get("CASH_USD", 0.0))
    actions = pos.actions.drop("CASH_USD", errors="ignore")
    derniere = hist.date.iloc[-1]
    jours = cours.index[cours.index > derniere]
    if not len(jours):
        raise SystemExit(f"Aucun cours après le {derniere.date()} dans {f_cours}.")
    divs = lire_dividendes(f_div) if f_div else None
    if divs is None:
        print("Attention : aucun fichier de dividendes, seuls les cours sont pris en compte cette semaine.")
    v0, n0 = hist.valeur_usd.iloc[0], hist.niveau_indice.iloc[0]
    debut_px = cours.loc[:derniere].iloc[-1]
    w_debut = (actions * debut_px[actions.index]) / ((actions * debut_px[actions.index]).sum() + cash)
    div_total, lignes_hist = 0.0, []
    for j in jours:
        px = cours.loc[j]
        if divs is not None:
            for _, d in divs[divs.date == j].iterrows():
                if d.ric in actions.index:
                    net = actions[d.ric] * d.montant * (1 - RETENUE)
                    cash += net
                    div_total += net
        manquants = [r for r in actions.index if pd.isna(px.get(r))]
        if manquants:
            raise SystemExit(f"Cours manquant le {j.date()} pour : {manquants}")
        v = (actions * px[actions.index]).sum() + cash
        lignes_hist.append({"date": j, "vl": 100 * v / v0, "indice": 100 * px[INDICE] / n0,
                            "niveau_indice": px[INDICE], "valeur_usd": v})
    # attribution de la semaine (avant rééquilibrage, sur les poids du début de semaine)
    fin = jours[-1]
    r_titres = cours.loc[fin] / debut_px - 1
    w_b_debut = poids_indice_a(ind, cours, derniere)
    attr = attribution(w_debut, w_b_debut, r_titres, ind.secteur)
    frais, rotation = 0.0, 0.0
    if f_poids:
        actions, cash, frais, rotation = reequilibrer(actions, cash, lire_poids(f_poids), cours.loc[fin], fin)
        v = (actions * cours.loc[fin][actions.index]).sum() + cash
        lignes_hist[-1].update({"vl": 100 * v / v0, "valeur_usd": v})
    hist = pd.concat([hist, pd.DataFrame(lignes_hist)], ignore_index=True)
    ecrire_etat(actions, cash, hist)
    info = {"du": derniere.strftime("%Y-%m-%d"), "au": fin.strftime("%Y-%m-%d"),
            "dividendes_nets_pct": div_total / hist.valeur_usd.iloc[-len(lignes_hist) - 1],
            "frais_pct": frais / hist.valeur_usd.iloc[-1], "rotation_pct": rotation,
            "attribution": attr, "reequilibre": bool(f_poids)}
    out = publier(hist, actions, cash, cours, ind, info)
    p = out["performances"]["semaine"]
    print(f"Semaine du {info['du']} au {info['au']} : portefeuille {p['portefeuille']:+.2%}, indice {p['indice']:+.2%}, "
          f"écart {p['ecart']:+.2%}. VL {out['vl']:.2f}, {out['nb_lignes']} lignes"
          + (f", rotation {rotation:.1%}, frais {info['frais_pct']:.3%}" if f_poids else ", pas de rééquilibrage") + ".")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("lancer", "semaine"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "lancer":
        lancer(*sys.argv[2:6])
    else:
        pos_args = [a for a in sys.argv[2:] if "=" not in a]
        opts = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
        if len(pos_args) != 2:
            raise SystemExit("Usage : run_hebdo.py semaine <cours.csv> <indice_secteurs.csv> [dividendes=...] [poids=...]")
        semaine(pos_args[0], pos_args[1], opts.get("dividendes"), opts.get("poids"))
