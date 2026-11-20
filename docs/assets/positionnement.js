// Synthèse : positionnement (poids de l'indice + avis par sous-secteur), dix premières valeurs (data/positionnement.json + data/indice.json)
// et prochains rendez-vous datés (data/agenda.json).
(() => {
  const fmt = (x) => x.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const TAG = { 1: ["p", "+", "Surpondérer"], 0: ["z", "=", "Neutre"], "-1": ["m", "−", "Sous-pondérer"] };
  const ORDRE = ["Énergie", "Métaux et mines", "Agriculture"];

  Promise.all([fetch("data/positionnement.json").then((r) => r.json()), fetch("data/indice.json").then((r) => r.json())])
    .then(([p, d]) => {
      const poids = Object.fromEntries(d.secteurs.map((s) => [s.nom, s.poids]));
      const nb = document.getElementById("nb"); if (nb) nb.textContent = d.nb_valeurs;
      const date = new Date(d.date).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
      document.querySelectorAll("[data-date]").forEach((e) => (e.textContent = date));
      const these = Object.fromEntries(p.secteurs.map((s) => [s.nom, s.these]));
      const COURT = { "Pétrolières intégrées": "Intégrées", "Exploration-production": "E&P", "Services pétroliers": "Services",
        "Mines diversifiées et fer": "Mines diversifiées", "Streaming métaux précieux": "Streaming", "Papier, bois et forêts": "Papier et bois",
        "Négoce et transformation": "Négoce", "Semences et phyto": "Semences, phyto" };
      const COUL = { "Énergie": "var(--series-1)", "Métaux et mines": "var(--series-3)", "Agriculture": "var(--series-2)" };
      const max = Math.max(...d.sous_secteurs.map((s) => s.poids));
      document.getElementById("positionnement").innerHTML = ORDRE.map((sec) => {
        const lignes = d.sous_secteurs.filter((s) => s.secteur === sec).sort((x, y) => y.poids - x.poids).map((s) => {
          const [c, t, mot] = TAG[p.avis[s.nom] ?? 0];
          return `<li><span class="ss-nom" title="${s.nom}">${COURT[s.nom] || s.nom}</span>
            <span class="ss-barre"><i style="width:${(s.poids / max) * 100}%;background:${COUL[sec]}"></i></span>
            <span class="ss-poids">${fmt(s.poids)} %</span>
            <span class="tag ${c}" title="${mot}">${t}</span></li>`;
        }).join("");
        return `<div class="pos-secteur">
          <h3><i style="background:${COUL[sec]}"></i>${sec}<span>${fmt(poids[sec])} %</span></h3>
          <p>${these[sec] || ""}</p><ul>${lignes}</ul></div>`;
      }).join("");
      const top = document.getElementById("t-top");
      if (top) top.innerHTML = d.top10.map((t) =>
        `<tr><td>${t.nom}</td><td>${t.sous_secteur}</td><td class="num">${fmt(t.poids)} %</td></tr>`).join("");
    })
    .catch(() => { document.getElementById("positionnement").innerHTML = '<p class="placeholder">Impossible de lire data/positionnement.json.</p>'; });

  const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];
  const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  window.chargerAgenda().then((a) => {
    const noms = Object.fromEntries(a.indicateurs.map((i) => [i.id, i.nom]));
    const auj = new Date(); auj.setHours(0, 0, 0, 0);
    const prochains = a.dates
      .map((x) => ({ ...x, j: new Date(...x.date.split("-").map((v, k) => (k === 1 ? v - 1 : +v))) }))
      .filter((x) => x.j >= auj).sort((x, y) => x.j - y.j).slice(0, 5);
    document.getElementById("rdv").innerHTML = prochains.map((x) =>
      `<dt>${JOURS[x.j.getDay()]} ${x.j.getDate()} ${MOIS[x.j.getMonth()]}</dt><dd>${noms[x.id]}${x.note ? " · " + x.note : ""}</dd>`).join("") +
      '<dd style="margin-top:10px"><a href="agenda.html">Tout l\'agenda</a></dd>';
  }).catch(() => {});
})();
