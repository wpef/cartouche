//! Clavier, interface de configuration (page d'usage 0x8C). Trames de 33 octets : rapport 0x52 (envoi)
//! ou 0x54 (réponse) puis 32 octets. Toute écriture est acquittée par `54 e4 08` (`54 e4 09` = refus).

use crate::keys::{self, Target};
use crate::transport::Transport;
use crate::{hex, Error, Result};
use serde::{Deserialize, Serialize};
use std::time::{Duration, Instant};

const OUT: u8 = 0x52;
const IN: u8 = 0x54;
const FRAME: usize = 33;

pub struct Keyboard<T> {
    t: T,
    /// Simulation : les écritures sont affichées et jamais envoyées.
    pub dry: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub enum Step {
    Down(u8),
    Up(u8),
    Wait(u16),
}

impl From<Step> for String {
    fn from(s: Step) -> String {
        match s {
            Step::Down(u) => format!("down:{}", keys::macro_usage_name(u)),
            Step::Up(u) => format!("up:{}", keys::macro_usage_name(u)),
            Step::Wait(ms) => format!("wait:{ms}"),
        }
    }
}

impl TryFrom<String> for Step {
    type Error = String;
    fn try_from(s: String) -> std::result::Result<Step, String> {
        let (op, arg) = s.split_once(':').ok_or("pas de macro : down:<touche>, up:<touche> ou wait:<ms>")?;
        let key = |a: &str| keys::macro_usage(a).map_err(|e| e.to_string());
        match op {
            "down" => Ok(Step::Down(key(arg)?)),
            "up" => Ok(Step::Up(key(arg)?)),
            "wait" => arg.parse().map(Step::Wait).map_err(|_| format!("durée invalide : {arg}")),
            _ => Err(format!("pas inconnu : {s}")),
        }
    }
}

/// Une macro est attachée à une touche physique (`key`).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Macro {
    pub key: String,
    pub name: String,
    /// Nombre de répétitions ; absent = en boucle.
    pub cycles: Option<u8>,
    #[serde(default)]
    pub interval_ms: u16,
    pub steps: Vec<Step>,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct KeyboardState {
    pub profile: Option<String>,
    /// Touches réaffectées : nom de la touche physique -> cible.
    pub keys: std::collections::BTreeMap<String, String>,
    pub macros: Vec<Macro>,
}

fn frame(payload: &[u8]) -> Vec<u8> {
    let mut f = vec![0u8; FRAME];
    f[0] = OUT;
    f[1..1 + payload.len()].copy_from_slice(payload);
    f
}

/// Noms en UTF-16 gros-boutiste (observé sur le matériel par les sources citées).
fn encode_name(s: &str) -> Vec<u8> {
    s.encode_utf16().flat_map(u16::to_be_bytes).collect()
}
fn decode_name(b: &[u8]) -> String {
    let units: Vec<u16> = b.chunks_exact(2).map(|p| u16::from_be_bytes([p[0], p[1]])).take_while(|u| *u != 0).collect();
    String::from_utf16_lossy(&units)
}

impl<T: Transport> Keyboard<T> {
    pub fn new(t: T) -> Self {
        Keyboard { t, dry: false }
    }

    fn drain(&mut self) -> Result<()> {
        while !self.t.read(0)?.is_empty() {}
        Ok(())
    }

    /// Lit jusqu'à une trame qui commence par `prefix` ; les autres (`54 8a …` « rien à signaler ») sont ignorées.
    fn read_until(&mut self, prefix: &[u8], timeout_ms: u64) -> Result<Vec<u8>> {
        let end = Instant::now() + Duration::from_millis(timeout_ms);
        while Instant::now() < end {
            let r = self.t.read(50)?;
            if r.starts_with(prefix) {
                return Ok(r);
            }
        }
        Err(Error::Protocol(format!("pas de réponse {}", hex(prefix))))
    }

    /// Lecture : une commande, une réponse `54 <commande> …`.
    fn query(&mut self, payload: &[u8]) -> Result<Vec<u8>> {
        self.drain()?;
        self.t.write(&frame(payload))?;
        let mut r = self.read_until(&[IN, payload[0]], 600)?;
        r.resize(FRAME, 0);
        Ok(r)
    }

