// Synthèse : performance du portefeuille contre l'indice (data/performance.json, écrit par run_hebdo.py).
(() => {
  const zone = document.getElementById("performance");
  if (!zone) return;
  const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  const lire = (s) => { const [a, m, j] = s.split("-").map(Number); return new Date(a, m - 1, j); };
  const court = (s) => { const d = lire(s); return `${d.getDate()} ${MOIS[d.getMonth()]}`; };
  const nf = (x, d = 2) => x.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x) => (x > 0 ? "+" : x < 0 ? "−" : "") + nf(Math.abs(100 * x)) + " %";

  function graphique(h) {
    const W = zone.clientWidth || 760, H = 260, g = 44, d = 12, haut = 12, bas = 28;
    const vals = h.flatMap((p) => [p[1], p[2]]);
    let min = Math.min(...vals), max = Math.max(...vals);
    const marge = Math.max((max - min) * 0.15, 0.5); min -= marge; max += marge;
    const x = (i) => g + (i / Math.max(h.length - 1, 1)) * (W - g - d);
    const y = (v) => haut + (1 - (v - min) / (max - min)) * (H - haut - bas);
    const ligne = (k) => h.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[k]).toFixed(1)}`).join("");
    const pas = (max - min) / 4;
    const graduations = [0, 1, 2, 3, 4].map((k) => min + k * pas);
    const nbx = Math.min(6, h.length);
    const ix = [...new Set(Array.from({ length: nbx }, (_, k) => Math.round((k * (h.length - 1)) / Math.max(nbx - 1, 1))))];
    return `<svg width="${W}" height="${H}" role="img" aria-label="Portefeuille et indice en base 100 depuis le lancement">
      ${graduations.map((v) => `<line x1="${g}" x2="${W - d}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/>
        <text x="${g - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--text-muted)">${nf(v, 1)}</text>`).join("")}
      ${ix.map((i, k) => `<text x="${x(i)}" y="${H - 8}" text-anchor="${k === 0 ? "start" : k === ix.length - 1 ? "end" : "middle"}" font-size="11" fill="var(--text-muted)">${court(h[i][0])}</text>`).join("")}
      <path d="${ligne(2)}" fill="none" stroke="#A99DA6" stroke-width="2"/>
      <path d="${ligne(1)}" fill="none" stroke="var(--bordeaux)" stroke-width="2"/>
      <line id="perf-curseur" y1="${haut}" y2="${H - bas}" stroke="var(--text-muted)" stroke-dasharray="3 3" visibility="hidden"/>
      <rect x="${g}" y="0" width="${W - g - d}" height="${H}" fill="transparent" id="perf-zone"/>
    </svg>`;
  }

  fetch("data/performance.json")
    .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
    .then((p) => {
      const h = p.historique;
      const lp = p.performances.lancement;
      // bandeau
      const vl = document.getElementById("b-vl"), rel = document.getElementById("b-rel");
      if (vl) vl.textContent = nf(p.vl);
      if (rel) rel.textContent = pct(lp.ecart);
      const lignes = [["Semaine", p.performances.semaine], ["Un mois", p.performances.mois], ["Depuis le lancement", lp]];
      zone.innerHTML = `
        <div class="legend"><span><i style="background:var(--bordeaux)"></i>Portefeuille</span><span><i style="background:#A99DA6"></i>Indice (Net TR, USD)</span></div>
        <div id="perf-graphe"></div>
        <table class="perf-table"><thead><tr><th></th><th class="num">Portefeuille</th><th class="num">Indice</th><th class="num">Écart</th></tr></thead><tbody>
        ${lignes.map(([nom, x]) => `<tr><td>${nom}<small>depuis le ${court(x.depuis)}</small></td><td class="num">${pct(x.portefeuille)}</td><td class="num">${pct(x.indice)}</td><td class="num"><b>${pct(x.ecart)}</b></td></tr>`).join("")}
        </tbody></table>
        <p class="note">Valeurs au ${court(p.maj)} ; base 100 au ${court(p.lancement)}. ${p.methode}</p>`;
      const box = document.getElementById("perf-graphe");
      const dessiner = () => {
        box.innerHTML = graphique(h);
        const svg = box.querySelector("svg"), zoneSvg = box.querySelector("#perf-zone"), curseur = box.querySelector("#perf-curseur");
        let tip = document.querySelector(".tooltip");
        if (!tip) { tip = document.createElement("div"); tip.className = "tooltip"; document.body.appendChild(tip); }
        zoneSvg.addEventListener("mousemove", (e) => {
          const r = svg.getBoundingClientRect(), W = r.width;
          const i = Math.max(0, Math.min(h.length - 1, Math.round(((e.clientX - r.left - 44) / (W - 56)) * (h.length - 1))));
          const xi = 44 + (i / Math.max(h.length - 1, 1)) * (W - 56);
          curseur.setAttribute("x1", xi); curseur.setAttribute("x2", xi); curseur.setAttribute("visibility", "visible");
          tip.innerHTML = `<b>${court(h[i][0])}</b><br>Portefeuille ${nf(h[i][1])}<br>Indice ${nf(h[i][2])}`;
          tip.style.display = "block"; tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 14 + "px";
        });
        zoneSvg.addEventListener("mouseleave", () => { tip.style.display = "none"; curseur.setAttribute("visibility", "hidden"); });
      };
      dessiner();
      window.addEventListener("resize", dessiner);
    })
    .catch(() => {
      zone.innerHTML = '<div class="placeholder">Base 100 au 27/11/2026. La courbe apparaîtra après le premier rebalancement.</div>';
    });
})();
