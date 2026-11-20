// Page Synthèse : lit data/indice.json et dessine les graphiques en SVG.
const COULEUR = { "Énergie": "var(--series-1)", "Agriculture": "var(--series-2)", "Métaux et mines": "var(--series-3)" };
const fmt = (x, d = 1) => x.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}, txt) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (txt !== undefined) e.textContent = txt;
  return e;
};

const tip = document.createElement("div");
tip.className = "tooltip";
document.body.appendChild(tip);
function survol(cible, html) {
  cible.addEventListener("mousemove", (ev) => {
    tip.innerHTML = html; tip.style.display = "block";
    tip.style.left = Math.min(ev.clientX + 14, innerWidth - 250) + "px";
    tip.style.top = ev.clientY + 14 + "px";
  });
  cible.addEventListener("mouseleave", () => (tip.style.display = "none"));
}

// Barres horizontales : lignes = [{label, poids, secteur, detail}]
function barres(conteneur, lignes, { max, repere, labelW = 170, auClic } = {}) {
  const H = 26, gap = 8, W = Math.max(conteneur.clientWidth, 320), padR = 56;
  labelW = Math.min(labelW, W * 0.4);
  const h = lignes.length * (H + gap) + (repere ? 22 : 4);
  const svg = el("svg", { viewBox: `0 0 ${W} ${h}`, width: W, height: h, role: "img" });
  const x = (v) => labelW + (v / max) * (W - labelW - padR);
  const y0 = repere ? 18 : 0;

  if (repere) {
    svg.append(
      el("line", { x1: x(repere.v), x2: x(repere.v), y1: 12, y2: h, stroke: "var(--text-muted)", "stroke-dasharray": "3 3", "stroke-width": 1 }),
      el("text", { x: x(repere.v), y: 9, "text-anchor": "middle", "font-size": 11, fill: "var(--text-muted)" }, repere.label)
    );
  }
  lignes.forEach((l, i) => {
    const y = y0 + i * (H + gap);
    const g = el("g");
    g.append(
      el("text", { x: labelW - 10, y: y + H / 2 + 4, "text-anchor": "end", "font-size": 12.5, fill: "var(--text-primary)" }, l.label),
      el("rect", { x: labelW, y: y + 3, width: Math.max(x(l.poids) - labelW, 2), height: H - 6, rx: 4, fill: COULEUR[l.secteur] }),
      el("text", { x: x(l.poids) + 6, y: y + H / 2 + 4, "font-size": 12, fill: "var(--text-secondary)" }, fmt(l.poids) + " %"),
      el("rect", { x: 0, y, width: W, height: H, fill: "transparent" }) // zone de survol plus large que la barre
    );
    survol(g, l.detail);
    if (auClic) {
      g.style.cursor = "pointer";
      g.addEventListener("click", () => auClic(l));
    }
    svg.append(g);
  });
  conteneur.replaceChildren(svg);
}

function legende(conteneur, noms) {
  conteneur.innerHTML = noms.map((n) => `<span><i style="background:${COULEUR[n]}"></i>${n}</span>`).join("");
}

let dessiner = () => {};
const idSous = (secteur, nom) => "ss-" + (secteur + "-" + nom).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-zA-Z0-9]+/g, "-").toLowerCase();

// Liste des valeurs : un bloc par secteur, un sous-secteur dépliable par ligne.
function composition(d) {
  const html = d.secteurs.map((sec) => {
    const sous = d.sous_secteurs.filter((s) => s.secteur === sec.nom);
    return `<div class="bloc-secteur">
      <h3><i style="background:${COULEUR[sec.nom]}"></i>${sec.nom} <span>${fmt(sec.poids)} % · ${sec.n} valeurs</span></h3>
      ${sous.map((s) => `<details id="${idSous(s.secteur, s.nom)}">
        <summary><span class="ss-nom">${s.nom}</span><span class="ss-info">${s.n} valeur${s.n > 1 ? "s" : ""} · ${fmt(s.poids)} %</span></summary>
        <table><thead><tr><th>Valeur</th><th class="num">Poids dans l'indice</th><th class="num">Part du sous-secteur</th></tr></thead><tbody>
        ${s.valeurs.map((v) => `<tr><td>${v.nom}</td><td class="num">${fmt(v.poids, 2)} %</td><td class="num">${fmt(100 * v.poids / s.poids, 0)} %</td></tr>`).join("")}
        </tbody></table></details>`).join("")}
    </div>`;
  }).join("");
  document.getElementById("c-secteurs").innerHTML = html;
}

function ouvrir(secteur, nom) {
  const el = document.getElementById(idSous(secteur, nom));
  if (!el) return;
  el.open = true;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("surligne");
  setTimeout(() => el.classList.remove("surligne"), 1500);
}
addEventListener("resize", () => dessiner());

fetch("data/indice.json")
  .then((r) => r.json())
  .then((d) => {
    const date = new Date(d.date).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
    document.querySelectorAll("[data-date]").forEach((e) => (e.textContent = date));
    const nb = document.getElementById("nb"); if (nb) nb.textContent = d.nb_valeurs;

    const noms = d.secteurs.map((s) => s.nom);
    legende(document.getElementById("l-sous"), noms);
    dessiner = () => {
    barres(document.getElementById("g-secteurs"),
      d.secteurs.map((s) => ({ label: s.nom, poids: s.poids, secteur: s.nom,
        detail: `<b>${s.nom}</b><br>${fmt(s.poids)} % de l'indice<br>${s.n} valeurs` })),
      { max: 45, repere: { v: d.plafond_secteur, label: "plafond 1/3" }, labelW: 130 });

    barres(document.getElementById("g-sous"),
      d.sous_secteurs.map((s) => ({ label: s.nom, poids: s.poids, secteur: s.secteur,
        detail: `<b>${s.nom}</b> (${s.secteur})<br>${fmt(s.poids)} % de l'indice<br>${s.n} valeur${s.n > 1 ? "s" : ""}` })),
      { max: 30, labelW: 190, auClic: (l) => ouvrir(l.secteur, l.label) });
    };
    dessiner();

    document.getElementById("t-top").innerHTML = d.top10.map((t, i) =>
      `<tr><td class="num">${i + 1}</td><td><span class="dot" style="background:${COULEUR[t.secteur]}"></span>${t.nom}</td><td>${t.sous_secteur}</td><td class="num">${fmt(t.poids, 2)}</td></tr>`).join("");

    if (d.sous_secteurs.every((s) => Array.isArray(s.valeurs))) {
      composition(d);
    } else {
      document.getElementById("c-secteurs").innerHTML =
        '<p class="placeholder">Le fichier data/indice.json est une ancienne version : relance build_site_data.py ou remplace-le, puis recharge avec Ctrl+F5.</p>';
    }
  })
  .catch(() => {
    document.querySelector("main").insertAdjacentHTML("afterbegin",
      '<p class="placeholder">Impossible de charger data/indice.json. Ouvre le site via un serveur local (voir README), pas en double-cliquant sur le fichier.</p>');
  });