    fn wait_ack(&mut self, timeout_ms: u64) -> Result<()> {
        let end = Instant::now() + Duration::from_millis(timeout_ms);
        while Instant::now() < end {
            let r = self.t.read(50)?;
            if r.starts_with(&[IN, 0xe4, 0x08]) {
                return Ok(());
            }
            if r.starts_with(&[IN, 0xe4]) {
                return Err(Error::Protocol(format!("écriture refusée par le clavier : {}", hex(&r[..4.min(r.len())]))));
            }
        }
        Err(Error::Protocol("pas d'accusé de réception".into()))
    }

    /// Écriture : les trames partent à la suite, puis un accusé est attendu.
    fn write_acked(&mut self, payloads: &[Vec<u8>], timeout_ms: u64) -> Result<()> {
        if self.dry {
            for p in payloads {
                println!("[simulation] envoi {}", hex(&frame(p)));
            }
            return Ok(());
        }
        self.drain()?;
        for p in payloads {
            self.t.write(&frame(p))?;
            std::thread::sleep(Duration::from_millis(5));
        }
        self.wait_ack(timeout_ms)
    }

    /// « Attention » avant une écriture : le clavier répond `54 e4 08` ou `54 8a …`, on s'en moque.
    fn handshake(&mut self) -> Result<()> {
        if self.dry {
            println!("[simulation] envoi {}", hex(&frame(&[0x76, 0xff])));
            return Ok(());
        }
        self.drain()?;
        self.t.write(&frame(&[0x76, 0xff]))?;
        let _ = self.read_until(&[IN], 300);
        Ok(())
    }

    // ---- lectures -------------------------------------------------------------------------

    pub fn profile_name(&mut self) -> Result<Option<String>> {
        let mut r = self.query(&[0x80])?;
        if r[2] == 0 {
            return Ok(None);
        }
        // r[2] : longueur du morceau, r[3] : un autre morceau suit.
        let mut bytes = r[4..].to_vec();
        for _ in 0..2 {
            if r[3] == 0 {
                break;
            }
            r = self.query(&[0x80])?;
            bytes.extend_from_slice(&r[4..]);
        }
        Ok(Some(decode_name(&bytes)))
    }

    /// Codes matériels des touches réaffectées.
    pub fn mapped_keys(&mut self) -> Result<Vec<u8>> {
        let mut r = self.query(&[0x81, 0x00])?;
        let mut out = Vec::new();
        loop {
            // paires (touche, 07) ; 0 termine ; le dernier octet vaut 1 s'il reste des trames
            for p in r[2..FRAME - 1].chunks_exact(2) {
                if p[0] == 0 {
                    return Ok(out);
                }
                out.push(p[0]);
            }
            if r[FRAME - 1] != 1 {
                return Ok(out);
            }
            r = self.read_until(&[IN, 0x81], 600)?;
            r.resize(FRAME, 0);
        }
    }

    pub fn get_key(&mut self, hw: u8) -> Result<Target> {
        let r = self.query(&[0x83, hw])?;
        if r[2] != hw {
            return Err(Error::Protocol(format!("réponse pour la touche {:#04x}, attendu {hw:#04x}", r[2])));
        }
        Ok(Target(r[3..9].try_into().unwrap()))
    }

    pub fn macros(&mut self) -> Result<Vec<Macro>> {
        // liste des touches porteuses : 4 octets par entrée, 28 octets, 4 de plus si r[29] != 0
        let r = self.query(&[0x82])?;
        let mut list = r[2..30].to_vec();
        if r[30] != 0 {
            list.extend_from_slice(&self.query(&[0x82])?[2..6]);
        }
        let mut out = Vec::new();
        for entry in list.chunks_exact(4).take(8) {
            if entry[0] == 0 {
                break;
            }
            out.push(self.macro_of(entry[0])?);
        }
        Ok(out)
    }

