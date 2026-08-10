"""
tests/unitaires/test_materiel_scanner.py
ÉTAPE 08 — Tests unitaires du service lecteur de code-barres.
Toutes les dépendances série/HID sont mockées (pas de matériel physique).

Couvre :
  - ConnecteurSerieScan : lecture ok, timeout, pyserial absent, port inaccessible
  - ServiceScannerCodeBarres.lire_code() : EAN-13 valide, EAN-8 valide,
    code vide, format inconnu, timeout propagé
  - ServiceScannerCodeBarres.identifier_lot() : trouvé direct, trouvé via CIP,
    lot introuvable
  - ServiceScannerCodeBarres.depuis_parametrage() : serie, hid, type inconnu
  - ServiceScannerCodeBarres.mode_degrade() : scanner ok, scanner indisponible

Marqueur : pytest.mark.unitaire
"""

import sys
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

pytestmark = pytest.mark.unitaire


# ─── 1. ConnecteurSerieScan ──────────────────────────────────────────────────

class TestConnecteurSerieScan:
    """Tests du connecteur série avec pyserial mocké."""

    def test_lecture_ok_retourne_code_brut(self):
        from gestion.materiel.scanner import ConnecteurSerieScan
        serial_mock = MagicMock()
        serial_mock.Serial.return_value.__enter__ = lambda s: s
        serial_mock.Serial.return_value.__exit__ = MagicMock(return_value=False)
        serial_mock.Serial.return_value.readline.return_value = b"3400935190298\r\n"
        with patch.dict(sys.modules, {"serial": serial_mock}):
            c = ConnecteurSerieScan("/dev/ttyUSB1", 9600)
            code = c.lire_brut(timeout=2.0)
        assert code == "3400935190298"

    def test_timeout_leve_exception(self):
        from gestion.materiel.scanner import ConnecteurSerieScan, TimeoutScan
        serial_mock = MagicMock()
        serial_mock.Serial.return_value.__enter__ = lambda s: s
        serial_mock.Serial.return_value.__exit__ = MagicMock(return_value=False)
        # readline retourne bytes vides → timeout
        serial_mock.Serial.return_value.readline.return_value = b""
        with patch.dict(sys.modules, {"serial": serial_mock}):
            c = ConnecteurSerieScan("/dev/ttyUSB1", 9600)
            with pytest.raises(TimeoutScan):
                c.lire_brut(timeout=1.0)

    def test_pyserial_absent_leve_erreur_scanner(self):
        from gestion.materiel.scanner import ConnecteurSerieScan, ErreurScanner
        import builtins
        original_import = builtins.__import__

        def import_bloque(name, *args, **kwargs):
            if name == "serial":
                raise ImportError("pyserial absent")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_bloque):
            c = ConnecteurSerieScan("/dev/ttyUSB1")
            with pytest.raises(ErreurScanner, match="pyserial"):
                c.lire_brut()

    def test_port_inaccessible_leve_erreur_scanner(self):
        from gestion.materiel.scanner import ConnecteurSerieScan, ErreurScanner
        serial_mock = MagicMock()
        serial_mock.Serial.side_effect = Exception("Accès refusé /dev/ttyUSB1")
        with patch.dict(sys.modules, {"serial": serial_mock}):
            c = ConnecteurSerieScan("/dev/ttyUSB1")
            with pytest.raises(ErreurScanner):
                c.lire_brut()


# ─── 2. ServiceScannerCodeBarres.lire_code() ─────────────────────────────────

class TestLireCode:
    """Tests de la méthode lire_code() avec connecteur mocké."""

    @pytest.fixture
    def connecteur_mock(self):
        m = MagicMock()
        m.lire_brut = MagicMock(return_value="3400935190298")
        return m

    @pytest.fixture
    def service(self, connecteur_mock):
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        return ServiceScannerCodeBarres(connecteur_mock)

    def test_ean13_valide_retourne_code(self, service):
        code = service.lire_code(timeout=2.0)
        assert code == "3400935190298"

    def test_ean8_valide_retourne_code(self, connecteur_mock):
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        connecteur_mock.lire_brut.return_value = "12345670"
        svc = ServiceScannerCodeBarres(connecteur_mock)
        assert svc.lire_code() == "12345670"

    def test_code_vide_leve_timeout_scan(self, connecteur_mock):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, TimeoutScan
        connecteur_mock.lire_brut.return_value = "   "
        svc = ServiceScannerCodeBarres(connecteur_mock)
        with pytest.raises(TimeoutScan):
            svc.lire_code()

    def test_format_inconnu_leve_code_non_reconnu(self, connecteur_mock):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, CodeNonReconnu
        connecteur_mock.lire_brut.return_value = "INVALIDE!@#$"
        svc = ServiceScannerCodeBarres(connecteur_mock)
        with pytest.raises(CodeNonReconnu):
            svc.lire_code()

    def test_timeout_scan_propagee(self, connecteur_mock):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, TimeoutScan
        connecteur_mock.lire_brut.side_effect = TimeoutScan("pas de code")
        svc = ServiceScannerCodeBarres(connecteur_mock)
        with pytest.raises(TimeoutScan):
            svc.lire_code()

    def test_code39_valide_accepte(self, connecteur_mock):
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        connecteur_mock.lire_brut.return_value = "AMOXICILLINE500"
        svc = ServiceScannerCodeBarres(connecteur_mock)
        assert svc.lire_code() == "AMOXICILLINE500"


