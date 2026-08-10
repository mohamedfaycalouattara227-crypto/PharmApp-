"""
tests/unitaires/test_bus_evenements.py
Tests unitaires du bus d'événements PharmApp.
Couverture cible : 100 % du module infrastructure/bus_evenements/bus.py
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from infrastructure.bus_evenements.bus import (
    BusEvenements,
    Evenement,
    EvenementVenteCreee,
    EvenementVenteAnnulee,
    EvenementStockAjuste,
    EvenementAlerteStockBas,
    EvenementConnexion,
    EvenementCompteCree,
    EvenementClotureCaisse,
    EvenementProduitsControlesDelivre,
    RegistreGestionnaires,
    gestionnaire_evenement,
    obtenir_bus,
)

pytestmark = pytest.mark.unitaire


# ─── Tests de la classe Evenement ────────────────────────────────────────────

class TestEvenement:
    """Tests de la classe de base Evenement."""

    def test_id_evenement_genere_automatiquement(self):
        """Chaque événement reçoit un UUID unique à la création."""
        evt1 = EvenementVenteCreee()
        evt2 = EvenementVenteCreee()
        assert evt1.id_evenement != evt2.id_evenement
        assert isinstance(evt1.id_evenement, uuid.UUID)

    def test_cree_le_genere_automatiquement(self):
        """L'horodatage est généré automatiquement."""
        from django.utils import timezone
        evt = EvenementVenteCreee()
        assert evt.cree_le is not None
        # L'horodatage doit être dans les dernières 5 secondes
        delta = timezone.now() - evt.cree_le
        assert delta.total_seconds() < 5

    def test_nom_retourne_nom_classe(self):
        """La propriété nom retourne le nom exact de la classe."""
        evt = EvenementVenteCreee()
        assert evt.nom == "EvenementVenteCreee"

    def test_domaine_vente(self):
        """EvenementVenteCreee appartient au domaine 'vente'."""
        evt = EvenementVenteCreee()
        assert evt.domaine == "vente"

    def test_domaine_stock(self):
        """EvenementStockAjuste appartient au domaine 'stock'."""
        evt = EvenementStockAjuste()
        assert evt.domaine == "stock"

    def test_domaine_connexion(self):
        """EvenementConnexion appartient au domaine 'inconnu' (non mappé)."""
        evt = EvenementConnexion()
        # 'connexion' n'est pas dans la liste → domaine 'inconnu'
        assert evt.domaine in ("inconnu", "connexion")

    def test_evenement_vente_creee_champs_par_defaut(self):
        """Les champs optionnels ont des valeurs par défaut correctes."""
        evt = EvenementVenteCreee()
        assert evt.id_vente is None
        assert evt.numero_vente == ""
        assert evt.montant_total == "0.00"
        assert evt.articles == []

    def test_evenement_vente_creee_avec_donnees(self):
        """On peut créer un événement avec toutes ses données."""
        id_vente = uuid.uuid4()
        evt = EvenementVenteCreee(
            id_vente=id_vente,
            numero_vente="V-2024-000001",
            montant_total="2400.00",
            mode_paiement="especes",
        )
        assert evt.id_vente == id_vente
        assert evt.numero_vente == "V-2024-000001"
        assert evt.montant_total == "2400.00"

    def test_evenement_connexion_echec(self):
        """Un événement de connexion échouée transporte le bon contexte."""
        evt = EvenementConnexion(
            email_tente="pirate@attaque.com",
            succes=False,
            raison_echec="Mot de passe incorrect",
            adresse_ip="192.168.1.100",
        )
        assert not evt.succes
        assert "incorrect" in evt.raison_echec
        assert evt.adresse_ip == "192.168.1.100"


# ─── Tests du RegistreGestionnaires ──────────────────────────────────────────

