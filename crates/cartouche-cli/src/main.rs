//! `cartouche` : ligne de commande. Toute écriture est précédée d'une sauvegarde de l'état lu
//! (`captures/sauvegardes/` par défaut) ; `--dry-run` affiche les trames sans rien envoyer.

use cartouche_core::cartouche::{apply_keyboard, apply_mouse, read_all, save_backup, Cartouche};
use cartouche_core::keyboard::{Keyboard, Macro};
use cartouche_core::keys::{self, Target};
use cartouche_core::mouse::Mouse;
use cartouche_core::transport::{self, Hid};
use cartouche_core::{Error, Result};
use std::path::{Path, PathBuf};

const USAGE: &str = "cartouche [--dry-run] [--dir <sauvegardes>] <commande>
  list                          périphériques détectés
  dump                          tout lire, en JSON
  map <touche> <cible>          affecter (f13, lctrl+c, media:playpause, mouse:left, none)
  unmap <touche>                rendre à la touche sa fonction d'origine
  profile show|create <nom>|delete
  macro list|set <fichier.json>
  mouse show|button <n> <action>|dpi|rate|liftoff|wheel
  apply <fichier.json>          amener le matériel à l'état de la cartouche
  restore <sauvegarde.json>     idem, depuis une sauvegarde";

fn main() {
    if let Err(e) = run() {
        eprintln!("erreur : {e}");
        std::process::exit(1);
    }
}

fn take_flag(args: &mut Vec<String>, flag: &str) -> bool {
    let n = args.len();
    args.retain(|a| a != flag);
    args.len() != n
}

fn take_opt(args: &mut Vec<String>, opt: &str) -> Option<String> {
    let i = args.iter().position(|a| a == opt)?;
    (i + 1 < args.len()).then(|| {
        args.remove(i);
        args.remove(i)
    })
}

fn keyboard(dry: bool) -> Result<Keyboard<Hid>> {
    let mut k = Keyboard::new(transport::open_keyboard()?);
    k.dry = dry;
    Ok(k)
}

fn mouse(dry: bool) -> Result<Mouse<Hid>> {
    let mut m = Mouse::new(transport::open_mouse()?);
    m.dry = dry;
    Ok(m)
}

/// Sauvegarde l'état lu avant d'écrire (pas en simulation : rien n'est écrit).
fn backup(dir: &Path, dry: bool, kb: Option<&mut Keyboard<Hid>>, m: Option<&mut Mouse<Hid>>) -> Result<()> {
    if !dry {
        let path = save_backup(dir, &read_all(kb, m)?)?;
        eprintln!("sauvegarde : {}", path.display());
    }
    Ok(())
}

fn run() -> Result<()> {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let dry = take_flag(&mut args, "--dry-run");
    let dir = PathBuf::from(take_opt(&mut args, "--dir").unwrap_or_else(|| "captures/sauvegardes".into()));
    let a: Vec<&str> = args.iter().map(String::as_str).collect();
    let no_mouse = None::<&mut Mouse<Hid>>;
    let no_kb = None::<&mut Keyboard<Hid>>;
    match a.as_slice() {
        ["list"] => {
            for d in transport::list_devices()? {
                println!(
                    "{:04X} if{:<2} page {:#06x} usage {:#04x}  {}{}",
                    d.pid, d.interface, d.usage_page, d.usage, d.product, if d.configurable { "  [configurable]" } else { "" }
                );
            }
        }
        ["dump"] => {
            let mut k = keyboard(false).ok();
            let mut m = mouse(false).ok();
            if k.is_none() && m.is_none() {
                return Err(Error::Device("ni clavier ni souris configurable".into()));
            }
            println!("{}", read_all(k.as_mut(), m.as_mut())?.to_json()?);
        }
        ["map", key, target] => {
            let mut k = keyboard(dry)?;
            backup(&dir, dry, Some(&mut k), no_mouse)?;
            k.set_key(keys::hw_code(key)?, Target::parse(target)?)?;
        }
        ["unmap", key] => {
            let hw = keys::hw_code(key)?;
            let t = keys::default_target(hw).ok_or(Error::Unsupported("fonction d'origine inconnue : supprimer le profil"))?;
            let mut k = keyboard(dry)?;
            backup(&dir, dry, Some(&mut k), no_mouse)?;
            k.set_key(hw, t)?;
        }
        ["profile", "show"] => println!("{}", keyboard(false)?.profile_name()?.unwrap_or_else(|| "(aucun profil)".into())),
        ["profile", "create", name] => {
            let mut k = keyboard(dry)?;
            backup(&dir, dry, Some(&mut k), no_mouse)?;
            k.create_profile(name)?;
        }
        ["profile", "delete"] => {
            let mut k = keyboard(dry)?;
            backup(&dir, dry, Some(&mut k), no_mouse)?;
            k.delete_profile()?;
        }
        ["macro", "list"] => println!("{}", serde_json::to_string_pretty(&keyboard(false)?.macros()?)?),
        ["macro", "set", file] => {
            let m: Macro = serde_json::from_str(&std::fs::read_to_string(file)?)?;
            let mut k = keyboard(dry)?;
            backup(&dir, dry, Some(&mut k), no_mouse)?;
            k.write_macro(&m)?;
        }
        ["mouse", "show"] => println!("{}", serde_json::to_string_pretty(&mouse(false)?.read_state()?)?),
        ["mouse", "button", n, action] => {
            let mut m = mouse(dry)?;
            backup(&dir, dry, no_kb, Some(&mut m))?;
            m.set_button(n.parse().map_err(|_| Error::Input(format!("bouton {n}")))?, keys::parse_mouse_value(action)?)?;
        }
        ["mouse", "dpi", ..] => mouse(dry)?.set_dpi(&[])?,
        ["mouse", "rate", ..] => mouse(dry)?.set_polling_rate(0)?,
        ["mouse", "liftoff", ..] => mouse(dry)?.set_lift_off(0)?,
        ["mouse", "wheel", ..] => mouse(dry)?.set_wheel(0)?,
        ["apply", file] | ["restore", file] => {
            let want = Cartouche::from_json(&std::fs::read_to_string(file)?)?;
            let mut notes = Vec::new();
            if let Some(w) = &want.keyboard {
                let mut k = keyboard(dry)?;
                backup(&dir, dry, Some(&mut k), no_mouse)?;
                notes.extend(apply_keyboard(&mut k, w)?);
            }
            if let Some(w) = &want.mouse {
                let mut m = mouse(dry)?;
                backup(&dir, dry, no_kb, Some(&mut m))?;
                notes.extend(apply_mouse(&mut m, w)?);
            }
            for n in notes {
                eprintln!("note : {n}");
            }
        }
        _ => println!("{USAGE}"),
    }
    Ok(())
}
