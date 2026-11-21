// Pages Lettres / Hebdo / Secteurs : liste les .md de la rubrique et affiche celui choisi.
// La rubrique est donnée par <body data-rubrique="lettres|hebdo">.
const rubrique = document.body.dataset.rubrique;
const liste = document.getElementById("liste");
const article = document.getElementById("article");

function afficher(item) {
  fetch(item.fichier)
    .then((r) => r.text())
    .then((md) => {
      article.innerHTML = marked.parse(md);
      liste.querySelectorAll("a").forEach((a) => a.setAttribute("aria-current", a.dataset.f === item.fichier));
      history.replaceState(null, "", "#" + item.fichier.split("/").pop().replace(".md", ""));
      // Lettres : bouton de téléchargement si le PDF généré par l'Action existe
      const lien = document.getElementById("lien-pdf");
      if (lien) {
        const pdf = item.fichier.replace(/\.md$/, ".pdf");
        lien.hidden = true;
        fetch(pdf, { method: "HEAD" }).then((r) => { if (r.ok) { lien.href = pdf; lien.hidden = false; } }).catch(() => {});
      }
      const copier = document.getElementById("copier-linkedin");
      if (copier) copier.hidden = false;
    });
}

fetch("contenu/index.json")
  .then((r) => r.json())
  .then((idx) => {
    const items = idx[rubrique] || [];
    if (!items.length) { article.innerHTML = '<p class="placeholder">' + (rubrique === "lettres" ? "La première lettre paraîtra début décembre." : rubrique === "hebdo" ? "La première lettre hebdo paraîtra le lundi 23 novembre." : "Rien de publié pour l\'instant.") + '</p>'; return; }
    liste.innerHTML = items.map((it) => `<a href="#" data-f="${it.fichier}">${it.titre}</a>`).join("");
    liste.querySelectorAll("a").forEach((a, i) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); afficher(items[i]); }));
    const ancre = location.hash.slice(1);
    afficher(items.find((it) => it.fichier.endsWith(ancre + ".md")) || items[0]);
  });

// Hebdo : version texte pour un post LinkedIn (titres en capitales, une ligne par rendez-vous)
function texteLinkedIn() {
  const lignes = ["Bonsoir,", ""];
  const propre = (t) => t.replace(/\s+/g, " ").trim();
  article.querySelectorAll(".lettre-couverture h1, h2, h3, p, table, .mentions").forEach((el) => {
    if (el.closest(".chiffres-mois")) return;
    if (el.matches(".lettre-couverture h1")) { lignes.push(propre(el.textContent), ""); return; }
    if (el.closest(".lettre-couverture")) return;
    if (el.closest(".mentions") && !el.matches(".mentions")) return;
    if (el.tagName === "H2" || el.tagName === "H3") { lignes.push(propre(el.textContent).toUpperCase(), ""); return; }
    if (el.tagName === "TABLE") {
      const entetes = [...el.querySelectorAll("th")].map((th) => propre(th.textContent));
      el.querySelectorAll("tbody tr").forEach((tr) => {
        const c = [...tr.children].map((td) => propre(td.textContent));
        const val = (nom) => { const i = entetes.indexOf(nom); return i >= 0 && c[i] && c[i] !== "-" ? c[i] : ""; };
        let l = c.slice(0, 3).filter((x) => x && x !== "-").join(" - ");
        const att = val("Attendu"), prec = val("Précédent"), nous = val("Pour nous");
        if (att) l += " : attendu " + att + (prec ? " (précédent " + prec + ")" : "");
        else if (prec) l += " (précédent " + prec + ")";
        if (nous) l += ". " + nous;
        lignes.push(l);
      });
      lignes.push("");
      return;
    }
    if (el.matches(".legende, .source")) return;
    lignes.push(propre(el.textContent), "");
  });
  const i = lignes.findIndex((l) => l.startsWith("Portefeuille fictif"));
  if (i >= 0) lignes.splice(i, 0, "Bonne semaine à tous,", "");
  return lignes.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
const boutonCopier = document.getElementById("copier-linkedin");
if (boutonCopier) boutonCopier.addEventListener("click", () => {
  navigator.clipboard.writeText(texteLinkedIn()).then(() => {
    boutonCopier.textContent = "Texte copié";
    setTimeout(() => { boutonCopier.textContent = "Copier pour LinkedIn"; }, 2000);
  });
});
