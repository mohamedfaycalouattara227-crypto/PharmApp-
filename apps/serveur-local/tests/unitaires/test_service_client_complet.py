"""
tests/unitaires/test_service_client_complet.py
Tests unitaires exhaustifs du ServiceClient — objectif : couvrir les branches
manquantes de gestion/clients/services.py (56 %) et gestion/clients/vues.py (45 %).

Couverture visée :
  - creer_client : nominal, permission refusée, téléphone dupliqué
  - modifier_client : nominal, permission refusée, client introuvable
  - verifier_credit_disponible : autorisation, dépassement plafond, crédit non autorisé
  - _calculer_solde_credit : avec ventes existantes, sans client
  - anonymiser_client : nominal, permission insuffisante, client introuvable
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from gestion.clients.services import ServiceClient
from gestion.exceptions import (
    PermissionRefusee,
    CreditNonAutorise,
    PlafondCreditDepasse,
    TelephoneDejaUtilise,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_user(role: str, a_permission: bool = True):
    """Crée un utilisateur mock avec a_permission_role défini."""
    user = MagicMock()
    user.role = role
    user.a_permission_role = MagicMock(return_value=a_permission)
    user.nom_complet = f"Test {role.capitalize()}"
    return user


def _mock_client(
    id=None,
    credit_autorise: bool = True,
    plafond_credit: Decimal = Decimal("50000"),
    encours_credit: Decimal = Decimal("0"),
    est_actif: bool = True,
    nom: str = "Diallo",
    prenom: str = "Mariama",
    telephone: str = "70000001",
):
    client = MagicMock()
    client.id = id or uuid.uuid4()
    client.nom = nom
    client.prenom = prenom
    client.telephone = telephone
    client.est_actif = est_actif
    client.credit_autorise = credit_autorise
    client.plafond_credit = plafond_credit
    client.encours_credit = encours_credit
    client.nom_complet = f"{prenom} {nom}"
    return client


# ══════════════════════════════════════════════════════════════════════════════
# creer_client
# ══════════════════════════════════════════════════════════════════════════════

class TestCreerClient:

    def test_creation_client_nominal(self, db):
        """Crée un client avec toutes les données valides."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        donnees = {
            "telephone": "70111222",
            "email": "mariama@test.bf",
            "type_client": "particulier",
        }
        client = service.creer_client(
            prenom="Mariama",
            nom="Diallo",
            donnees=donnees,
            utilisateur=utilisateur,
        )
        assert client.prenom == "Mariama"
        assert client.nom == "Diallo"

    def test_creation_client_refuse_si_stagiaire(self, db):
        """Un stagiaire ne peut pas créer un client."""
        service = ServiceClient()
        utilisateur = _mock_user("stagiaire", a_permission=False)
        with pytest.raises(PermissionRefusee):
            service.creer_client(
                prenom="Test",
                nom="User",
                donnees={"telephone": "70000000"},
                utilisateur=utilisateur,
            )

    def test_creation_refuse_telephone_duplique(self, db):
        """La création est refusée si le numéro de téléphone existe déjà."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        # Premier client
        service.creer_client(
            prenom="Premier",
            nom="Client",
            donnees={"telephone": "70999888"},
            utilisateur=utilisateur,
        )
        # Deuxième client avec le même numéro
        with pytest.raises(TelephoneDejaUtilise):
            service.creer_client(
                prenom="Second",
                nom="Doublon",
                donnees={"telephone": "70999888"},
                utilisateur=utilisateur,
            )

    def test_creation_sans_telephone_acceptee(self, db):
        """La création sans téléphone est acceptée (téléphone optionnel)."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        client = service.creer_client(
            prenom="Sans",
            nom="Telephone",
            donnees={},
            utilisateur=utilisateur,
        )
        assert client.prenom == "Sans"

    def test_creation_client_avec_credit(self, db):
        """Crée un client avec crédit autorisé et plafond."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        client = service.creer_client(
            prenom="Credit",
            nom="Client",
            donnees={
                "telephone": "70888777",
                "credit_autorise": True,
                "plafond_credit": "100000.00",
            },
            utilisateur=utilisateur,
        )
        assert client.credit_autorise is True
        assert client.plafond_credit == Decimal("100000.00")


# ══════════════════════════════════════════════════════════════════════════════
# modifier_client
# ══════════════════════════════════════════════════════════════════════════════

class TestModifierClient:

    def test_modification_client_nominal(self, db):
        """Modifie un client existant avec les données valides."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        client = service.creer_client(
            prenom="Awa",
            nom="Coulibaly",
            donnees={"telephone": "70777666"},
            utilisateur=utilisateur,
        )
        client_modifie = service.modifier_client(
            client_id=client.id,
            donnees={"prenom": "Awa-Modifie", "adresse": "Secteur 15, Ouaga"},
            utilisateur=utilisateur,
        )
        assert client_modifie.prenom == "Awa-Modifie"
        assert client_modifie.adresse == "Secteur 15, Ouaga"

    def test_modification_refuse_si_stagiaire(self, db):
        """Un stagiaire ne peut pas modifier un client."""
        service = ServiceClient()
        utilisateur_stagiaire = _mock_user("stagiaire", a_permission=False)
        with pytest.raises(PermissionRefusee):
            service.modifier_client(
                client_id=uuid.uuid4(),
                donnees={"prenom": "Hack"},
                utilisateur=utilisateur_stagiaire,
            )

    def test_modification_leve_valeur_si_introuvable(self, db):
        """Lève ValueError si le client_id n'existe pas."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        with pytest.raises(ValueError, match="introuvable"):
            service.modifier_client(
                client_id=uuid.uuid4(),
                donnees={"prenom": "Fantome"},
                utilisateur=utilisateur,
            )

    def test_modification_ignore_champs_non_autorises(self, db):
        """Les champs non autorisés sont silencieusement ignorés."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        client = service.creer_client(
            prenom="Fatou",
            nom="Ndiaye",
            donnees={"telephone": "70555444"},
            utilisateur=utilisateur,
        )
        # Tenter de modifier un champ non autorisé
        client_modifie = service.modifier_client(
            client_id=client.id,
            donnees={"__class__": "hack", "prenom": "Fatou-OK"},
            utilisateur=utilisateur,
        )
        assert client_modifie.prenom == "Fatou-OK"


