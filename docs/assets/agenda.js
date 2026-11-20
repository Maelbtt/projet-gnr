// Page Agenda : lit data/agenda.json, calcule les dates récurrentes (hebdomadaires)
// et affiche la semaine choisie + le calendrier complet filtrable.
const JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const COULEURS = { "Énergie": "var(--series-1)", "Agriculture": "var(--series-2)", "Métaux": "var(--series-3)" };

// Dates manipulées en heure locale, au format AAAA-MM-JJ (pas de décalage de fuseau).
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const lire = (s) => { const [a, m, j] = s.split("-").map(Number); return new Date(a, m - 1, j); };
const plus = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const lundi = (d) => plus(d, -((d.getDay() + 6) % 7));
const court = (d) => `${JOURS[d.getDay()].slice(0, 3)}. ${d.getDate()} ${MOIS[d.getMonth()]}`;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pastille = (secteur) => `<i class="dot" style="background:${COULEURS[secteur] || "var(--text-muted)"}"></i>${esc(secteur)}`;

let donnees, parId, debutSemaine;
const aujourdhui = new Date(); aujourdhui.setHours(0, 0, 0, 0);

// Tous les événements datés entre deux dates (incluses) : dates fixes + règles hebdomadaires.
function evenements(debut, fin) {
  const out = [];
  for (const d of donnees.dates) {
    const jour = lire(d.date);
    if (jour >= debut && jour <= fin) out.push({ ...d, jour, ind: parId[d.id] });
  }
  for (const ind of donnees.indicateurs) {
    if (!ind.regle || ind.regle.type !== "hebdo") continue;
    for (let j = new Date(debut); j <= fin; j = plus(j, 1)) {
      if (j.getDay() !== ind.regle.jour) continue;
      let jour = j;
      const dec = (ind.decalages || []).find((x) => x.de === iso(j));
      if (dec) jour = lire(dec.a);
      if (jour >= debut && jour <= fin) out.push({ id: ind.id, jour, heure: ind.regle.heure, ind, note: dec ? "décalé (jour férié US)" : "" });
    }
  }
  return out.sort((a, b) => a.jour - b.jour || String(a.heure || "").localeCompare(String(b.heure || "")));
}

// Une publication du jour dont l'heure est passée ne compte plus comme « prochaine ».
const passee = (e) => {
  if (iso(e.jour) !== iso(aujourdhui) || !/^\d{1,2}:\d{2}$/.test(e.heure || "")) return false;
  const [h, m] = e.heure.split(":").map(Number), n = new Date();
  return n.getHours() * 60 + n.getMinutes() > h * 60 + m;
};
function prochaineDate(ind) {
  if (ind.regle && ind.regle.type === "hebdo") {
    const e = evenements(aujourdhui, plus(aujourdhui, 13)).find((x) => x.id === ind.id && !passee(x));
    if (e) return e.jour;
  }
  const datee = donnees.dates.filter((d) => d.id === ind.id && lire(d.date) >= aujourdhui).sort((a, b) => a.date.localeCompare(b.date))[0];
  return datee ? lire(datee.date) : null;
}

// Pastilles d'avis lues dans data/positionnement.json (un seul endroit à modifier quand un avis change)
let AVIS = {};
const COURT_SS = { "Pétrolières intégrées": "Intégrées", "Exploration-production": "E&P", "Services pétroliers": "Services",
  "Mines diversifiées et fer": "Mines diversifiées", "Papier, bois et forêts": "Bois", "Négoce et transformation": "Négoce",
  "Semences et phyto": "Phytos" };
const TAGS = { 1: ["p", "+", "surpondérer"], 0: ["z", "=", "neutre"], "-1": ["m", "−", "sous-pondérer"] };
function avisLies(ind) {
  return (ind.sous_secteurs || []).map((nom) => {
    const a = AVIS[nom];
    if (a === undefined) return "";
    const [c, t, mot] = TAGS[a];
    return `<span class="avis-lie"><span class="tag ${c}" title="${esc(nom)} : ${mot}">${t}</span>${esc(COURT_SS[nom] || nom)}</span>`;
  }).join("");
}

function prochaine(ind) {
  if (ind.regle && ind.regle.type === "hebdo") {
    const e = evenements(aujourdhui, plus(aujourdhui, 13)).find((x) => x.id === ind.id && !passee(x));
    if (e) return court(e.jour);
  }
  const datee = donnees.dates.filter((d) => d.id === ind.id && lire(d.date) >= aujourdhui).sort((a, b) => a.date.localeCompare(b.date))[0];
  if (datee) return court(lire(datee.date));
  if (ind.approx) return ind.approx;
  if (ind.frequence === "Quotidien") return "chaque jour";
  if (ind.frequence === "Continu") return "en continu";
  return "à confirmer";
}