    fn macro_of(&mut self, hw: u8) -> Result<Macro> {
        let mut name = Vec::new();
        for _ in 0..3 {
            let r = self.query(&[0x84, hw])?;
            name.extend_from_slice(&r[5..33]);
            if r[4] == 0 {
                break;
            }
        }
        let mut rec = Vec::new();
        while rec.len() < 609 {
            let r = self.query(&[0x86, hw])?;
            rec.extend_from_slice(&r[4..30]);
            if r[3] == 0 {
                break;
            }
        }
        decode_macro(hw, decode_name(&name), &rec)
    }

    pub fn read_state(&mut self) -> Result<KeyboardState> {
        let profile = self.profile_name()?;
        let mut keys = std::collections::BTreeMap::new();
        for hw in self.mapped_keys()? {
            keys.insert(keys::hw_name(hw), self.get_key(hw)?.to_string());
        }
        Ok(KeyboardState { profile, keys, macros: self.macros()? })
    }

    // ---- écritures ------------------------------------------------------------------------

    pub fn set_key(&mut self, hw: u8, target: Target) -> Result<()> {
        self.handshake()?;
        let mut p = vec![0xfa, 0x03, 0x0c, 0x00, 0xaa, 0x09, 0x71, hw];
        p.extend_from_slice(&target.0);
        self.write_acked(&[p], 1500)?;
        self.write_acked(&[vec![0x76, 0xa5]], 1500)
    }

    /// Nomme le profil courant : c'est ce qui l'enregistre dans le clavier.
    pub fn create_profile(&mut self, name: &str) -> Result<()> {
        let n = encode_name(name);
        if n.is_empty() || n.len() > 28 {
            return Err(Error::Input("nom de profil : 1 à 14 caractères".into()));
        }
        self.handshake()?;
        let mut p = vec![0x70, n.len() as u8, 0];
        p.extend_from_slice(&n);
        self.write_acked(&[p], 1500)
    }

    /// Supprime le profil courant et ses affectations.
    pub fn delete_profile(&mut self) -> Result<()> {
        self.write_acked(&[vec![0x70]], 1500)
    }

