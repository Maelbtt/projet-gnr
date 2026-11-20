"""Indicateurs de marché et anticipations pour le site : FRED + EIA + CFTC -> docs/data/marches.json.

Les clés ne sont jamais écrites dans un fichier : elles sont lues dans les variables
d'environnement FRED_API_KEY et EIA_API_KEY (secrets GitHub dans l'Action, ou
`set FRED_API_KEY=...` dans le terminal Windows pour un test local).

Usage : py -3.13 scripts\\marches.py
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

# Sous Windows, Python ne lit pas toujours les certificats du système (antivirus, réseau
# d'université...). Si le paquet « truststore » est installé, on utilise le magasin de
# certificats de Windows ; sinon le comportement par défaut (suffisant sur GitHub Actions).
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

RACINE = pathlib.Path(__file__).resolve().parents[1]
SORTIE = RACINE / "docs" / "data" / "marches.json"
HISTO_JOURS = 400  # un peu plus d'un an pour les mini-courbes

# Chaque indicateur : d'où il vient et quel avis du portefeuille il touche.
FRED = [
    {"id": "DCOILBRENTEU", "nom": "Brent", "unite": "$/baril", "secteur": "Énergie",
     "lien_avis": "E&P (−), intégrées (+) : niveau du baril", "decimales": 1},
    {"id": "DFII10", "nom": "Taux réel 10 ans US", "unite": "%", "secteur": "Macro",
     "lien_avis": "Or (+) : un taux réel qui monte joue contre l'or", "decimales": 2, "variation_en_points": True},
    {"id": "DTWEXBGS", "nom": "Dollar (indice large de la Fed)", "unite": "indice", "secteur": "Macro",
     "lien_avis": "Or et métaux : un dollar fort pèse sur les prix", "decimales": 1},
    {"id": "MORTGAGE30US", "nom": "Taux immobilier 30 ans US", "unite": "%", "secteur": "Agriculture",
     "lien_avis": "Bois (−) : des taux hauts freinent la construction", "decimales": 2, "variation_en_points": True},
    {"id": "HOUST", "nom": "Mises en chantier US", "unite": "milliers (rythme annuel)", "secteur": "Agriculture",
     "lien_avis": "Bois (−) : une reprise contredirait l'avis", "decimales": 0},
    {"id": "PCOPPUSDM", "nom": "Cuivre (moyenne mensuelle)", "unite": "$/t", "secteur": "Métaux",
     "lien_avis": "Cuivre (+) : déficit d'offre", "decimales": 0},
]
EIA = [
    {"id": "WDISTUS1", "nom": "Stocks de distillats US", "unite": "millions de barils", "secteur": "Énergie",
     "lien_avis": "Raffinage (+) : retour vers la moyenne 5 ans = signal de réduction", "decimales": 1, "echelle": 0.001},
    {"id": "WCESTUS1", "nom": "Stocks de brut US (hors réserve stratégique)", "unite": "millions de barils", "secteur": "Énergie",
     "lien_avis": "Équilibre du marché du brut", "decimales": 1, "echelle": 0.001},
]


def lire_json(url, essais=3):
    """Lit une URL JSON ; réessaie après une erreur serveur passagère (500, 502, 503...)."""
    import time
    import urllib.error
    req = urllib.request.Request(url, headers={"User-Agent": "projet-gnr/1.0"})
    for k in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code < 500 or k == essais - 1:
                raise
            time.sleep(3 * (k + 1))


def fred(serie, cle, debut):
    q = urllib.parse.urlencode({"series_id": serie, "api_key": cle, "file_type": "json", "observation_start": debut})
    obs = lire_json(f"https://api.stlouisfed.org/fred/series/observations?{q}")["observations"]
    return [(o["date"], float(o["value"])) for o in obs if o["value"] not in (".", "")]


def eia(serie, cle, v1=None, route="petroleum/stoc/wstk", facet="series", frequence="weekly", longueur=400):
    """Série EIA. Essaie la route « seriesid » (identifiant v1) puis la route v2 classique."""
    v1 = v1 or f"PET.{serie}.W"
    essais = [
        f"https://api.eia.gov/v2/seriesid/{v1}?" + urllib.parse.urlencode({"api_key": cle}),
        f"https://api.eia.gov/v2/{route}/data/?" + urllib.parse.urlencode(
            {"api_key": cle, "frequency": frequence, "data[0]": "value", f"facets[{facet}][]": serie,
             "sort[0][column]": "period", "sort[0][direction]": "desc", "length": longueur}),
    ]
    derniere_erreur = None
    for url in essais:
        try:
            lignes = lire_json(url)["response"]["data"]
            pts = [(str(l["period"])[:10], float(l["value"])) for l in lignes if l.get("value") not in (None, "")]
            if pts:
                return sorted(pts)
        except Exception as e:  # on tente l'autre route
            derniere_erreur = e
    raise RuntimeError(f"EIA {serie} : aucune route n'a répondu ({derniere_erreur})")


def moyenne_5_ans(points):
    """Moyenne des 5 années précédentes pour la même semaine (± 3 jours), comme l'EIA."""
    date_fin, _ = points[-1]
    fin = dt.date.fromisoformat(date_fin)
    valeurs = []
    for k in range(1, 6):
        cible = fin.replace(year=fin.year - k)
        proches = [v for d, v in points if abs((dt.date.fromisoformat(d) - cible).days) <= 3]
        if proches:
            valeurs.append(proches[0])
    return sum(valeurs) / len(valeurs) if len(valeurs) == 5 else None


