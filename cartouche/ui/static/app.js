"use strict";
/* Noyau : appels API, brouillon, navigation. Une section de plus = un `C.sections.push({id, titre, rendre})`. */
const C = window.C = { sections: [], etat: null, cat: null, base: {}, draft: {}, erreurs: {}, layout: "azerty", courante: null };

const h = (t, a = {}, ...k) => {
  const e = document.createElement(t);
  for (const [n, v] of Object.entries(a)) {
    if (n === "class") e.className = v;
    else if (n.startsWith("on")) e.addEventListener(n.slice(2), v);
    else if (v === true) e.setAttribute(n, "");
    else if (v !== false && v != null) e.setAttribute(n, v);
  }
  e.append(...k.flat(9).filter(x => x != null && x !== false));
  return e;
};
const sv = (t, a = {}, ...k) => {
  const e = document.createElementNS("http://www.w3.org/2000/svg", t);
  for (const [n, v] of Object.entries(a)) n.startsWith("on") ? e.addEventListener(n.slice(2), v) : e.setAttribute(n, v);
  e.append(...k.flat(9).filter(x => x != null));
  return e;
};
const $ = s => document.querySelector(s);
const clone = o => JSON.parse(JSON.stringify(o));
const stock = { get: k => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch { } } };

C.h = h; C.sv = sv; C.clone = clone;

