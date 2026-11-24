"""Tables : noms <-> codes matériels <-> codes HID, et la « cible » d'une touche.
Un code matériel (hw) désigne la touche physique ; une cible dit ce qu'elle envoie.
Cible = 6 octets : genre puis 5 octets. `07 mod touche` clavier (un seul modificateur),
`0c lo hi` multimédia, `01 masque 00 00 v h` souris, tout à zéro = rôle d'origine."""
from .transport import Erreur

NOMMEES = {
    "enter": 0x28, "esc": 0x29, "backspace": 0x2A, "tab": 0x2B, "space": 0x2C, "minus": 0x2D,
    "equal": 0x2E, "lbracket": 0x2F, "rbracket": 0x30, "backslash": 0x31, "semicolon": 0x33,
    "apostrophe": 0x34, "grave": 0x35, "comma": 0x36, "dot": 0x37, "slash": 0x38, "capslock": 0x39,
    "printscreen": 0x46, "scrolllock": 0x47, "pause": 0x48, "insert": 0x49, "home": 0x4A,
    "pageup": 0x4B, "delete": 0x4C, "end": 0x4D, "pagedown": 0x4E, "right": 0x4F, "left": 0x50,
    "down": 0x51, "up": 0x52, "numlock": 0x53, "kpslash": 0x54, "kpasterisk": 0x55,
    "kpminus": 0x56, "kpplus": 0x57, "kpenter": 0x58, "kp1": 0x59, "kp2": 0x5A, "kp3": 0x5B,
    "kp4": 0x5C, "kp5": 0x5D, "kp6": 0x5E, "kp7": 0x5F, "kp8": 0x60, "kp9": 0x61, "kp0": 0x62,
    "kpdot": 0x63, "app": 0x65,
}
MODS = {"lctrl": 0xE0, "lshift": 0xE1, "lalt": 0xE2, "lwin": 0xE3,
        "rctrl": 0xE4, "rshift": 0xE5, "ralt": 0xE6, "rwin": 0xE7}
# Codes matériels qui ne sont pas un code HID. A et B : boutons intégrés ; K1..K8 : externes (K2 à gauche, K1 à droite).
HW_SEUL = {"lctrl": 0x64, "lshift": 0x65, "lalt": 0x66, "lwin": 0x67, "rctrl": 0x68, "rshift": 0x69,
           "ralt": 0x6A, "rwin": 0x6B, "superb": 0x6C, "supera": 0x6D, "k7": 0x6E, "k8": 0x6F,
           "k5": 0x70, "k6": 0x71, "k3": 0x72, "k4": 0x73, "k1": 0x74, "k2": 0x75}
MEDIA = {"playpause": 0xCD, "next": 0xB5, "prev": 0xB6, "mute": 0xE2, "volup": 0xE9, "voldown": 0xEA,
         "mail": 0x18A, "calc": 0x192, "explorer": 0x223, "brightup": 0x6F, "brightdown": 0x70}
# nom -> (masque, molette verticale, molette horizontale), molette signée comme sur le fil
SOURIS = {"left": (1, 0, 0), "right": (2, 0, 0), "middle": (4, 0, 0), "button4": (8, 0, 0),
          "button5": (0x10, 0, 0), "doubleclick": (0x80, 0, 0), "wheelup": (0, 2, 0),
          "wheeldown": (0, 0xFE, 0), "wheelleft": (0, 0, 0xFE), "wheelright": (0, 0, 2)}
# Valeurs des boutons dans le micrologiciel de la souris (r8-rs)
BOUTONS_SOURIS = {"left": 1, "right": 2, "middle": 3, "forward": 4, "back": 5, "disabled": 0xFF}


def usage(nom):
    """Code HID d'une touche de clavier (pas un modificateur), ou None."""
    if len(nom) == 1 and "a" <= nom <= "z":
        return 4 + ord(nom) - 97
    if len(nom) == 1 and "1" <= nom <= "9":
        return 0x1E + ord(nom) - 49
    if nom == "0":
        return 0x27
    if nom[:1] == "f" and nom[1:].isdigit():
        n = int(nom[1:])
        if 1 <= n <= 12:
            return 0x3A + n - 1
        if 13 <= n <= 24:
            return 0x68 + n - 13  # norme HID ; goncalor donne 0x76.. (autre modèle ?). À confirmer au matériel.
        return None
    return NOMMEES.get(nom)