    pub fn write_macro(&mut self, m: &Macro) -> Result<()> {
        let hw = keys::hw_code(&m.key)?;
        let name = macro_name_frames(hw, &encode_name(&m.name))?;
        let body = macro_frames(hw, m)?;
        self.write_acked(&name, 4000)?;
        self.write_acked(&body, 4000)
    }
}

fn encode_steps(m: &Macro) -> Vec<u8> {
    let mut d = Vec::new();
    for s in &m.steps {
        d.extend_from_slice(&match *s {
            Step::Down(u) => [if keys::is_macro_modifier(u) { 0x83 } else { 0x81 }, u, 0],
            Step::Up(u) => [if keys::is_macro_modifier(u) { 0x03 } else { 0x01 }, u, 0],
            Step::Wait(ms) => [0x0f, ms as u8, (ms >> 8) as u8],
        });
    }
    if m.interval_ms > 0 || m.steps.len() > 1 {
        // entrée de délai final ; le quatrième octet gonfle la longueur comme dans l'application d'origine
        d.extend_from_slice(&[0x0f, m.interval_ms as u8, (m.interval_ms >> 8) as u8, 0]);
    }
    d
}

/// Trames d'écriture du corps d'une macro (commande 0x76), d'après retro87-configurator.
fn macro_frames(hw: u8, m: &Macro) -> Result<Vec<Vec<u8>>> {
    let data = encode_steps(m);
    if data.len() > 1000 {
        return Err(Error::Input("macro trop longue".into()));
    }
    let len = data.len();
    let mut first = vec![0u8; 32];
    first[0] = 0x76;
    first[1] = hw;
    first[6] = 1;
    match m.cycles {
        None => first[8] = 0x20,
        Some(c) => first[7] = c,
    }
    first[9] = (len / 3) as u8;
    let mut frames = Vec::new();
    if len < 0x16 {
        first[5] = 0x1a;
        first[10..10 + len].copy_from_slice(&data);
        return Ok(vec![first]);
    }
    first[2] = 1;
    first[5] = 0x19;
    first[10..31].copy_from_slice(&data[..21]);
    frames.push(first);
    let mut cur = 21;
    while cur < len {
        let mut c = vec![0u8; 32];
        c[0] = 0x76;
        c[1] = hw;
        let n = (len - cur).min(0x18);
        c[2] = u8::from(len - cur > 0x18);
        c[5] = n as u8;
        let off = cur + 4; // décalage dans l'enregistrement, 2 octets
        c[3] = off as u8;
        c[4] = (off >> 8) as u8;
        c[6..6 + n].copy_from_slice(&data[cur..cur + n]);
        frames.push(c);
        cur += n;
    }
    Ok(frames)
}

/// Nom de macro (commande 0x74), morceaux de 28 octets.
fn macro_name_frames(hw: u8, name: &[u8]) -> Result<Vec<Vec<u8>>> {
    if name.is_empty() || name.len() > 56 {
        return Err(Error::Input("nom de macro : 1 à 28 caractères".into()));
    }
    let chunks: Vec<&[u8]> = name.chunks(28).collect();
    Ok(chunks
        .iter()
        .enumerate()
        .map(|(i, c)| {
            let mut f = vec![0u8; 32];
            f[0] = 0x74;
            f[1] = hw;
            f[2] = c.len() as u8;
            f[3] = u8::from(i + 1 < chunks.len());
            f[4..4 + c.len()].copy_from_slice(c);
            f
        })
        .collect())
}

fn decode_macro(hw: u8, name: String, rec: &[u8]) -> Result<Macro> {
    let bad = || Error::Protocol("enregistrement de macro trop court".into());
    let (cycles_b, flag, count) = (*rec.get(1).ok_or_else(bad)?, *rec.get(2).ok_or_else(bad)?, *rec.get(3).ok_or_else(bad)? as usize);
    let entry = |i: usize| rec.get(4 + 3 * i..7 + 3 * i);
    let mut steps = Vec::new();
    let mut interval_ms = 0;
    for i in 0..count {
        let e = entry(i).ok_or_else(bad)?;
        match e[0] {
            0x0f if i + 1 == count => interval_ms = u16::from_le_bytes([e[1], e[2]]),
            0x0f => steps.push(Step::Wait(u16::from_le_bytes([e[1], e[2]]))),
            0x81 | 0x83 => steps.push(Step::Down(e[1])),
            0x01 | 0x03 => steps.push(Step::Up(e[1])),
            _ => {}
        }
    }
    Ok(Macro {
        key: keys::hw_name(hw),
        name,
        cycles: if flag == 0x20 { None } else { Some(cycles_b) },
        interval_ms,
        steps,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::transport::Mock;

    fn rx(hexs: &str) -> Vec<u8> {
        let mut v: Vec<u8> = hexs.split_whitespace().map(|b| u8::from_str_radix(b, 16).unwrap()).collect();
        v.resize(33, 0);
        v
    }
    fn kb(replies: &[&str]) -> Keyboard<Mock> {
        let mut m = Mock::default();
        m.replies = replies.iter().map(|r| rx(r)).collect();
        Keyboard::new(m)
    }

    #[test]
    fn profil_absent_trame_reelle() {
        // docs/sonde-lot0.md, clavier en câble
        assert_eq!(kb(&["54 80 00 00"]).profile_name().unwrap(), None);
    }

    #[test]
    fn profil_nomme_exemple_goncalor() {
        let r = "54 80 10 00 00 70 00 72 00 6f 00 66 00 69 00 6c 00 65 00 31";
        assert_eq!(kb(&[r]).profile_name().unwrap().as_deref(), Some("profile1"));
    }

    #[test]
    fn aucune_touche_reaffectee_trame_reelle() {
        assert!(kb(&["54 81 00 00"]).mapped_keys().unwrap().is_empty());
    }

    #[test]
    fn touches_reaffectees_sur_deux_trames() {
        let a = format!("54 81 04 07 05 07 {} 01", "00 ".repeat(25).trim_end());
        let mut a = rx(&a);
        a[32] = 1;
        let b = rx("54 81 29 07");
        let mut k = kb(&[]);
        k.t.replies = [a, b].into();
        assert_eq!(k.mapped_keys().unwrap(), vec![4, 5, 0x29]);
    }

    #[test]
    fn affectation_lue() {
        let t = kb(&["54 83 04 07 00 05"]).get_key(4).unwrap();
        assert_eq!(t, Target::parse("b").unwrap());
        assert_eq!(kb(&["54 83 04 00 00"]).get_key(4).unwrap().to_string(), "default");
    }

    #[test]
    fn trame_d_affectation_identique_a_goncalor() {
        let mut k = kb(&["54 e4 08", "54 e4 08", "54 e4 08"]);
        k.set_key(0x29, Target([7, 0, 4, 0, 0, 0])).unwrap();
        assert_eq!(k.t.sent[0], rx("52 76 ff"));
        assert_eq!(k.t.sent[1], rx("52 fa 03 0c 00 aa 09 71 29 07 00 04"));
        assert_eq!(k.t.sent[2], rx("52 76 a5"));
    }

    #[test]
    fn nom_de_profil_trame_goncalor() {
        let mut k = kb(&["54 e4 08", "54 e4 08"]);
        k.create_profile("profile1").unwrap();
        assert_eq!(k.t.sent[1], rx("52 70 10 00 00 70 00 72 00 6f 00 66 00 69 00 6c 00 65 00 31"));
    }

    #[test]
    fn refus_du_clavier() {
        assert!(kb(&["54 e4 09"]).delete_profile().is_err());
    }

    #[test]
    fn simulation_n_envoie_rien() {
        let mut k = kb(&[]);
        k.dry = true;
        k.set_key(0x6c, Target::parse("f13").unwrap()).unwrap();
        k.delete_profile().unwrap();
        assert!(k.t.sent.is_empty());
    }

    #[test]
    fn rapport_b2_refuse() {
        let mut m = Mock::default();
        assert!(matches!(m.write(&[0xB2, 0xAA]), Err(Error::Refused(_))));
    }

    #[test]
    fn macro_aller_retour() {
        let m = Macro {
            key: "k1".into(),
            name: "ab".into(),
            cycles: Some(2),
            interval_ms: 20,
            steps: vec![Step::Down(4), Step::Up(4), Step::Wait(50), Step::Down(0xe1), Step::Up(0xe1)],
        };
        // 5 pas + délai final = 6 entrées, 19 octets : une seule trame
        let frames = macro_frames(0x74, &m).unwrap();
        assert_eq!(frames.len(), 1);
        assert_eq!((frames[0][..2].to_vec(), frames[0][5], frames[0][7], frames[0][9]), (vec![0x76, 0x74], 0x1a, 2, 6));
        // reconstitue l'enregistrement tel que la lecture le rend
        let mut rec = vec![1, 2, 0, 6];
        rec.extend(encode_steps(&m));
        assert_eq!(decode_macro(0x74, "ab".into(), &rec).unwrap(), m);
    }

    #[test]
    fn macro_longue_en_deux_trames() {
        let steps = (0..5).flat_map(|_| [Step::Down(4), Step::Up(4)]).collect();
        let m = Macro { key: "k1".into(), name: "x".into(), cycles: None, interval_ms: 0, steps };
        // 10 pas + délai final : 34 octets ; 21 dans la première trame, 13 dans la seconde à l'offset 25
        let f = macro_frames(0x74, &m).unwrap();
        assert_eq!(f.len(), 2);
        assert_eq!((f[0][2], f[0][5], f[0][8], f[0][9]), (1, 0x19, 0x20, 11));
        assert_eq!((f[1][2], f[1][3], f[1][5]), (0, 25, 13));
    }

    #[test]
    fn nom_de_macro_en_deux_morceaux() {
        let f = macro_name_frames(0x74, &encode_name(&"x".repeat(20))).unwrap();
        assert_eq!(f.len(), 2);
        assert_eq!((f[0][2], f[0][3]), (28, 1));
        assert_eq!((f[1][2], f[1][3]), (12, 0));
    }
}