# ─── 3. ServiceScannerCodeBarres.identifier_lot() ────────────────────────────

class TestIdentifierLot:
    """Tests de résolution lot depuis code-barres (ORM mocké)."""

    @pytest.fixture
    def connecteur_mock(self):
        return MagicMock()

    @pytest.fixture
    def service(self, connecteur_mock):
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        return ServiceScannerCodeBarres(connecteur_mock)

    def test_lot_trouve_directement(self, service):
        lot_mock = MagicMock()
        lot_mock.id = "lot-uuid-001"
        qs = MagicMock()
        qs.select_related.return_value.filter.return_value.first.return_value = lot_mock
        with patch("gestion.materiel.scanner.Lot.objects", qs):
            resultat = service.identifier_lot("3400935190298")
        assert resultat is lot_mock

    def test_lot_trouve_via_code_cip(self, service):
        """Pas de lot direct → cherche via Medicament.code_cip."""
        lot_mock = MagicMock()
        med_mock = MagicMock()
        # Lot direct introuvable
        qs_lot = MagicMock()
        qs_lot.select_related.return_value.filter.return_value.first.return_value = None
        qs_lot.filter.return_value.order_by.return_value.first.return_value = lot_mock
        qs_med = MagicMock()
        qs_med.filter.return_value.first.return_value = med_mock
        with patch("gestion.materiel.scanner.Lot.objects", qs_lot), \
             patch("gestion.materiel.scanner.Medicament.objects", qs_med):
            resultat = service.identifier_lot("3400935190298")
        assert resultat is lot_mock

    def test_lot_introuvable_leve_exception(self, service):
        from gestion.materiel.scanner import LotIntrouvable
        qs_lot = MagicMock()
        qs_lot.select_related.return_value.filter.return_value.first.return_value = None
        qs_lot.filter.return_value.order_by.return_value.first.return_value = None
        qs_med = MagicMock()
        qs_med.filter.return_value.first.return_value = None
        with patch("gestion.materiel.scanner.Lot.objects", qs_lot), \
             patch("gestion.materiel.scanner.Medicament.objects", qs_med):
            with pytest.raises(LotIntrouvable):
                service.identifier_lot("9999999999999")


# ─── 4. ServiceScannerCodeBarres.depuis_parametrage() ────────────────────────

class TestDepuisParametrageScanner:
    """Résolution du connecteur via SCANNER_TYPE."""

    def test_type_serie_instancie_connecteur_serie(self):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, ConnecteurSerieScan
        with patch("django.conf.settings") as s:
            s.SCANNER_TYPE = "serie"
            s.SCANNER_PORT = "/dev/ttyUSB1"
            s.SCANNER_BAUD = "9600"
            svc = ServiceScannerCodeBarres.depuis_parametrage()
        assert isinstance(svc._connecteur, ConnecteurSerieScan)

    def test_type_hid_instancie_connecteur_hid(self):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, ConnecteurHIDScan
        with patch("django.conf.settings") as s:
            s.SCANNER_TYPE = "hid"
            s.SCANNER_HID = "/dev/input/event1"
            svc = ServiceScannerCodeBarres.depuis_parametrage()
        assert isinstance(svc._connecteur, ConnecteurHIDScan)

    def test_type_inconnu_leve_scanner_non_configure(self):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, ScannerNonConfigure
        with patch("django.conf.settings") as s:
            s.SCANNER_TYPE = "bluetooth"
            with pytest.raises(ScannerNonConfigure, match="inconnu"):
                ServiceScannerCodeBarres.depuis_parametrage()


# ─── 5. ServiceScannerCodeBarres.mode_degrade() ──────────────────────────────

class TestModeDegrade:
    """Vérification de la disponibilité du scanner."""

    def test_scanner_disponible_retourne_true(self):
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        connecteur = MagicMock()
        connecteur.lire_brut.return_value = "3400935190298"
        svc = ServiceScannerCodeBarres(connecteur)
        assert svc.mode_degrade() is True

    def test_scanner_timeout_retourne_false(self):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, TimeoutScan
        connecteur = MagicMock()
        connecteur.lire_brut.side_effect = TimeoutScan("indisponible")
        svc = ServiceScannerCodeBarres(connecteur)
        assert svc.mode_degrade() is False

    def test_scanner_erreur_retourne_false(self):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, ErreurScanner
        connecteur = MagicMock()
        connecteur.lire_brut.side_effect = ErreurScanner("port fermé")
        svc = ServiceScannerCodeBarres(connecteur)
        assert svc.mode_degrade() is False
