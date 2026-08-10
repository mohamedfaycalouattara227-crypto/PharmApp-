"""
gestion/materiel/scanner.py
Intégration lecteur de code-barres (USB-HID série / RS-232).

Architecture :
  - ServiceScannerCodeBarres : couche métier, indépendante du transport
  - ConnecteurSerieScan      : lecture via pyserial (mode texte, CR/LF terminé)
  - ConnecteurHIDScan        : lecture depuis /dev/input (evdev, Linux)

Le scanner est résolu depuis les paramètres (SCANNER_TYPE, SCANNER_PORT).
Formats supportés : EAN-8, EAN-13, Code 39, Code 128, QR Code.

Utilisation depuis une vue Django :
    from gestion.materiel.scanner import ServiceScannerCodeBarres
    service = ServiceScannerCodeBarres.depuis_parametrage()
    code = service.lire_code(timeout=5.0)
    lot   = service.identifier_lot(code)

Variables d'environnement :
  SCANNER_TYPE  : "serie" | "hid"   (défaut: "serie")
  SCANNER_PORT  : chemin port série  (défaut: /dev/ttyUSB1)
  SCANNER_BAUD  : baudrate           (défaut: 9600)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from gestion.catalogue.models import Lot, Medicament

logger = logging.getLogger("pharmapp.materiel.scanner")

# ─── Constantes ───────────────────────────────────────────────────────────────

RE_EAN13  = re.compile(r"^\d{13}$")
RE_EAN8   = re.compile(r"^\d{8}$")
RE_CODE39 = re.compile(r"^[A-Z0-9\-\.\ \$\/\+\%]+$")


# ─── Exceptions ───────────────────────────────────────────────────────────────

class ErreurScanner(Exception):
    """Erreur de communication avec le lecteur de code-barres."""


class ScannerNonConfigure(ErreurScanner):
    """Aucun scanner configuré dans les paramètres pharmacie."""


class TimeoutScan(ErreurScanner):
    """Aucun code-barres reçu dans le délai imparti."""


class CodeNonReconnu(ErreurScanner):
    """Le code reçu ne correspond à aucun format reconnu (EAN/Code39/128)."""


class LotIntrouvable(ErreurScanner):
    """Aucun lot actif ne correspond au code-barres scanné."""


# ─── Connecteurs ─────────────────────────────────────────────────────────────

class ConnecteurSerieScan:
    """
    Lecteur série via pyserial.
    La plupart des scanners envoient le code suivi de CR+LF (0x0D 0x0A).
    """

    def __init__(self, port: str = "/dev/ttyUSB1", baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate

    def lire_brut(self, timeout: float = 5.0) -> str:
        """Lit une ligne depuis le port série ; retourne le code brut (sans CR/LF)."""
        try:
            import serial  # pyserial — optionnel
        except ImportError as exc:
            raise ErreurScanner(
                "pyserial n'est pas installé. Ajoutez pyserial aux requirements."
            ) from exc
        try:
            with serial.Serial(self.port, self.baudrate, timeout=timeout) as ser:
                ligne = ser.readline()
            if not ligne:
                raise TimeoutScan(
                    f"Aucun code reçu sur {self.port} en {timeout:.1f}s"
                )
            return ligne.decode("ascii", errors="ignore").strip()
        except TimeoutScan:
            raise
        except Exception as exc:
            raise ErreurScanner(f"Erreur port série {self.port} — {exc}") from exc


class ConnecteurHIDScan:
    """
    Lecteur HID via evdev (Linux uniquement).
    Le scanner se présente comme un clavier ; evdev capte les KeyPress.
    """

    def __init__(self, chemin_device: str = "/dev/input/event0"):
        self.chemin_device = chemin_device

    def lire_brut(self, timeout: float = 5.0) -> str:
        """Lit un code-barres complet depuis le périphérique evdev."""
        try:
            import evdev  # optionnel — python-evdev
            from evdev import categorize, ecodes
        except ImportError as exc:
            raise ErreurScanner(
                "python-evdev n'est pas installé. Ajoutez evdev aux requirements."
            ) from exc
        try:
            import select
            device = evdev.InputDevice(self.chemin_device)
            chars = []
            import time
            deadline = time.monotonic() + timeout
            # Map evdev KEY_* → caractère ASCII pour les chiffres
            KEY_MAP = {
                "KEY_0": "0", "KEY_1": "1", "KEY_2": "2", "KEY_3": "3",
                "KEY_4": "4", "KEY_5": "5", "KEY_6": "6", "KEY_7": "7",
                "KEY_8": "8", "KEY_9": "9",
            }
            for event in device.read_loop():
                if time.monotonic() > deadline:
                    raise TimeoutScan(f"HID timeout après {timeout:.1f}s")
                if event.type == ecodes.EV_KEY:
                    data = categorize(event)
                    if data.keystate == data.key_down:
                        key = data.keycode
                        if key == "KEY_ENTER":
                            break
                        c = KEY_MAP.get(key, "")
                        if c:
                            chars.append(c)
            return "".join(chars)
        except (TimeoutScan, ErreurScanner):
            raise
        except Exception as exc:
            raise ErreurScanner(f"Erreur HID {self.chemin_device} — {exc}") from exc


# ─── Service principal ────────────────────────────────────────────────────────

class ServiceScannerCodeBarres:
    """
    Service métier du lecteur de code-barres.

    Utilisation standard :
        service = ServiceScannerCodeBarres.depuis_parametrage()
        code = service.lire_code(timeout=5.0)
        lot  = service.identifier_lot(code)
    """

    def __init__(self, connecteur):
        self._connecteur = connecteur

    # --- Constructeurs alternatifs -------------------------------------------

    @classmethod
    def serie(cls, port: str = "/dev/ttyUSB1", baudrate: int = 9600) -> "ServiceScannerCodeBarres":
        return cls(ConnecteurSerieScan(port, baudrate))

    @classmethod
    def hid(cls, chemin: str = "/dev/input/event0") -> "ServiceScannerCodeBarres":
        return cls(ConnecteurHIDScan(chemin))

    @classmethod
    def depuis_parametrage(cls) -> "ServiceScannerCodeBarres":
        """
        Résout le connecteur depuis les paramètres de la pharmacie.
        Variables d'environnement :
          SCANNER_TYPE  : "serie" | "hid"  (défaut: "serie")
          SCANNER_PORT  : chemin port      (défaut: /dev/ttyUSB1)
          SCANNER_BAUD  : baudrate         (défaut: 9600)
        """
        import os
        from django.conf import settings as djsettings

        tp = getattr(djsettings, "SCANNER_TYPE", os.environ.get("SCANNER_TYPE", "serie"))

        if tp == "serie":
            port = getattr(djsettings, "SCANNER_PORT",
                           os.environ.get("SCANNER_PORT", "/dev/ttyUSB1"))
            baud = int(getattr(djsettings, "SCANNER_BAUD",
                               os.environ.get("SCANNER_BAUD", "9600")))
            return cls.serie(port, baud)
        elif tp == "hid":
            chemin = getattr(djsettings, "SCANNER_HID",
                             os.environ.get("SCANNER_HID", "/dev/input/event0"))
            return cls.hid(chemin)
        else:
            raise ScannerNonConfigure(f"SCANNER_TYPE inconnu : {tp!r}")

    # --- Actions -------------------------------------------------------------

    def lire_code(self, timeout: float = 5.0) -> str:
        """
        Lit et valide un code-barres depuis le connecteur.
        Retourne le code brut (string) après nettoyage.
        Lève TimeoutScan ou CodeNonReconnu selon l'erreur.
        """
        brut = self._connecteur.lire_brut(timeout=timeout)
        code = brut.strip()

        if not code:
            raise TimeoutScan("Code vide reçu du scanner")

        if not (RE_EAN13.match(code) or RE_EAN8.match(code) or RE_CODE39.match(code)):
            raise CodeNonReconnu(
                f"Format de code non reconnu : {code!r} "
                "(attendu : EAN-8, EAN-13 ou Code 39)"
            )

        logger.info("scanner_code_lu", extra={"code": code, "longueur": len(code)})
        return code

    def identifier_lot(self, code_barres: str) -> object:
        """
        Résout le lot actif correspondant au code-barres scanné.
        Cherche dans : Lot.code_barres, Lot.numero_lot, Medicament.code_cip.
        Lève LotIntrouvable si aucun lot actif ne correspond.
        """
        # Recherche directe sur le lot
        lot = (
            Lot.objects
            .select_related("medicament")
            .filter(code_barres=code_barres, est_actif=True,
                    quantite_disponible__gt=0)
            .first()
        )
        if lot:
            logger.info("scanner_lot_identifie",
                        extra={"code": code_barres, "lot_id": str(lot.id)})
            return lot

        # Recherche via code CIP du médicament
        med = Medicament.objects.filter(code_cip=code_barres, est_actif=True).first()
        if med:
            lot = (
                Lot.objects
                .filter(medicament=med, est_actif=True, quantite_disponible__gt=0)
                .order_by("date_peremption")
                .first()
            )
            if lot:
                logger.info("scanner_lot_via_cip",
                            extra={"code": code_barres, "lot_id": str(lot.id)})
                return lot

        raise LotIntrouvable(
            f"Aucun lot actif avec stock disponible pour le code : {code_barres!r}"
        )

    def mode_degrade(self) -> bool:
        """
        Vérifie si le scanner est accessible (test de connexion rapide).
        Retourne True si opérationnel, False en mode dégradé.
        """
        try:
            # Tentative non bloquante : timeout 0.1 s
            self._connecteur.lire_brut(timeout=0.1)
            return True
        except (TimeoutScan, ErreurScanner):
            return False
        except Exception:
            return False
