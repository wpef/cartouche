"""Trames réelles (docs/sonde-lot0.md, protocol.txt de goncalor), sans matériel."""
import unittest

from cartouche import clavier as K
from cartouche import profil, souris as S
from cartouche import touches as T
from cartouche.transport import Erreur, Faux, NonPris, Refuse


def rx(h, n=33):
    return bytes.fromhex(h.replace(" ", "")).ljust(n, b"\0")


def clav(*reponses, dry=False):
    return K.Clavier(Faux(rx(r) for r in reponses), dry)


def sou(*reponses):
    return S.Souris(Faux(rx(r, 64) for r in reponses))


class Clavier(unittest.TestCase):
    def test_profil_absent_reel(self):
        self.assertIsNone(clav("54 80 00 00").nom_profil())

    def test_profil_nomme_goncalor(self):
        r = "54 80 10 00 00 70 00 72 00 6f 00 66 00 69 00 6c 00 65 00 31"
        self.assertEqual(clav(r).nom_profil(), "profile1")

    def test_aucune_touche_reelle(self):
        self.assertEqual(clav("54 81 00 00").touches_mappees(), [])

    def test_touches_sur_deux_trames(self):
        a = bytes([0x54, 0x81] + [x for i in range(15) for x in (4 + i, 7)] + [1])
        k = K.Clavier(Faux([a, rx("54 81 29 07")]))
        self.assertEqual(k.touches_mappees(), list(range(4, 19)) + [0x29])

    def test_affectation_lue(self):
        self.assertEqual(clav("54 83 04 07 00 05").lire_touche(4), T.cible("b"))
        self.assertEqual(T.cible_texte(clav("54 83 04 00 00").lire_touche(4)), "default")

    def test_trame_d_affectation_goncalor(self):
        k = clav("54 e4 08", "54 e4 08", "54 e4 08")
        k.affecter(0x29, T.cible("a"))
        self.assertEqual(k.t.envoye, [rx("52 76 ff"), rx("52 fa 03 0c 00 aa 09 71 29 07 00 04"), rx("52 76 a5")])

    def test_nom_de_profil_goncalor(self):
        k = clav("54 e4 08", "54 e4 08")
        k.creer_profil("profile1")
        self.assertEqual(k.t.envoye[1], rx("52 70 10 00 00 70 00 72 00 6f 00 66 00 69 00 6c 00 65 00 31"))

    def test_refus_du_clavier(self):
        with self.assertRaises(Erreur):
            clav("54 e4 09").supprimer_profil()

    def test_simulation_n_envoie_rien(self):
        k = clav(dry=True)
        k.affecter(0x6C, T.cible("f13"))
        k.supprimer_profil()
        self.assertEqual(k.t.envoye, [])

    def test_rapport_b2_refuse(self):
        with self.assertRaises(Refuse):
            Faux().ecrire(bytes([0xB2, 0xAA]))

    def test_macro_courte_aller_retour(self):
        m = {"key": "k1", "name": "ab", "cycles": 2, "interval_ms": 20,
             "steps": ["down:a", "up:a", "wait:50", "down:lshift", "up:lshift"]}
        f = K.trames_macro(0x74, m)
        self.assertEqual((len(f), f[0][:2], f[0][5], f[0][7], f[0][9]), (1, b"\x76\x74", 0x1A, 2, 6))
        rec = bytes([1, 2, 0, 6]) + K.corps_macro(m)
        self.assertEqual(K.decode_macro(0x74, "ab", rec), m)

    def test_macro_longue_deux_trames(self):
        m = {"key": "k1", "name": "x", "cycles": None, "steps": ["down:a", "up:a"] * 5}
        f = K.trames_macro(0x74, m)  # 34 octets : 21 puis 13 à l'offset 25
        self.assertEqual((len(f), f[0][2], f[0][5], f[0][8], f[0][9]), (2, 1, 0x19, 0x20, 11))
        self.assertEqual((f[1][2], f[1][3], f[1][5]), (0, 25, 13))

    def test_nom_de_macro_deux_morceaux(self):
        f = K.trames_nom_macro(0x74, "x" * 20)
        self.assertEqual([(p[2], p[3]) for p in f], [(28, 1), (12, 0)])


