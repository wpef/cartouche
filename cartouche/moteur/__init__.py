"""Moteur logiciel de Cartouche. Intégration : Service(config).demarrer() / arreter() / recharger() / etat()."""
from .logique import ErreurConfig, Moteur
from .service import Service, charger_config, demarrage_auto, demarrage_auto_actif

__all__ = ["ErreurConfig", "Moteur", "Service", "charger_config", "demarrage_auto", "demarrage_auto_actif"]
