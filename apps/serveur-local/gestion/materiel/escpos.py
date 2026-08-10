"""
gestion/materiel/escpos.py
Intégration imprimante thermique ESC/POS (Epson TM-T20, TM-T88, Star TSP, etc.)

Architecture :
  - ServiceImprimanteESCPOS  : couche métier, indépendante du transport
  - ConnecteurUSB            : connexion via usb.core (pyusb)
  - ConnecteurSerie          : connexion via pyserial (/dev/ttyUSB0, COM3)
  - ConnecteurReseau         : connexion TCP socket (port 9100)

Le connecteur est résolu à partir des paramètres Pharmacie (Parametrage).
Fallback : window.print() via l'API (comportement historique conservé).

Utilisation (depuis une vue Django) :
    from gestion.materiel.escpos import ServiceImprimanteESCPOS
    service = ServiceImprimanteESCPOS.depuis_parametrage()
    service.imprimer_recu(dto_recu)

Commandes ESC/POS utilisées :
  ESC @ — initialisation
  ESC a — alignement (0=gauche, 1=centre, 2=droite)
  ESC E — gras (1=on, 0=off)
  ESC ! — sélection police (bit 3 = double hauteur, bit 4 = double largeur)
  GS V  — coupe papier
  ESC p  — ouverture tiroir-caisse
"""

from __future__ import annotations

import logging
import socket
import struct
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pharmapp.materiel.escpos")

# ─── Constantes ESC/POS ───────────────────────────────────────────────────────

ESC = b"\x1b"
GS  = b"\x1d"
NL  = b"\n"

CMD_INIT            = ESC + b"@"           # Réinitialiser l'imprimante
CMD_ALIGN_GAUCHE    = ESC + b"a\x00"
CMD_ALIGN_CENTRE    = ESC + b"a\x01"
CMD_ALIGN_DROITE    = ESC + b"a\x02"
CMD_GRAS_ON         = ESC + b"E\x01"
CMD_GRAS_OFF        = ESC + b"E\x00"
CMD_DOUBLE_HAUTEUR  = ESC + b"!\x10"       # Double hauteur
CMD_NORMAL          = ESC + b"!\x00"       # Police normale
CMD_COUPE_PARTIELLE = GS  + b"V\x42\x00"  # Coupe partielle (laisse marge)
CMD_COUPE_TOTALE    = GS  + b"V\x00"       # Coupe complète
CMD_TIROIR_CAISSE   = ESC + b"p\x00\x19\xfa"  # Ouvre le tiroir (pin 2, Epson)
CMD_TRAIT           = b"-" * 48 + NL
CMD_DOUBLE_TRAIT    = b"=" * 48 + NL

# Encodage par défaut (Afrique francophone)
CODEC = "cp1252"

LARGEUR_TICKET = 48  # colonnes pour 80 mm ; 32 pour 58 mm


# ─── Exceptions ───────────────────────────────────────────────────────────────

class ErreurImprimante(Exception):
    """Erreur de communication avec l'imprimante ESC/POS."""


class ImprimanteNonConfiguree(ErreurImprimante):
    """Aucune imprimante configurée dans les paramètres pharmacie."""


# ─── Connecteurs (adapters) ───────────────────────────────────────────────────

class ConnecteurReseau:
    """Connexion TCP directe au port ESC/POS (9100 par défaut)."""

    def __init__(self, hote: str, port: int = 9100, timeout: float = 5.0):
        self.hote = hote
        self.port = port
        self.timeout = timeout

    def envoyer(self, donnees: bytes) -> None:
        try:
            with socket.create_connection(
                (self.hote, self.port), timeout=self.timeout
            ) as sock:
                sock.sendall(donnees)
        except OSError as exc:
            raise ErreurImprimante(
                f"Impossible de joindre l'imprimante réseau {self.hote}:{self.port} — {exc}"
            ) from exc


class ConnecteurSerie:
    """Connexion RS-232/USB série via pyserial."""

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate

    def envoyer(self, donnees: bytes) -> None:
        try:
            import serial  # pyserial — optionnel
        except ImportError as exc:
            raise ErreurImprimante(
                "pyserial n'est pas installé. Ajoutez pyserial aux requirements."
            ) from exc
        try:
            with serial.Serial(self.port, self.baudrate, timeout=2) as ser:
                ser.write(donnees)
        except Exception as exc:
            raise ErreurImprimante(f"Erreur port série {self.port} — {exc}") from exc


class ConnecteurUSB:
    """Connexion USB directe via pyusb (libusb)."""

    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id

    def envoyer(self, donnees: bytes) -> None:
        try:
            import usb.core  # pyusb — optionnel
        except ImportError as exc:
            raise ErreurImprimante(
                "pyusb n'est pas installé. Ajoutez pyusb aux requirements."
            ) from exc
        dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
        if dev is None:
            raise ErreurImprimante(
                f"Imprimante USB introuvable (VID=0x{self.vendor_id:04X} PID=0x{self.product_id:04X})"
            )
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
            dev.set_configuration()
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]
            ep_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_OUT,
            )
            ep_out.write(donnees)
        except Exception as exc:
            raise ErreurImprimante(f"Erreur USB ESC/POS — {exc}") from exc


