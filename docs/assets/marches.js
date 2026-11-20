// Synthèse : bloc « Marchés » lu dans data/marches.json (mis à jour par l'Action GitHub).
(() => {
  const bloc = document.getElementById("marches");
  if (!bloc) return;
  const nf = (x, dec) => x.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  const date = (s) => { const [a, m, j] = s.split("-").map(Number); return `${j} ${MOIS[m - 1]}`; };

  function courbe(points) {
    if (points.length < 2) return "";
    const W = 120, H = 30, v = points.map((p) => p[1]);
    const min = Math.min(...v), max = Math.max(...v), et = max - min || 1;
    const xy = v.map((y, i) => [(i / (v.length - 1)) * (W - 4) + 2, H - 3 - ((y - min) / et) * (H - 6)]);
    const d = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const [xf, yf] = xy[xy.length - 1];
    return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Évolution sur un an, de ${nf(v[0], 1)} à ${nf(v[v.length - 1], 1)}">
      <polyline points="${d}" fill="none" stroke="var(--text-secondary)" stroke-width="1.5" stroke-linejoin="round"/>
      <circle cx="${xf}" cy="${yf}" r="2.5" fill="var(--bordeaux)"/></svg>`;
  }

  function variation(s) {
    if (!s.reference) return "—";
    const dv = s.valeur - s.reference.valeur;
    const signe = dv > 0 ? "+" : dv < 0 ? "−" : "";
    const txt = s.variation_en_points
      ? `${signe}${nf(Math.abs(dv), 2)} pt`
      : `${signe}${nf(Math.abs((100 * dv) / s.reference.valeur), 1)} %`;
    return `${txt}<small>depuis le ${date(s.reference.date)}</small>`;
  }

  // Avis du moment : lus dans data/positionnement.json (un seul endroit à modifier).
  const COURT = { "Pétrolières intégrées": "Intégrées", "Exploration-production": "E&P", "Papier, bois et forêts": "Bois", "Services pétroliers": "Services" };
  const TAG = { 1: ["p", "+", "surpondérer"], 0: ["z", "=", "neutre"], "-1": ["m", "−", "sous-pondérer"] };
  function lienAvis(s, pos, lecture) {
    const ind = pos && pos.indicateurs && pos.indicateurs[s.id];
    if (!ind) return lecture ? `<small>${lecture}</small>` : s.lien_avis || "";
    const tags = ind.sous_secteurs.map((nom) => {
      const a = pos.avis[nom];
      if (a === undefined) return `<span class="avis-lie">${COURT[nom] || nom}</span>`;
      const [c, t, mot] = TAG[a];
      return `<span class="avis-lie"><span class="tag ${c}" title="${nom} : ${mot}">${t}</span>${COURT[nom] || nom}</span>`;
    }).join("");
    return `${tags}<small>${lecture || ind.explication}</small>`;
  }

  Promise.all([
    fetch("data/marches.json").then((r) => { if (!r.ok) throw new Error(); return r.json(); }),
    fetch("data/positionnement.json").then((r) => r.json()).catch(() => null),
  ])
    .then(([d, pos]) => {
      if (!d.series || !d.series.length) {
        bloc.innerHTML = '<p class="placeholder">Les indicateurs s\'afficheront après la première mise à jour automatique.</p>';
        return;
      }
      document.getElementById("marches-maj").textContent = `Mis à jour automatiquement le ${d.maj}. Sources : FRED (Réserve fédérale de Saint-Louis), EIA et CFTC.`;
      const ligne = (s, lecture) => `<tr>
          <td><b>${s.nom}</b><small>${s.unite} · ${date(s.date)}</small></td>
          <td class="num">${nf(s.valeur, s.decimales)}${s.moyenne_5_ans ? `<small>moy. 5 ans ${nf(s.moyenne_5_ans, s.decimales)}</small>` : ""}</td>
          <td class="num">${variation(s)}</td>
          <td>${courbe(s.historique)}</td>
          <td class="lien-avis">${lecture !== undefined ? `<span class="lecture">${lecture}</span>` : lienAvis(s, pos)}</td></tr>`;
      const table = (titre1, lignes, titre5) => `<div class="table-defile"><table class="marches"><thead><tr>
        <th>${titre1}</th><th class="num">Dernier</th><th class="num">Variation</th><th>Sur un an</th><th>${titre5}</th></tr></thead><tbody>
        ${lignes}</tbody></table></div>`;
      bloc.innerHTML = table("Indicateur", d.series.map((s) => ligne(s)).join(""), "Avis concerné");
      const zone = document.getElementById("anticipations");
      if (zone) {
        zone.innerHTML = d.anticipations && d.anticipations.length
          ? table("Anticipation", d.anticipations.map((s) => ligne(s, s.lecture || "")).join(""), "Ce que le marché anticipe")
          : '<p class="placeholder">Les anticipations s\'afficheront après la prochaine mise à jour automatique.</p>';
      }
    })
    .catch(() => { bloc.innerHTML = '<p class="placeholder">Impossible de lire data/marches.json.</p>'; });
})();