def resumer(meta, points, source):
    ech = meta.get("echelle", 1)
    points = [(d, v * ech) for d, v in points]
    date, val = points[-1]
    fin = dt.date.fromisoformat(date)
    # variation sur ~1 semaine (dernier point à au moins 7 jours) ou sur la période précédente
    avant = [p for p in points if (fin - dt.date.fromisoformat(p[0])).days >= 7]
    ref = avant[-1] if avant else points[-2] if len(points) > 1 else None
    debut_histo = fin - dt.timedelta(days=HISTO_JOURS)
    histo = [(d, round(v, 4)) for d, v in points if dt.date.fromisoformat(d) >= debut_histo]
    if len(histo) > 120:  # séries quotidiennes : un point par semaine suffit pour une mini-courbe
        pas = len(histo) // 60
        histo = histo[::pas] + ([histo[-1]] if histo[-1] != histo[::pas][-1] else [])
    out = {
        "id": meta["id"], "nom": meta["nom"], "unite": meta["unite"], "secteur": meta["secteur"],
        "lien_avis": meta["lien_avis"], "decimales": meta["decimales"], "source": source,
        "date": date, "valeur": round(val, 4),
        "reference": {"date": ref[0], "valeur": round(ref[1], 4)} if ref else None,
        "variation_en_points": meta.get("variation_en_points", False),
        "historique": histo,
    }
    if source == "EIA":
        m5 = moyenne_5_ans(points)
        if m5:
            out["moyenne_5_ans"] = round(m5, 2)
    return out


# ------------------------------------------------------------------ Ce que le marché anticipe
CFTC = [  # rapport « disaggregated », futures seuls : position des gérants (managed money)
    {"id": "CFTC_WTI", "code": "067651", "nom": "Fonds sur le pétrole (WTI)"},
    {"id": "CFTC_OR", "code": "088691", "nom": "Fonds sur l'or"},
    {"id": "CFTC_CUIVRE", "code": "085692", "nom": "Fonds sur le cuivre"},
]


