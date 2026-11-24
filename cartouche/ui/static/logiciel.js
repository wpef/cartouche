"use strict";
/* Logiciel : le moteur (état, pause, arrêt), ses règles (formulaires + JSON), les applications en pause, le démarrage de Windows.
   Le brouillon de la configuration (L.cfg) vit dans la page ; rien n'est enregistré avant « Enregistrer et recharger ». */
(() => {
  const { h, clone } = C;
  const L = C.logi = { cfg: null, saved: null, meta: null, apps: [], sel: { profil: "(commun)", table: "touches" }, texte: null, etat: null };
  const MEDIA = ["playpause", "next", "prev", "stop", "mute", "volup", "voldown"];
  const STATUT = { actif: "Actif", pause: "En pause", arrete: "Arrêté" };
  const MOLETTES = { haut: [0, 120], bas: [0, -120], gauche: [-120, 0], droite: [120, 0] };
  /* les formulaires créent des tables vides à la demande : elles ne comptent pas comme un changement */
  const nettoye = o => Array.isArray(o) ? o : o && typeof o === "object"
    ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, nettoye(v)]).filter(([, v]) => !(v && typeof v === "object" && !Object.keys(v).length)))
    : o;
  const sale = () => JSON.stringify(nettoye(L.cfg)) !== JSON.stringify(nettoye(L.saved));
  const defaut = () => L.cfg.profil_defaut || "defaut";
  const profils = () => [...new Set([defaut(), ...Object.keys(L.cfg.profils || {})])];
  const sansNul = a => a.filter(x => x != null && x !== false); // replaceChildren / append écrivent « null » sinon
  const maj = () => { L.texte = null; C.afficher(); };

  const charger = async () => {
    const [r, a] = await Promise.all([C.api("GET", "/api/logiciel"), C.api("GET", "/api/applications").catch(() => ({ applications: [] }))]);
    L.meta = r; L.etat = r.moteur; L.apps = a.applications;
    L.saved = r.config;
    if (!L.cfg) L.cfg = clone(r.config);
  };
  /* utilisés par l'import / l'export de l'écran Cartouche */
  C.logiImporter = async cfg => { if (!L.meta) await charger(); L.cfg = clone(cfg); L.texte = null; };
  C.logiExporter = async () => { if (!L.meta) await charger(); return L.cfg; };

  const portee = () => {
    const p = L.sel.profil;
    const o = p === "(commun)" ? (L.cfg.commun ||= {}) : ((L.cfg.profils ||= {})[p] ||= {});
    return L.sel.table === "touches" ? (o.touches ||= {}) : ((o.couches ||= {})[L.sel.table] ||= {});
  };
  const objetProfil = () => L.sel.profil === "(commun)" ? (L.cfg.commun ||= {}) : ((L.cfg.profils ||= {})[L.sel.profil] ||= {});
  const verifier = async cfg => { await C.api("POST", "/api/logiciel/valider", { config: cfg }); };

  /* ---- libellés ------------------------------------------------------------------------------------------- */
  const court = a => typeof a === "string" ? a : a.media ? C.MEDIA_FR[a.media] || a.media : a.texte != null ? `« ${a.texte} »` : a.lancer ? "lancer " + [].concat(a.lancer).join(" ")
    : a.url ? a.url : a.profil ? "profil " + a.profil : a.molette ? "molette" : a.envoyer ? a.envoyer : JSON.stringify(a);
  const resume = v => {
    if (typeof v === "string") return `réaffectée en ${v}`;
    if (v && typeof v === "object" && ["couche", "court", "long", "double"].some(k => k in v))
      return [v.couche ? `couche « ${v.couche} » tant que tenue` : null, v.court ? `appui court : ${court(v.court)}` : null,
        v.long ? `appui long : ${court(v.long)}` : null, v.double ? `double appui : ${court(v.double)}` : null].filter(Boolean).join(" · ");
    return "action : " + court(v);
  };

  /* ---- champ « action » ------------------------------------------------------------------------------------ */
  const champAction = profilsListe => {
    const type = h("select", { "aria-label": "Type d'action" },
      [["touche", "Touche ou raccourci"], ["media", "Touche multimédia"], ["texte", "Taper un texte"], ["lancer", "Lancer un programme"],
        ["url", "Ouvrir une adresse"], ["profil", "Changer de profil"], ["molette", "Défiler"]].map(([v, t]) => h("option", { value: v }, t)));
    const zone = h("span", {});
    let champ;
    const poser = () => {
      const t = type.value;
      champ = t === "media" ? h("select", {}, MEDIA.map(m => h("option", { value: m }, C.MEDIA_FR[m] || m)))
        : t === "profil" ? h("select", {}, ["auto", "suivant", ...profilsListe].map(m => h("option", { value: m }, m)))
          : t === "molette" ? h("select", {}, Object.keys(MOLETTES).map(m => h("option", { value: m }, m)))
            : h("input", { type: "text", list: t === "touche" ? "dl-touches" : null, size: 22, "aria-label": "Valeur",
              placeholder: { touche: "ctrl+c, f13, a…", texte: "texte à taper", lancer: "prog.exe argument", url: "https://…" }[t] });
      zone.replaceChildren(champ);
    };
    type.onchange = poser; poser();
    const valeur = () => {
      const t = type.value, v = champ.value.trim();
      if (!v) return undefined;
      return { touche: v, media: { media: v }, texte: { texte: champ.value }, lancer: { lancer: v.split(/\s+/) }, url: { url: v },
        profil: { profil: v }, molette: { molette: MOLETTES[v] } }[t];
    };
    return { el: h("span", { class: "ligne", style: "margin:0" }, type, zone), valeur };
  };

  /* ---- liste d'applications (processus) ------------------------------------------------------------------- */
  const listeApps = (liste, apres) => {
    const choix = h("select", { "aria-label": "Applications ouvertes" }, h("option", { value: "" }, "— choisir parmi les applications ouvertes —"),
      L.apps.filter(a => !liste.includes(a)).map(a => h("option", { value: a }, a)));
    const libre = h("input", { type: "text", size: 18, placeholder: "ou un autre : jeu.exe", "aria-label": "Nom de processus" });
    const ajouter = () => { const v = (choix.value || libre.value).trim().toLowerCase(); if (v && !liste.includes(v)) { liste.push(v); apres(); } };
    libre.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); ajouter(); } };
    return h("div", {}, liste.map(a => h("span", { class: "puce" }, a, " ",
      h("button", { type: "button", class: "x", "aria-label": "Retirer " + a, onclick: () => { liste.splice(liste.indexOf(a), 1); apres(); } }, "✕"))),
    h("div", { class: "ligne" }, choix, libre, h("button", { type: "button", onclick: ajouter }, "Ajouter")));
  };

  /* ---- moteur ---------------------------------------------------------------------------------------------- */
  const carteMoteur = () => {
    const corps = h("div", {});
    const agir = async action => { try { L.etat = await C.api("POST", "/api/logiciel/moteur", { action }); C.msg(""); dessiner(); } catch (e) { C.msg(e.message); } };
    const dessiner = () => {
      const e = L.etat;
      corps.replaceChildren(...sansNul([
        h("p", {}, h("span", { class: "point " + (e.statut === "actif" ? "ok" : e.statut === "pause" ? "" : "non") }), h("strong", {}, STATUT[e.statut]),
          ` · profil courant : ${e.profil || "—"} · dernière application vue au premier plan : ${e.app || "—"} · ${e.evenements} événement(s) vu(s)`),
        e.erreur ? h("div", { class: "alerte" }, "Erreur du moteur : " + e.erreur) : null,
        h("div", { class: "ligne" },
          e.statut === "arrete" ? h("button", { class: "primaire", onclick: () => agir("demarrer") }, "Démarrer") : null,
          e.statut === "actif" ? h("button", { onclick: () => agir("pause") }, "Mettre en pause") : null,
          e.statut === "pause" ? h("button", { class: "primaire", onclick: () => agir("reprendre") }, "Reprendre") : null,
          e.statut !== "arrete" ? h("button", { onclick: () => agir("arreter") }, "Arrêter") : null)]));
    };
    dessiner();
    const t = setInterval(async () => { try { L.etat = await C.api("GET", "/api/logiciel/etat"); dessiner(); } catch { } }, 2000);
    C.nettoyer = () => clearInterval(t);
    return h("div", { class: "carte" }, h("h3", { style: "margin-top:0" }, "Moteur"), corps,
      h("div", { class: "ok" }, h("strong", {}, "Arrêt d'urgence : Ctrl+Alt+Pause"), " coupe ou rétablit le moteur à tout moment, quelles que soient les règles."));
  };

  const carteAuto = () => h("div", { class: "carte" }, h("h3", { style: "margin-top:0" }, "Démarrage de Windows"),
    h("label", {}, h("input", {
      type: "checkbox", checked: L.etat.auto, onchange: async e => {
        try { L.etat = await C.api("POST", "/api/logiciel/auto", { activer: e.target.checked }); C.msg(L.etat.auto ? "Lanceur posé dans le dossier Démarrage." : "Lanceur retiré.", true); }
        catch (x) { e.target.checked = !e.target.checked; C.msg(x.message); }
      },
    }), " Lancer Cartouche à l'ouverture de session"),
    h("p", { class: "doux" }, "Pose (ou retire) un petit lanceur dans le dossier Démarrage de ton profil : pas de droits administrateur, pas de registre. Rien n'est fait tant que tu ne coches pas."));

  /* ---- règles ------------------------------------------------------------------------------------------------ */
  const formRegle = () => {
    const touche = h("input", { type: "text", list: "dl-touches", size: 16, placeholder: "f13, capslock, mouse4, ctrl+alt+p", "aria-label": "Touche qui déclenche" });
    const type = h("select", { "aria-label": "Type de règle" }, [["remap", "Réaffectation ou accord (tenu tant que la touche l'est)"],
      ["tap", "Appui court / long / double"], ["couche", "Couche (tant que la touche est tenue)"], ["action", "Action à l'appui"]].map(([v, t]) => h("option", { value: v }, t)));
    const zone = h("div", {});
    let champs = {}, accord, nomCouche;
    const poser = () => {
      champs = {};
      const t = type.value, pf = profils();
      if (t === "remap") {
        accord = h("input", { type: "text", list: "dl-touches", size: 22, placeholder: "ctrl+shift+x, f13, a…", "aria-label": "Résultat" });
        zone.replaceChildren(h("label", {}, "Envoie ", accord));
      } else if (t === "tap") {
        champs = { court: champAction(pf), long: champAction(pf), double: champAction(pf) };
        zone.replaceChildren(...["court", "long", "double"].map(k => h("div", { class: "ligne" }, h("span", { style: "width:8em" }, { court: "Appui court", long: "Appui long", double: "Double appui" }[k]), champs[k].el)),
          h("p", { class: "doux", style: "margin:0" }, "Un champ vide garde le comportement normal de la touche (court) ou n'en ajoute pas (long, double)."));
      } else if (t === "couche") {
        nomCouche = h("input", { type: "text", size: 14, placeholder: "navigation", "aria-label": "Nom de la couche" });
        champs = { court: champAction(pf) };
        zone.replaceChildren(h("label", {}, "Nom de la couche ", nomCouche), h("div", { class: "ligne" }, h("span", {}, "Appui court (sans autre touche)"), champs.court.el));
      } else {
        champs = { action: champAction(pf) };
        zone.replaceChildren(champs.action.el);
      }
    };
    type.onchange = poser; poser();
    const construire = () => {
      const t = type.value, v = k => champs[k].valeur();
      if (t === "remap") { const a = accord.value.trim(); if (!a) throw new Error("Dis ce que la touche doit envoyer."); return a; }
      if (t === "action") { const a = v("action"); if (a === undefined) throw new Error("Choisis une action."); return typeof a === "string" ? { envoyer: a } : a; }
      if (t === "couche") {
        const n = nomCouche.value.trim();
        if (!n) throw new Error("Donne un nom à la couche.");
        const r = { couche: n }, c = v("court");
        if (c !== undefined) r.court = c;
        return r;
      }
      const r = {};
      for (const k of ["court", "long", "double"]) if (v(k) !== undefined) r[k] = v(k);
      if (!r.long && !r.double) throw new Error("Renseigne au moins l'appui long ou le double appui.");
      return r;
    };
    const ajouter = async () => {
      try {
        const spec = touche.value.trim().toLowerCase();
        if (!spec) throw new Error("Dis quelle touche déclenche la règle.");
        const r = construire(), avant = clone(L.cfg);
        if (r.couche) (objetProfil().couches ||= {})[r.couche] ||= {};
        portee()[spec] = r;
        try { await verifier(L.cfg); } catch (e) { L.cfg = avant; throw e; }
        C.msg(""); maj();
      } catch (e) { C.msg(e.message); }
    };
    return h("div", { class: "carte" }, h("h4", { style: "margin:0 0 6px" }, "Ajouter une règle"),
      h("div", { class: "ligne" }, h("label", {}, "Touche ", touche), type), zone, h("div", { class: "ligne" }, h("button", { class: "primaire", onclick: ajouter }, "Ajouter la règle")));
  };

  const sectionRegles = () => {
    const pf = ["(commun)", ...profils()];
    if (!pf.includes(L.sel.profil)) L.sel.profil = "(commun)";
    const obj = objetProfil();
    const tables = ["touches", ...Object.keys(obj.couches || {})];
    if (!tables.includes(L.sel.table)) L.sel.table = "touches";
    const sel = (valeurs, courant, fn, libelle) => { const s = h("select", { "aria-label": libelle }, valeurs.map(v => h("option", { value: v, selected: v === courant }, v === "touches" ? "touches directes" : v === "(commun)" ? "commun (toutes les applications)" : v))); s.onchange = () => fn(s.value); return s; };
    const regles = Object.entries(portee());
    const estProfil = L.sel.profil !== "(commun)";
    const nouveau = () => {
      const nom = h("input", { type: "text", size: 14, placeholder: "navigateur", "aria-label": "Nom du profil" }), apps = [];
      const zone = h("div", {});
      const dessiner = () => zone.replaceChildren(h("p", { class: "doux", style: "margin:4px 0" }, "Applications (le profil s'active quand l'une d'elles est au premier plan) :"), listeApps(apps, dessiner));
      dessiner();
      const d = C.dialogue(h("h2", {}, "Nouveau profil"), h("label", {}, "Nom ", nom), zone,
        h("div", { class: "ligne" }, h("button", {
          class: "primaire", onclick: () => {
            const n = nom.value.trim();
            if (!n || profils().includes(n) || n === "(commun)") return C.msg("Nom vide ou déjà pris.");
            (L.cfg.profils ||= {})[n] = { apps: [...apps], touches: {} }; L.sel = { profil: n, table: "touches" }; C.fermer(); C.msg(""); maj();
          },
        }, "Créer"), h("button", { onclick: () => C.fermer() }, "Annuler")));
      nom.focus();
    };
    return h("div", {},
      h("div", { class: "ligne" }, h("label", {}, "Profil ", sel(pf, L.sel.profil, v => { L.sel = { profil: v, table: "touches" }; C.afficher(); }, "Profil")),
        h("button", { onclick: nouveau }, "Nouveau profil…"),
        estProfil && L.sel.profil !== defaut() ? h("button", {
          onclick: async () => {
            if (!await C.confirmer("Supprimer ce profil ?", `Le profil « ${L.sel.profil} » et ses règles quittent le brouillon (rien n'est enregistré avant « Enregistrer »).`, "Supprimer")) return;
            delete L.cfg.profils[L.sel.profil]; L.sel = { profil: "(commun)", table: "touches" }; maj();
          },
        }, "Supprimer ce profil") : null,
        tables.length > 1 ? h("label", {}, "Table ", sel(tables, L.sel.table, v => { L.sel.table = v; C.afficher(); }, "Table de règles")) : null),
      estProfil && L.sel.profil !== defaut() ? h("div", {}, h("p", { class: "doux", style: "margin:4px 0" }, "Applications de ce profil :"), listeApps(objetProfil().apps ||= [], maj))
        : h("p", { class: "doux" }, estProfil ? "Profil par défaut : utilisé quand aucune application ne correspond à un autre profil." : "Les règles « commun » valent partout, après celles du profil actif."),
      regles.length ? h("table", {}, regles.map(([k, v]) => h("tr", {}, h("td", {}, h("code", {}, k)), h("td", {}, resume(v)),
        h("td", {}, h("button", { "aria-label": "Retirer la règle " + k, onclick: () => { delete portee()[k]; maj(); } }, "Retirer")))))
        : h("p", { class: "doux" }, "Aucune règle dans cette table."),
      formRegle());
  };

  /* ---- éditeur JSON ----------------------------------------------------------------------------------------- */
  const editeurJson = () => {
    const t = h("textarea", { rows: 14, spellcheck: false, "aria-label": "Configuration JSON", style: "width:100%;font-family:ui-monospace,Consolas,monospace" });
    t.value = L.texte ?? JSON.stringify(L.cfg, null, 2);
    t.oninput = () => { L.texte = t.value; };
    const lire = () => { try { return JSON.parse(t.value); } catch (e) { throw new Error("JSON illisible : " + e.message); } };
    return h("div", {}, t, h("div", { class: "ligne" },
      h("button", { onclick: async () => { try { await verifier(lire()); C.msg("Configuration valide.", true); } catch (e) { C.msg(e.message); } } }, "Vérifier"),
      h("button", { onclick: async () => { try { const c = lire(); await verifier(c); L.cfg = clone(c.logiciel || c); C.msg("Chargé dans les formulaires (pas encore enregistré).", true); maj(); } catch (e) { C.msg(e.message); } } }, "Charger dans les formulaires")));
  };

  C.sections.push({
    id: "logiciel", titre: "Logiciel", rendre: m => {
      C.nettoyer?.(); C.nettoyer = null;
      if (!L.meta) {
        m.append(h("p", { class: "doux" }, "Chargement…"));
        charger().then(() => C.afficher()).catch(e => m.replaceChildren(h("h2", {}, "Logiciel"), h("div", { class: "alerte" }, e.message)));
        return;
      }
      const enregistrer = async () => {
        try {
          const r = await C.api("POST", "/api/logiciel/enregistrer", { config: L.cfg });
          L.saved = r.config; L.cfg = clone(r.config); L.etat = r.moteur; L.texte = null;
          C.msg("Enregistré dans le fichier de l'utilisateur et rechargé à chaud.", true); C.afficher();
        } catch (e) { C.msg(e.message); }
      };
      m.append(...sansNul([
        h("datalist", { id: "dl-touches" }, L.meta.touches.map(t => h("option", { value: t }))),
        h("p", { class: "doux" }, "Règles que le matériel ne sait pas faire : profils par application, couches, appui court ou long, actions. Elles s'appliquent à l'ordinateur, pas au clavier ni à la souris eux-mêmes."),
        L.meta.alerte ? h("div", { class: "alerte" }, L.meta.alerte) : null,
        h("div", { class: "cartes" }, carteMoteur(), carteAuto()),
        h("h3", {}, "Règles"), sectionRegles(),
        h("h3", {}, "Applications où le moteur se met en pause"),
        h("p", { class: "doux", style: "margin:0" }, "Le moteur laisse tout passer dans ces applications (jeux avec anti-triche, par exemple)."),
        listeApps(L.cfg.pause_apps ||= [], maj),
        h("h3", {}, "Éditeur JSON"), editeurJson(),
        h("div", { class: "ligne barre-logi" },
          h("span", { class: sale() ? "alerte" : "doux", style: "margin:0;flex:1" }, sale() ? "Modifications non enregistrées : le moteur tourne encore avec l'ancienne configuration." : "Configuration enregistrée et chargée."),
          h("button", { disabled: !sale(), onclick: () => { L.cfg = clone(L.saved); maj(); } }, "Annuler les changements"),
          h("button", { class: "primaire", disabled: !sale(), onclick: enregistrer }, "Enregistrer et recharger"))]));
    },
  });
})();
