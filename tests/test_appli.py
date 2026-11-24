"""Écran Logiciel (API), fichier de données et point d'entrée complet, en mode simulé : aucun matériel, aucun crochet, aucune icône."""
import json
import tempfile
import unittest
import urllib.request

from cartouche import appli, donnees, touches as T
from cartouche.transport import Erreur
from cartouche.ui import api

from .test_ui import Base

REGLE_F24 = {"profils": {"defaut": {"touches": {"f24": "f23"}}}, "pause_apps": ["jeu.exe"]}


class Logiciel(Base):
    def test_lecture(self):
        s, d = self.appel("GET", "/api/logiciel")
        self.assertEqual(s, 200)
        self.assertEqual((d["moteur"]["statut"], d["arret_urgence"]), ("arrete", "Ctrl+Alt+Pause"))
        self.assertIn("f13", d["touches"])
        self.assertIn("chrome.exe", self.appel("GET", "/api/applications")[1]["applications"])

    def test_jeton_et_hote_exiges(self):
        for c in ("/api/logiciel/valider", "/api/logiciel/enregistrer", "/api/logiciel/moteur", "/api/logiciel/auto"):
            self.assertEqual(self.post(c, {}, jeton=False)[0], 403, c)
            self.assertEqual(self.post(c, {}, hote="evil.example")[0], 403, c)

    def test_validation_refuse_sans_rien_changer(self):
        avant = self.appel("GET", "/api/logiciel")[1]["config"]
        for mauvais in ({"profils": {"p": {"touches": {"f13": "touche-inconnue"}}}}, {"profils": []}, {"profils": {"p": 3}},
                        {"commun": {"touches": {"f13": {"url": "file:///c:/x"}}}}, {"commun": {"touches": {"f13": {"couche": "nulle part"}}}},
                        [1], "x", None):
            self.assertEqual(self.post("/api/logiciel/valider", {"config": mauvais})[0], 400, mauvais)
            self.assertEqual(self.post("/api/logiciel/enregistrer", {"config": mauvais})[0], 400, mauvais)
        self.assertEqual(self.appel("GET", "/api/logiciel")[1]["config"], avant)

    def test_enregistrer_recharge_et_ecrit_le_fichier(self):
        s, r = self.post("/api/logiciel/enregistrer", {"config": REGLE_F24})
        self.assertEqual(s, 200, r)
        self.assertEqual(donnees.lire(self.app.donnees)["logiciel"], REGLE_F24)
        self.assertEqual(self.appel("GET", "/api/logiciel")[1]["config"], REGLE_F24)
        # une cartouche entière collée à la place de la section est ramenée à la section
        s, r = self.post("/api/logiciel/enregistrer", {"config": {"cartouche": 1, "logiciel": REGLE_F24}})
        self.assertEqual(r["config"], REGLE_F24)

    def test_cycle_du_moteur(self):
        statut = lambda a: self.post("/api/logiciel/moteur", {"action": a})[1]["statut"]
        self.assertEqual([statut(a) for a in ("demarrer", "pause", "reprendre", "arreter")], ["actif", "pause", "actif", "arrete"])
        self.assertEqual(self.post("/api/logiciel/moteur", {"action": "format"})[0], 400)

    def test_demarrage_auto_simule(self):
        self.assertTrue(self.post("/api/logiciel/auto", {"activer": True})[1]["auto"])
        self.assertFalse(self.post("/api/logiciel/auto", {"activer": False})[1]["auto"])
        self.assertEqual(self.post("/api/logiciel/auto", {"activer": "oui"})[0], 400)

    def test_import_avec_logiciel(self):
        s, d = self.post("/api/importer", {"cartouche": {"cartouche": 1, "logiciel": REGLE_F24}})
        self.assertEqual(d["logiciel"], REGLE_F24)
        self.assertEqual(self.post("/api/importer", {"cartouche": {"cartouche": 1, "logiciel": {"profils": {"p": {"apps": 3}}}}})[0], 400)

    def test_ecriture_materiel_memorisee(self):
        self.post("/api/appliquer", {"clavier": {"profil": "memo", "touches": {"superb": "f13"}, "macros": []}})
        c = donnees.lire(self.app.donnees)
        self.assertEqual((c["clavier"]["profil"], c["clavier"]["touches"]), ("memo", {"superb": "f13"}))
        self.post("/api/usine", {"confirmer": True})


