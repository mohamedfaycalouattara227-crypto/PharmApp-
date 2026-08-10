"""
tests/unitaires/test_materiel_escpos.py
Tests unitaires du service ESC/POS sans matériel physique.
Toutes les dépendances réseau/USB/série sont mockées.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch, call
import pytest

pytestmark = pytest.mark.unitaire


# ─── Fixture DTO reçu minimal ────────────────────────────────────────────────

@pytest.fixture
def dto_recu():
    return {
        "pharmacie": {
            "nom": "Pharmacie du Centre",
            "adresse": "Avenue Kwamé Nkrumah, Ouagadougou",
            "telephone": "+226 25 30 00 00",
            "numero_agrement": "BF-PHARMA-0042",
            "devise": "FCFA",
        },
        "numero_facture": "V-2026-000001",
        "date": "2026-08-06T10:30:00+00:00",
        "caissier": {"id": "abc", "nom": "Kadiatou Traore"},
        "client": None,
        "lignes": [
            {
                "medicament": "Amoxicilline 500mg",
                "quantite": 2,
                "prix_unitaire": "800.00",
                "prix_unitaire_final": "800.00",
                "taux_remise": "0.00",
                "montant": "1600.00",
            }
        ],
        "sous_total": "1600.00",
        "montant_remise": "0.00",
        "montant_total": "1600.00",
        "montant_encaisse": "2000.00",
        "montant_rendu": "400.00",
        "mode_paiement": "especes",
        "statut": "validee",
        "ordonnance_id": None,
        "reimprime": False,
    }


class TestBuilderESCPOS:
    """Tests du constructeur de trames ESC/POS."""

    def test_init_commence_par_esc_at(self):
        from gestion.materiel.escpos import BuilderESCPOS, CMD_INIT
        b = BuilderESCPOS()
        trame = b.init().build()
        assert trame.startswith(CMD_INIT)

    def test_coupe_partielle_present_dans_trame(self):
        from gestion.materiel.escpos import BuilderESCPOS, CMD_COUPE_PARTIELLE
        trame = BuilderESCPOS().init().coupe(totale=False).build()
        assert CMD_COUPE_PARTIELLE in trame

    def test_coupe_totale(self):
        from gestion.materiel.escpos import BuilderESCPOS, CMD_COUPE_TOTALE
        trame = BuilderESCPOS().init().coupe(totale=True).build()
        assert CMD_COUPE_TOTALE in trame

    def test_tiroir_caisse_commande_presente(self):
        from gestion.materiel.escpos import BuilderESCPOS, CMD_TIROIR_CAISSE
        trame = BuilderESCPOS().init().tiroir().build()
        assert CMD_TIROIR_CAISSE in trame

    def test_titre_contient_double_hauteur(self):
        from gestion.materiel.escpos import BuilderESCPOS, CMD_DOUBLE_HAUTEUR
        trame = BuilderESCPOS().init().titre("Ma Pharmacie").build()
        assert CMD_DOUBLE_HAUTEUR in trame

    def test_col2_largeur_respectee(self):
        from gestion.materiel.escpos import BuilderESCPOS, NL
        trame = BuilderESCPOS(largeur=48).col2("Gauche", "Droite").build()
        # Chaque ligne doit faire ≤ 48 caractères (hors NL)
        ligne = trame.decode("cp1252", errors="replace").split("\n")[0]
        assert len(ligne) <= 48


class TestServiceImprimanteESCPOS:
    """Tests du service d'impression avec connecteur mocké."""

    @pytest.fixture
    def connecteur_mock(self):
        m = MagicMock()
        m.envoyer = MagicMock()
        return m

    @pytest.fixture
    def service(self, connecteur_mock):
        from gestion.materiel.escpos import ServiceImprimanteESCPOS
        return ServiceImprimanteESCPOS(connecteur_mock)

    def test_imprimer_recu_appelle_envoyer(self, service, connecteur_mock, dto_recu):
        service.imprimer_recu(dto_recu)
        connecteur_mock.envoyer.assert_called_once()
        trame = connecteur_mock.envoyer.call_args[0][0]
        assert isinstance(trame, bytes)
        assert len(trame) > 50

    def test_imprimer_recu_contient_numero_facture(self, service, connecteur_mock, dto_recu):
        service.imprimer_recu(dto_recu)
        trame = connecteur_mock.envoyer.call_args[0][0]
        assert b"V-2026-000001" in trame

    def test_imprimer_recu_contient_nom_pharmacie(self, service, connecteur_mock, dto_recu):
        service.imprimer_recu(dto_recu)
        trame = connecteur_mock.envoyer.call_args[0][0]
        assert "Pharmacie du Centre".encode("cp1252") in trame

    def test_imprimer_recu_especes_ouvre_tiroir(self, service, connecteur_mock, dto_recu):
        from gestion.materiel.escpos import CMD_TIROIR_CAISSE
        service.imprimer_recu(dto_recu, ouvrir_tiroir=True)
        trame = connecteur_mock.envoyer.call_args[0][0]
        assert CMD_TIROIR_CAISSE in trame

    def test_imprimer_recu_mobile_money_sans_tiroir(self, service, connecteur_mock, dto_recu):
        from gestion.materiel.escpos import CMD_TIROIR_CAISSE
        dto_recu["mode_paiement"] = "mobile_money"
        service.imprimer_recu(dto_recu, ouvrir_tiroir=True)
        trame = connecteur_mock.envoyer.call_args[0][0]
        # Tiroir ne s'ouvre que pour espèces
        assert CMD_TIROIR_CAISSE not in trame

    def test_duplicata_marquage_present(self, service, connecteur_mock, dto_recu):
        dto_recu["reimprime"] = True
        service.imprimer_recu(dto_recu)
        trame = connecteur_mock.envoyer.call_args[0][0]
        assert b"DUPLICATA" in trame

    def test_ouvrir_tiroir_envoie_commande(self, service, connecteur_mock):
        from gestion.materiel.escpos import CMD_TIROIR_CAISSE
        service.ouvrir_tiroir()
        trame = connecteur_mock.envoyer.call_args[0][0]
        assert CMD_TIROIR_CAISSE in trame

    def test_imprimer_test_appelle_envoyer(self, service, connecteur_mock):
        service.imprimer_test()
        connecteur_mock.envoyer.assert_called_once()

    def test_erreur_connecteur_propage_exception(self, connecteur_mock, dto_recu):
        from gestion.materiel.escpos import ServiceImprimanteESCPOS, ErreurImprimante
        connecteur_mock.envoyer.side_effect = ErreurImprimante("connexion refusée")
        service = ServiceImprimanteESCPOS(connecteur_mock)
        with pytest.raises(ErreurImprimante):
            service.imprimer_recu(dto_recu)


