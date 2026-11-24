use crate::{Error, Result};
use hidapi::{HidApi, HidDevice};

pub const VID: u16 = 0x2DC8;
/// Clavier en câble (`5209` : variante 108 touches, même protocole). Le récepteur 2,4 G (`5201`) reste muet.
pub const KEYBOARD_PIDS: [u16; 2] = [0x5200, 0x5209];
pub const KEYBOARD_USAGE_PAGE: u16 = 0x8C;
/// Adaptateur 2,4 G de la souris.
pub const MOUSE_PID: u16 = 0x5206;
pub const MOUSE_USAGE_PAGE: u16 = 0xFF00;

/// Une trame commence par l'identifiant de rapport, comme sur le fil.
pub trait Transport {
    fn write(&mut self, frame: &[u8]) -> Result<()>;
    /// Une trame lue, vide si rien n'arrive avant le délai.
    fn read(&mut self, timeout_ms: i32) -> Result<Vec<u8>>;
}

/// Garde-fou : le rapport 0xB2 est le canal de mise à jour du firmware. Jamais.
pub fn guard(frame: &[u8]) -> Result<()> {
    if frame.first() == Some(&0xB2) {
        return Err(Error::Refused("rapport 0xB2 (firmware)"));
    }
    Ok(())
}

pub struct Hid(HidDevice);

impl Transport for Hid {
    fn write(&mut self, frame: &[u8]) -> Result<()> {
        guard(frame)?;
        self.0.write(frame)?;
        Ok(())
    }
    fn read(&mut self, timeout_ms: i32) -> Result<Vec<u8>> {
        let mut buf = [0u8; 65];
        let n = self.0.read_timeout(&mut buf, timeout_ms)?;
        Ok(buf[..n].to_vec())
    }
}

/// Ce que l'énumération révèle, sans numéro de série ni adresse Bluetooth.
#[derive(Debug, Clone, serde::Serialize)]
pub struct DeviceInfo {
    pub pid: u16,
    pub interface: i32,
    pub usage_page: u16,
    pub usage: u16,
    pub product: String,
    /// Interface de configuration qu'on sait parler.
    pub configurable: bool,
}

pub fn list_devices() -> Result<Vec<DeviceInfo>> {
    let api = HidApi::new()?;
    let mut v: Vec<DeviceInfo> = api
        .device_list()
        .filter(|d| d.vendor_id() == VID)
        .map(|d| DeviceInfo {
            pid: d.product_id(),
            interface: d.interface_number(),
            usage_page: d.usage_page(),
            usage: d.usage(),
            product: d.product_string().unwrap_or_default().to_string(),
            configurable: is_keyboard(d.product_id(), d.usage_page()) || is_mouse(d.product_id(), d.usage_page()),
        })
        .collect();
    v.sort_by_key(|d| (d.pid, d.interface, d.usage_page));
    Ok(v)
}

fn is_keyboard(pid: u16, up: u16) -> bool {
    KEYBOARD_PIDS.contains(&pid) && up == KEYBOARD_USAGE_PAGE
}
fn is_mouse(pid: u16, up: u16) -> bool {
    pid == MOUSE_PID && up == MOUSE_USAGE_PAGE
}

fn open(pick: impl Fn(u16, u16) -> bool, what: &str) -> Result<Hid> {
    let api = HidApi::new()?;
    let info = api
        .device_list()
        .find(|d| d.vendor_id() == VID && pick(d.product_id(), d.usage_page()))
        .ok_or_else(|| Error::Device(format!("{what} introuvable (clavier : câble USB, interrupteur sur OFF ; souris : adaptateur 2,4 G)")))?;
    Ok(Hid(info.open_device(&api)?))
}

pub fn open_keyboard() -> Result<Hid> {
    open(is_keyboard, "clavier")
}
pub fn open_mouse() -> Result<Hid> {
    open(is_mouse, "souris")
}

/// Transport de test : rejoue des réponses, garde ce qui a été envoyé.
#[derive(Default)]
pub struct Mock {
    pub sent: Vec<Vec<u8>>,
    pub replies: std::collections::VecDeque<Vec<u8>>,
}
impl Transport for Mock {
    fn write(&mut self, frame: &[u8]) -> Result<()> {
        guard(frame)?;
        self.sent.push(frame.to_vec());
        Ok(())
    }
    fn read(&mut self, timeout_ms: i32) -> Result<Vec<u8>> {
        // un délai nul sert à vider le tampon : rien d'ancien dans le jeu d'essai
        Ok(if timeout_ms == 0 { vec![] } else { self.replies.pop_front().unwrap_or_default() })
    }
}