def nom_usage(u):
    for n in list(NOMMEES) + [chr(97 + i) for i in range(26)] + [str(i) for i in range(10)] + [f"f{i}" for i in range(1, 25)]:
        if usage(n) == u:
            return n
    return f"0x{u:02x}"


# Les deux sources (8bitdo-kbd-mapper, 8db-retro-config) donnent « menu » et « compose » comme alias du bouton A (0x6D) :
# le clavier n'a pas de touche Menu, c'est ce que le bouton A envoie d'origine. 0x65 est Maj gauche, pas Menu.
HW_ALIAS = {"menu": "supera", "compose": "supera", "app": "supera"}


def hw_code(nom):
    nom = HW_ALIAS.get(nom.lower(), nom.lower())
    if nom.startswith("0x"):
        return int(nom, 16)
    if nom in HW_SEUL:
        return HW_SEUL[nom]
    u = usage(nom)
    if u is None or u >= 0x64:
        raise Erreur(f"touche physique inconnue : {nom}")
    return u


def hw_nom(code):
    for n, c in HW_SEUL.items():
        if c == code:
            return n
    n = nom_usage(code)
    return n if code < 0x64 and not n.startswith("0x") else f"0x{code:02x}"


def cible_defaut(hw):
    """Ce que la touche envoie d'origine : sa propre fonction. Les Super Buttons : inconnu (None)."""
    if hw in HW_SEUL.values():
        n = hw_nom(hw)
        return bytes([7, MODS[n], 0, 0, 0, 0]) if n in MODS else None
    return bytes([7, 0, hw, 0, 0, 0])


def cible(texte):
    """'f13', 'lctrl+c', 'lshift', 'media:playpause', 'mouse:left', 'none', 'default', 'raw:<12 hex>'."""
    s = texte.strip().lower()
    mauvais = Erreur(f"cible inconnue : {texte}")
    if s == "default":
        return bytes(6)
    if s == "none":
        return bytes([7, 0, 0, 0, 0, 0])
    if s.startswith("media:"):
        if s[6:] not in MEDIA:
            raise mauvais
        c = MEDIA[s[6:]]
        return bytes([0x0C, c & 255, c >> 8, 0, 0, 0])
    if s.startswith("mouse:"):
        if s[6:] not in SOURIS:
            raise mauvais
        m, v, h = SOURIS[s[6:]]
        return bytes([1, m, 0, 0, v, h])
    if s.startswith("raw:"):
        try:
            b = bytes.fromhex(s[4:])
        except ValueError:
            raise mauvais
        if len(b) != 6:
            raise mauvais
        return b
    if "+" in s:
        m, k = s.split("+", 1)
        if m not in MODS or usage(k) is None:
            raise mauvais
        return bytes([7, MODS[m], usage(k), 0, 0, 0])
    if s in MODS:
        return bytes([7, MODS[s], 0, 0, 0, 0])
    if usage(s) is None:
        raise mauvais
    return bytes([7, 0, usage(s), 0, 0, 0])


def cible_texte(b):
    k, a, x, c, d, e = b
    inv_mods = {v: n for n, v in MODS.items()}
    if bytes(b) == bytes(6):
        return "default"
    if k == 7 and (c, d, e) == (0, 0, 0):
        if (a, x) == (0, 0):
            return "none"
        if a == 0:
            return nom_usage(x)
        if a in inv_mods:
            return inv_mods[a] if x == 0 else f"{inv_mods[a]}+{nom_usage(x)}"
    if k == 0x0C and (c, d, e) == (0, 0, 0):
        for n, v in MEDIA.items():
            if v == a | x << 8:
                return f"media:{n}"
    if k == 1 and (x, c) == (0, 0):
        for n, v in SOURIS.items():
            if v == (a, d, e):
                return f"mouse:{n}"
    return "raw:" + bytes(b).hex()


def usage_macro(nom):
    u = MODS.get(nom, usage(nom))
    if u is None:
        raise Erreur(f"touche de macro inconnue : {nom}")
    return u


def nom_usage_macro(u):
    for n, v in MODS.items():
        if v == u:
            return n
    return nom_usage(u)


def est_modificateur_macro(u):
    return u == 0xA6 or 0xE0 <= u <= 0xE7


def valeur_souris(texte):
    s = texte.strip().lower()
    if s.startswith("code:"):
        return int(s[5:])
    if s not in BOUTONS_SOURIS:
        raise Erreur(f"action souris inconnue : {texte}")
    return BOUTONS_SOURIS[s]


def nom_valeur_souris(v):
    for n, x in BOUTONS_SOURIS.items():
        if x == v:
            return n
    return f"code:{v}"