class Donnees(unittest.TestCase):
    def test_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(donnees.lire(d), {"cartouche": 1})
            donnees.mettre(d, logiciel={"pause_apps": ["a.exe"]})
            donnees.mettre(d, clavier={"profil": None, "touches": {}, "macros": []})
            c = donnees.lire(d)
            self.assertEqual((c["logiciel"], c["clavier"]["profil"]), ({"pause_apps": ["a.exe"]}, None))
            (donnees.dossier(d) / donnees.NOM).write_text("pas du json")
            self.assertRaises(Erreur, donnees.lire, d)
            (donnees.dossier(d) / donnees.NOM).write_text('{"cartouche": 2}')
            self.assertRaises(Erreur, donnees.lire, d)

    def test_dossier_par_defaut(self):
        self.assertEqual(donnees.dossier().name, "Cartouche")

    def test_configuration_enregistree_refusee_n_empeche_pas_de_demarrer(self):
        with tempfile.TemporaryDirectory() as d:
            donnees.mettre(d, logiciel={"profils": {"p": {"touches": {"f1": "nimporte"}}}})
            a = api.App(True, d + "/s", d)
            self.assertIn("refusée", a.erreur_config)
            self.assertEqual(a.moteur.etat()["profil"], "defaut")


class Touches(unittest.TestCase):
    def test_menu_est_le_bouton_a(self):
        self.assertEqual({T.hw_code(n) for n in ("menu", "compose", "app", "supera")}, {0x6D})
        self.assertEqual(T.hw_code("lshift"), 0x65)


class Batterie(unittest.TestCase):
    def test_alerte_une_seule_fois_puis_rearme(self):
        b = lambda p, c=False: {"known": True, "percent": p, "charging": c}
        m, deja = appli.alerte_batterie(b(15), False)
        self.assertIn("15 %", m)
        self.assertEqual(appli.alerte_batterie(b(14), deja), (None, True))
        self.assertEqual(appli.alerte_batterie(b(25), deja), (None, True))  # entre les deux seuils : pas de réarmement
        self.assertEqual(appli.alerte_batterie(b(40), deja), (None, False))
        self.assertEqual(appli.alerte_batterie(b(10, True), False), (None, False))  # en charge
        self.assertEqual(appli.alerte_batterie({"known": False, "percent": 0, "charging": False}, False), (None, False))
        self.assertEqual(appli.alerte_batterie(None, True), (None, True))


class PointDEntree(unittest.TestCase):
    def test_application_complete_simulee(self):
        with tempfile.TemporaryDirectory() as d:
            x = appli.Appli(True, d, None, 0, navigateur=False, icone=False)
            x.demarrer()
            try:
                self.assertTrue(x.app.moteur.etat()["tourne"])
                with urllib.request.urlopen(x.url + "api/logiciel/etat") as r:
                    self.assertEqual(json.load(r)["statut"], "actif")
                self.assertEqual([e[0] for e in x._entrees()], ["ouvrir", "pause", "quitter"])
                x._pause_ou_reprise()
                self.assertFalse(x.app.moteur.etat()["actif"])
                self.assertIn("Reprendre", x._entrees()[1][1])
            finally:
                x.arreter()
            self.assertFalse(x.app.moteur.etat()["tourne"])
            x.arreter()  # idempotent

    def test_main_duree(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(appli.main(["--demo", "--donnees", d, "--port", "0", "--duree", "0.3", "--sans-navigateur", "--sans-icone"]), 0)

    def test_port_pris(self):
        with tempfile.TemporaryDirectory() as d:
            x = appli.Appli(True, d, None, 0, navigateur=False, icone=False)
            try:
                self.assertEqual(appli.main(["--demo", "--port", str(x.serveur.server_address[1]), "--duree", "0.1", "--sans-icone"]), 1)
            finally:
                x.serveur.server_close()


if __name__ == "__main__":
    unittest.main()
