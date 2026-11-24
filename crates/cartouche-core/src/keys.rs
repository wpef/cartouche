//! Tables des touches : noms <-> codes matériels <-> codes HID, et la valeur d'affectation (« cible »).
//! Un code matériel (`hw`) désigne la touche physique ; une cible dit ce qu'elle envoie.

use crate::{Error, Result};
use std::fmt;

const NAMED: &[(&str, u8)] = &[
    ("enter", 0x28), ("esc", 0x29), ("backspace", 0x2a), ("tab", 0x2b), ("space", 0x2c),
    ("minus", 0x2d), ("equal", 0x2e), ("lbracket", 0x2f), ("rbracket", 0x30), ("backslash", 0x31),
    ("semicolon", 0x33), ("apostrophe", 0x34), ("grave", 0x35), ("comma", 0x36), ("dot", 0x37),
    ("slash", 0x38), ("capslock", 0x39), ("printscreen", 0x46), ("scrolllock", 0x47), ("pause", 0x48),
    ("insert", 0x49), ("home", 0x4a), ("pageup", 0x4b), ("delete", 0x4c), ("end", 0x4d),
    ("pagedown", 0x4e), ("right", 0x4f), ("left", 0x50), ("down", 0x51), ("up", 0x52),
    ("numlock", 0x53), ("kpslash", 0x54), ("kpasterisk", 0x55), ("kpminus", 0x56), ("kpplus", 0x57),
    ("kpenter", 0x58), ("kp1", 0x59), ("kp2", 0x5a), ("kp3", 0x5b), ("kp4", 0x5c), ("kp5", 0x5d),
    ("kp6", 0x5e), ("kp7", 0x5f), ("kp8", 0x60), ("kp9", 0x61), ("kp0", 0x62), ("kpdot", 0x63),
    ("app", 0x65),
];

const MODS: &[(&str, u8)] = &[
    ("lctrl", 0xe0), ("lshift", 0xe1), ("lalt", 0xe2), ("lwin", 0xe3),
    ("rctrl", 0xe4), ("rshift", 0xe5), ("ralt", 0xe6), ("rwin", 0xe7),
];

/// Codes matériels qui ne sont pas un code HID : modificateurs, Super Buttons.
/// A et B : boutons intégrés ; K1..K8 : boutons externes (K2 à gauche, K1 à droite).
const HW_ONLY: &[(&str, u8)] = &[
    ("lctrl", 0x64), ("lshift", 0x65), ("lalt", 0x66), ("lwin", 0x67),
    ("rctrl", 0x68), ("rshift", 0x69), ("ralt", 0x6a), ("rwin", 0x6b),
    ("superb", 0x6c), ("supera", 0x6d), ("k7", 0x6e), ("k8", 0x6f),
    ("k5", 0x70), ("k6", 0x71), ("k3", 0x72), ("k4", 0x73), ("k1", 0x74), ("k2", 0x75),
];

const MEDIA: &[(&str, u16)] = &[
    ("playpause", 0x00cd), ("next", 0x00b5), ("prev", 0x00b6), ("mute", 0x00e2),
    ("volup", 0x00e9), ("voldown", 0x00ea), ("mail", 0x018a), ("calc", 0x0192),
    ("explorer", 0x0223), ("brightup", 0x006f), ("brightdown", 0x0070),
];

/// (nom, masque de boutons, molette verticale, molette horizontale) ; molette signée comme sur le fil.
const MOUSE: &[(&str, u8, u8, u8)] = &[
    ("left", 0x01, 0, 0), ("right", 0x02, 0, 0), ("middle", 0x04, 0, 0),
    ("button4", 0x08, 0, 0), ("button5", 0x10, 0, 0), ("doubleclick", 0x80, 0, 0),
    ("wheelup", 0, 0x02, 0), ("wheeldown", 0, 0xfe, 0), ("wheelleft", 0, 0, 0xfe), ("wheelright", 0, 0, 0x02),
];

