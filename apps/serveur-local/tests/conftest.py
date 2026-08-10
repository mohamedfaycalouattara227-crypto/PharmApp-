"""
tests/conftest.py — Fixtures partagées pour tous les tests PharmApp.

Ce fichier est chargé automatiquement par pytest pour chaque test.
Il fournit les fixtures Django, les utilisateurs par rôle et le client API.
"""

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient


# ─── Fixtures utilisateurs par rôle ──────────────────────────────────────────

def _creer_utilisateur(role: str, **kwargs):
    """Crée un utilisateur réel en base de données pour les tests."""
    from tests.usine.usine_utilisateurs import (
        UsineCaissier, UsineAssistant, UsineGestionnaireStock,
        UsinePharmacienAdjoint, UsineTitulaire, UsineUtilisateurPharmacien
    )
    factories = {
        "caissier": UsineCaissier,
        "assistant": UsineAssistant,
        "gestionnaire_stock": UsineGestionnaireStock,
        "pharmacien_adjoint": UsinePharmacienAdjoint,
        "titulaire": UsineTitulaire,
        "stagiaire": UsineUtilisateurPharmacien,
    }
    factory = factories.get(role, UsineUtilisateurPharmacien)
    kwargs.setdefault("role", role)
    # On force la création en base pour éviter les erreurs d'intégrité (FK)
    return factory.create(**kwargs)


@pytest.fixture
def caissier(db):
    """Utilisateur avec le rôle Caissier."""
    return _creer_utilisateur("caissier", prenom="Kadiatou", nom="Traore")


@pytest.fixture
def assistant(db):
    """Utilisateur avec le rôle Pharmacien assistant."""
    return _creer_utilisateur("assistant", prenom="Mamadou", nom="Diallo")


@pytest.fixture
def gestionnaire_stock(db):
    """Utilisateur avec le rôle Gestionnaire de stock."""
    return _creer_utilisateur("gestionnaire_stock", prenom="Aminata", nom="Ouedraogo")


@pytest.fixture
def pharmacien_adjoint(db):
    """Utilisateur avec le rôle Pharmacien adjoint."""
    return _creer_utilisateur("pharmacien_adjoint", prenom="Issa", nom="Kone")


@pytest.fixture
def titulaire(db):
    """Utilisateur avec le rôle Pharmacien titulaire."""
    return _creer_utilisateur("titulaire", prenom="Fatoumata", nom="Sawadogo")


@pytest.fixture
def stagiaire(db):
    """Utilisateur avec le rôle Stagiaire (permissions minimales)."""
    return _creer_utilisateur("stagiaire", prenom="Oumar", nom="Coulibaly")


# ─── Fixtures médicaments et lots ─────────────────────────────────────────────

@pytest.fixture
def medicament_mock():
    """Médicament mock générique."""
    med = MagicMock()
    med.id = uuid.uuid4()
    med.nom = "Amoxicilline 500mg"
    med.denomination_commune_internationale = "Amoxicilline"
    med.prix_public = Decimal("800.00")
    med.prix_min_autorise = Decimal("700.00")
    med.prix_max_autorise = Decimal("900.00")
    med.est_actif = True
    med.necessite_ordonnance = False
    med.est_produit_controle = False
    med.seuil_alerte_stock = 20
    med.stock_total_disponible = 150
    med.est_en_alerte_stock = False
    return med


@pytest.fixture
def medicament_ordonnance_mock():
    """Médicament mock nécessitant une ordonnance."""
    med = MagicMock()
    med.id = uuid.uuid4()
    med.nom = "Diazépam 10mg"
    med.est_actif = True
    med.necessite_ordonnance = True
    med.est_produit_controle = True
    med.prix_public = Decimal("1500.00")
    med.prix_min_autorise = Decimal("1400.00")
    med.prix_max_autorise = Decimal("1600.00")
    med.seuil_alerte_stock = 10
    med.stock_total_disponible = 5
    med.est_en_alerte_stock = True
    return med


@pytest.fixture
def lot_mock(medicament_mock):
    """Lot mock générique."""
    lot = MagicMock()
    lot.id = uuid.uuid4()
    lot.medicament = medicament_mock
    lot.numero_lot = "LOT-2024-001"
    lot.quantite_disponible = 100
    lot.est_actif = True
    lot.date_peremption = None
    return lot


@pytest.fixture
def client_mock():
    """Client mock générique (sans crédit)."""
    client = MagicMock()
    client.id = uuid.uuid4()
    client.prenom = "Issa"
    client.nom = "Sawadogo"
    client.nom_complet = "Issa Sawadogo"
    client.telephone = "+226 70 00 00 00"
    client.email = "issa.sawadogo@example.com"
    client.est_actif = True
    client.credit_autorise = False
    client.plafond_credit = Decimal("0.00")
    client.type_client = "particulier"
    return client


