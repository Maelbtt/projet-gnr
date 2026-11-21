# Portefeuille Ressources naturelles

Portefeuille actions fictif géré contre le S&P Global Natural Resources Index (Net TR, USD).
Site publié avec GitHub Pages depuis le dossier `docs/`.

## Organisation

```
data_brute/   exports LSEG et fichiers SSGA (ignoré par git, jamais publié)
scripts/      calculs (poids de l'indice, secteurs, données du site)
docs/         le site public
  data/       JSON produits par les scripts
  contenu/    textes en markdown (lettres/, hebdo/, secteurs/)
```

## Chaque vendredi

1. Télécharger le fichier des positions de GNR sur ssga.com → `data_brute/holdings_gnr_AAAAMMJJ.csv`.
2. Dans Excel (LSEG), coller les RIC de `data_brute/ric_gnr.csv` en A2:A93, puis en D1 :
   `=RDP.Data(A2:A93;"TR.PriceClose;TR.PriceClose.date;TR.PriceClose.currency";"SDate=AAAA-MM-JJ Curn=USD RH=IN CH=Fd")`
   → enregistrer en CSV dans `data_brute/cours_usd_AAAAMMJJ.csv`.
3. Lancer :
   ```
   python scripts/poids_indice.py data_brute/holdings_gnr_AAAAMMJJ.csv data_brute/ric_gnr.csv data_brute/cours_usd_AAAAMMJJ.csv data_brute/poids_indice_AAAAMMJJ.csv
   python scripts/secteurs.py data_brute/poids_indice_AAAAMMJJ.csv data_brute/indice_secteurs_AAAAMMJJ.csv
   python scripts/build_site_data.py data_brute/indice_secteurs_AAAAMMJJ.csv AAAA-MM-JJ
   ```
