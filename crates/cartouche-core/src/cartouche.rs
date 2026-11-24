//! Une « cartouche » : l'état lisible du clavier et de la souris, en JSON. Sert de profil, d'export et de sauvegarde.

use crate::keyboard::{Keyboard, KeyboardState};
use crate::keys::{self, Target};
use crate::mouse::{Mouse, MouseState};
use crate::transport::Transport;
use crate::{Error, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Cartouche {
    /// Version du format.
    pub cartouche: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub keyboard: Option<KeyboardState>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mouse: Option<MouseState>,
}

impl Cartouche {
    pub fn to_json(&self) -> Result<String> {
        Ok(serde_json::to_string_pretty(self)?)
    }
    pub fn from_json(s: &str) -> Result<Cartouche> {
        let c: Cartouche = serde_json::from_str(s)?;
        if c.cartouche != 1 {
            return Err(Error::Input(format!("version de cartouche inconnue : {}", c.cartouche)));
        }
        Ok(c)
    }
}

pub fn read_all<K: Transport, M: Transport>(kb: Option<&mut Keyboard<K>>, mouse: Option<&mut Mouse<M>>) -> Result<Cartouche> {
    Ok(Cartouche {
        cartouche: 1,
        keyboard: kb.map(|k| k.read_state()).transpose()?,
        mouse: mouse.map(|m| m.read_state()).transpose()?,
    })
}

/// Écrit la cartouche dans `dir` sous un nom daté (secondes depuis 1970) ; le dossier est créé au besoin.
pub fn save_backup(dir: &Path, c: &Cartouche) -> Result<PathBuf> {
    std::fs::create_dir_all(dir)?;
    let secs = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_secs());
    let mut path = dir.join(format!("sauvegarde-{secs}.json"));
    let mut n = 1;
    while path.exists() {
        path = dir.join(format!("sauvegarde-{secs}-{n}.json"));
        n += 1;
    }
    std::fs::write(&path, c.to_json()?)?;
    Ok(path)
}

/// Amène le clavier à l'état voulu, puis relit pour vérifier. Renvoie des remarques (ce qui n'a pas pu l'être).
pub fn apply_keyboard<T: Transport>(kb: &mut Keyboard<T>, want: &KeyboardState) -> Result<Vec<String>> {
    let mut notes = Vec::new();
    // noms normalisés : ce que la lecture rend
    let mut wanted = std::collections::BTreeMap::new();
    for (k, v) in &want.keys {
        wanted.insert(keys::hw_code(k)?, Target::parse(v)?);
    }
    if want.profile.is_none() && !wanted.is_empty() {
        return Err(Error::Input("des affectations sans nom de profil : un profil non nommé ne reste pas dans le clavier".into()));
    }
    let mut cur = kb.read_state()?;
    let current_keys = |s: &KeyboardState| -> Result<std::collections::BTreeMap<u8, Target>> {
        s.keys.iter().map(|(k, v)| Ok((keys::hw_code(k)?, Target::parse(v)?))).collect()
    };
    let mut have = current_keys(&cur)?;
    // Retirer une affectation = supprimer le profil, il n'existe pas d'autre commande documentée.
    if cur.profile.is_some() && (want.profile.is_none() || have.keys().any(|k| !wanted.contains_key(k))) {
        kb.delete_profile()?;
        cur.profile = None;
        have.clear();
    }
    if let Some(p) = &want.profile {
        if cur.profile.as_ref() != Some(p) {
            kb.create_profile(p)?;
        }
    }
    for (hw, t) in &wanted {
        if have.get(hw) != Some(t) {
            kb.set_key(*hw, *t)?;
        }
    }
    for m in &want.macros {
        if !cur.macros.contains(m) {
            kb.write_macro(m)?;
        }
    }
    if cur.macros.iter().any(|m| !want.macros.contains(m)) {
        notes.push("des macros du clavier ne sont pas dans la cartouche : aucune commande documentée pour les retirer".into());
    }
    if !kb.dry {
        let now = kb.read_state()?;
        if now.profile != want.profile || current_keys(&now)? != wanted {
            return Err(Error::Verify(format!("clavier relu : profil {:?}, touches {:?}", now.profile, now.keys)));
        }
    }
    Ok(notes)
}

pub fn apply_mouse<T: Transport>(m: &mut Mouse<T>, want: &MouseState) -> Result<Vec<String>> {
    let mut notes = Vec::new();
    let cur = m.read_state()?;
    if cur.dpi.stages != want.dpi.stages {
        notes.push("paliers DPI différents : écriture non documentée, ignorée".into());
    }
    for (n, v) in &want.buttons {
        let (b, value) = (n.parse::<u8>().map_err(|_| Error::Input(format!("bouton {n}")))?, keys::parse_mouse_value(v)?);
        if cur.buttons.get(n).map(|c| keys::parse_mouse_value(c)).transpose()? != Some(value) {
            m.set_button(b, value)?;
        }
    }
    Ok(notes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_aller_retour() {
        let json = r#"{ "cartouche": 1,
            "keyboard": { "profile": "p", "keys": { "superb": "f13", "capslock": "lctrl+c", "k1": "media:playpause" },
              "macros": [ { "key": "k2", "name": "m", "cycles": null, "steps": ["down:a", "up:a", "wait:30"] } ] },
            "mouse": null }"#;
        let c = Cartouche::from_json(json).unwrap();
        let again = Cartouche::from_json(&c.to_json().unwrap()).unwrap();
        assert_eq!(c, again);
        assert_eq!(c.keyboard.unwrap().macros[0].steps.len(), 3);
        assert!(Cartouche::from_json(r#"{"cartouche": 9}"#).is_err());
    }

    #[test]
    fn cibles() {
        for s in ["f13", "lctrl+c", "media:volup", "mouse:wheeldown", "none", "default", "lshift", "raw:0700680a0b0c"] {
            assert_eq!(Target::parse(s).unwrap().to_string(), s);
        }
        assert_eq!(Target::parse("f13").unwrap().0, [7, 0, 0x68, 0, 0, 0]);
        assert_eq!(Target::parse("media:playpause").unwrap().0, [0x0c, 0xcd, 0, 0, 0, 0]);
        assert!(Target::parse("zzz").is_err());
    }

    #[test]
    fn touches_physiques() {
        assert_eq!(keys::hw_code("superb").unwrap(), 0x6c);
        assert_eq!(keys::hw_code("a").unwrap(), 4);
        assert_eq!(keys::hw_name(0x29), "esc");
        assert_eq!(keys::hw_name(0x75), "k2");
        assert!(keys::hw_code("f13").is_err());
    }
}
