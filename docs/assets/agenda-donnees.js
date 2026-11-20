// Agenda : fusionne la liste manuelle (data/agenda.json) et les dates US récupérées
// automatiquement sur FRED (data/agenda_auto.json). Pour un indicateur présent dans
// les deux, les dates automatiques remplacent les dates saisies à la main.
window.chargerAgenda = function () {
  const manuel = fetch("data/agenda.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const auto = fetch("data/agenda_auto.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
  return Promise.all([manuel, auto]).then(([m, a]) => {
    if (!a || !a.dates || !a.dates.length) return m;
    const heures = Object.fromEntries(m.indicateurs.map((i) => [i.id, i.heure]));
    const auto_ids = new Set(a.dates.map((x) => x.id).filter((id) => heures[id] !== undefined || m.indicateurs.some((i) => i.id === id)));
    const dates = m.dates.filter((x) => !auto_ids.has(x.id))
      .concat(a.dates.filter((x) => auto_ids.has(x.id)).map((x) => ({ ...x, heure: x.heure || heures[x.id], auto: true })));
    return { ...m, dates };
  });
};