# ─── Constructeur de trame ESC/POS ───────────────────────────────────────────

class BuilderESCPOS:
    """Construit une trame ESC/POS binaire pour un ticket de 48 ou 32 colonnes."""

    def __init__(self, largeur: int = LARGEUR_TICKET):
        self._buf: List[bytes] = []
        self.largeur = largeur

    # --- Helpers privés -------------------------------------------------------

    def _ligne(self, texte: str) -> bytes:
        return texte.encode(CODEC, errors="replace") + NL

    def _col2(self, gauche: str, droite: str) -> bytes:
        espace = max(1, self.largeur - len(gauche) - len(droite))
        return self._ligne(gauche + " " * espace + droite)

    # --- API publique ---------------------------------------------------------

    def init(self) -> "BuilderESCPOS":
        self._buf.append(CMD_INIT)
        return self

    def centre(self, texte: str) -> "BuilderESCPOS":
        self._buf.extend([CMD_ALIGN_CENTRE, self._ligne(texte), CMD_ALIGN_GAUCHE])
        return self

    def gras(self, texte: str) -> "BuilderESCPOS":
        self._buf.extend([CMD_GRAS_ON, self._ligne(texte), CMD_GRAS_OFF])
        return self

    def titre(self, texte: str) -> "BuilderESCPOS":
        self._buf.extend([
            CMD_ALIGN_CENTRE, CMD_DOUBLE_HAUTEUR, CMD_GRAS_ON,
            self._ligne(texte),
            CMD_GRAS_OFF, CMD_NORMAL, CMD_ALIGN_GAUCHE,
        ])
        return self

    def ligne(self, texte: str = "") -> "BuilderESCPOS":
        self._buf.append(self._ligne(texte))
        return self

    def trait(self) -> "BuilderESCPOS":
        self._buf.append(CMD_TRAIT)
        return self

    def col2(self, gauche: str, droite: str) -> "BuilderESCPOS":
        self._buf.append(self._col2(gauche, droite))
        return self

    def coupe(self, totale: bool = False) -> "BuilderESCPOS":
        self._buf.append(CMD_COUPE_TOTALE if totale else CMD_COUPE_PARTIELLE)
        return self

    def tiroir(self) -> "BuilderESCPOS":
        self._buf.append(CMD_TIROIR_CAISSE)
        return self

    def build(self) -> bytes:
        return b"".join(self._buf)


# ─── Service principal ────────────────────────────────────────────────────────