/// Code HID d'une touche du clavier (pas un modificateur).
pub fn usage(name: &str) -> Option<u8> {
    let b = name.as_bytes();
    match b {
        [c @ b'a'..=b'z'] => return Some(4 + c - b'a'),
        [c @ b'1'..=b'9'] => return Some(0x1e + c - b'1'),
        [b'0'] => return Some(0x27),
        _ => {}
    }
    if let Some(n) = name.strip_prefix('f').and_then(|n| n.parse::<u8>().ok()) {
        return match n {
            1..=12 => Some(0x3a + n - 1),
            // F13..F24 suivent la norme HID (0x68..0x73) ; Aryaman73 l'a vérifié sur le matériel,
            // alors que la table de goncalor donne 0x76.. (probablement un autre modèle).
            13..=24 => Some(0x68 + n - 13),
            _ => None,
        };
    }
    NAMED.iter().find(|(n, _)| *n == name).map(|(_, u)| *u)
}

pub fn usage_name(u: u8) -> String {
    match u {
        4..=0x1d => ((b'a' + u - 4) as char).to_string(),
        0x1e..=0x26 => ((b'1' + u - 0x1e) as char).to_string(),
        0x27 => "0".into(),
        0x3a..=0x45 => format!("f{}", u - 0x3a + 1),
        0x68..=0x73 => format!("f{}", u - 0x68 + 13),
        _ => NAMED.iter().find(|(_, x)| *x == u).map_or_else(|| format!("0x{u:02x}"), |(n, _)| n.to_string()),
    }
}

fn modifier(name: &str) -> Option<u8> {
    MODS.iter().find(|(n, _)| *n == name).map(|(_, u)| *u)
}

fn modifier_name(m: u8) -> Option<&'static str> {
    MODS.iter().find(|(_, u)| *u == m).map(|(n, _)| *n)
}

/// Touche physique : nom (`capslock`, `superb`, `k1`) ou code (`0x6c`).
pub fn hw_code(name: &str) -> Result<u8> {
    let name = name.to_lowercase();
    if let Some(c) = name.strip_prefix("0x").and_then(|h| u8::from_str_radix(h, 16).ok()) {
        return Ok(c);
    }
    HW_ONLY
        .iter()
        .find(|(n, _)| *n == name)
        .map(|(_, c)| *c)
        .or_else(|| usage(&name).filter(|u| *u < 0x64))
        .ok_or_else(|| Error::Input(format!("touche physique inconnue : {name}")))
}

pub fn hw_name(code: u8) -> String {
    if let Some((n, _)) = HW_ONLY.iter().find(|(_, c)| *c == code) {
        return n.to_string();
    }
    let n = usage_name(code);
    if code < 0x64 && !n.starts_with("0x") { n } else { format!("0x{code:02x}") }
}

/// Ce que la touche envoie par défaut : sa propre fonction (un modificateur pour les modificateurs).
/// Les Super Buttons n'ont pas de défaut connu.
pub fn default_target(hw: u8) -> Option<Target> {
    match HW_ONLY.iter().find(|(_, c)| *c == hw) {
        Some((n, _)) => modifier(n).map(|m| Target([7, m, 0, 0, 0, 0])),
        None => Some(Target([7, 0, hw, 0, 0, 0])),
    }
}

/// Valeur d'affectation telle qu'elle voyage : 1 octet de genre puis 5 octets.
/// `07 mod touche` clavier (un seul modificateur), `0c lo hi` multimédia, `01 masque 00 00 v h` souris.
/// Tout à zéro : la touche garde son rôle d'origine.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Target(pub [u8; 6]);