class Souris(unittest.TestCase):
    def test_dpi_reel(self):
        s = sou("21 06 12 01", "01 06 12 11 06 03 60 09 20 03 b0 04 40 06 60 09 80 0c 00 19")
        d = s.dpi()
        self.assertEqual((d["index"], d["current"], d["stages"]), (3, 2400, [800, 1200, 1600, 2400, 3200, 6400]))
        self.assertEqual(s.t.envoye[0][:5], bytes([0, 1, 6, 0x12, 1]))

    def test_boutons_reels(self):
        self.assertEqual(sou("21 06 10 01 00 03", "01 06 10 11 00 03 05").bouton(3), 5)
        self.assertEqual(sou("01 06 10 11 01 04 04").bouton(4), 4)
        self.assertEqual(T.nom_valeur_souris(5), "back")

    def test_batterie_vide_inconnue(self):
        self.assertFalse(sou("01 06 1a 11 00 00").batterie()["known"])

    def test_ecriture_relue(self):
        s = sou("01 06 10 11 00 03 05")
        s.affecter_bouton(3, 5)
        self.assertEqual(s.t.envoye[0][:9], bytes([0, 1, 6, 0x10, 4, 0, 3, 5, 0]))
        with self.assertRaises(Erreur):
            sou("01 06 10 11 00 03 04", "01 06 10 11 00 03 04").affecter_bouton(3, 5)

    def test_non_documente(self):
        with self.assertRaises(NonPris):
            sou().ecrire_dpi([800])
        with self.assertRaises(NonPris):
            sou().frequence_scrutation(1000)


class Tables(unittest.TestCase):
    def test_cibles(self):
        for s in ["f13", "lctrl+c", "media:volup", "mouse:wheeldown", "none", "default", "lshift", "raw:0700680a0b0c"]:
            self.assertEqual(T.cible_texte(T.cible(s)), s)
        self.assertEqual(T.cible("f13"), bytes([7, 0, 0x68, 0, 0, 0]))
        self.assertEqual(T.cible("media:playpause"), bytes([0x0C, 0xCD, 0, 0, 0, 0]))
        with self.assertRaises(Erreur):
            T.cible("zzz")

    def test_touches_physiques(self):
        self.assertEqual((T.hw_code("superb"), T.hw_code("a"), T.hw_nom(0x29), T.hw_nom(0x75)), (0x6C, 4, "esc", "k2"))
        with self.assertRaises(Erreur):
            T.hw_code("f13")


class Profil(unittest.TestCase):
    def test_json_aller_retour(self):
        import tempfile, pathlib
        c = {"cartouche": 1, "clavier": {"profil": "p", "touches": {"superb": "f13"}, "macros": []}}
        with tempfile.TemporaryDirectory() as d:
            p = profil.sauvegarder(c, d)
            self.assertEqual(profil.importer(p), c)
        with self.assertRaises(Erreur):
            profil.appliquer_clavier(clav(), {"profil": None, "touches": {"a": "b"}})

    def test_appliquer_relit_et_verifie(self):
        # état courant vide ; on veut profil p + superb -> f13 ; la relecture finale doit le confirmer
        ack = "54 e4 08"
        k = clav("54 80 00 00", "54 81 00 00", "54 82", ack, ack, ack, ack, ack,
                 "54 80 10 00 00 70", "54 81 6c 07", "54 83 6c 07 00 68", "54 82")
        profil.appliquer_clavier(k, {"profil": "p", "touches": {"superb": "f13"}, "macros": []})


if __name__ == "__main__":
    unittest.main()