class ServiceImprimanteESCPOS:
    """
    Service métier d'impression ESC/POS.

    Utilisation standard :
        service = ServiceImprimanteESCPOS.depuis_parametrage()
        service.imprimer_recu(recu_dto)
        service.ouvrir_tiroir()
    """

    def __init__(self, connecteur):
        self._connecteur = connecteur

    # --- Constructeurs alternatifs -------------------------------------------

    @classmethod
    def reseau(cls, hote: str, port: int = 9100) -> "ServiceImprimanteESCPOS":
        return cls(ConnecteurReseau(hote, port))

    @classmethod
    def serie(cls, port: str = "/dev/ttyUSB0") -> "ServiceImprimanteESCPOS":
        return cls(ConnecteurSerie(port))

    @classmethod
    def usb(cls, vendor_id: int, product_id: int) -> "ServiceImprimanteESCPOS":
        return cls(ConnecteurUSB(vendor_id, product_id))

    @classmethod
    def depuis_parametrage(cls) -> "ServiceImprimanteESCPOS":
        """
        Résout le connecteur depuis les paramètres de la pharmacie.
        Variables d'environnement (ou settings) :
          ESCPOS_TYPE  : "reseau" | "serie" | "usb"  (défaut: "reseau")
          ESCPOS_HOTE  : adresse IP (pour type=reseau)
          ESCPOS_PORT  : port TCP (défaut 9100)
          ESCPOS_SERIE : chemin port série (défaut /dev/ttyUSB0)
          ESCPOS_USB_VID / ESCPOS_USB_PID : IDs USB en hex
        """
        from django.conf import settings as djsettings
        import os

        tp = getattr(djsettings, "ESCPOS_TYPE", os.environ.get("ESCPOS_TYPE", "reseau"))
        if tp == "reseau":
            hote = getattr(djsettings, "ESCPOS_HOTE", os.environ.get("ESCPOS_HOTE", "127.0.0.1"))
            port = int(getattr(djsettings, "ESCPOS_PORT", os.environ.get("ESCPOS_PORT", "9100")))
            return cls.reseau(hote, port)
        elif tp == "serie":
            port_s = getattr(djsettings, "ESCPOS_SERIE", os.environ.get("ESCPOS_SERIE", "/dev/ttyUSB0"))
            return cls.serie(port_s)
        elif tp == "usb":
            vid = int(os.environ.get("ESCPOS_USB_VID", "0x04B8"), 16)  # Epson par défaut
            pid = int(os.environ.get("ESCPOS_USB_PID", "0x0202"), 16)
            return cls.usb(vid, pid)
        else:
            raise ImprimanteNonConfiguree(f"ESCPOS_TYPE inconnu : {tp!r}")

    # --- Actions -------------------------------------------------------------

    def imprimer_recu(self, recu: Dict[str, Any], ouvrir_tiroir: bool = True) -> None:
        """
        Imprime un reçu de vente complet (ticket thermique 80 mm).
        `recu` est le DTO renvoyé par GET /ventes/{id}/recu/.
        """
        pharmacie = recu.get("pharmacie", {})
        b = BuilderESCPOS()
        b.init()

        # En-tête pharmacie
        b.ligne().titre(pharmacie.get("nom", "PharmApp"))
        b.centre(pharmacie.get("adresse", ""))
        if pharmacie.get("telephone"):
            b.centre(f"Tél : {pharmacie['telephone']}")
        if pharmacie.get("numero_agrement"):
            b.centre(f"Agrément : {pharmacie['numero_agrement']}")

        b.ligne().trait()

        # Numéro & date
        from django.utils.dateformat import format as dfmt
        from django.utils import timezone
        from datetime import datetime

        date_str = recu.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str)
            date_fmt = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            date_fmt = date_str

        b.col2(f"Reçu : {recu.get('numero_facture', '')}", date_fmt)
        caissier = recu.get("caissier", {})
        b.ligne(f"Caissier : {caissier.get('nom', '')}")
        client = recu.get("client")
        if client:
            b.ligne(f"Client   : {client.get('nom', 'Client de passage')}")

        if recu.get("reimprime"):
            b.gras("*** DUPLICATA ***")

        b.trait()

        # Lignes de vente
        devise = pharmacie.get("devise", "FCFA")
        for ligne in recu.get("lignes", []):
            nom = ligne.get("medicament", "")[:32]
            qte = ligne.get("quantite", 1)
            pu = Decimal(str(ligne.get("prix_unitaire_final", ligne.get("prix_unitaire", 0))))
            montant = Decimal(str(ligne.get("montant", 0)))
            b.ligne(nom)
            b.col2(f"  {qte} x {pu:,.0f} {devise}", f"{montant:,.0f} {devise}")
            if ligne.get("taux_remise") and Decimal(str(ligne["taux_remise"])) > 0:
                b.ligne(f"  Remise {ligne['taux_remise']}%")

        b.trait()

        # Totaux
        sous_total = Decimal(str(recu.get("sous_total", 0)))
        remise    = Decimal(str(recu.get("montant_remise", 0)))
        total     = Decimal(str(recu.get("montant_total", 0)))
        encaisse  = Decimal(str(recu.get("montant_encaisse", 0)))
        rendu     = Decimal(str(recu.get("montant_rendu", 0)))

        if remise > 0:
            b.col2("Sous-total", f"{sous_total:,.0f} {devise}")
            b.col2("Remise", f"-{remise:,.0f} {devise}")

        b.gras(f"Total     {total:,.0f} {devise}")
        b.col2(f"Mode : {recu.get('mode_paiement', '').upper()}", "")
        b.col2("Encaissé", f"{encaisse:,.0f} {devise}")
        if rendu > 0:
            b.gras(f"Rendu     {rendu:,.0f} {devise}")

        b.trait()
        b.centre("Merci de votre confiance !")
        b.centre("Conservez ce reçu.")
        b.ligne()

        if recu.get("ordonnance_id"):
            b.ligne(f"Ord. : {recu['ordonnance_id']}")

        b.coupe()

        if ouvrir_tiroir and recu.get("mode_paiement") == "especes":
            b.tiroir()

        trame = b.build()
        logger.info(
            "escpos_impression",
            extra={"numero": recu.get("numero_facture"), "taille_octets": len(trame)},
        )
        self._connecteur.envoyer(trame)

    def imprimer_test(self) -> None:
        """Imprime un ticket de test (diagnostique rapide)."""
        b = BuilderESCPOS()
        b.init().titre("TEST IMPRIMANTE").trait()
        b.ligne("PharmApp — ESC/POS OK").ligne()
        b.coupe()
        self._connecteur.envoyer(b.build())

    def ouvrir_tiroir(self) -> None:
        """Ouvre le tiroir-caisse (commande ESC p)."""
        donnees = CMD_INIT + CMD_TIROIR_CAISSE
        self._connecteur.envoyer(donnees)
        logger.info("tiroir_caisse_ouvert")
