//! Souris Retro R8 via l'adaptateur 2,4 G, interface de configuration (page d'usage 0xFF00).
//! Rapports de 64 octets sans identifiant (sous hidapi : un `00` devant à l'envoi). Chaque commande
//! reçoit deux paquets : un écho qui commence par `21` (ignoré), puis la vraie réponse `01 06 <cmd> 11 …`.

use crate::keys;
use crate::transport::Transport;
use crate::{hex, Error, Result};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::time::{Duration, Instant};

const PACKET: usize = 64;
/// Boutons lus : 0 gauche, 1 droit, 2 milieu, 3 latéral, 4 supplémentaire, 5 (DPI ?, non confirmé).
pub const BUTTONS: u8 = 6;

pub struct Mouse<T> {
    t: T,
    /// Simulation : les écritures sont affichées et jamais envoyées.
    pub dry: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Dpi {
    /// Palier courant (à partir de 0).
    pub index: u8,
    pub current: u16,
    pub stages: Vec<u16>,
}

/// Lecture batterie : sur le matériel testé la réponse est vide (`known: false`), le sens des octets vient de r8-rs.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Battery {
    pub percent: u8,
    pub charging: bool,
    pub known: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct MouseState {
    pub dpi: Dpi,
    /// Numéro de bouton -> action (`left`, `back`, `code:7`…).
    pub buttons: BTreeMap<String, String>,
    pub battery: Battery,
}

impl<T: Transport> Mouse<T> {
    pub fn new(t: T) -> Self {
        Mouse { t, dry: false }
    }

    fn packet(body: &[u8]) -> Vec<u8> {
        let mut f = vec![0u8; PACKET + 1];
        f[1..1 + body.len()].copy_from_slice(body);
        f
    }

    fn query(&mut self, body: &[u8]) -> Result<Vec<u8>> {
        while !self.t.read(0)?.is_empty() {}
        self.t.write(&Self::packet(body))?;
        let end = Instant::now() + Duration::from_millis(500);
        while Instant::now() < end {
            let r = self.t.read(50)?;
            // body = 01 06 <commande> … ; l'écho commence par 21
            if r.len() >= 4 && r[..3] == body[..3] {
                return Ok(r);
            }
        }
        Err(Error::Protocol(format!("souris : pas de réponse à {}", hex(&body[..4.min(body.len())]))))
    }

    pub fn dpi(&mut self) -> Result<Dpi> {
        let r = self.query(&[0x01, 0x06, 0x12, 0x01])?;
        let count = r[4] as usize;
        if r.len() < 8 + 2 * count {
            return Err(Error::Protocol("réponse DPI trop courte".into()));
        }
        let le = |i: usize| u16::from_le_bytes([r[i], r[i + 1]]);
        Ok(Dpi { index: r[5], current: le(6), stages: (0..count).map(|i| le(8 + 2 * i)).collect() })
    }

    /// Valeur du micrologiciel pour un bouton (voir `keys::MOUSE_VALUES`).
    pub fn button(&mut self, n: u8) -> Result<u16> {
        let r = self.query(&[0x01, 0x06, 0x10, 0x01, 0x00, n])?;
        if r[5] != n {
            return Err(Error::Protocol(format!("réponse pour le bouton {}, attendu {n}", r[5])));
        }
        Ok(u16::from_le_bytes([r[6], r[7]]))
    }

    pub fn battery(&mut self) -> Result<Battery> {
        let r = self.query(&[0x01, 0x06, 0x1a, 0x01])?;
        Ok(Battery { percent: r[4].min(100), charging: r[5] & 1 != 0, known: r[4] != 0 || r[5] != 0 })
    }

    pub fn read_state(&mut self) -> Result<MouseState> {
        let mut buttons = BTreeMap::new();
        for n in 0..BUTTONS {
            buttons.insert(n.to_string(), keys::mouse_value_name(self.button(n)?));
        }
        Ok(MouseState { dpi: self.dpi()?, buttons, battery: self.battery()? })
    }

