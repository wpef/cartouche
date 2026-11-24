//! Protocole HID du clavier 8BitDo Retro Mechanical et de la souris Retro R8.
//! Ce qui est écrit ici vient du matériel (docs/sonde-lot0.md) ou des sources citées dans NOTICE.md.

pub mod cartouche;
pub mod keyboard;
pub mod keys;
pub mod mouse;
pub mod transport;

use std::fmt;

#[derive(Debug)]
pub enum Error {
    /// Périphérique absent, ouverture ou E/S HID impossible.
    Device(String),
    /// Réponse inattendue ou absente.
    Protocol(String),
    /// Fonction non documentée : on ne l'invente pas.
    Unsupported(&'static str),
    /// Trame refusée par le garde-fou du transport.
    Refused(&'static str),
    /// Texte, JSON ou fichier invalide.
    Input(String),
    /// La relecture après écriture ne correspond pas.
    Verify(String),
}

pub type Result<T> = std::result::Result<T, Error>;

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Device(s) => write!(f, "périphérique : {s}"),
            Error::Protocol(s) => write!(f, "protocole : {s}"),
            Error::Unsupported(s) => write!(f, "non pris en charge (protocole non documenté) : {s}"),
            Error::Refused(s) => write!(f, "refusé : {s}"),
            Error::Input(s) => write!(f, "entrée invalide : {s}"),
            Error::Verify(s) => write!(f, "vérification échouée : {s}"),
        }
    }
}
impl std::error::Error for Error {}
impl From<hidapi::HidError> for Error {
    fn from(e: hidapi::HidError) -> Self {
        Error::Device(e.to_string())
    }
}
impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error::Input(e.to_string())
    }
}
impl From<serde_json::Error> for Error {
    fn from(e: serde_json::Error) -> Self {
        Error::Input(e.to_string())
    }
}

pub fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect::<Vec<_>>().join(" ")
}
