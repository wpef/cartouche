"""API de l'interface, sur les périphériques simulés (mode démonstration) : aucun matériel."""
import http.client
import json
import tempfile
import threading
import unittest

from cartouche.ui import api
from cartouche.ui.serveur import Serveur


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = api.App(True, cls.tmp.name)
        cls.srv = Serveur(cls.app, 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def appel(self, methode, chemin, corps=None, jeton=True, hote=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        h = {"Host": hote or f"127.0.0.1:{self.port}"}
        if jeton:
            h["X-Jeton"] = self.srv.jeton
        c.request(methode, chemin, json.dumps(corps) if corps is not None else None, h)
        r = c.getresponse()
        data = r.read()
        c.close()
        try:
            return r.status, json.loads(data)
        except ValueError:
            return r.status, data

    def post(self, chemin, corps, **kw):
        return self.appel("POST", chemin, corps, **kw)


class Securite(Base):
    def test_mauvais_host_refuse(self):
        for h in ("evil.example", "127.0.0.1", "localhost:1", f"evil.example:{self.port}"):
            self.assertEqual(self.appel("GET", "/api/etat", hote=h)[0], 403, h)
            self.assertEqual(self.appel("GET", "/", hote=h)[0], 403, h)

    def test_host_localhost_accepte(self):
        self.assertEqual(self.appel("GET", "/api/etat", hote=f"localhost:{self.port}")[0], 200)

    def test_ecriture_sans_jeton_refusee(self):
        for chemin in ("/api/appliquer", "/api/diff", "/api/usine", "/api/restaurer", "/api/importer"):
            self.assertEqual(self.post(chemin, {}, jeton=False)[0], 403, chemin)
        self.assertEqual(self.app.maquettes["clavier"].etat()["profil"], None)

    def test_mauvais_jeton_refuse(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("POST", "/api/usine", "{}", {"Host": f"127.0.0.1:{self.port}", "X-Jeton": "x"})
        self.assertEqual(c.getresponse().status, 403)

    def test_page_porte_le_jeton(self):
        s, page = self.appel("GET", "/")
        self.assertEqual(s, 200)
        self.assertIn(self.srv.jeton.encode(), page)

    def test_pas_de_chemin_hors_static(self):
        for p in ("/static/../api.py", "/static/..%2fapi.py", "/static/api.py", "/%2e%2e/api.py"):
            self.assertEqual(self.appel("GET", p)[0], 404, p)

    def test_json_invalide(self):
        self.assertEqual(self.post("/api/diff", [1])[0], 400)


class Lectures(Base):
    def test_etat_demo(self):
        s, d = self.appel("GET", "/api/etat")
        self.assertTrue(d["demo"] and d["peripheriques"]["clavier"]["pret"] and not d["macros_ecriture"])

    def test_statuts_et_messages(self):
        ifs = lambda *p: [{"pid": a, "page": b} for a, b in p]
        self.assertEqual(api.statut(ifs((0x5200, 0x8C)))["clavier"]["statut"], "cable")
        r = api.statut(ifs((0x5201, 0x8C)))
        self.assertEqual(r["clavier"]["statut"], "recepteur")
        self.assertIn("interrupteur sur OFF", r["clavier"]["message"])
        self.assertEqual(api.statut([])["clavier"]["statut"], "absent")
        self.assertEqual(api.statut(ifs((0x5206, 0xFF00)))["souris"]["statut"], "adaptateur")
        self.assertEqual(api.statut(ifs((0x5205, 1)))["souris"]["statut"], "bluetooth")
        self.assertEqual(api.statut([])["souris"]["statut"], "absente")

    def test_catalogue_et_cible(self):
        self.assertIn("f13", self.appel("GET", "/api/catalogue")[1]["touches"])
        self.assertEqual(self.appel("GET", "/api/cible?texte=LCTRL%2BC")[1], {"texte": "lctrl+c"})
        self.assertEqual(self.appel("GET", "/api/cible?texte=nimporte")[0], 400)

    def test_souris(self):
        d = self.appel("GET", "/api/souris")[1]
        self.assertEqual(d["dpi"]["stages"][3], 2400)


class Ecriture(Base):
    def test_validation(self):
        for mauvais in ({"clavier": {"profil": "x" * 15, "touches": {}}},
                        {"clavier": {"profil": "p", "touches": {"nimporte": "f1"}}},
                        {"clavier": {"profil": "p", "touches": {"superb": "zzz"}}},
                        {"clavier": {"profil": 3}},
                        {"clavier": {"profil": "p", "macros": [{"key": "k1", "name": "m", "steps": ["bof"]}]}},
                        {"souris": {"boutons": {"9": "left"}}},
                        {"souris": {"boutons": {"0": "tir"}}},
                        {"souris": {"boutons": {"0": "code:999999"}}}):
            self.assertEqual(self.post("/api/diff", mauvais)[0], 400, mauvais)

    def test_touches_sans_profil_bloque(self):
        s, d = self.post("/api/diff", {"clavier": {"profil": None, "touches": {"superb": "f13"}}})
        self.assertTrue(d["bloque"])
        self.assertEqual(self.post("/api/appliquer", {"clavier": {"profil": None, "touches": {"superb": "f13"}}})[0], 409)

    def test_cycle_complet(self):
        brouillon = {"clavier": {"profil": "essai", "touches": {"superb": "f13", "a": "lctrl+c"}, "macros": []},
                     "souris": {"boutons": {"3": "forward"}}}
        s, d = self.post("/api/diff", brouillon)
        self.assertEqual(s, 200)
        self.assertTrue(d["a_ecrire"])
        self.assertIn("bouton B : d'origine → f13", [l["texte"] for l in d["lignes"]])
        # rien n'a été écrit par la simple comparaison
        self.assertIsNone(self.appel("GET", "/api/clavier")[1]["profil"])
        s, r = self.post("/api/appliquer", brouillon)
        self.assertEqual(s, 200, r)
        self.assertTrue(r["ecrit"])
        k = self.appel("GET", "/api/clavier")[1]
        self.assertEqual((k["profil"], k["touches"]), ("essai", {"superb": "f13", "a": "lctrl+c"}))
        self.assertEqual(self.appel("GET", "/api/souris")[1]["boutons"]["3"], "forward")
        # la sauvegarde d'avant l'écriture existe et contient l'état d'avant
        sv = self.appel("GET", "/api/sauvegardes")[1]["sauvegardes"]
        self.assertEqual(sv[0]["nom"], r["sauvegarde"])
        self.assertIsNone(sv[0]["profil"])
        # rien de plus à écrire
        self.assertFalse(self.post("/api/diff", brouillon)[1]["a_ecrire"])
        # retirer une touche : avertissement, puis l'autre reste
        moins = {"clavier": {"profil": "essai", "touches": {"a": "lctrl+c"}}}
        s, d = self.post("/api/diff", moins)
        self.assertTrue(d["avertissements"])
        self.assertEqual(self.post("/api/appliquer", moins)[0], 200)
        self.assertEqual(self.appel("GET", "/api/clavier")[1]["touches"], {"a": "lctrl+c"})
        # restauration de la sauvegarde initiale : retour au clavier vide
        self.assertEqual(self.post("/api/restaurer", {"nom": sv[-1]["nom"]})[0], 200)
        self.assertEqual(self.appel("GET", "/api/clavier")[1], {"profil": None, "touches": {}, "macros": []})

    def test_restaurer_nom_dangereux(self):
        for n in ("../x.json", "sauvegarde-../../x.json", "", None, "sauvegarde-20200101-000000.json"):
            self.assertEqual(self.post("/api/restaurer", {"nom": n})[0], 400, n)

    def test_macros_non_ecrites(self):
        m = {"key": "k1", "name": "copie", "cycles": None, "interval_ms": 0, "steps": ["down:lctrl", "down:c", "up:c", "up:lctrl"]}
        b = {"clavier": {"profil": None, "touches": {}, "macros": [m]}}
        s, d = self.post("/api/diff", b)
        self.assertTrue(d["lignes"][0]["ignore"])
        self.assertFalse(d["a_ecrire"])
        self.assertFalse(self.post("/api/appliquer", b)[1]["ecrit"])
        self.assertEqual(self.appel("GET", "/api/clavier")[1]["macros"], [])

    def test_import_et_usine(self):
        s, d = self.post("/api/importer", {"cartouche": {"cartouche": 1, "clavier": {"profil": "p", "touches": {"supera": "media:mute"}, "macros": []}}})
        self.assertEqual(d["clavier"]["touches"], {"supera": "media:mute"})
        self.assertEqual(self.post("/api/importer", {"cartouche": {"cartouche": 2}})[0], 400)
        self.assertEqual(self.post("/api/appliquer", d)[0], 200)
        self.assertEqual(self.post("/api/usine", {})[0], 400)  # sans confirmation
        self.assertEqual(self.appel("GET", "/api/clavier")[1]["profil"], "p")
        self.assertEqual(self.post("/api/usine", {"confirmer": True})[0], 200)
        self.assertEqual(self.appel("GET", "/api/clavier")[1], {"profil": None, "touches": {}, "macros": []})
        self.assertEqual(self.appel("GET", "/api/etat")[0], 200)


if __name__ == "__main__":
    unittest.main()
