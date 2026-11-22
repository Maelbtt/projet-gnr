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