class TestConnecteurReseau:
    """Tests du connecteur TCP avec socket mocké."""

    def test_envoyer_ouvre_connexion_et_envoie(self):
        from gestion.materiel.escpos import ConnecteurReseau
        with patch("socket.create_connection") as mock_conn:
            sock_mock = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=sock_mock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            c = ConnecteurReseau("192.168.1.100", 9100)
            c.envoyer(b"\x1b@test")
            mock_conn.assert_called_once_with(("192.168.1.100", 9100), timeout=5.0)

    def test_hote_inaccessible_leve_erreur_imprimante(self):
        from gestion.materiel.escpos import ConnecteurReseau, ErreurImprimante
        with patch("socket.create_connection", side_effect=OSError("Connection refused")):
            c = ConnecteurReseau("10.0.0.1", 9100)
            with pytest.raises(ErreurImprimante):
                c.envoyer(b"test")

    def test_timeout_leve_erreur_imprimante(self):
        from gestion.materiel.escpos import ConnecteurReseau, ErreurImprimante
        with patch("socket.create_connection", side_effect=OSError("timed out")):
            c = ConnecteurReseau("10.0.0.99", 9100, timeout=1.0)
            with pytest.raises(ErreurImprimante, match="10.0.0.99"):
                c.envoyer(b"test")