class TestRegistreGestionnaires:
    """Tests du registre interne des gestionnaires."""

    @pytest.fixture(autouse=True)
    def nettoyer_registre(self):
        """Vide le registre avant et après chaque test."""
        RegistreGestionnaires().tout_effacer()
        yield
        RegistreGestionnaires().tout_effacer()

    def test_singleton(self):
        """RegistreGestionnaires est un Singleton."""
        r1 = RegistreGestionnaires()
        r2 = RegistreGestionnaires()
        assert r1 is r2

    def test_enregistrer_gestionnaire(self):
        """On peut enregistrer un gestionnaire pour un type d'événement."""
        registre = RegistreGestionnaires()
        gestionnaire = MagicMock()
        registre.enregistrer(EvenementVenteCreee, gestionnaire)
        assert gestionnaire in registre.obtenir(EvenementVenteCreee)

    def test_pas_de_doublon(self):
        """Enregistrer le même gestionnaire deux fois ne crée pas de doublon."""
        registre = RegistreGestionnaires()
        gestionnaire = MagicMock()
        registre.enregistrer(EvenementVenteCreee, gestionnaire)
        registre.enregistrer(EvenementVenteCreee, gestionnaire)
        assert registre.obtenir(EvenementVenteCreee).count(gestionnaire) == 1

    def test_plusieurs_gestionnaires_par_type(self):
        """Plusieurs gestionnaires peuvent s'abonner au même type d'événement."""
        registre = RegistreGestionnaires()
        g1, g2, g3 = MagicMock(), MagicMock(), MagicMock()
        registre.enregistrer(EvenementVenteCreee, g1)
        registre.enregistrer(EvenementVenteCreee, g2)
        registre.enregistrer(EvenementVenteCreee, g3)
        gestionnaires = registre.obtenir(EvenementVenteCreee)
        assert len(gestionnaires) == 3

    def test_obtenir_type_sans_abonnes(self):
        """Obtenir les gestionnaires d'un type sans abonnés retourne une liste vide."""
        registre = RegistreGestionnaires()
        assert registre.obtenir(EvenementVenteCreee) == []

    def test_nombre_gestionnaires(self):
        """La propriété nombre_gestionnaires compte tous les abonnements."""
        registre = RegistreGestionnaires()
        g1, g2 = MagicMock(), MagicMock()
        registre.enregistrer(EvenementVenteCreee, g1)
        registre.enregistrer(EvenementStockAjuste, g2)
        registre.enregistrer(EvenementVenteCreee, MagicMock())
        assert registre.nombre_gestionnaires == 3

    def test_tout_effacer(self):
        """tout_effacer() supprime tous les abonnements."""
        registre = RegistreGestionnaires()
        registre.enregistrer(EvenementVenteCreee, MagicMock())
        registre.enregistrer(EvenementStockAjuste, MagicMock())
        registre.tout_effacer()
        assert registre.nombre_gestionnaires == 0


# ─── Tests du BusEvenements ───────────────────────────────────────────────────

