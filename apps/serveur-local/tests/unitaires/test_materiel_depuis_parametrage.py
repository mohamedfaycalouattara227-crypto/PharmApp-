"""
tests/unitaires/test_materiel_depuis_parametrage.py
ÉTAPE 08 — Tests de résolution du connecteur via ServiceImprimanteESCPOS.depuis_parametrage().

Couvre :
  - ESCPOS_TYPE=reseau → ConnecteurReseau instancié
  - ESCPOS_TYPE=serie  → ConnecteurSerie instancié
  - ESCPOS_TYPE=usb    → ConnecteurUSB instancié
  - ESCPOS_TYPE inconnu → ImprimanteNonConfiguree
  - Valeurs par défaut (type réseau, hôte 127.0.0.1, port 9100)
  - Surcharge par variables d'environnement

Marqueur : pytest.mark.unitaire
"""

import os
from unittest.mock import patch, MagicMock

import pytest

pytestmark = pytest.mark.unitaire


class TestDepuisParametrage:
    """ServiceImprimanteESCPOS.depuis_parametrage() résout le bon connecteur."""

    def test_type_reseau_instancie_connecteur_reseau(self):
        from gestion.materiel.escpos import (
            ServiceImprimanteESCPOS, ConnecteurReseau,
        )
        with patch.dict(os.environ, {"ESCPOS_TYPE": "reseau", "ESCPOS_HOTE": "192.168.1.50"}):
            with patch("django.conf.settings") as mock_settings:
                mock_settings.ESCPOS_TYPE = "reseau"
                mock_settings.ESCPOS_HOTE = "192.168.1.50"
                mock_settings.ESCPOS_PORT = "9100"
                svc = ServiceImprimanteESCPOS.depuis_parametrage()
        assert isinstance(svc._connecteur, ConnecteurReseau)
        assert svc._connecteur.hote == "192.168.1.50"

    def test_type_serie_instancie_connecteur_serie(self):
        from gestion.materiel.escpos import (
            ServiceImprimanteESCPOS, ConnecteurSerie,
        )
        with patch("django.conf.settings") as mock_settings:
            mock_settings.ESCPOS_TYPE = "serie"
            mock_settings.ESCPOS_SERIE = "/dev/ttyUSB0"
            # Effacer l'env pour ne pas interférer
            env = {k: v for k, v in os.environ.items() if not k.startswith("ESCPOS_")}
            env["ESCPOS_TYPE"] = "serie"
            with patch.dict(os.environ, env, clear=True):
                svc = ServiceImprimanteESCPOS.depuis_parametrage()
        assert isinstance(svc._connecteur, ConnecteurSerie)

    def test_type_usb_instancie_connecteur_usb(self):
        from gestion.materiel.escpos import (
            ServiceImprimanteESCPOS, ConnecteurUSB,
        )
        env = {
            "ESCPOS_TYPE": "usb",
            "ESCPOS_USB_VID": "0x04B8",
            "ESCPOS_USB_PID": "0x0202",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("django.conf.settings") as mock_settings:
                mock_settings.ESCPOS_TYPE = "usb"
                svc = ServiceImprimanteESCPOS.depuis_parametrage()
        assert isinstance(svc._connecteur, ConnecteurUSB)
        assert svc._connecteur.vendor_id == 0x04B8
        assert svc._connecteur.product_id == 0x0202

    def test_type_inconnu_leve_imprimante_non_configuree(self):
        from gestion.materiel.escpos import (
            ServiceImprimanteESCPOS, ImprimanteNonConfiguree,
        )
        with patch("django.conf.settings") as mock_settings:
            mock_settings.ESCPOS_TYPE = "bluetooth"
            with patch.dict(os.environ, {"ESCPOS_TYPE": "bluetooth"}, clear=False):
                with pytest.raises(ImprimanteNonConfiguree, match="inconnu"):
                    ServiceImprimanteESCPOS.depuis_parametrage()

    def test_valeur_par_defaut_reseau_127_0_0_1(self):
        """Sans configuration, le connecteur par défaut est réseau sur 127.0.0.1:9100."""
        from gestion.materiel.escpos import (
            ServiceImprimanteESCPOS, ConnecteurReseau,
        )
        env_propre = {k: v for k, v in os.environ.items() if not k.startswith("ESCPOS_")}
        with patch.dict(os.environ, env_propre, clear=True):
            with patch("django.conf.settings") as mock_settings:
                # Simuler l'absence de l'attribut ESCPOS_TYPE dans settings
                del mock_settings.ESCPOS_TYPE
                type(mock_settings).__getattr__ = lambda s, name: (_ for _ in ()).throw(
                    AttributeError(name)
                )
                svc = ServiceImprimanteESCPOS.depuis_parametrage()
        assert isinstance(svc._connecteur, ConnecteurReseau)
        assert svc._connecteur.hote == "127.0.0.1"
        assert svc._connecteur.port == 9100

    def test_port_reseau_configurable(self):
        """ESCPOS_PORT override le port par défaut."""
        from gestion.materiel.escpos import (
            ServiceImprimanteESCPOS, ConnecteurReseau,
        )
        with patch("django.conf.settings") as mock_settings:
            mock_settings.ESCPOS_TYPE = "reseau"
            mock_settings.ESCPOS_HOTE = "10.0.0.5"
            mock_settings.ESCPOS_PORT = "9200"
            svc = ServiceImprimanteESCPOS.depuis_parametrage()
        assert isinstance(svc._connecteur, ConnecteurReseau)
        assert svc._connecteur.port == 9200
