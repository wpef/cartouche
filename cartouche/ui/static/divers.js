"use strict";
/* Appareils, cartouche (sauvegardes, import/export, usine), testeur de touches, emplacement « Logiciel ». */
(() => {
  const { h } = C;

  C.sections.push({
    id: "appareils", titre: "Appareils", rendre: m => {
      const carte = (z, titre, ok) => {
        const p = C.etat.peripheriques[z], d = C.base[z];
        return h("div", { class: "carte" }, h("h3", { style: "margin-top:0" }, h("span", { class: "point " + (p.pret ? "ok" : "non") }), titre),
          h("p", {}, p.message), C.erreurs[z] ? h("div", { class: "alerte" }, C.erreurs[z]) : null,
          d ? ok(d) : null);
      };
      m.append(C.etat.demo ? h("div", { class: "ok" }, "Mode démonstration : clavier et souris simulés en mémoire, rien n'est écrit dans le matériel.") : null,
        h("div", { class: "cartes" },
          carte("clavier", "Clavier 8BitDo Retro Mechanical", d => h("p", {}, `Profil : ${d.profil ?? "aucun"} · ${Object.keys(d.touches).length} touche(s) modifiée(s) · ${d.macros.length} macro(s)`)),
          carte("souris", "Souris Retro R8", d => h("p", {}, `${d.dpi.current} DPI · batterie ${d.batterie.known ? d.batterie.percent + " %" : "inconnue"}`))),
        h("div", { class: "ligne" }, h("button", {
          onclick: async () => {
            if (C.modifs().length && !await C.confirmer("Relire le matériel ?", "Le brouillon en cours sera perdu.", "Relire")) return;
            await C.charger(); C.msg("Matériel relu.", true);
          },
        }, "Actualiser")));
    },
  });

  /* ---- cartouche ----------------------------------------------------------------------------------------- */
  C.sections.push({
    id: "cartouche", titre: "Cartouche", rendre: m => {
      const liste = h("div", {}, h("p", { class: "doux" }, "Chargement…"));
      const exporter = () => {
        const c = { cartouche: 1 };
        if (C.draft.clavier) c.clavier = C.draft.clavier;
        if (C.draft.souris) c.souris = C.draft.souris;
        const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(c, null, 2)], { type: "application/json" })), download: "cartouche.json" });
        a.click(); URL.revokeObjectURL(a.href);
      };
      const importer = async f => {
        if (!f) return;
        try {
          const r = await C.api("POST", "/api/importer", { cartouche: JSON.parse(await f.text()) });
          for (const z of ["clavier", "souris"]) if (r[z] && C.draft[z]) C.draft[z] = z === "souris" ? { ...C.draft[z], boutons: { ...C.draft[z].boutons, ...r[z].boutons } } : { ...r[z] };
          C.msg("Cartouche chargée dans le brouillon : rien n'est écrit tant que tu n'as pas validé.", true);
          C.rafraichir();
        } catch (e) { C.msg("Import refusé : " + e.message); }
      };
      m.append(h("h3", {}, "Export et import"),
        h("div", { class: "ligne" }, h("button", { onclick: exporter }, "Exporter le brouillon en JSON"),
          h("label", {}, "Importer ", h("input", { type: "file", accept: ".json,application/json", onchange: e => importer(e.target.files[0]) }))),
        h("h3", {}, "Sauvegardes automatiques"), liste,
        h("h3", {}, "État d'usine"),
        h("p", {}, "Supprime le profil du clavier et ses affectations. Une sauvegarde est écrite avant."),
        h("button", {
          disabled: !C.base.clavier, onclick: async () => {
            if (!await C.confirmer("Retour à l'état d'usine ?", "Le profil du clavier et toutes ses affectations seront supprimés dans le matériel. Une sauvegarde est écrite d'abord.", "Supprimer le profil")) return;
            try { const r = await C.api("POST", "/api/usine", { confirmer: true }); await C.charger(); C.msg(`Profil supprimé (sauvegarde « ${r.sauvegarde} »).`, true); } catch (e) { C.msg(e.message); }
          },
        }, "Rétablir l'état d'usine"));
      C.api("GET", "/api/sauvegardes").then(r => liste.replaceChildren(r.sauvegardes.length ? h("table", {}, r.sauvegardes.map(s => h("tr", {},
        h("td", {}, h("code", {}, s.nom)), h("td", { class: "doux" }, s.clavier ? `profil ${s.profil ?? "aucun"}, ${s.touches} touche(s)` : "", s.souris ? " · souris" : ""),
        h("td", {}, h("button", {
          onclick: async () => {
            if (!await C.confirmer("Restaurer cette sauvegarde ?", `« ${s.nom} » sera écrite dans le matériel (l'état actuel est sauvegardé d'abord).`, "Restaurer")) return;
            try { const x = await C.api("POST", "/api/restaurer", { nom: s.nom }); await C.charger(); C.msg(`Restauré (sauvegarde de l'état précédent : « ${x.sauvegarde || "aucune écriture nécessaire"} »).`, true); } catch (e) { C.msg(e.message); }
          },
        }, "Restaurer"))))) : h("p", { class: "doux" }, "Aucune sauvegarde pour l'instant."))).catch(e => liste.replaceChildren(h("div", { class: "alerte" }, e.message)));
    },
  });

  /* ---- testeur de touches -------------------------------------------------------------------------------- */
  const SPECIAL = { Enter: "enter", Escape: "esc", Backspace: "backspace", Tab: "tab", Space: "space", Minus: "minus", Equal: "equal", BracketLeft: "lbracket", BracketRight: "rbracket",
    Backslash: "backslash", Semicolon: "semicolon", Quote: "apostrophe", Backquote: "grave", Comma: "comma", Period: "dot", Slash: "slash", CapsLock: "capslock",
    ShiftLeft: "lshift", ShiftRight: "rshift", ControlLeft: "lctrl", ControlRight: "rctrl", AltLeft: "lalt", AltRight: "ralt", MetaLeft: "lwin", MetaRight: "rwin",
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Insert: "insert", Delete: "delete", Home: "home", End: "end", PageUp: "pageup", PageDown: "pagedown",
    PrintScreen: "printscreen", ScrollLock: "scrolllock", Pause: "pause" };
  const codeVersId = c => /^Key[A-Z]$/.test(c) ? c[3].toLowerCase() : /^Digit\d$/.test(c) ? c[5] : /^F\d+$/.test(c) ? c.toLowerCase() : SPECIAL[c] || null;
  const histo = [];

  C.sections.push({
    id: "testeur", titre: "Testeur de touches", rendre: m => {
      const zone = h("div", { class: "test-zone", tabindex: 0, "aria-live": "off" }, "Clique ici puis tape sur le clavier.");
      const liste = h("ol", { class: "doux", reversed: true });
      const dessin = h("div", {});
      const maj = id => dessin.replaceChildren(C.dessinerClavier({ lecture: true, surligne: id }));
      const montre = () => liste.replaceChildren(...histo.map(x => h("li", {}, x)));
      zone.onkeydown = e => {
        if (e.key === "Tab") return; // on ne piège pas la navigation au clavier
        e.preventDefault();
        const id = codeVersId(e.code), mods = ["ctrlKey", "shiftKey", "altKey", "metaKey"].filter(k => e[k]).map(k => k.replace("Key", ""));
        zone.replaceChildren(h("div", { style: "font-size:1.6rem;font-weight:700" }, e.key === " " ? "Espace" : e.key),
          h("div", {}, `code : `, h("code", {}, e.code), ` · touche du cœur : `, h("code", {}, id || "inconnue"), e.location ? ` · position ${["", "gauche", "droite", "pavé numérique"][e.location]}` : ""),
          h("div", { class: "doux" }, `modificateurs : ${mods.join(", ") || "aucun"}${e.repeat ? " · répétition" : ""}`));
        histo.unshift(`${e.key} (${e.code})`); histo.length = Math.min(histo.length, 12);
        montre(); maj(id);
      };
      zone.onkeyup = () => maj(null);
      m.append(h("p", { class: "doux" }, "Ce que le navigateur reçoit, après la disposition du système : utile pour vérifier une affectation une fois écrite. La touche Tab n'est pas capturée."),
        zone, dessin, h("h3", {}, "Dernières touches"), liste);
      maj(null); montre();
    },
  });

  /* ---- emplacement pour la suite : le moteur logiciel (cartouche/moteur) viendra ici --------------------- */
  C.sections.push({
    id: "logiciel", titre: "Logiciel", vide: true, rendre: m =>
      m.append(h("p", { class: "doux" }, "Réservé aux fonctions côté ordinateur (profils par application, couches). Rien ici pour l'instant.")),
  });

  C.demarrer();
})();