C.api = async (methode, chemin, corps) => {
  const r = await fetch(chemin, {
    method: methode, headers: { "X-Jeton": document.querySelector('meta[name="jeton"]').content, "Content-Type": "application/json" },
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.erreur || `erreur ${r.status}`);
  return d;
};

C.msg = (texte, ok = false) => {
  const m = $("#msg");
  m.replaceChildren(texte ? h("div", { class: ok ? "ok" : "alerte" }, texte) : "");
};

C.demande = async (...args) => { try { return await C.api(...args); } catch (e) { C.msg(e.message); throw e; } };

/* ---- brouillon -------------------------------------------------------------------------------------------- */
C.modifs = () => {
  const l = [], b = C.base, d = C.draft;
  if (b.clavier && d.clavier) {
    if (b.clavier.profil !== d.clavier.profil) l.push("profil");
    for (const k of new Set([...Object.keys(b.clavier.touches), ...Object.keys(d.clavier.touches)]))
      if (b.clavier.touches[k] !== d.clavier.touches[k]) l.push(k);
    if (JSON.stringify(b.clavier.macros) !== JSON.stringify(d.clavier.macros)) l.push("macros");
  }
  if (b.souris && d.souris)
    for (const n of Object.keys(d.souris.boutons)) if (b.souris.boutons[n] !== d.souris.boutons[n]) l.push("bouton" + n);
  return l;
};
C.touchePlus = id => (C.base.clavier?.touches[id]) !== (C.draft.clavier?.touches[id]);

C.setCible = (id, t) => {
  const k = C.draft.clavier;
  if (t === "default") delete k.touches[id]; else k.touches[id] = t;
  if (k.profil === null && Object.keys(k.touches).length) k.profil = "Cartouche"; // un profil non nommé n'est pas conservé
  C.rafraichir();
};

C.abandonner = () => { C.draft = clone(C.base); C.msg(""); C.rafraichir(); };

C.barre = () => {
  const n = C.modifs().length, b = $("#barre");
  b.hidden = n === 0;
  b.replaceChildren(h("span", { class: "grow" }, `Brouillon : ${n} modification${n > 1 ? "s" : ""}, rien n'est encore écrit`),
    h("button", { onclick: C.abandonner }, "Abandonner"),
    h("button", { class: "primaire", onclick: C.voirDiff }, "Voir ce qui va changer"));
};

C.dialogue = (...contenu) => {
  const d = $("#dlg");
  d.replaceChildren(...contenu);
  if (!d.open) d.showModal();
  return d;
};
C.fermer = () => { const d = $("#dlg"); if (d.open) d.close(); };
C.confirmer = (titre, texte, bouton) => new Promise(ok => {
  const d = C.dialogue(h("h2", {}, titre), h("p", {}, texte),
    h("div", { class: "ligne" }, h("button", { class: "primaire", onclick: () => { d.onclose = null; C.fermer(); ok(true); } }, bouton),
      h("button", { onclick: () => C.fermer() }, "Annuler")));
  d.onclose = () => ok(false);
});

C.brouillonServeur = () => ({ clavier: C.draft.clavier, souris: C.draft.souris ? { boutons: C.draft.souris.boutons } : null });

C.voirDiff = async () => {
  let d;
  try { d = await C.api("POST", "/api/diff", C.brouillonServeur()); } catch (e) { return C.msg(e.message); }
  const pret = d.a_ecrire && !d.bloque.length;
  const dlg = C.dialogue(h("h2", {}, "Ce qui va changer"),
    d.lignes.length ? h("ul", { class: "diff" }, d.lignes.map(l => h("li", { class: l.ignore ? "ignore" : "" }, h("strong", {}, l.zone + " : "), l.texte)))
      : h("p", { class: "doux" }, "Aucune différence avec le matériel."),
    d.avertissements.map(a => h("div", { class: "alerte" }, a)), d.bloque.map(a => h("div", { class: "alerte" }, a)),
    h("p", { class: "doux" }, "Une sauvegarde de l'état actuel est écrite dans le dossier des sauvegardes avant toute écriture, puis le matériel est relu pour vérifier."),
    h("div", { class: "ligne" },
      h("button", { class: "primaire", disabled: !pret, onclick: () => C.ecrire(dlg) }, C.etat.demo ? "Écrire (démonstration)" : "Écrire dans le matériel"),
      h("button", { onclick: () => C.fermer() }, "Fermer")));
};

C.ecrire = async dlg => {
  dlg.querySelectorAll("button").forEach(b => b.disabled = true);
  try {
    const r = await C.api("POST", "/api/appliquer", C.brouillonServeur());
    C.fermer();
    await C.charger(true);
    C.msg(`Écrit et relu : sauvegarde « ${r.sauvegarde} »` + (r.notes.length ? ". Notes : " + r.notes.join(" ; ") : "") + ".", true);
  } catch (e) { C.fermer(); C.msg("Écriture échouée : " + e.message); }
};

/* ---- chargement ------------------------------------------------------------------------------------------- */
C.charger = async (garderMacros = false) => {
  const macros = garderMacros ? C.draft.clavier?.macros : null;
  try { C.etat = await C.api("GET", "/api/etat"); } catch (e) { C.etat = null; C.msg(e.message); return; }
  C.cat = C.cat || await C.api("GET", "/api/catalogue");
  C.base = {}; C.erreurs = {};
  for (const z of ["clavier", "souris"]) {
    if (!C.etat.peripheriques[z].pret) continue;
    try { C.base[z] = await C.api("GET", "/api/" + z); } catch (e) { C.erreurs[z] = e.message; }
  }
  C.draft = clone(C.base);
  if (macros && C.draft.clavier) C.draft.clavier.macros = macros;
  $("#badge-demo").hidden = !C.etat.demo;
  C.rafraichir();
};

C.rafraichir = () => { C.barre(); if (C.courante) C.afficher(); };

/* ---- navigation ------------------------------------------------------------------------------------------- */
C.afficher = () => {
  const s = C.sections.find(x => x.id === C.courante) || C.sections[0];
  C.courante = s.id;
  $("#nav").replaceChildren(...C.sections.map(x => h("a", { href: "#" + x.id, class: x.vide ? "vide" : "", "aria-current": x.id === s.id ? "page" : null }, x.titre)));
  const m = $("#main");
  m.replaceChildren(h("h2", {}, s.titre));
  if (C.etat) s.rendre(m); else m.append(h("p", { class: "alerte" }, "Le serveur ne répond pas."));
};
window.addEventListener("hashchange", () => { C.nettoyer?.(); C.nettoyer = null; C.courante = location.hash.slice(1); C.afficher(); $("#main").focus(); });

/* libellé d'une touche selon la disposition choisie : les noms du cœur sont ceux des positions QWERTY */
const AZ = { q: "a", w: "z", a: "q", z: "w", semicolon: "m", m: ",", comma: ";", dot: ":", slash: "!", grave: "²",
  1: "&", 2: "é", 3: "\"", 4: "'", 5: "(", 6: "-", 7: "è", 8: "_", 9: "ç", 0: "à", minus: ")", equal: "=",
  lbracket: "^", rbracket: "$", backslash: "*", apostrophe: "ù" };
const QW = { semicolon: ";", comma: ",", dot: ".", slash: "/", grave: "`", minus: "-", equal: "=", lbracket: "[", rbracket: "]", backslash: "\\", apostrophe: "'" };
const FR = { esc: "Échap", backspace: "Retour", tab: "Tab", capslock: "Verr.Maj", enter: "Entrée", space: "Espace", lshift: "Maj", rshift: "Maj",
  lctrl: "Ctrl", rctrl: "Ctrl", lalt: "Alt", ralt: "Alt Gr", lwin: "Win", rwin: "Win", printscreen: "Impr", scrolllock: "Arrêt", pause: "Pause",
  insert: "Inser", delete: "Suppr", home: "Début", end: "Fin", pageup: "Pg↑", pagedown: "Pg↓", left: "←", right: "→", up: "↑", down: "↓",
  supera: "A", superb: "B", app: "Menu", numlock: "Verr.Num" };
C.libelle = id => {
  if (C.cat?.noms_fr[id] && id[0] === "k") return C.cat.noms_fr[id].replace("Super Button ", "");
  if (C.layout === "azerty" && id in AZ) return AZ[id].toUpperCase();
  if (C.layout === "qwerty" && id in QW) return QW[id];
  return FR[id] || (id.length === 1 ? id.toUpperCase() : id.toUpperCase());
};
const MEDIA_FR = { playpause: "Lecture / pause", next: "Piste suivante", prev: "Piste précédente", mute: "Muet", volup: "Volume +", voldown: "Volume −",
  mail: "Messagerie", calc: "Calculatrice", explorer: "Explorateur", brightup: "Luminosité +", brightdown: "Luminosité −" };
const SOURIS_FR = { left: "Clic gauche", right: "Clic droit", middle: "Clic milieu", button4: "Bouton 4", button5: "Bouton 5", doubleclick: "Double-clic",
  wheelup: "Molette haut", wheeldown: "Molette bas", wheelleft: "Molette gauche", wheelright: "Molette droite" };
C.MEDIA_FR = MEDIA_FR; C.SOURIS_FR = SOURIS_FR;
C.cibleLibelle = t => {
  if (!t || t === "default") return "d'origine";
  if (t === "none") return "désactivée";
  if (t.startsWith("media:")) return MEDIA_FR[t.slice(6)] || t;
  if (t.startsWith("mouse:")) return SOURIS_FR[t.slice(6)] || t;
  if (t.startsWith("raw:")) return t;
  return t.split("+").map(C.libelle).join(" + ");
};

C.demarrer = async () => {
  C.layout = stock.get("layout") === "qwerty" ? "qwerty" : "azerty";
  const sel = $("#sel-layout");
  sel.value = C.layout;
  sel.onchange = () => { C.layout = sel.value; stock.set("layout", C.layout); C.rafraichir(); };
  const th = stock.get("theme");
  if (th) document.documentElement.dataset.theme = th;
  $("#btn-theme").onclick = () => {
    const sombre = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = sombre ? "light" : "dark";
    stock.set("theme", document.documentElement.dataset.theme);
  };
  const ordre = ["appareils", "clavier", "souris", "macros", "cartouche", "testeur", "logiciel"];
  C.sections.sort((a, b) => ordre.indexOf(a.id) - ordre.indexOf(b.id)); // une section inconnue passe en dernier
  C.courante = location.hash.slice(1) || C.sections[0].id;
  await C.charger();
};