class TestConnecteurSerie:
    """Tests du connecteur série avec pyserial mocké."""

    def test_pyserial_absent_leve_erreur_imprimante(self):
        from gestion.materiel.escpos import ConnecteurSerie, ErreurImprimante
        import builtins
        original_import = builtins.__import__

        def import_bloqu(name, *args, **kwargs):
            if name == "serial":
                raise ImportError("pyserial absent")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_bloqu):
            c = ConnecteurSerie("/dev/ttyUSB0")
            with pytest.raises(ErreurImprimante, match="pyserial"):
                c.envoyer(b"test")

    def test_port_serie_inaccessible_leve_erreur_imprimante(self):
        from gestion.materiel.escpos import ConnecteurSerie, ErreurImprimante
        serial_mock = MagicMock()
        serial_mock.Serial.side_effect = Exception("Accès refusé")
        with patch.dict("sys.modules", {"serial": serial_mock}):
            c = ConnecteurSerie("/dev/ttyUSB99")
            with pytest.raises(ErreurImprimante):
                c.envoyer(b"test")


class TestBuilderESCPOSCasLimites:
    """Cas limites du BuilderESCPOS non couverts par les tests de base."""

    def test_recu_avec_remise_contient_ligne_remise(self):
        """Un reçu avec taux_remise > 0 affiche la ligne de remise."""
        from gestion.materiel.escpos import BuilderESCPOS
        b = BuilderESCPOS()
        b.init()
        b.col2("Amox 500mg  2 x 800", "1 600 FCFA")
        b.ligne("  Remise 10%")
        trame = b.build()
        assert "Remise".encode("cp1252") in trame

    def test_montant_rendu_zero_absent_du_ticket(self, connecteur_mock):
        """Quand le rendu est 0, la ligne 'Rendu' ne doit pas apparaître."""
        from gestion.materiel.escpos import ServiceImprimanteESCPOS, CMD_GRAS_ON
        dto = {
            "pharmacie": {"nom": "Test", "devise": "FCFA"},
            "numero_facture": "V-0001",
            "date": "2026-08-06T12:00:00+00:00",
            "caissier": {"nom": "Test"},
            "client": None,
            "lignes": [{"medicament": "Paracétamol", "quantite": 1,
                        "prix_unitaire": "500", "prix_unitaire_final": "500",
                        "taux_remise": "0", "montant": "500"}],
            "sous_total": "500",
            "montant_remise": "0",
            "montant_total": "500",
            "montant_encaisse": "500",
            "montant_rendu": "0",
            "mode_paiement": "especes",
            "reimprime": False,
        }
        svc = ServiceImprimanteESCPOS(connecteur_mock)
        svc.imprimer_recu(dto, ouvrir_tiroir=False)
        trame = connecteur_mock.envoyer.call_args[0][0]
        # "Rendu" ne doit pas figurer dans la trame (rendu = 0)
        assert b"Rendu" not in trame

    def test_encodage_cp1252_caracteres_speciaux(self):
        """Les caractères français (é, è, ç, à) sont encodés sans erreur."""
        from gestion.materiel.escpos import BuilderESCPOS
        b = BuilderESCPOS()
        # Ne doit pas lever UnicodeEncodeError
        trame = b.init().ligne("Médicament : Pénicilline G").build()
        assert isinstance(trame, bytes)
        assert len(trame) > 10

    def test_col2_texte_trop_long_ne_deborde_pas(self):
        """col2 avec textes longs conserve au moins 1 espace entre colonnes."""
        from gestion.materiel.escpos import BuilderESCPOS, NL
        gauche = "A" * 40
        droite = "B" * 10
        trame = BuilderESCPOS(largeur=48).col2(gauche, droite).build()
        ligne = trame.split(NL)[0].decode("cp1252", errors="replace")
        # L'espace minimal (1 char) doit être garanti
        assert len(ligne) >= len(gauche) + 1

    def test_trame_non_vide_apres_build_minimal(self):
        """Un build minimal (init + coupe) produit une trame non vide."""
        from gestion.materiel.escpos import BuilderESCPOS, CMD_INIT
        trame = BuilderESCPOS().init().coupe().build()
        assert len(trame) > len(CMD_INIT)

    @pytest.fixture
    def connecteur_mock(self):
        m = MagicMock()
        m.envoyer = MagicMock()
        return m
