// Pages Lettres / Hebdo / Secteurs : liste les .md de la rubrique et affiche celui choisi.
// La rubrique est donnée par <body data-rubrique="lettres|hebdo|secteurs">.
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
    });
}

fetch("contenu/index.json")
  .then((r) => r.json())
  .then((idx) => {
    const items = idx[rubrique] || [];
    if (!items.length) { article.innerHTML = '<p class="placeholder">Rien de publié pour l\'instant.</p>'; return; }
    liste.innerHTML = items.map((it) => `<a href="#" data-f="${it.fichier}">${it.titre}</a>`).join("");
    liste.querySelectorAll("a").forEach((a, i) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); afficher(items[i]); }));
    const ancre = location.hash.slice(1);
    afficher(items.find((it) => it.fichier.endsWith(ancre + ".md")) || items[0]);
  });
