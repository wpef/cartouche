"use strict";
/* Clavier : dessin, choix d'une cible, profil, macros. Les identifiants de touche sont les noms du cœur. */
(() => {
  const { h } = C;
  const ligne = (y, x0, ids, w = 1) => ids.map((id, i) => [id, x0 + i * w, y, w, 1]);
  const lettres = s => s.split("");
  const TOUCHES = [
    ["esc", 0, 0, 1, 1], ...ligne(0, 2, ["f1", "f2", "f3", "f4"]), ...ligne(0, 6.5, ["f5", "f6", "f7", "f8"]), ...ligne(0, 11, ["f9", "f10", "f11", "f12"]),
    ...ligne(0, 15.25, ["printscreen", "scrolllock", "pause"]),
    ...ligne(1.5, 0, ["grave", ...lettres("1234567890"), "minus", "equal"]), ["backspace", 13, 1.5, 2, 1], ...ligne(1.5, 15.25, ["insert", "home", "pageup"]),
    ["tab", 0, 2.5, 1.5, 1], ...ligne(2.5, 1.5, [...lettres("qwertyuiop"), "lbracket", "rbracket"]), ["backslash", 13.5, 2.5, 1.5, 1], ...ligne(2.5, 15.25, ["delete", "end", "pagedown"]),
    ["capslock", 0, 3.5, 1.75, 1], ...ligne(3.5, 1.75, [...lettres("asdfghjkl"), "semicolon", "apostrophe"]), ["enter", 12.75, 3.5, 2.25, 1],
    ["lshift", 0, 4.5, 2.25, 1], ...ligne(4.5, 2.25, [...lettres("zxcvbnm"), "comma", "dot", "slash"]), ["rshift", 12.25, 4.5, 2.75, 1], ["up", 16.25, 4.5, 1, 1],
    ["lctrl", 0, 5.5, 1.25, 1], ["lwin", 1.25, 5.5, 1.25, 1], ["lalt", 2.5, 5.5, 1.25, 1], ["space", 3.75, 5.5, 6.25, 1],
    ["ralt", 10, 5.5, 1.5, 1], ["rwin", 11.5, 5.5, 1.5, 1], ["rctrl", 13, 5.5, 2, 1], ...ligne(5.5, 15.25, ["left", "down", "right"]),
    ["supera", 19.4, 0, 2.4, 2.4, "gros a"], ["superb", 22.4, 0, 2.4, 2.4, "gros b"],
    ...[1, 2, 3, 4, 5, 6, 7, 8].map((n, i) => ["k" + n, 19.4 + (i % 4) * 1.55, 3.9 + Math.floor(i / 4) * 1.4, 1.4, 1.2, "ext"]),
  ];
  const W = 26, H = 6.9, pc = (v, t) => (100 * v / t).toFixed(3) + "%";
  C.touchesClavier = TOUCHES.map(t => t[0]);

  /* opts : {actif, surligne, lecture, onclick} */
  C.dessinerClavier = (opts = {}) => {
    const k = h("div", { class: "clavier" + (opts.lecture ? " lecture" : ""), role: "group", "aria-label": "Clavier" });
    for (const [id, x, y, w, hh, cls = ""] of TOUCHES) {
      const cible = C.draft.clavier?.touches[id];
      const nom = C.libelle(id);
      const b = h("button", {
        type: "button", class: `t ${cls}` + (cible ? " modif" : "") + (!opts.lecture && C.touchePlus(id) ? " brouillon" : "") + (opts.actif === id || opts.surligne === id ? " actif" : ""),
        style: `left:${pc(x, W)};top:${pc(y, H)};width:${pc(w, W)};height:${pc(hh, H)}`, "data-id": id,
        title: `${C.cat.noms_fr[id] || id}${cible ? " → " + C.cibleLibelle(cible) : ""}`,
        "aria-label": `${C.cat.noms_fr[id] || C.libelle(id)}${cible ? ", envoie " + C.cibleLibelle(cible) : ""}`,
        tabindex: opts.lecture ? -1 : 0, onclick: () => opts.onclick?.(id),
      }, nom, cible && !opts.lecture ? h("small", {}, C.cibleLibelle(cible)) : null);
      k.append(b);
    }
    k.append(h("span", { class: "etiq", style: `left:${pc(19.4, W)};top:${pc(3.3, H)}` }, "Super Buttons externes"),
      h("span", { class: "etiq", style: `left:${pc(19.4, W)};top:${pc(2.55, H)}` }, "Boutons intégrés"));
    return k;
  };

  /* ---- choix de la cible --------------------------------------------------------------------------------- */
  const cherche = s => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const entrees = () => [
    ...C.cat.touches.map(n => ({ t: n, lib: C.libelle(n), cat: "touche", cle: `${n} ${C.libelle(n)} touche` })),
    ...C.cat.mods.map(n => ({ t: n, lib: C.libelle(n) + (n[0] === "l" ? " gauche" : " droit"), cat: "modificateur", cle: `${n} ${C.libelle(n)} modificateur ${n[0] === "l" ? "gauche" : "droit"}` })),
    ...C.cat.media.map(n => ({ t: "media:" + n, lib: C.MEDIA_FR[n] || n, cat: "multimédia", cle: `${n} ${C.MEDIA_FR[n] || ""} multimedia media` })),
    ...C.cat.souris.map(n => ({ t: "mouse:" + n, lib: C.SOURIS_FR[n] || n, cat: "souris", cle: `${n} ${C.SOURIS_FR[n] || ""} souris mouse` })),
  ].map(e => ({ ...e, cle: cherche(e.cle) }));

  C.choisirCible = id => {
    const actuelle = C.draft.clavier.touches[id] || "default";
    let mod = "";
    const toutes = entrees();
    const liste = h("ul", { class: "resultats", role: "listbox", "aria-label": "Cibles" });
    const champ = h("input", { type: "search", placeholder: "Chercher : f13, volume, souris, ctrl+c…", "aria-label": "Chercher une cible", style: "flex:1;min-width:14em" });
    const choisir = t => { C.setCible(id, t); C.fermer(); };
    const maj = async () => {
      const q = cherche(champ.value.trim());
      let r = toutes.filter(e => !q || q.split(/\s+/).every(m => e.cle.includes(m))).slice(0, 80);
      const items = r.map(e => {
        const t = e.cat === "touche" && mod ? `${mod}+${e.t}` : e.t;
        return h("li", {}, h("button", { type: "button", onclick: () => choisir(t) }, e.lib + (t !== e.t ? ` (${C.cibleLibelle(t)})` : ""), h("span", { class: "cat" }, e.cat + " · " + t)));
      });
      liste.replaceChildren(...items);
      const brut = champ.value.trim();
      if (brut && (brut.includes("+") || brut.startsWith("raw:") || !items.length)) {
        try {
          const v = await C.api("GET", "/api/cible?texte=" + encodeURIComponent(brut));
          if (champ.value.trim() === brut) liste.prepend(h("li", {}, h("button", { type: "button", onclick: () => choisir(v.texte) }, "Utiliser « " + v.texte + " »", h("span", { class: "cat" }, "saisie libre"))));
        } catch { if (!items.length) liste.replaceChildren(h("li", { class: "doux", style: "padding:8px" }, "Aucune cible de ce nom.")); }
      }
    };
    champ.oninput = maj;
    champ.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); liste.querySelector("button")?.click(); } };
    const selMod = h("select", { "aria-label": "Avec le modificateur", onchange: e => { mod = e.target.value; maj(); } },
      h("option", { value: "" }, "aucun"), C.cat.mods.map(m => h("option", { value: m }, m)));
    C.dialogue(h("h2", {}, `Touche ${C.cat.noms_fr[id] || C.libelle(id)}`),
      h("p", { class: "doux" }, `Envoie actuellement : ${C.cibleLibelle(actuelle)}. Disposition affichée : ${C.layout.toUpperCase()} (les noms sont ceux des positions QWERTY).`),
      h("div", { class: "ligne" }, champ, h("label", {}, "Accord avec ", selMod)), liste,
      h("div", { class: "ligne" },
        h("button", { type: "button", onclick: () => choisir("none") }, "Désactivée"),
        h("button", { type: "button", onclick: () => choisir("default") }, "Par défaut (d'origine)"),
        h("button", { type: "button", onclick: () => C.fermer() }, "Annuler")));
    maj();
    champ.focus();
  };

  /* ---- section Clavier ----------------------------------------------------------------------------------- */
  const indispo = (z, m) => [h("div", { class: "alerte" }, C.erreurs[z] || C.etat.peripheriques[z].message)];

  C.sections.push({
    id: "clavier", titre: "Clavier", rendre: m => {
      if (!C.draft.clavier) return m.append(...indispo("clavier"));
      const k = C.draft.clavier;
      const nom = h("input", { type: "text", maxlength: 14, value: k.profil || "", "aria-label": "Nom du profil", placeholder: "aucun profil" });
      m.append(
        h("div", { class: "ligne" },
          h("label", {}, "Profil ", nom),
          h("button", { onclick: () => { const v = nom.value.trim(); if (v) { k.profil = v; C.rafraichir(); } else C.msg("Un nom de profil fait de 1 à 14 caractères."); } }, k.profil === null ? "Créer le profil" : "Renommer"),
          h("button", { disabled: k.profil === null, onclick: async () => { if (await C.confirmer("Supprimer le profil ?", "Les affectations du profil seront retirées du brouillon ; rien n'est écrit avant « Voir ce qui va changer ».", "Retirer du brouillon")) { k.profil = null; k.touches = {}; C.rafraichir(); } } }, "Supprimer le profil"),
          h("span", { class: "doux" }, "Sans nom, une affectation n'est pas conservée par le clavier.")),
        h("p", { class: "doux" }, "Clique une touche pour choisir ce qu'elle envoie. En violet : touche modifiée. Contour pointillé : modification du brouillon pas encore écrite."),
        C.dessinerClavier({ onclick: C.choisirCible }),
        h("h3", {}, "Touches modifiées"),
        Object.keys(k.touches).length ? h("table", {}, Object.entries(k.touches).map(([id, t]) => h("tr", {},
          h("td", {}, C.cat.noms_fr[id] || C.libelle(id)), h("td", {}, "→ " + C.cibleLibelle(t)), h("td", {}, h("code", {}, t)),
          h("td", {}, h("button", { onclick: () => C.setCible(id, "default") }, "Rétablir"))))) : h("p", { class: "doux" }, "Aucune."));
    },
  });

  /* ---- section Macros ------------------------------------------------------------------------------------ */
  let sel = null;
  const vide = () => ({ key: "k1", name: "Nouvelle macro", cycles: null, interval_ms: 0, steps: ["down:a", "up:a"] });
  const TOUCHES_MACRO = () => [...C.cat.mods, ...C.cat.touches];

  C.sections.push({
    id: "macros", titre: "Macros", rendre: m => {
      if (!C.draft.clavier) return m.append(...indispo("clavier"));
      const ms = C.draft.clavier.macros;
      m.append(h("div", { class: "alerte" }, "Écriture désactivée : " + C.etat.macros_message + ". Les macros se préparent ici mais ne sont jamais envoyées au clavier."));
      m.append(h("ul", {}, ms.map((x, i) => h("li", {}, h("button", { onclick: () => { sel = i; C.afficher(); } }, `${x.name} (${C.cat.noms_fr[x.key] || x.key})`), " ",
        h("button", { onclick: () => { ms.splice(i, 1); sel = null; C.rafraichir(); } }, "Supprimer"))), ms.length ? null : h("li", { class: "doux" }, "Aucune macro dans le clavier ni dans le brouillon.")),
        h("button", { disabled: ms.length >= 8, onclick: () => { ms.push(vide()); sel = ms.length - 1; C.rafraichir(); } }, "Nouvelle macro"));
      const x = ms[sel];
      if (!x) return;
      const maj = () => C.barre();
      const pas = x.steps.map((s, i) => {
        const [op, ...r] = s.split(":"), arg = r.join(":");
        const type = h("select", { "aria-label": "Type de pas", onchange: e => { x.steps[i] = e.target.value === "wait" ? "wait:50" : `${e.target.value}:a`; C.afficher(); maj(); } },
          [["down", "Appui"], ["up", "Relâchement"], ["wait", "Délai (ms)"]].map(([v, l]) => h("option", { value: v, selected: v === op }, l)));
        const valeur = op === "wait" ? h("input", { type: "number", min: 0, max: 65535, value: arg, "aria-label": "Délai", onchange: e => { x.steps[i] = "wait:" + e.target.value; maj(); } })
          : h("select", { "aria-label": "Touche", onchange: e => { x.steps[i] = `${op}:${e.target.value}`; maj(); } },
            TOUCHES_MACRO().map(t => h("option", { value: t, selected: t === arg }, C.libelle(t) + (C.libelle(t).toLowerCase() === t ? "" : ` (${t})`))));
        return h("div", { class: "pas" }, type, valeur,
          h("span", {}, h("button", { disabled: i === 0, "aria-label": "Monter", onclick: () => { x.steps.splice(i - 1, 0, ...x.steps.splice(i, 1)); C.afficher(); maj(); } }, "↑"),
            h("button", { disabled: i === x.steps.length - 1, "aria-label": "Descendre", onclick: () => { x.steps.splice(i + 1, 0, ...x.steps.splice(i, 1)); C.afficher(); maj(); } }, "↓"),
            h("button", { "aria-label": "Supprimer le pas", onclick: () => { x.steps.splice(i, 1); C.afficher(); maj(); } }, "×")));
      });
      m.append(h("h3", {}, "Édition"), h("div", { class: "ligne" },
        h("label", {}, "Nom ", h("input", { value: x.name, maxlength: 28, onchange: e => { x.name = e.target.value || x.name; C.rafraichir(); } })),
        h("label", {}, "Touche ", h("select", { onchange: e => { x.key = e.target.value; C.rafraichir(); } },
          [...C.cat.hw, ...C.touchesClavier.filter(t => !C.cat.hw.includes(t))].map(t => h("option", { value: t, selected: t === x.key }, C.cat.noms_fr[t] || C.libelle(t))))),
        h("label", {}, "Répétitions ", h("input", { type: "number", min: 0, max: 255, value: x.cycles ?? "", placeholder: "par défaut", style: "width:7em", onchange: e => { x.cycles = e.target.value === "" ? null : +e.target.value; maj(); } })),
        h("label", {}, "Délai entre pas (ms) ", h("input", { type: "number", min: 0, max: 65535, value: x.interval_ms, style: "width:7em", onchange: e => { x.interval_ms = +e.target.value || 0; maj(); } }))),
        h("div", {}, pas), h("div", { class: "ligne" },
          h("button", { onclick: () => { x.steps.push("down:a"); C.afficher(); maj(); } }, "Ajouter un appui"),
          h("button", { onclick: () => { x.steps.push("up:a"); C.afficher(); maj(); } }, "Ajouter un relâchement"),
          h("button", { onclick: () => { x.steps.push("wait:50"); C.afficher(); maj(); } }, "Ajouter un délai")),
        h("div", { class: "ligne" }, h("button", { class: "primaire", disabled: !C.etat.macros_ecriture, title: C.etat.macros_message }, "Écrire dans le clavier"), h("span", { class: "doux" }, C.etat.macros_message)));
    },
  });
})();
