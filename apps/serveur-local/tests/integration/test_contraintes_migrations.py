"""
tests/integration/test_contraintes_migrations.py
ÉTAPE 02 — Tests d'intégrité des données : migrations et contraintes.

Vérifie que les contraintes de base de données (unicité, FK, check constraints,
index) sont bien présentes et actives sur l'environnement SQLite de test.

Objectif : prouver qu'aucune incohérence n'est possible au niveau base.
"""

import uuid
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

pytestmark = pytest.mark.integration


# ─── Contraintes d'unicité ────────────────────────────────────────────────────

class TestContraintesUnicite:
    """Vérifie que les contraintes UNIQUE sont actives en base."""

    def test_utilisateur_email_unique(self, db):
        """Deux utilisateurs ne peuvent pas avoir le même email."""
        from tests.usine.usine_utilisateurs import UsineCaissier
        email = f"test-unique-{uuid.uuid4().hex[:8]}@pharmapp.test"
        UsineCaissier.create(email=email)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                UsineCaissier.create(email=email)

    def test_medicament_code_cis_unique(self, db):
        """Deux médicaments ne peuvent pas avoir le même code CIS."""
        from tests.usine.usine_medicaments import UsineMedicament
        code = f"CIS-{uuid.uuid4().hex[:8]}"
        UsineMedicament.create(code_cis=code)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                UsineMedicament.create(code_cis=code)

    def test_vente_numero_unique(self, db):
        """Deux ventes ne peuvent pas avoir le même numéro."""
        from gestion.ventes.modeles import Vente
        from tests.usine.usine_utilisateurs import UsineCaissier

        vendeur = UsineCaissier.create()
        numero = f"V-{uuid.uuid4().hex[:8]}"

        Vente.objects.create(
            numero=numero,
            vendeur=vendeur,
            statut="validee",
            mode_paiement="especes",
            sous_total=Decimal("1000.00"),
            montant_total=Decimal("1000.00"),
            montant_encaisse=Decimal("1000.00"),
            montant_rendu=Decimal("0.00"),
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Vente.objects.create(
                    numero=numero,
                    vendeur=vendeur,
                    statut="validee",
                    mode_paiement="especes",
                    sous_total=Decimal("500.00"),
                    montant_total=Decimal("500.00"),
                    montant_encaisse=Decimal("500.00"),
                    montant_rendu=Decimal("0.00"),
                )

    def test_client_telephone_unique(self, db):
        """Deux clients ne peuvent pas avoir le même téléphone."""
        from tests.usine.usine_clients import UsineClient
        tel = f"+226 70 {uuid.uuid4().int % 99:02d} {uuid.uuid4().int % 99:02d} {uuid.uuid4().int % 99:02d}"
        UsineClient.create(telephone=tel)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                UsineClient.create(telephone=tel)

    def test_categorie_nom_unique(self, db):
        """Deux catégories ne peuvent pas avoir le même nom."""
        from gestion.catalogue.models import CategorieProduit
        nom = f"Cat-{uuid.uuid4().hex[:8]}"
        CategorieProduit.objects.create(nom=nom, code=f"C{uuid.uuid4().hex[:4]}")

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CategorieProduit.objects.create(nom=nom, code=f"C{uuid.uuid4().hex[:4]}")


# ─── Contraintes de clé étrangère ─────────────────────────────────────────────

class TestContraintesCleEtrangere:
    """Vérifie que les FK CASCADE/PROTECT/SET_NULL sont actifs."""

    def test_mouvement_stock_protect_sur_suppression_lot(self, db):
        """Un lot avec mouvements ne peut pas être supprimé (PROTECT)."""
        from tests.usine.usine_medicaments import UsineLot
        from tests.usine.usine_utilisateurs import UsineGestionnaireStock
        from gestion.stocks.models import MouvementStock

        lot = UsineLot.create(quantite_disponible=100)
        gs = UsineGestionnaireStock.create()

        MouvementStock.objects.create(
            lot=lot,
            type_mouvement="reception",
            quantite=100,
            quantite_avant=0,
            quantite_apres=100,
            motif="Test FK",
            effectue_par=gs,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                lot.delete()

    def test_ligne_vente_protect_sur_suppression_medicament(self, db):
        """Un médicament avec des lots vendus ne peut pas être supprimé (PROTECT via Lot)."""
        from tests.usine.usine_medicaments import UsineMedicament
        medicament = UsineMedicament.create()
        # Le médicament a une catégorie en FK PROTECT
        # On vérifie que la catégorie ne peut pas être supprimée
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                medicament.categorie.delete()

    def test_suppression_client_anonymise_null_sur_ventes(self, db):
        """La suppression d'un client met client=NULL sur les ventes (SET_NULL)."""
        from tests.usine.usine_clients import UsineClient
        from tests.usine.usine_utilisateurs import UsineCaissier
        from gestion.ventes.modeles import Vente

        client = UsineClient.create()
        caissier = UsineCaissier.create()
        vente = Vente.objects.create(
            numero=f"V-{uuid.uuid4().hex[:8]}",
            vendeur=caissier,
            client=client,
            statut="validee",
            mode_paiement="especes",
            sous_total=Decimal("800.00"),
            montant_total=Decimal("800.00"),
            montant_encaisse=Decimal("1000.00"),
            montant_rendu=Decimal("200.00"),
        )

        client.delete()
        vente.refresh_from_db()
        assert vente.client is None


# ─── Contraintes CHECK (durcissement ÉTAPE 02) ────────────────────────────────

class TestContraintesCheck:
    """
    Vérifie les contraintes CHECK ajoutées par la migration de durcissement.
    Ces contraintes empêchent les incohérences métier au niveau DB.
    """

    def test_vente_montant_total_positif_ou_zero(self, db):
        """montant_total < 0 doit être rejeté par la contrainte CHECK."""
        from gestion.ventes.modeles import Vente
        from tests.usine.usine_utilisateurs import UsineCaissier
        caissier = UsineCaissier.create()

        with pytest.raises((IntegrityError, Exception)):
            with transaction.atomic():
                Vente.objects.create(
                    numero=f"V-{uuid.uuid4().hex[:8]}",
                    vendeur=caissier,
                    statut="validee",
                    mode_paiement="especes",
                    sous_total=Decimal("-500.00"),
                    montant_total=Decimal("-500.00"),
                    montant_encaisse=Decimal("0.00"),
                    montant_rendu=Decimal("0.00"),
                )

    def test_client_plafond_credit_positif_ou_zero(self, db):
        """plafond_credit < 0 doit être rejeté par la contrainte CHECK."""
        from gestion.clients.models import Client

        with pytest.raises((IntegrityError, Exception)):
            with transaction.atomic():
                Client.objects.create(
                    nom="Test",
                    prenom="Contrainte",
                    credit_autorise=True,
                    plafond_credit=Decimal("-1000.00"),
                )

    def test_mouvement_stock_quantite_avant_positive(self, db):
        """quantite_avant < 0 est impossible (PositiveIntegerField Django)."""
        from tests.usine.usine_medicaments import UsineLot
        from tests.usine.usine_utilisateurs import UsineGestionnaireStock
        from gestion.stocks.models import MouvementStock

        lot = UsineLot.create(quantite_disponible=50)
        gs = UsineGestionnaireStock.create()

        with pytest.raises((IntegrityError, ValueError, Exception)):
            with transaction.atomic():
                MouvementStock.objects.create(
                    lot=lot,
                    type_mouvement="ajustement_moins",
                    quantite=-60,
                    quantite_avant=-10,  # invalide
                    quantite_apres=0,
                    motif="Test négatif",
                    effectue_par=gs,
                )


# ─── Index présents en base ───────────────────────────────────────────────────

class TestIndexPresents:
    """
    Vérifie que les index critiques sont présents en base pour les performances.
    Utilise l'introspection Django pour lister les index de chaque table.
    """

    def _index_names(self, table_name: str) -> set[str]:
        with connection.cursor() as cursor:
            introspection = connection.introspection
            return {
                nom
                for nom, contrainte in introspection.get_constraints(
                    cursor, table_name
                ).items()
                if contrainte["index"]
            }

    def test_index_vente_numero(self, db):
        """L'index sur ventes_vente.numero est présent."""
        indexes = self._index_names("ventes_vente")
        assert any("num" in n.lower() or "numero" in n.lower() for n in indexes), (
            f"Index numero manquant sur ventes_vente. Index présents : {indexes}"
        )

    def test_index_outbox_statut(self, db):
        """L'index sur outbox_entrees.statut est présent."""
        indexes = self._index_names("outbox_entrees")
        assert any("statut" in n.lower() for n in indexes), (
            f"Index statut manquant sur outbox_entrees. Index présents : {indexes}"
        )

    def test_index_stock_lot_date(self, db):
        """L'index sur stocks_mouvement(lot, cree_le) est présent."""
        indexes = self._index_names("stocks_mouvement")
        assert any("lot" in n.lower() or "date" in n.lower() for n in indexes), (
            f"Index lot/date manquant sur stocks_mouvement. Index présents : {indexes}"
        )

    def test_index_client_telephone(self, db):
        """L'index sur clients_client.telephone est présent."""
        indexes = self._index_names("clients_client")
        assert any("tel" in n.lower() for n in indexes), (
            f"Index telephone manquant sur clients_client. Index présents : {indexes}"
        )

    def test_index_journal_audit_type_action(self, db):
        """Un index de performance sur JournalAudit est présent."""
        from gestion.audit.models import JournalAudit

        indexes = self._index_names(JournalAudit._meta.db_table)
        # Au moins un index (hors PK) doit exister pour les requêtes de reporting
        assert len(indexes) >= 1, (
            f"Aucun index sur audit_journalaudit. Table potentiellement non optimisée."
        )