4. Écrire le texte de la semaine dans `docs/contenu/hebdo/AAAA-MM-JJ-semaine-NN.md`
   (puis relancer `build_site_data.py` pour qu'il apparaisse dans la liste).
5. Publier : `git add . && git commit -m "Semaine du JJ/MM" && git push`

## Construire le portefeuille (optimiseur)

1. **Cours quotidiens sur trois ans** (pour la covariance et le risque), dans Excel avec LSEG :
   `=RDP.Data(A2:A93;"TR.PriceClose.date;TR.PriceClose";"SDate=2023-11-20 EDate=2026-11-20 Frq=D Curn=USD RH=IN CH=Fd")`
   → enregistrer en CSV (séparateur `;`) dans `data_brute/cours_quotidiens_AAAAMMJJ.csv`.
   Des cours hors dividendes suffisent pour estimer les risques. Le script lit le RIC dans la colonne remplie
   par LSEG (« Updated at… »), pas dans la colonne collée à la main.
2. **Scores** : remplir la colonne `score` de `data_brute/scores.csv`, avec un entier de -2 à +2.
   - Case vide = valeur non détenue (0 %).
   - 0 = valeur détenue, sans avis. Les scores sont standardisés : si tu notes surtout positivement,
     un 0 devient « sous la moyenne de tes convictions » et a de bonnes chances de tomber à 0 %.
   - Les valeurs marquées « oui » (plus de 3 % de l'indice) doivent obligatoirement être notées.
   - Pour détenir 35 à 45 titres, il faut noter environ 45 à 55 valeurs : les scores négatifs finissent souvent à 0 %.
3. Lancer :
   ```
   cd scripts
   python optimiseur.py ../data_brute/indice_secteurs_AAAAMMJJ.csv ../data_brute/cours_quotidiens_AAAAMMJJ.csv ../data_brute/scores.csv ../data_brute/portefeuille_AAAAMMJJ.csv
   ```
   Par défaut, la covariance est estimée sur des rendements **hebdomadaires sur 3 ans** : les places mondiales ne ferment pas
   à la même heure, et les rendements quotidiens sous-estiment les corrélations entre l'Asie et les États-Unis
   (0,06 en quotidien contre 0,17 en hebdomadaire au 20/11/2026). Option : ajouter `quotidien 2025-11-20` en fin de commande.
   Les valeurs sans historique suffisant (moins d'un an en hebdomadaire) restent à leur poids d'indice.
   Le script affiche le risque ex ante (écart de suivi, ratio d'information attendu, bêta, active share,
   contribution de chaque secteur à l'écart de suivi) et la liste des dépassements de règles, vide si tout est respecté.

Méthode : alpha = IC (0,05) × volatilité résiduelle × score standardisé (moyenne 0, écart type 1 sur les valeurs notées) ; maximisation de alpha − λ × écart de suivi²
sous les règles de gestion ; λ ajusté pour viser 5 % d'écart de suivi (ou 90 % du maximum atteignable si 5 % est hors de portée) ;
covariance estimée sur un an de rendements quotidiens, rétrécie selon Ledoit-Wolf. Paramètres modifiables en tête de `optimiseur.py`.

Dépendances : `pip install pandas numpy scipy`

Note : la colonne de poids s'appelle encore `poids_3110` dans les scripts ; à renommer quand on passera au rebalancement hebdomadaire.

## Voir le site en local

```
cd docs
py -3.13 -m http.server 8000
```
puis ouvrir http://localhost:8000. Ouvrir `index.html` en double-cliquant ne marche pas : le navigateur bloque la lecture des JSON.

## Mise en ligne (une seule fois)

1. Créer un dépôt public sur GitHub et y pousser ce dossier.
2. Settings → Pages → Source : *Deploy from a branch*, branche `main`, dossier `/docs`.
3. Le site est à l'adresse `https://<pseudo>.github.io/<nom-du-depot>/`.

## Valorisation hebdomadaire (run_hebdo.py)

**Lancement, une seule fois** (vendredi 27/11/2026 après la clôture) :
```
py -3.13 scripts\run_hebdo.py lancer data_brute\portefeuille_20261127.csv data_brute\cours_20261127.csv data_brute\indice_secteurs_20261031.csv 2026-11-27
```
- `portefeuille_20261127.csv` : la sortie de `optimiseur.py`.
- `cours_...csv` : export LSEG des cours de clôture quotidiens en USD des 91 valeurs **et de `.SPGNRUN`**
  (même formule que pour l'optimiseur, avec `Curn=USD`).

**Chaque vendredi soir** :
```
py -3.13 scripts\run_hebdo.py semaine data_brute\cours_AAAAMMJJ.csv data_brute\indice_secteurs_20261031.csv dividendes=data_brute\dividendes_AAAAMMJJ.csv poids=data_brute\portefeuille_AAAAMMJJ.csv
```
- `dividendes=` (facultatif) : dividendes détachés dans la semaine, en USD par action :
  `=RDP.Data(RICs;"TR.DivExDate;TR.DivUnadjustedGross(Curn=USD);TR.DivCurr(Curn=USD)";"SDate=... EDate=... RH=IN CH=Fd")`
  (vérifier que la colonne devise affiche bien USD).
- `poids=` (facultatif) : nouveaux poids de l'optimiseur ; sans lui, pas de rééquilibrage cette semaine.

Règles : capital fictif 10 M$, dividendes nets de 15 % réinvestis au rééquilibrage suivant, frais de 10 pb par
transaction, exécution à la clôture du vendredi. L'état du portefeuille est dans `portefeuille/` (non publié :
il contient le niveau de l'indice LSEG) : **le sauvegarder** (copie sur un cloud). Le site lit
`docs/data/performance.json`, qui ne contient que des résultats (base 100, poids, contributions).

## Lettre mensuelle

Modèle : `modeles/lettre-mensuelle.md` (mise en page bordeaux : couverture, l'essentiel, chiffres du mois, trois encadrés
marchés, tableau des convictions, commentaire de gestion, focus, ESG, mois prochain, mentions).
1. Copier le modèle dans `docs/contenu/lettres/AAAA-MM-lettre-NN.md` et remplacer les crochets.
2. Ajouter la lettre en tête de la liste `lettres` de `docs/contenu/index.json`.
3. Commit, Push. L'Action « PDF des lettres » génère le PDF A4 de chaque lettre (même nom, en .pdf) en 2 minutes
   environ ; le bouton « Télécharger en PDF » de la page Lettre mensuelle apparaît alors.

## Indicateurs de marché (FRED + EIA, automatique)

`scripts/marches.py` récupère le Brent, le taux réel 10 ans, le dollar, le taux immobilier 30 ans,
les mises en chantier, le cuivre (FRED) et les stocks de distillats et de brut (EIA), puis écrit
`docs/data/marches.json`, affiché dans le bloc « Marchés » de la Synthèse.

Les clés ne sont **jamais** écrites dans un fichier du dépôt.

Test en local (invite de commandes Windows, depuis la racine du projet) :
```
set FRED_API_KEY=ta_cle_fred
set EIA_API_KEY=ta_cle_eia
py -3.13 scripts\marches.py
```

En ligne : `.github/workflows/marches.yml` lance le script chaque jour ouvré à 11h37 UTC.
Il faut ajouter les deux clés dans GitHub : Settings → Secrets and variables → Actions →
New repository secret, une fois `FRED_API_KEY`, une fois `EIA_API_KEY`.
Onglet Actions → « Indicateurs de marché » → Run workflow pour le lancer à la main.

L'Action enregistre elle-même `docs/data/marches.json` : faire `git pull` avant de travailler.

Portefeuille fictif, à but pédagogique. Données : LSEG Workspace, usage académique.