    /// Écrit l'affectation d'un bouton puis la relit ; un second essai est permis (r8-rs).
    pub fn set_button(&mut self, n: u8, value: u16) -> Result<()> {
        if n >= BUTTONS {
            return Err(Error::Input(format!("bouton {n} : 0 à {}", BUTTONS - 1)));
        }
        let body = [0x01, 0x06, 0x10, 0x04, 0x00, n, value as u8, (value >> 8) as u8];
        if self.dry {
            println!("[simulation] envoi 00 {}", hex(&Self::packet(&body)[1..]));
            return Ok(());
        }
        for _ in 0..2 {
            while !self.t.read(0)?.is_empty() {}
            self.t.write(&Self::packet(&body))?;
            std::thread::sleep(Duration::from_millis(60));
            if self.button(n)? == value {
                return Ok(());
            }
        }
        Err(Error::Verify(format!("bouton {n} : la relecture ne donne pas {value}")))
    }

    // Aucune de ces commandes n'est documentée : on ne les invente pas.
    pub fn set_dpi(&mut self, _stages: &[u16]) -> Result<()> {
        Err(Error::Unsupported("écriture des DPI"))
    }
    pub fn set_polling_rate(&mut self, _hz: u16) -> Result<()> {
        Err(Error::Unsupported("fréquence de scrutation"))
    }
    pub fn set_lift_off(&mut self, _mm: u8) -> Result<()> {
        Err(Error::Unsupported("distance de décollage"))
    }
    pub fn set_wheel(&mut self, _setting: u8) -> Result<()> {
        Err(Error::Unsupported("réglage de la molette"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::transport::Mock;

    fn rx(hexs: &str) -> Vec<u8> {
        let mut v: Vec<u8> = hexs.split_whitespace().map(|b| u8::from_str_radix(b, 16).unwrap()).collect();
        v.resize(64, 0);
        v
    }
    fn mouse(replies: &[&str]) -> Mouse<Mock> {
        let mut m = Mock::default();
        m.replies = replies.iter().map(|r| rx(r)).collect();
        Mouse::new(m)
    }

    #[test]
    fn dpi_trame_reelle() {
        // docs/sonde-lot0.md : écho 21 puis réponse
        let mut m = mouse(&["21 06 12 01", "01 06 12 11 06 03 60 09 20 03 b0 04 40 06 60 09 80 0c 00 19"]);
        let d = m.dpi().unwrap();
        assert_eq!((d.index, d.current), (3, 2400));
        assert_eq!(d.stages, vec![800, 1200, 1600, 2400, 3200, 6400]);
        assert_eq!(m.t.sent[0][..5], [0, 1, 6, 0x12, 1]);
    }

    #[test]
    fn boutons_trames_reelles() {
        assert_eq!(mouse(&["21 06 10 01 00 03", "01 06 10 11 00 03 05"]).button(3).unwrap(), 5);
        assert_eq!(mouse(&["01 06 10 11 01 04 04"]).button(4).unwrap(), 4);
        assert_eq!(keys::mouse_value_name(5), "back");
    }

    #[test]
    fn batterie_vide_est_inconnue() {
        assert!(!mouse(&["01 06 1a 11 00 00"]).battery().unwrap().known);
    }

    #[test]
    fn ecriture_bouton_relue() {
        let mut m = mouse(&["01 06 10 11 00 03 05"]);
        m.set_button(3, 5).unwrap();
        // 00 + 01 06 10 04 00 <btn> <lo> <hi>
        assert_eq!(m.t.sent[0][..9], [0, 1, 6, 0x10, 4, 0, 3, 5, 0]);
        assert!(mouse(&["01 06 10 11 00 03 04", "01 06 10 11 00 03 04"]).set_button(3, 5).is_err());
    }

    #[test]
    fn non_documente() {
        assert!(matches!(mouse(&[]).set_dpi(&[800]), Err(Error::Unsupported(_))));
        assert!(matches!(mouse(&[]).set_polling_rate(1000), Err(Error::Unsupported(_))));
    }
}