def serie_resumee(id_, nom, unite, points, decimales, lecture, en_points=True, source=""):
    """Même format que les indicateurs de marché, avec une phrase de lecture."""
    points = sorted(points)
    date, val = points[-1]
    fin = dt.date.fromisoformat(date)
    avant = [p for p in points if (fin - dt.date.fromisoformat(p[0])).days >= 7]
    ref = avant[-1] if avant else None
    debut = fin - dt.timedelta(days=HISTO_JOURS)
    histo = [(d, round(v, 4)) for d, v in points if dt.date.fromisoformat(d) >= debut]
    if len(histo) > 120:
        pas = len(histo) // 60
        histo = histo[::pas] + ([histo[-1]] if histo[-1] != histo[::pas][-1] else [])
    return {"id": id_, "nom": nom, "unite": unite, "decimales": decimales, "source": source,
            "date": date, "valeur": round(val, 4),
            "reference": {"date": ref[0], "valeur": round(ref[1], 4)} if ref else None,
            "variation_en_points": en_points, "lecture": lecture, "historique": histo}


def aligner(a, b):
    """Garde les dates communes à deux séries."""
    db = dict(b)
    return [(d, va, db[d]) for d, va in a if d in db]


def courbe_wti(cle):
    c1 = eia("RCLC1", cle, v1="PET.RCLC1.D", route="petroleum/pri/fut", frequence="daily", longueur=450)
    c4 = eia("RCLC4", cle, v1="PET.RCLC4.D", route="petroleum/pri/fut", frequence="daily", longueur=450)
    pts = [(d, 100 * (v4 - v1) / v1) for d, v1, v4 in aligner(c1, c4)]
    p = pts[-1][1]
    lecture = ("Backwardation : les échéances lointaines sont moins chères, le marché anticipe un pétrole en baisse."
               if p < -1 else "Contango : les échéances lointaines sont plus chères, le marché anticipe une hausse ou un surplus de stocks."
               if p > 1 else "Courbe plate : pas d'anticipation marquée.")
    return serie_resumee("WTI_PENTE", "Pente de la courbe du pétrole (WTI, 4e mois contre 1er)", "% d'écart",
                         pts, 1, lecture, source="EIA (contrats à terme NYMEX)")


def ecart_2ans_fed(cle, debut):
    deux = fred("DGS2", cle, debut)
    haut, bas = dict(fred("DFEDTARU", cle, debut)), dict(fred("DFEDTARL", cle, debut))
    pts = [(d, v - (haut[d] + bas[d]) / 2) for d, v in deux if d in haut and d in bas]
    e = pts[-1][1]
    lecture = ("Le taux à 2 ans est au-dessus du taux directeur : le marché anticipe des hausses de taux."
               if e > 0.10 else "Le taux à 2 ans est sous le taux directeur : le marché anticipe des baisses de taux."
               if e < -0.10 else "Le marché anticipe un statu quo sur les taux.")
    return serie_resumee("ECART_2A_FED", "Taux à 2 ans moins taux directeur de la Fed", "points de %",
                         pts, 2, lecture, source="FRED")


def inflation_anticipee(cle, debut):
    pts = fred("T10YIE", cle, debut)
    v, d = pts[-1][1], dt.date.fromisoformat(pts[-1][0])
    il_y_a_un_an = [x for x in pts if (d - dt.date.fromisoformat(x[0])).days >= 365]
    sens = ""
    if il_y_a_un_an:
        sens = " En hausse sur un an." if v > il_y_a_un_an[-1][1] + 0.05 else " En baisse sur un an." if v < il_y_a_un_an[-1][1] - 0.05 else " Stable sur un an."
    return serie_resumee("T10YIE", "Inflation anticipée à 10 ans (point mort)", "%", pts, 2,
                         f"Inflation moyenne que le marché obligataire anticipe sur 10 ans.{sens}", source="FRED")


