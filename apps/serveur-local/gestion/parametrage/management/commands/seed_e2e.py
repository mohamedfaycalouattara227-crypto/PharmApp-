from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from gestion.authentification.models import RoleUtilisateur, UtilisateurPharmacien
from gestion.catalogue.models import CategorieProduit, Lot, Medicament
from gestion.clients.models import Client, TypeClient


class Command(BaseCommand):
    help = "Provisionne de manière idempotente les données nécessaires aux scénarios Playwright E2E."

    @transaction.atomic
    def handle(self, *args, **options):
        categorie, _ = CategorieProduit.objects.update_or_create(
            code="E2E",
            defaults={
                "nom": "Catalogue E2E PharmApp",
                "description": "Données déterministes pour les tests Playwright.",
                "est_active": True,
            },
        )

        utilisateurs = [
            {
                "email": "caissier-e2e@pharmapp-test.bf",
                "prenom": "Caissier",
                "nom": "E2E",
                "role": RoleUtilisateur.CAISSIER,
            },
            {
                "email": "adjoint-e2e@pharmapp-test.bf",
                "prenom": "Adjoint",
                "nom": "E2E",
                "role": RoleUtilisateur.PHARMACIEN_ADJOINT,
            },
        ]
        comptes = {}
        for donnees in utilisateurs:
            email = donnees["email"]
            utilisateur, _ = UtilisateurPharmacien.objects.get_or_create(
                email=email,
                defaults=donnees,
            )
            utilisateur.prenom = donnees["prenom"]
            utilisateur.nom = donnees["nom"]
            utilisateur.role = donnees["role"]
            utilisateur.est_actif = True
            utilisateur.est_verrouille = False
            utilisateur.tentatives_connexion_echouees = 0
            utilisateur.set_password("MotDePasse@E2E-2026!")
            utilisateur.save()
            comptes[email] = utilisateur

        medicament, _ = Medicament.objects.update_or_create(
            code_cis="E2E-PARACETAMOL-001",
            defaults={
                "nom": "Paracétamol E2E 500 mg",
                "denomination_commune_internationale": "Paracétamol",
                "code_barre": "E2E5000001",
                "categorie": categorie,
                "forme_pharmaceutique": "Comprimé",
                "dosage": "500 mg",
                "conditionnement": "Boîte de 16",
                "fabricant": "PharmApp E2E",
                "prix_public": Decimal("1500.00"),
                "prix_min_autorise": Decimal("1000.00"),
                "prix_max_autorise": Decimal("2000.00"),
                "est_actif": True,
                "necessite_ordonnance": False,
                "est_produit_controle": False,
                "seuil_alerte_stock": 20,
                "seuil_rupture_stock": 5,
            },
        )

        Lot.objects.update_or_create(
            numero_lot_interne="E2E-LOT-PAR-001",
            defaults={
                "medicament": medicament,
                "numero_lot": "E2E-PAR-LOT-001",
                "date_fabrication": timezone.now().date() - timedelta(days=30),
                "date_peremption": timezone.now().date() + timedelta(days=365),
                "quantite_initiale": 100,
                "quantite_disponible": 100,
                "prix_achat_unitaire": Decimal("800.00"),
                "fournisseur": "Fournisseur E2E",
                "emplacement_stockage": "RAYON-E2E",
                "est_actif": True,
            },
        )

        client, _ = Client.objects.update_or_create(
            telephone="70000001",
            defaults={
                "nom": "Client E2E",
                "prenom": "Test",
                "email": "client-e2e@pharmapp-test.bf",
                "type_client": TypeClient.PARTICULIER,
                "credit_autorise": True,
                "plafond_credit": Decimal("100000.00"),
                "encours_credit": Decimal("0.00"),
                "est_actif": True,
                "est_anonymise": False,
            },
        )

        self.stdout.write(self.style.SUCCESS("seed_e2e terminé avec succès"))
        self.stdout.write(
            "medicaments=1 lots=1 clients=1 utilisateurs=%d caissier=%s adjoint=%s"
            % (
                len(comptes),
                comptes["caissier-e2e@pharmapp-test.bf"].id,
                comptes["adjoint-e2e@pharmapp-test.bf"].id,
            )
        )