class TestBusEvenements:
    """Tests principaux du bus d'événements."""

    @pytest.fixture
    def registre_vide(self):
        """Registre vide isolé pour chaque test."""
        r = RegistreGestionnaires()
        r.tout_effacer()
        return r

    @pytest.fixture
    def bus(self, registre_vide):
        return BusEvenements(registre=registre_vide)

    def test_publier_sans_gestionnaire_retourne_rapport(self, bus):
        """Publier un événement sans gestionnaire retourne un rapport valide."""
        evt = EvenementVenteCreee()
        rapport = bus.publier(evt)
        assert rapport["evenement"] == "EvenementVenteCreee"
        assert rapport["gestionnaires_executes"] == 0
        assert rapport["erreurs"] == []

    def test_publier_appelle_le_gestionnaire(self, bus):
        """Le gestionnaire est appelé avec l'événement publié."""
        gestionnaire = MagicMock()
        bus.abonner(EvenementVenteCreee, gestionnaire)
        evt = EvenementVenteCreee(numero_vente="V-2024-001")

        bus.publier(evt)

        gestionnaire.assert_called_once_with(evt)

    def test_publier_appelle_tous_les_gestionnaires(self, bus):
        """Tous les gestionnaires abonnés reçoivent l'événement."""
        g1, g2, g3 = MagicMock(), MagicMock(), MagicMock()
        bus.abonner(EvenementVenteCreee, g1)
        bus.abonner(EvenementVenteCreee, g2)
        bus.abonner(EvenementVenteCreee, g3)
        evt = EvenementVenteCreee()

        rapport = bus.publier(evt)

        g1.assert_called_once_with(evt)
        g2.assert_called_once_with(evt)
        g3.assert_called_once_with(evt)
        assert rapport["gestionnaires_executes"] == 3

    def test_erreur_gestionnaire_ninterrompt_pas_les_autres(self, bus):
        """
        Une exception dans un gestionnaire ne doit pas empêcher
        les gestionnaires suivants d'être exécutés.
        """
        g1 = MagicMock(side_effect=RuntimeError("Erreur simulée"))
        g2 = MagicMock()
        bus.abonner(EvenementVenteCreee, g1)
        bus.abonner(EvenementVenteCreee, g2)

        rapport = bus.publier(EvenementVenteCreee())

        # g2 doit avoir été appelé malgré l'erreur dans g1
        g2.assert_called_once()
        assert len(rapport["erreurs"]) == 1
        assert rapport["gestionnaires_executes"] == 1

    def test_rapport_contient_les_erreurs(self, bus):
        """Le rapport inclut le détail des erreurs par gestionnaire."""
        message_erreur = "Erreur base de données simulée"
        g = MagicMock(side_effect=ValueError(message_erreur))
        bus.abonner(EvenementVenteCreee, g)

        rapport = bus.publier(EvenementVenteCreee())

        assert len(rapport["erreurs"]) == 1
        assert message_erreur in rapport["erreurs"][0]["erreur"]

    def test_gestionnaires_par_type_isoles(self, bus):
        """Les gestionnaires d'un type ne reçoivent pas les autres types."""
        gestionnaire_vente = MagicMock()
        gestionnaire_stock = MagicMock()
        bus.abonner(EvenementVenteCreee, gestionnaire_vente)
        bus.abonner(EvenementStockAjuste, gestionnaire_stock)

        bus.publier(EvenementVenteCreee())

        gestionnaire_vente.assert_called_once()
        gestionnaire_stock.assert_not_called()

    def test_rapport_contient_id_evenement(self, bus):
        """Le rapport contient l'identifiant unique de l'événement."""
        evt = EvenementVenteCreee()
        rapport = bus.publier(evt)
        assert rapport["id_evenement"] == str(evt.id_evenement)

    def test_abonner_puis_publier(self, bus):
        """Abonner un gestionnaire puis publier fonctionne correctement."""
        resultats = []

        def mon_gestionnaire(evt: EvenementVenteCreee):
            resultats.append(evt.numero_vente)

        bus.abonner(EvenementVenteCreee, mon_gestionnaire)
        bus.publier(EvenementVenteCreee(numero_vente="V-001"))
        bus.publier(EvenementVenteCreee(numero_vente="V-002"))

        assert resultats == ["V-001", "V-002"]

    def test_acces_au_registre(self, bus, registre_vide):
        """La propriété registre expose le registre interne."""
        assert bus.registre is registre_vide

    def test_publier_alerte_stock_bas(self, bus):
        """L'événement d'alerte de stock bas est correctement dispatché."""
        appele = []

        def sur_alerte(evt: EvenementAlerteStockBas):
            appele.append(evt.est_en_rupture)

        bus.abonner(EvenementAlerteStockBas, sur_alerte)
        bus.publier(EvenementAlerteStockBas(
            nom_medicament="Amoxicilline",
            stock_actuel=0,
            est_en_rupture=True,
        ))

        assert appele == [True]

    def test_publier_cloture_caisse(self, bus):
        """L'événement de clôture de caisse transporte les bonnes données."""
        appele_avec = []

        bus.abonner(EvenementClotureCaisse, appele_avec.append)
        evt = EvenementClotureCaisse(
            date_cloture="2024-01-15",
            chiffre_affaires="125000.00",
            nombre_ventes=87,
        )
        bus.publier(evt)

        assert len(appele_avec) == 1
        assert appele_avec[0].nombre_ventes == 87

    def test_obtenir_bus_global(self):
        """obtenir_bus() retourne toujours la même instance globale."""
        bus1 = obtenir_bus()
        bus2 = obtenir_bus()
        assert bus1 is bus2


# ─── Tests du décorateur @gestionnaire_evenement ─────────────────────────────

class TestDecorateurGestionnaireEvenement:
    """Tests du décorateur @gestionnaire_evenement."""

    @pytest.fixture(autouse=True)
    def nettoyer(self):
        RegistreGestionnaires().tout_effacer()
        yield
        RegistreGestionnaires().tout_effacer()

    def test_decorateur_enregistre_la_fonction(self):
        """@gestionnaire_evenement enregistre la fonction sur le bus global."""
        @gestionnaire_evenement(EvenementVenteCreee)
        def sur_vente_creee(evt):
            pass

        registre = RegistreGestionnaires()
        assert sur_vente_creee in registre.obtenir(EvenementVenteCreee)

    def test_decorateur_retourne_la_fonction_originale(self):
        """Le décorateur ne modifie pas la fonction décorée."""
        @gestionnaire_evenement(EvenementStockAjuste)
        def mon_gestionnaire(evt):
            return "ok"

        assert mon_gestionnaire.__name__ == "mon_gestionnaire"
        assert mon_gestionnaire(MagicMock()) == "ok"

    def test_decorateur_plusieurs_types(self):
        """On peut décorer la même fonction pour plusieurs types d'événements."""
        @gestionnaire_evenement(EvenementVenteCreee)
        @gestionnaire_evenement(EvenementVenteAnnulee)
        def sur_evenement_vente(evt):
            pass

        registre = RegistreGestionnaires()
        assert sur_evenement_vente in registre.obtenir(EvenementVenteCreee)
        assert sur_evenement_vente in registre.obtenir(EvenementVenteAnnulee)
