"use strict";
/* Souris : boutons, DPI en lecture, batterie. Les réglages que le cœur déclare NonPris sont grisés. */
(() => {
  const { h, sv } = C;
  const NOMS = ["Clic gauche", "Clic droit", "Molette (clic)", "Latéral 1", "Latéral 2", "Bouton 6 (rôle non confirmé)"];
  const ACTIONS = { left: "Clic gauche", right: "Clic droit", middle: "Clic milieu", forward: "Avancer", back: "Reculer", disabled: "Désactivé" };
  // [x, y, largeur, hauteur] des zones cliquables sur le dessin
  const ZONES = [[45, 20, 55, 85], [120, 20, 55, 85], [100, 30, 20, 40], [10, 125, 22, 30], [10, 165, 22, 30], [100, 80, 20, 22]];
  let choisi = 0;

  C.sections.push({
    id: "souris", titre: "Souris", rendre: m => {
      const s = C.draft.souris, b = C.base.souris;
      if (!s) return m.append(h("div", { class: "alerte" }, C.erreurs.souris || C.etat.peripheriques.souris.message));
      const dessin = sv("svg", { class: "souris", viewBox: "0 0 220 300", role: "group", "aria-label": "Souris Retro R8" },
        sv("path", { class: "corps", d: "M30 110 Q30 10 110 10 Q190 10 190 110 L190 220 Q190 290 110 290 Q30 290 30 220 Z" }),
        ZONES.map(([x, y, w, hh], n) => sv("rect", {
          class: "bt" + (n === choisi ? " sel" : ""), x, y, width: w, height: hh, rx: 8, tabindex: 0, role: "button", "aria-label": NOMS[n],
          onclick: () => { choisi = n; C.afficher(); }, onkeydown: e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choisi = n; C.afficher(); } },
        })),
        ZONES.map(([x, y, w, hh], n) => sv("text", { x: x + w / 2, y: y + hh / 2 + 4 }, String(n))));
      const ligne = n => {
        const v = s.boutons[String(n)], connu = v in ACTIONS;
        const sel = h("select", { "aria-label": NOMS[n], onchange: e => { s.boutons[String(n)] = e.target.value; C.rafraichir(); } },
          Object.entries(ACTIONS).map(([k, l]) => h("option", { value: k, selected: k === v }, l)), connu ? null : h("option", { value: v, selected: true }, v));
        const code = h("input", { type: "number", min: 0, max: 65535, placeholder: "code", style: "width:6em", "aria-label": `Code brut du bouton ${n}`,
          onchange: e => { if (e.target.value !== "") { s.boutons[String(n)] = "code:" + e.target.value; C.rafraichir(); } } });
        return h("tr", { class: n === choisi ? "sel" : "" }, h("td", {}, `${n} · ${NOMS[n]}`), h("td", {}, sel), h("td", {}, code),
          h("td", {}, b.boutons[String(n)] !== v ? h("span", { class: "doux" }, "brouillon") : ""));
      };
      const bat = s.batterie;
      m.append(h("div", { class: "souris-zone" }, dessin, h("div", { style: "flex:1;min-width:300px" },
        h("h3", {}, "Boutons"), h("table", {}, [0, 1, 2, 3, 4, 5].map(ligne)),
        h("h3", {}, "Paliers DPI (lecture seule)"),
        h("div", {}, s.dpi.stages.map((d, i) => h("span", { class: "puce" + (i === s.dpi.index ? " cour" : ""), "aria-current": i === s.dpi.index ? "true" : null }, d))),
        h("p", { class: "doux" }, `Palier courant : ${s.dpi.current} DPI.`),
        h("h3", {}, "Batterie"),
        bat.known ? h("p", {}, h("span", { class: "jauge" }, h("span", { style: `width:${bat.percent}%` })), ` ${bat.percent} %`, bat.charging ? " (en charge)" : "")
          : h("p", { class: "doux" }, "Inconnue : la souris ne renvoie pas de valeur."),
        h("h3", {}, "Autres réglages"),
        C.etat.non_pris.map(n => h("div", { class: "ligne grise" }, h("label", {}, n, " ", h("input", { disabled: true, "aria-label": n, style: "width:6em" })),
          h("span", {}, "protocole pas encore connu"))))));
    },
  });
})();
