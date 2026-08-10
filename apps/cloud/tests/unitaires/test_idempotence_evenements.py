"""
tests/unitaires/test_idempotence_evenements.py
Tests unitaires — idempotence de l'ingestion d'événements.
"""

import uuid
from datetime import datetime, timezone

import pytest
from django.utils import timezone as dj_timezone

from apps.identite.models import Officine, StatutAbonnement
from apps.identite.services import generer_cle_api
from apps.synchronisation.models import EvenementSync, StatutTraitement
from apps.synchronisation.services import DonneesEvenement, ServiceIngestion


def creer_officine_test(code: str = "PHA-TEST") -> Officine:
    """Crée une officine de test en base."""
    _, prefixe, hash_cle = generer_cle_api()
    return Officine.objects.create(
        nom="Pharmacie Test",
        code=code,
        cle_api_hash=hash_cle,
        cle_api_prefixe=prefixe,
        statut_abonnement=StatutAbonnement.ACTIF,
        est_active=True,
    )


def donnees_test(event_uuid=None, type_ev="VENTE_CREEE") -> DonneesEvenement:
    """Construit un DonneesEvenement de test."""
    return DonneesEvenement(
        uuid=event_uuid or uuid.uuid4(),
        type_evenement=type_ev,
        version_schema=1,
        timestamp_local=dj_timezone.now(),
        charge_utile={"total": 5000, "lignes": []},
    )


@pytest.mark.django_db
@pytest.mark.unitaire
class TestIdempotenceEvenements:

    def test_premier_envoi_retourne_recu(self):
        """Le premier envoi d'un UUID doit retourner statut='reçu'."""
        officine = creer_officine_test("PHA-IDP-01")
        donnees = donnees_test()
        resultat = ServiceIngestion.ingerer(officine, donnees)
        assert resultat.statut == "reçu"
        assert str(resultat.uuid) == str(donnees.uuid)

    def test_deuxieme_envoi_meme_uuid_retourne_deja_connu(self):
        """Le deuxième envoi du même UUID doit retourner statut='déjà_connu'."""
        officine = creer_officine_test("PHA-IDP-02")
        donnees = donnees_test()

        # Premier envoi
        ServiceIngestion.ingerer(officine, donnees)

        # Deuxième envoi — même UUID
        resultat = ServiceIngestion.ingerer(officine, donnees)
        assert resultat.statut == "déjà_connu"

    def test_deuxieme_envoi_ne_cree_pas_de_doublon(self):
        """Le deuxième envoi ne doit pas créer d'entrée supplémentaire en base."""
        officine = creer_officine_test("PHA-IDP-03")
        donnees = donnees_test()

        ServiceIngestion.ingerer(officine, donnees)
        ServiceIngestion.ingerer(officine, donnees)

        nb = EvenementSync.objects.filter(uuid=donnees.uuid).count()
        assert nb == 1, f"Doublon détecté : {nb} entrées pour le même UUID"

    def test_uuid_different_cree_nouvel_evenement(self):
        """Deux UUIDs différents doivent créer deux événements distincts."""
        officine = creer_officine_test("PHA-IDP-04")
        donnees1 = donnees_test()
        donnees2 = donnees_test()  # UUID différent

        r1 = ServiceIngestion.ingerer(officine, donnees1)
        r2 = ServiceIngestion.ingerer(officine, donnees2)

        assert r1.statut == "reçu"
        assert r2.statut == "reçu"
        assert str(r1.uuid) != str(r2.uuid)
        assert EvenementSync.objects.filter(officine=officine).count() == 2

    def test_evenement_persiste_avec_bonne_officine(self):
        """L'événement doit être lié à l'officine émettrice."""
        officine = creer_officine_test("PHA-IDP-05")
        donnees = donnees_test()

        ServiceIngestion.ingerer(officine, donnees)

        ev = EvenementSync.objects.get(uuid=donnees.uuid)
        assert ev.officine_id == officine.id

    def test_evenement_heartbeat_traite(self):
        """Un HEARTBEAT doit être ingéré et marqué TRAITE."""
        officine = creer_officine_test("PHA-IDP-06")
        donnees = donnees_test(type_ev="HEARTBEAT")
        donnees = DonneesEvenement(
            uuid=donnees.uuid,
            type_evenement="HEARTBEAT",
            version_schema=1,
            timestamp_local=dj_timezone.now(),
            charge_utile={},
        )

        ServiceIngestion.ingerer(officine, donnees)

        ev = EvenementSync.objects.get(uuid=donnees.uuid)
        assert ev.statut_traitement == StatutTraitement.TRAITE

    def test_type_inconnu_marque_ignore(self):
        """Un type d'événement inconnu doit être marqué IGNORE, jamais silencieux."""
        officine = creer_officine_test("PHA-IDP-07")
        donnees = DonneesEvenement(
            uuid=uuid.uuid4(),
            type_evenement="TYPE_COMPLETEMENT_INCONNU_XYZ",
            version_schema=1,
            timestamp_local=dj_timezone.now(),
            charge_utile={"data": "test"},
        )

        ServiceIngestion.ingerer(officine, donnees)

        ev = EvenementSync.objects.get(uuid=donnees.uuid)
        assert ev.statut_traitement == StatutTraitement.IGNORE
        assert ev.message_erreur != ""
