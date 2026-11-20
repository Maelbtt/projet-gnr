// Actualités des sociétés (data/actualites.json, écrit chaque matin par l'agent de veille).
// Faits uniquement : résumé d'une ligne, source et lien. Avis du moment lus dans positionnement.json.
(() => {
  const plein = document.getElementById("actualites");
  const court = document.getElementById("actus-synthese");
  if (!plein && !court) return;
  const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  const date = (s) => { const [a, m, j] = s.slice(0, 10).split("-").map(Number); return `${j} ${MOIS[m - 1]}`; };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const TAG = { 1: ["p", "+", "surpondérer"], 0: ["z", "=", "neutre"], "-1": ["m", "−", "sous-pondérer"] };

  Promise.all([
    fetch("data/actualites.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch("data/positionnement.json").then((r) => r.json()).catch(() => ({})),
  ]).then(([d, pos]) => {
    const liste = (d && d.actualites) || [];
    const avis = (pos && pos.avis) || {};
    const tag = (ss) => {
      const a = avis[ss];
      if (a === undefined) return "";
      const [c, t, mot] = TAG[a];
      return `<span class="tag ${c}" title="${esc(ss)} : ${mot}">${t}</span>`;
    };
    const ligne = (x) => `<li class="actu ${x.importance === "forte" ? "forte" : ""}">
        <span class="actu-date">${date(x.date)}</span>
        <span class="actu-corps"><b>${esc(x.societe)}</b>${x.sous_secteur ? ` <span class="actu-ss">${tag(x.sous_secteur)}${esc(x.sous_secteur)}</span>` : ""}
        <span class="actu-titre">${esc(x.titre)}</span>
        ${x.lien ? `<a href="${esc(x.lien)}" target="_blank" rel="noopener">${esc(x.source || "Source")}</a>` : `<span class="muted">${esc(x.source || "")}</span>`}</span></li>`;
    if (plein) {
      plein.innerHTML = liste.length
        ? `<ul class="actus">${liste.map(ligne).join("")}</ul>
           <p class="note">Veille automatique mise à jour le ${esc(String(d.maj).replace("T", " à "))}. Résumés factuels d'une ligne, sans opinion ; lire la source pour le détail.</p>`
        : '<p class="placeholder">Les actualités s\'afficheront après la prochaine veille automatique (chaque jour ouvré vers 7h15).</p>';
    }
    if (court) {
      const fortes = liste.filter((x) => x.importance === "forte").slice(0, 4);
      court.innerHTML = fortes.length
        ? fortes.map((x) => `<dt>${date(x.date)} · ${esc(x.societe)}</dt><dd>${esc(x.titre)}</dd>`).join("") + '<dd style="margin-top:10px"><a href="marches.html#actualites-titre">Toutes les actualités</a></dd>'
        : '<dd class="muted">Pas d\'actualité majeure récente.</dd>';
    }
  });
})();