impl Target {
    pub fn parse(s: &str) -> Result<Target> {
        let s = s.trim().to_lowercase();
        let bad = || Error::Input(format!("cible inconnue : {s}"));
        if s == "default" {
            return Ok(Target([0; 6]));
        }
        if s == "none" {
            return Ok(Target([7, 0, 0, 0, 0, 0]));
        }
        if let Some(n) = s.strip_prefix("media:") {
            let c = MEDIA.iter().find(|(m, _)| *m == n).ok_or_else(bad)?.1;
            return Ok(Target([0x0c, c as u8, (c >> 8) as u8, 0, 0, 0]));
        }
        if let Some(n) = s.strip_prefix("mouse:") {
            let m = MOUSE.iter().find(|m| m.0 == n).ok_or_else(bad)?;
            return Ok(Target([1, m.1, 0, 0, m.2, m.3]));
        }
        if let Some(h) = s.strip_prefix("raw:") {
            let v: Vec<u8> = (0..h.len() / 2).filter_map(|i| u8::from_str_radix(h.get(2 * i..2 * i + 2)?, 16).ok()).collect();
            return <[u8; 6]>::try_from(v).map(Target).map_err(|_| bad());
        }
        match s.split_once('+') {
            Some((m, k)) => Ok(Target([7, modifier(m).ok_or_else(bad)?, usage(k).ok_or_else(bad)?, 0, 0, 0])),
            None => match modifier(&s) {
                Some(m) => Ok(Target([7, m, 0, 0, 0, 0])),
                None => Ok(Target([7, 0, usage(&s).ok_or_else(bad)?, 0, 0, 0])),
            },
        }
    }
}

impl fmt::Display for Target {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let [k, a, b, c, d, e] = self.0;
        let named = match k {
            0 if self.0 == [0; 6] => Some("default".to_string()),
            7 if (c, d, e) == (0, 0, 0) => match (a, b) {
                (0, 0) => Some("none".into()),
                (0, _) => Some(usage_name(b)),
                (m, 0) => modifier_name(m).map(str::to_string),
                (m, _) => modifier_name(m).map(|m| format!("{m}+{}", usage_name(b))),
            },
            0x0c if (c, d, e) == (0, 0, 0) => {
                MEDIA.iter().find(|(_, v)| *v == u16::from_le_bytes([a, b])).map(|(n, _)| format!("media:{n}"))
            }
            1 if (b, c) == (0, 0) => MOUSE.iter().find(|m| (m.1, m.2, m.3) == (a, d, e)).map(|m| format!("mouse:{}", m.0)),
            _ => None,
        };
        match named {
            Some(n) => write!(f, "{n}"),
            None => write!(f, "raw:{}", self.0.iter().map(|x| format!("{x:02x}")).collect::<String>()),
        }
    }
}

/// Code d'une touche dans un pas de macro : HID, modificateurs compris.
pub fn macro_usage(name: &str) -> Result<u8> {
    modifier(name).or_else(|| usage(name)).ok_or_else(|| Error::Input(format!("touche de macro inconnue : {name}")))
}
pub fn macro_usage_name(u: u8) -> String {
    modifier_name(u).map_or_else(|| usage_name(u), str::to_string)
}
pub fn is_macro_modifier(u: u8) -> bool {
    u == 0xa6 || (0xe0..=0xe7).contains(&u)
}

/// Boutons de la souris (valeurs du micrologiciel, r8-rs). 0xff désactive.
pub const MOUSE_VALUES: &[(&str, u16)] =
    &[("left", 1), ("right", 2), ("middle", 3), ("forward", 4), ("back", 5), ("disabled", 0xff)];

pub fn mouse_value_name(v: u16) -> String {
    MOUSE_VALUES.iter().find(|(_, x)| *x == v).map_or_else(|| format!("code:{v}"), |(n, _)| n.to_string())
}
pub fn parse_mouse_value(s: &str) -> Result<u16> {
    let s = s.trim().to_lowercase();
    if let Some(n) = s.strip_prefix("code:") {
        return n.parse().map_err(|_| Error::Input(format!("code souris invalide : {s}")));
    }
    MOUSE_VALUES.iter().find(|(n, _)| *n == s).map(|(_, v)| *v).ok_or_else(|| Error::Input(format!("action souris inconnue : {s}")))
}