def cftc(meta):
    q = urllib.parse.urlencode({"cftc_contract_market_code": meta["code"], "$order": "report_date_as_yyyy_mm_dd DESC",
                                "$limit": 160, "$select": "report_date_as_yyyy_mm_dd,m_money_positions_long_all,"
                                "m_money_positions_short_all,open_interest_all"})
    lignes = lire_json(f"https://publicreporting.cftc.gov/resource/72hh-3qpy.json?{q}")
    pts = []
    for l in lignes:
        oi = float(l["open_interest_all"])
        if oi:
            net = float(l["m_money_positions_long_all"]) - float(l["m_money_positions_short_all"])
            pts.append((l["report_date_as_yyyy_mm_dd"][:10], 100 * net / oi))
    pts.sort()
    v = pts[-1][1]
    rang = 100 * sum(x[1] <= v for x in pts) / len(pts)  # rang sur ~3 ans
    if rang >= 80:
        lecture = f"Fonds très acheteurs (plus haut que {rang:.0f} % des semaines sur 3 ans) : position chargée, risque de prises de bénéfices."
    elif rang <= 20:
        lecture = f"Fonds peu exposés (plus bas que {100 - rang:.0f} % des semaines sur 3 ans) : marge pour des achats."
    else:
        lecture = f"Positionnement dans la moyenne des 3 dernières années (rang {rang:.0f} %)."
    return serie_resumee(meta["id"], meta["nom"], "position nette, % de l'intérêt ouvert", pts, 1, lecture,
                         source="CFTC (rapport hebdomadaire)")


def prevision_eia_brent(cle, brent_spot=None):
    pts = eia("BREPUUS", cle, v1="STEO.BREPUUS.M", route="steo", facet="seriesId", frequence="monthly", longueur=60)
    pts = sorted((d if len(d) == 10 else d + "-01", v) for d, v in pts)
    annee = dt.date.today().year + 1
    prev = [v for d, v in pts if d.startswith(str(annee))]
    if not prev:
        raise RuntimeError("pas de prévision STEO pour l'année prochaine")
    moy = sum(prev) / len(prev)
    auj = dt.date.today().replace(day=1).isoformat()
    histo = [(d, v) for d, v in pts if dt.date.fromisoformat(d) >= dt.date.today() - dt.timedelta(days=365)]
    actuel = brent_spot[1] if brent_spot else [v for d, v in pts if d <= auj][-1]
    ecart = 100 * (moy - actuel) / actuel
    if brent_spot:
        a_, m_, j_ = brent_spot[0].split("-")
        reference = f"au Brent du {j_}/{m_} ({actuel:.1f} $)".replace(".", ",")
    else:
        reference = "au mois en cours"
    signe = "+" if ecart >= 0 else "−"
    return {"id": "STEO_BRENT", "nom": f"Prévision de l'EIA pour le Brent en {annee}", "unite": "$/baril (moyenne annuelle)",
            "decimales": 1, "source": "EIA, Short-Term Energy Outlook", "date": auj, "valeur": round(moy, 2),
            "reference": None, "variation_en_points": False, "historique": [(d, round(v, 2)) for d, v in histo],
            "lecture": f"L'EIA prévoit {moy:.0f} $ en moyenne en {annee}, soit {signe}{abs(ecart):.0f} % par rapport {reference} (courbe : historique puis prévision mensuelle)."}


def anticipations(cle_fred, cle_eia, debut, erreurs, brent_spot=None):
    out = []
    # La pente de la courbe WTI a été retirée : l'EIA ne publie plus les contrats à terme NYMEX depuis le 5/04/2024.
    taches = [("ECART_2A_FED", lambda: ecart_2ans_fed(cle_fred, debut)),
              ("T10YIE", lambda: inflation_anticipee(cle_fred, debut))]
    taches += [(m["id"], (lambda m=m: cftc(m))) for m in CFTC]
    taches += [("STEO_BRENT", lambda: prevision_eia_brent(cle_eia, brent_spot))]
    for id_, f in taches:
        try:
            out.append(f())
        except Exception as e:
            erreurs.append(f"{id_} : {e}")
    return out


# ------------------------------------------------------------------ Calendrier des publications US (FRED)
CALENDRIER_FRED = {  # nom exact de la publication sur FRED -> identifiant dans docs/data/agenda.json
    "Employment Situation": "emploi-us",
    "Consumer Price Index": "cpi-us",
    "New Residential Construction": "logement-us",
    "Gross Domestic Product": "pib-us",
    "Personal Income and Outlays": "pce-us",
}
SORTIE_AGENDA = RACINE / "docs" / "data" / "agenda_auto.json"