# ══════════════════════════════════════════════════════════════════════════════
# verifier_credit_disponible
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifierCreditDisponible:

    def test_credit_disponible_leve_rien(self):
        """Ne lève rien si le montant est dans le plafond."""
        service = ServiceClient()
        client = _mock_client(
            credit_autorise=True,
            plafond_credit=Decimal("50000"),
            encours_credit=Decimal("0"),
        )
        # Patch _calculer_solde_credit pour retourner la disponibilité
        with patch.object(
            service,
            "_calculer_solde_credit",
            return_value={
                "plafond": Decimal("50000"),
                "utilise": Decimal("0"),
                "disponible": Decimal("50000"),
            },
        ):
            # Ne doit pas lever d'exception
            service.verifier_credit_disponible(client, Decimal("10000"))

    def test_credit_non_autorise_leve_exception(self):
        """Lève CreditNonAutorise si le client n'a pas le crédit."""
        service = ServiceClient()
        client = _mock_client(credit_autorise=False)
        with pytest.raises(CreditNonAutorise):
            service.verifier_credit_disponible(client, Decimal("5000"))

    def test_plafond_depasse_leve_exception(self):
        """Lève PlafondCreditDepasse si le montant dépasse le disponible."""
        service = ServiceClient()
        client = _mock_client(
            credit_autorise=True,
            plafond_credit=Decimal("10000"),
        )
        with patch.object(
            service,
            "_calculer_solde_credit",
            return_value={
                "plafond": Decimal("10000"),
                "utilise": Decimal("9500"),
                "disponible": Decimal("500"),
            },
        ):
            with pytest.raises(PlafondCreditDepasse):
                service.verifier_credit_disponible(client, Decimal("1000"))


# ══════════════════════════════════════════════════════════════════════════════
# _calculer_solde_credit
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculerSoldeCredit:

    @pytest.mark.django_db
    def test_solde_retourne_zeros_si_client_introuvable(self):
        """Retourne des zéros si le client n'existe pas."""
        service = ServiceClient()
        resultat = service._calculer_solde_credit(uuid.uuid4())
        assert resultat["plafond"] == Decimal("0")
        assert resultat["utilise"] == Decimal("0")
        assert resultat["disponible"] == Decimal("0")

    def test_solde_calcul_correct_avec_client(self, db):
        """Calcule correctement l'encours sur un client réel."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier")
        client = service.creer_client(
            prenom="Solde",
            nom="Credit",
            donnees={
                "telephone": "70123456",
                "credit_autorise": True,
                "plafond_credit": "30000.00",
            },
            utilisateur=utilisateur,
        )
        solde = service._calculer_solde_credit(client.id)
        # Sans ventes, l'encours est 0
        assert solde["plafond"] == Decimal("30000.00")
        assert solde["utilise"] == Decimal("0")
        assert solde["disponible"] == Decimal("30000.00")


# ══════════════════════════════════════════════════════════════════════════════
# anonymiser_client
# ══════════════════════════════════════════════════════════════════════════════

class TestAnonymiserClient:

    def test_anonymisation_refuse_si_role_insuffisant(self, db):
        """Un caissier ne peut pas anonymiser un client."""
        service = ServiceClient()
        utilisateur = _mock_user("caissier", a_permission=False)
        with pytest.raises(PermissionRefusee):
            service.anonymiser_client(uuid.uuid4(), utilisateur)

    def test_anonymisation_leve_valeur_si_introuvable(self, db):
        """Lève ValueError si le client est introuvable pour anonymisation."""
        service = ServiceClient()
        utilisateur = _mock_user("pharmacien_adjoint", a_permission=True)
        # Le pharmacien_adjoint a la permission mais le client n'existe pas
        with pytest.raises(ValueError, match="introuvable"):
            service.anonymiser_client(uuid.uuid4(), utilisateur)