function afficherSemaine() {
  const fin = plus(debutSemaine, 6);
  document.getElementById("titre-semaine").textContent =
    `Semaine du ${debutSemaine.getDate()} ${MOIS[debutSemaine.getMonth()]} au ${fin.getDate()} ${MOIS[fin.getMonth()]} ${fin.getFullYear()}`;
  const evs = evenements(debutSemaine, fin);
  const bloc = document.getElementById("semaine");
  if (!evs.length) { bloc.innerHTML = '<p class="placeholder">Aucune publication datée cette semaine.</p>'; return; }
  const parJour = {};
  evs.forEach((e) => (parJour[iso(e.jour)] ||= []).push(e));
  bloc.innerHTML = Object.entries(parJour).map(([j, liste]) => `
    <div class="jour${j === iso(aujourdhui) ? " aujourdhui" : ""}">
      <h3>${court(lire(j))}</h3>
      <ul>${liste.map((e) => `
        <li><span class="heure">${esc(e.heure || "")}</span>
          <span><b>${esc(e.ind.nom)}</b>${e.note ? ` <span class="muted">· ${esc(e.note)}</span>` : ""}
          <span class="secteur">${pastille(e.ind.secteur)}</span>
          <span class="pourquoi">${avisLies(e.ind)}${esc(e.ind.pourquoi)}</span></span></li>`).join("")}
      </ul>
    </div>`).join("");
}

function texteSemaine() {
  const fin = plus(debutSemaine, 6);
  const lignes = [`Agenda ressources naturelles : semaine du ${debutSemaine.getDate()} ${MOIS[debutSemaine.getMonth()]}`, ""];
  let jourPrec = "";
  for (const e of evenements(debutSemaine, fin)) {
    const j = court(e.jour);
    if (j !== jourPrec) { lignes.push("", j.charAt(0).toUpperCase() + j.slice(1)); jourPrec = j; }
    lignes.push(`- ${e.heure ? e.heure + " " : ""}${e.ind.nom}${e.note ? " (" + e.note + ")" : ""} : ${e.ind.pourquoi}`);
  }
  return lignes.join("\n").replace(/\n{3,}/g, "\n\n");
}

function afficherTable() {
  const s = document.getElementById("f-secteur").value;
  const f = document.getElementById("f-freq").value;
  const lignes = donnees.indicateurs
    .filter((i) => !["Quotidien", "Continu"].includes(i.frequence))
    .filter((i) => (!s || i.secteur === s) && (!f || i.frequence === f))
    .map((i) => ({ i, d: prochaineDate(i) }))
    .sort((x, y) => (x.d && y.d ? x.d - y.d : x.d ? -1 : y.d ? 1 : x.i.nom.localeCompare(y.i.nom)))
    .map((x) => x.i);
  document.getElementById("table-agenda").innerHTML = lignes.map((i) => `
    <tr>
      <td><b>${esc(i.nom)}</b></td>
      <td class="nowrap">${pastille(i.secteur)}</td>
      <td>${esc(i.frequence)}</td>
      <td class="nowrap">${esc(prochaine(i))}</td>
      <td>${i.lien ? `<a href="${esc(i.lien)}" target="_blank" rel="noopener">${esc(i.source)}</a>` : esc(i.source)}${i.ric ? `<br><code>${esc(i.ric)}</code>` : ""}</td>
      <td>${avisLies(i)}<span class="pourquoi-t">${esc(i.pourquoi)}</span></td>
    </tr>`).join("") || '<tr><td colspan="6" class="muted">Aucun indicateur pour ce filtre.</td></tr>';
}

function remplirFiltre(id, valeurs) {
  const sel = document.getElementById(id);
  [...new Set(valeurs)].sort().forEach((v) => sel.insertAdjacentHTML("beforeend", `<option>${esc(v)}</option>`));
  sel.addEventListener("change", afficherTable);
}

Promise.all([window.chargerAgenda(), fetch("data/positionnement.json").then((r) => r.json()).catch(() => ({}))])
  .then(([d, pos]) => {
    AVIS = pos.avis || {};
    donnees = d;
    parId = Object.fromEntries(d.indicateurs.map((i) => [i.id, i]));
    // Du vendredi au dimanche, on montre la semaine suivante (celle du post du lundi).
    const base = [0, 5, 6].includes(aujourdhui.getDay()) ? plus(lundi(aujourdhui), 7) : lundi(aujourdhui);
    debutSemaine = base;
    document.getElementById("note-agenda").textContent = `${d.note} Mis à jour le ${court(lire(d.maj))} ${lire(d.maj).getFullYear()}.`;
    const suivis = d.indicateurs.filter((i) => ["Quotidien", "Continu"].includes(i.frequence)).map((i) => i.nom);
    document.getElementById("quotidien").textContent = "À suivre en continu : " + suivis.join(" · ") + ".";
    document.getElementById("prec").onclick = () => { debutSemaine = plus(debutSemaine, -7); afficherSemaine(); };
    document.getElementById("suiv").onclick = () => { debutSemaine = plus(debutSemaine, 7); afficherSemaine(); };
    document.getElementById("auj").onclick = () => { debutSemaine = base; afficherSemaine(); };
    document.getElementById("copier").onclick = (ev) => {
      const t = texteSemaine();
      (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(
        () => { ev.target.textContent = "Copié"; setTimeout(() => (ev.target.textContent = "Copier le texte"), 1500); },
        () => window.prompt("Copie ce texte :", t));
    };
    remplirFiltre("f-secteur", d.indicateurs.map((i) => i.secteur));
    remplirFiltre("f-freq", d.indicateurs.map((i) => i.frequence).filter((x) => !["Quotidien", "Continu"].includes(x)));
    afficherSemaine();
    afficherTable();
  })
  .catch(() => {
    document.getElementById("semaine").innerHTML =
      '<p class="placeholder">Impossible de lire data/agenda.json. Lance le site avec le serveur local (py -3.13 -m http.server 8000 dans docs).</p>';
  });