def calendrier_fred(cle, erreurs):
    """Prochaines dates de publication (90 jours) des publications US suivies, d'après FRED."""
    q = urllib.parse.urlencode({"api_key": cle, "file_type": "json", "limit": 1000})
    publications = lire_json(f"https://api.stlouisfed.org/fred/releases?{q}")["releases"]
    ids = {p["name"].strip().lower(): p["id"] for p in publications}
    auj, fin = dt.date.today(), dt.date.today() + dt.timedelta(days=90)
    dates = []
    for nom, id_agenda in CALENDRIER_FRED.items():
        rid = ids.get(nom.lower())
        if rid is None:
            erreurs.append(f"Calendrier : publication « {nom} » introuvable sur FRED")
            continue
        try:
            q = urllib.parse.urlencode({"release_id": rid, "api_key": cle, "file_type": "json",
                                        "realtime_start": auj.isoformat(), "realtime_end": "9999-12-31",
                                        "include_release_dates_with_no_data": "true", "sort_order": "asc", "limit": 20})
            for r in lire_json(f"https://api.stlouisfed.org/fred/release/dates?{q}")["release_dates"]:
                d = dt.date.fromisoformat(r["date"])
                if auj <= d <= fin:
                    dates.append({"id": id_agenda, "date": r["date"]})
        except Exception as e:
            erreurs.append(f"Calendrier {nom} : {e}")
    return sorted(dates, key=lambda x: x["date"])


PERIME_JOURS = 75  # au-delà, la série n'est plus alimentée : on ne l'affiche pas


def retirer_perimees(liste, erreurs):
    garde = []
    for x in liste:
        age = (dt.date.today() - dt.date.fromisoformat(x["date"])).days
        if age > PERIME_JOURS and x["id"] != "STEO_BRENT":
            erreurs.append(f"{x['id']} : dernière donnée le {x['date']} ({age} jours), série retirée de la page")
        else:
            garde.append(x)
    return garde


def main():
    cle_fred, cle_eia = os.environ.get("FRED_API_KEY"), os.environ.get("EIA_API_KEY")
    if not cle_fred or not cle_eia:
        sys.exit("Il manque FRED_API_KEY ou EIA_API_KEY dans les variables d'environnement.")
    debut = (dt.date.today() - dt.timedelta(days=HISTO_JOURS + 30)).isoformat()
    series, erreurs = [], []
    for meta in FRED:
        try:
            series.append(resumer(meta, fred(meta["id"], cle_fred, debut), "FRED"))
        except Exception as e:
            erreurs.append(f"{meta['id']} : {e}")
    for meta in EIA:
        try:
            series.append(resumer(meta, eia(meta["id"], cle_eia), "EIA"))
        except Exception as e:
            erreurs.append(f"{meta['id']} : {e}")
    if not series:
        sys.exit("Aucune série récupérée :\n" + "\n".join(erreurs))
    brent = next((s for s in series if s["id"] == "DCOILBRENTEU"), None)
    antic = anticipations(cle_fred, cle_eia, (dt.date.today() - dt.timedelta(days=HISTO_JOURS + 400)).isoformat(), erreurs,
                          (brent["date"], brent["valeur"]) if brent else None)
    series, antic = retirer_perimees(series, erreurs), retirer_perimees(antic, erreurs)
    SORTIE.write_text(json.dumps({
        "maj": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "series": series,
        "anticipations": antic,
        "erreurs": erreurs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    agenda = calendrier_fred(cle_fred, erreurs)
    if agenda:
        SORTIE_AGENDA.write_text(json.dumps({"maj": dt.date.today().isoformat(), "source": "FRED (calendrier des publications)",
                                             "dates": agenda}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(agenda)} dates de publication US écrites dans {SORTIE_AGENDA.relative_to(RACINE)}")
    print(f"{len(series)} séries et {len(antic)} anticipations écrites dans {SORTIE.relative_to(RACINE)}")
    for e in erreurs:
        print("  Attention :", e)


if __name__ == "__main__":
    main()