@pytest.fixture
def client_credit_mock():
    """Client mock avec crédit activé (pour les tests de plafond)."""
    client = MagicMock()
    client.id = uuid.uuid4()
    client.prenom = "Aminata"
    client.nom = "Ouedraogo"
    client.nom_complet = "Aminata Ouedraogo"
    client.telephone = "+226 71 00 00 00"
    client.email = "aminata.ouedraogo@example.com"
    client.est_actif = True
    client.credit_autorise = True
    client.plafond_credit = Decimal("50000.00")
    client.type_client = "assurance"
    return client


# ─── Fixtures médicaments réels en base ───────────────────────────────────────

@pytest.fixture
def medicament_db(db):
    """Médicament réel en base (pour les tests d'intégration)."""
    from tests.usine.usine_medicaments import UsineMedicament
    return UsineMedicament.create()


@pytest.fixture
def medicament_ordonnance_db(db):
    """Médicament nécessitant une ordonnance, réel en base."""
    from tests.usine.usine_medicaments import UsineMedicamentOrdonnance
    return UsineMedicamentOrdonnance.create()


@pytest.fixture
def lot_db(db):
    """Lot réel en base (quantité 150)."""
    from tests.usine.usine_medicaments import UsineLot
    return UsineLot.create(quantite_disponible=150)


@pytest.fixture
def lot_stock_faible_db(db):
    """Lot réel en base avec stock faible (quantité 2)."""
    from tests.usine.usine_medicaments import UsineLot
    return UsineLot.create(quantite_disponible=2)


@pytest.fixture
def client_db(db):
    """Client réel en base sans crédit."""
    from tests.usine.usine_clients import UsineClient
    return UsineClient.create()


@pytest.fixture
def client_credit_db(db):
    """Client réel en base avec crédit autorisé."""
    from tests.usine.usine_clients import UsineClientCredit
    return UsineClientCredit.create()


# ─── Fixtures Bus d'événements ────────────────────────────────────────────────

@pytest.fixture
def registre_evenements():
    """Registre de gestionnaires vide pour les tests unitaires."""
    # RegistreGestionnaires est un Singleton — on efface avant et après
    from infrastructure.bus_evenements.bus import RegistreGestionnaires
    registre = RegistreGestionnaires()
    registre.tout_effacer()
    yield registre
    registre.tout_effacer()


@pytest.fixture
def bus_evenements(registre_evenements):
    """Bus d'événements pour les tests unitaires (registre isolé)."""
    from infrastructure.bus_evenements.bus import BusEvenements
    bus = BusEvenements(registre=registre_evenements)
    yield bus
    registre_evenements.tout_effacer()


# ─── Fixtures API (tests d'intégration) ───────────────────────────────────────

@pytest.fixture
def api_client():
    """Client API DRF non authentifié."""
    return APIClient()


@pytest.fixture
def api_caissier(api_client, caissier):
    """Client API authentifié en tant que caissier."""
    api_client.force_authenticate(user=caissier)
    return api_client


@pytest.fixture
def api_titulaire(api_client, titulaire):
    """Client API authentifié en tant que titulaire."""
    api_client.force_authenticate(user=titulaire)
    return api_client


@pytest.fixture
def api_pharmacien_adjoint(api_client, pharmacien_adjoint):
    """Client API authentifié en tant que pharmacien adjoint."""
    api_client.force_authenticate(user=pharmacien_adjoint)
    return api_client


@pytest.fixture
def api_gestionnaire_stock(api_client, gestionnaire_stock):
    """Client API authentifié en tant que gestionnaire de stock."""
    api_client.force_authenticate(user=gestionnaire_stock)
    return api_client


# ─── Fixtures Outbox ──────────────────────────────────────────────────────────

@pytest.fixture
def outbox_vide(db):
    """S'assure que la table Outbox est vide avant chaque test."""
    from infrastructure.outbox.modeles import EntreeOutbox
    EntreeOutbox.objects.all().delete()
    yield
    EntreeOutbox.objects.all().delete()


# ─── Fixtures Matériel (ÉTAPE 08) ─────────────────────────────────────────────

@pytest.fixture
def scanner_mock():
    """
    Mock du lecteur de code-barres.
    Simule la lecture d'un code-barres via l'interface serial/USB.
    Retourne un objet avec la méthode `lire_code_barres(timeout)`.
    """
    scanner = MagicMock()
    scanner.lire_code_barres = MagicMock(return_value="3400935190298")  # Code EAN-13 générique
    scanner.est_connecte = True
    scanner.port = "/dev/ttyUSB1"
    return scanner


@pytest.fixture
def imprimante_mock():
    """
    Mock du service d'impression ESC/POS.
    Toutes les méthodes d'impression sont des MagicMock (pas d'appel réseau).
    """
    from gestion.materiel.escpos import ServiceImprimanteESCPOS
    svc = MagicMock(spec=ServiceImprimanteESCPOS)
    svc.imprimer_recu = MagicMock()
    svc.ouvrir_tiroir = MagicMock()
    svc.imprimer_test = MagicMock()
    return svc
