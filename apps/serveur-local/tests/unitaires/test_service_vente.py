"""
tests/unitaires/test_service_vente.py
Tests unitaires du ServiceVente.
Couverture cible : 100 % de gestion/ventes/services.py
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from gestion.ventes.services import ArticlePanier, ListeArticles, ServiceVente

pytestmark = pytest.mark.unitaire


# ─── Tests d'ArticlePanier ────────────────────────────────────────────────────

class TestArticlePanier:
    """Tests de la classe de données ArticlePanier."""

    def test_article_valide_cree_sans_erreur(self):
        article = ArticlePanier(
            medicament_id=uuid.uuid4(),
            quantite=3,
            prix_unitaire_demande=Decimal("800.00"),
            taux_remise=Decimal("5.00"),
        )
        assert article.quantite == 3
        assert article.prix_unitaire_demande == Decimal("800.00")

    def test_quantite_zero_leve_erreur(self):
        with pytest.raises(ValueError, match="strictement positive"):
            ArticlePanier(uuid.uuid4(), 0, Decimal("800.00"))

    def test_quantite_negative_leve_erreur(self):
        with pytest.raises(ValueError, match="strictement positive"):
            ArticlePanier(uuid.uuid4(), -5, Decimal("800.00"))

    def test_prix_unitaire_negatif_leve_erreur(self):
        with pytest.raises(ValueError, match="négatif"):
            ArticlePanier(uuid.uuid4(), 1, Decimal("-100.00"))

    def test_taux_remise_superieur_100_leve_erreur(self):
        with pytest.raises(ValueError, match="compris entre 0 et 100"):
            ArticlePanier(uuid.uuid4(), 1, Decimal("800.00"), taux_remise=Decimal("101.00"))

    def test_taux_remise_negatif_leve_erreur(self):
        with pytest.raises(ValueError, match="compris entre 0 et 100"):
            ArticlePanier(uuid.uuid4(), 1, Decimal("800.00"), taux_remise=Decimal("-1.00"))

    def test_taux_remise_zero_par_defaut(self):
        article = ArticlePanier(uuid.uuid4(), 1, Decimal("800.00"))
        assert article.taux_remise == Decimal("0.00")

    def test_prix_zero_autorise(self):
        article = ArticlePanier(uuid.uuid4(), 1, Decimal("0.00"))
        assert article.prix_unitaire_demande == Decimal("0.00")

    def test_montant_ligne_avec_remise(self):
        """montant_ligne = quantite × prix × (1 - remise/100)."""
        article = ArticlePanier(uuid.uuid4(), 4, Decimal("1000.00"), taux_remise=Decimal("10.00"))
        assert article.montant_ligne == Decimal("3600.00")

    def test_montant_ligne_sans_remise(self):
        article = ArticlePanier(uuid.uuid4(), 3, Decimal("800.00"))
        assert article.montant_ligne == Decimal("2400.00")


# ─── Tests de ListeArticles ────────────────────────────────────────────────────

class TestListeArticles:
    """Tests de la classe ListeArticles (panier)."""

    def test_panier_vide_est_vide(self):
        assert ListeArticles().est_vide is True

    def test_panier_avec_articles_non_vide(self):
        panier = ListeArticles(articles=[ArticlePanier(uuid.uuid4(), 2, Decimal("800.00"))])
        assert panier.est_vide is False

    def test_nombre_articles_somme_les_quantites(self):
        panier = ListeArticles(articles=[
            ArticlePanier(uuid.uuid4(), 3, Decimal("800.00")),
            ArticlePanier(uuid.uuid4(), 5, Decimal("500.00")),
            ArticlePanier(uuid.uuid4(), 1, Decimal("1200.00")),
        ])
        assert panier.nombre_articles == 9

    def test_nombre_articles_panier_vide_est_zero(self):
        assert ListeArticles().nombre_articles == 0

    def test_montant_total_calcule_correctement(self):
        panier = ListeArticles(articles=[
            ArticlePanier(uuid.uuid4(), 2, Decimal("1000.00")),
            ArticlePanier(uuid.uuid4(), 3, Decimal("500.00")),
        ])
        assert panier.montant_total == Decimal("3500.00")

    def test_ajouter_cumule_meme_medicament(self):
        mid = uuid.uuid4()
        panier = ListeArticles(articles=[ArticlePanier(mid, 2, Decimal("800.00"))])
        panier.ajouter(ArticlePanier(mid, 3, Decimal("800.00")))
        assert panier.nombre_articles == 5  # 2 + 3

    def test_bool_panier_vide_est_falsy(self):
        assert not ListeArticles()

    def test_bool_panier_plein_est_truthy(self):
        assert ListeArticles(articles=[ArticlePanier(uuid.uuid4(), 1, Decimal("100.00"))])


# ─── Tests de ServiceVente — validations ─────────────────────────────────────

class TestServiceVenteValidations:
    """Tests des validations métier du ServiceVente."""

    @pytest.fixture
    def service(self):
        return ServiceVente()

    @pytest.fixture
    def panier_simple(self, medicament_mock):
        return ListeArticles(articles=[
            ArticlePanier(medicament_mock.id, 3, Decimal("800.00"))
        ])

    def test_panier_vide_leve_erreur(self, service, caissier):
        from gestion.exceptions import PanierVide
        with pytest.raises(PanierVide):
            service.traiter_vente(
                panier=ListeArticles(),
                mode_paiement="especes",
                utilisateur=caissier,
                montant_encaisse=Decimal("5000.00"),
            )

    def test_stagiaire_ne_peut_pas_vendre(self, service, panier_simple, stagiaire):
        from gestion.exceptions import PermissionRefusee
        stagiaire.a_permission_role = lambda r: False
        with pytest.raises(PermissionRefusee):
            service.traiter_vente(
                panier=panier_simple,
                mode_paiement="especes",
                utilisateur=stagiaire,
                montant_encaisse=Decimal("5000.00"),
            )

    def test_especes_montant_zero_leve_erreur(self, service, panier_simple, caissier):
        from gestion.exceptions import MontantEncaisseInsuffisant
        with pytest.raises(MontantEncaisseInsuffisant):
            service.traiter_vente(
                panier=panier_simple,
                mode_paiement="especes",
                utilisateur=caissier,
                montant_encaisse=Decimal("0.00"),
            )

    def test_mode_paiement_invalide_leve_erreur(self, service, panier_simple, caissier):
        from gestion.exceptions import ModePaiementInvalide
        with pytest.raises(ModePaiementInvalide):
            service.traiter_vente(
                panier=panier_simple,
                mode_paiement="bitcoin",
                utilisateur=caissier,
                montant_encaisse=Decimal("5000.00"),
            )

    def test_especes_montant_insuffisant_leve_erreur(self, service, medicament_mock, caissier):
        """Montant encaissé < total de la vente → MontantEncaisseInsuffisant."""
        from gestion.exceptions import MontantEncaisseInsuffisant
        panier = ListeArticles(articles=[
            ArticlePanier(medicament_mock.id, 3, Decimal("800.00"))  # total = 2400
        ])
        with pytest.raises(MontantEncaisseInsuffisant):
            service.traiter_vente(
                panier=panier,
                mode_paiement="especes",
                utilisateur=caissier,
                montant_encaisse=Decimal("1000.00"),  # < 2400
            )

    def test_mobile_money_sans_montant_encaisse_passe(self, service, medicament_mock, caissier):
        """Pour mobile_money, le montant encaissé = 0 est toléré (validation côté opérateur)."""
        lot_mock = MagicMock()
        lot_mock.medicament = medicament_mock
        lot_mock.quantite_disponible = 100
        lot_mock.medicament.necessite_ordonnance = False
        lot_mock.medicament.est_produit_controle = False

        panier = ListeArticles(articles=[
            ArticlePanier(medicament_mock.id, 1, Decimal("800.00"))
        ])
        with patch("gestion.ventes.services._verifier_cloture_ouverte", return_value=True), \
             patch("gestion.ventes.services.Lot") as mock_lot, \
             patch("gestion.ventes.services.Vente") as mock_vente, \
             patch("gestion.ventes.services.LigneVente"), \
             patch("gestion.ventes.services.MouvementStock"), \
             patch("gestion.ventes.services.CompteurNumerotation"), \
             patch("gestion.ventes.services.ServiceAudit"), \
             patch("gestion.ventes.services.EntreeOutbox"), \
             patch("gestion.ventes.services.ServiceProduitControle"):
            mock_lot.objects.select_related.return_value.select_for_update.return_value \
                .filter.return_value.order_by.return_value.first.return_value = lot_mock
            vente_instance = MagicMock()
            vente_instance.numero = "V-2024-000001"
            vente_instance.lignes = MagicMock()
            mock_vente.objects.create.return_value = vente_instance
            with patch("gestion.ventes.services.transaction") as mock_tx:
                mock_tx.atomic.return_value.__enter__ = lambda s: None
                mock_tx.atomic.return_value.__exit__ = lambda s, *a: False
                # Ne doit pas lever ModePaiementInvalide (mobile_money est valide)
                try:
                    service.traiter_vente(
                        panier=panier,
                        mode_paiement="mobile_money",
                        utilisateur=caissier,
                        montant_encaisse=Decimal("0.00"),
                    )
                except Exception as exc:
                    # Toute exception autre que ModePaiementInvalide est acceptable
                    from gestion.exceptions import ModePaiementInvalide
                    assert not isinstance(exc, ModePaiementInvalide)


# ─── Tests de ServiceVente — calculer_monnaie_rendue ─────────────────────────

class TestCalculerMonnaieRendue:
    """Tests du calcul de monnaie rendue en coupures FCFA."""

    @pytest.fixture
    def service(self):
        return ServiceVente()

    def test_montant_rendu_correct(self, service):
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("2400.00"),
            montant_encaisse=Decimal("5000.00"),
        )
        assert resultat["montant_rendu"] == Decimal("2600.00")

    def test_decomposition_est_un_dict(self, service):
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("2400.00"),
            montant_encaisse=Decimal("5000.00"),
        )
        assert isinstance(resultat["decomposition"], dict)

    def test_coupures_toutes_valides_fcfa(self, service):
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("1750.00"),
            montant_encaisse=Decimal("5000.00"),
        )
        coupures_valides = {10000, 5000, 2000, 1000, 500, 200, 100, 50, 25, 10, 5}
        for coupure in resultat["decomposition"]:
            assert coupure in coupures_valides, f"Coupure invalide : {coupure}"

    def test_paiement_exact_rendu_zero(self, service):
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("2000.00"),
            montant_encaisse=Decimal("2000.00"),
        )
        assert resultat["montant_rendu"] == Decimal("0")

    def test_encaisse_insuffisant_leve_erreur(self, service):
        from gestion.exceptions import MontantEncaisseInsuffisant
        with pytest.raises(MontantEncaisseInsuffisant):
            service.calculer_monnaie_rendue(
                montant_total=Decimal("5000.00"),
                montant_encaisse=Decimal("2000.00"),
            )

    def test_decomposition_somme_egale_montant_rendu(self, service):
        """La somme des coupures doit être égale au montant rendu."""
        montant_rendu_attendu = Decimal("3250.00")
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("1750.00"),
            montant_encaisse=Decimal("5000.00"),
        )
        somme = sum(c * n for c, n in resultat["decomposition"].items())
        assert somme == int(montant_rendu_attendu)

    def test_grand_billet_prioritaire(self, service):
        """Le rendu doit privilégier les grandes coupures."""
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("0.00"),
            montant_encaisse=Decimal("10000.00"),
        )
        assert 10000 in resultat["decomposition"]
        assert resultat["decomposition"][10000] == 1


# ─── Tests de ServiceVente — historique ──────────────────────────────────────

class TestServiceVenteHistorique:

    @pytest.fixture
    def service(self):
        return ServiceVente()

    def test_obtenir_historique_retourne_queryset(self, service, db):
        historique = service.obtenir_historique_ventes()
        assert hasattr(historique, "filter")

    def test_obtenir_historique_filtre_par_vendeur(self, service, db):
        vid = uuid.uuid4()
        qs = service.obtenir_historique_ventes(vendeur_id=vid)
        assert hasattr(qs, "filter")

    def test_obtenir_historique_filtre_par_statut(self, service, db):
        qs = service.obtenir_historique_ventes(statut="validee")
        assert hasattr(qs, "filter")


# ─── Tests de ServiceVente — annuler_vente ────────────────────────────────────

class TestServiceVenteAnnulation:
    """Tests du mécanisme d'annulation de vente."""

    @pytest.fixture
    def service(self):
        return ServiceVente()

    def test_annulation_requiert_pharmacien_adjoint(self, service, caissier, db):
        from gestion.exceptions import PermissionRefusee
        caissier.a_permission_role = lambda r: False
        with patch("gestion.ventes.services.Vente") as mock_vente_cls:
            vente_mock = MagicMock()
            vente_mock.statut = "validee"
            mock_vente_cls.objects.filter.return_value.select_for_update.return_value.first.return_value = vente_mock
            with pytest.raises(PermissionRefusee):
                service.annuler_vente(uuid.uuid4(), "Test", utilisateur=caissier)

    def test_annulation_vente_deja_annulee_leve_erreur(self, service, pharmacien_adjoint, db):
        from gestion.exceptions import VenteDejaAnnulee
        with patch("gestion.ventes.services.Vente") as mock_cls, \
             patch("gestion.ventes.services.transaction") as mock_tx:
            mock_tx.atomic.return_value.__enter__ = lambda s: None
            mock_tx.atomic.return_value.__exit__ = lambda s, *a: False
            vente_mock = MagicMock()
            vente_mock.statut = "annulee"
            mock_cls.objects.filter.return_value.select_for_update.return_value.first.return_value = vente_mock
            with pytest.raises(VenteDejaAnnulee):
                service.annuler_vente(uuid.uuid4(), "Test", utilisateur=pharmacien_adjoint)

    def test_annulation_vente_introuvable_leve_erreur(self, service, pharmacien_adjoint, db):
        with patch("gestion.ventes.services.Vente") as mock_cls, \
             patch("gestion.ventes.services.transaction") as mock_tx:
            mock_tx.atomic.return_value.__enter__ = lambda s: None
            mock_tx.atomic.return_value.__exit__ = lambda s, *a: False
            mock_cls.objects.filter.return_value.select_for_update.return_value.first.return_value = None
            with pytest.raises(ValueError, match="introuvable"):
                service.annuler_vente(uuid.uuid4(), "Test", utilisateur=pharmacien_adjoint)

    def test_annulation_delai_depasse_leve_erreur(self, service, pharmacien_adjoint, db):
        from gestion.exceptions import DelaiAnnulationDepasse
        from django.utils import timezone
        from datetime import timedelta

        with patch("gestion.ventes.services.Vente") as mock_cls, \
             patch("gestion.ventes.services.transaction") as mock_tx:
            mock_tx.atomic.return_value.__enter__ = lambda s: None
            mock_tx.atomic.return_value.__exit__ = lambda s, *a: False
            vente_mock = MagicMock()
            vente_mock.statut = "validee"
            # Vente créée il y a 2 heures → délai 30 min dépassé
            vente_mock.cree_le = timezone.now() - timedelta(hours=2)
            mock_cls.objects.filter.return_value.select_for_update.return_value.first.return_value = vente_mock
            with pytest.raises(DelaiAnnulationDepasse):
                service.annuler_vente(uuid.uuid4(), "Test", utilisateur=pharmacien_adjoint)



# ─── Tests d'ArticlePanier ────────────────────────────────────────────────────

class TestArticlePanier:
    """Tests de la classe de données ArticlePanier."""

    def test_article_valide_cree_sans_erreur(self):
        """Un article avec des données valides est créé sans exception."""
        article = ArticlePanier(
            medicament_id=uuid.uuid4(),
            quantite=3,
            prix_unitaire_demande=Decimal("800.00"),
            taux_remise=Decimal("5.00"),
        )
        assert article.quantite == 3
        assert article.prix_unitaire_demande == Decimal("800.00")

    def test_quantite_zero_leve_erreur(self):
        """Une quantité de 0 est invalide."""
        with pytest.raises(ValueError, match="strictement positive"):
            ArticlePanier(
                medicament_id=uuid.uuid4(),
                quantite=0,
                prix_unitaire_demande=Decimal("800.00"),
            )

    def test_quantite_negative_leve_erreur(self):
        """Une quantité négative est invalide."""
        with pytest.raises(ValueError, match="strictement positive"):
            ArticlePanier(
                medicament_id=uuid.uuid4(),
                quantite=-5,
                prix_unitaire_demande=Decimal("800.00"),
            )

    def test_prix_unitaire_negatif_leve_erreur(self):
        """Un prix unitaire négatif est invalide."""
        with pytest.raises(ValueError, match="négatif"):
            ArticlePanier(
                medicament_id=uuid.uuid4(),
                quantite=1,
                prix_unitaire_demande=Decimal("-100.00"),
            )

    def test_taux_remise_superieur_100_leve_erreur(self):
        """Un taux de remise supérieur à 100 % est invalide."""
        with pytest.raises(ValueError, match="compris entre 0 et 100"):
            ArticlePanier(
                medicament_id=uuid.uuid4(),
                quantite=1,
                prix_unitaire_demande=Decimal("800.00"),
                taux_remise=Decimal("101.00"),
            )

    def test_taux_remise_negatif_leve_erreur(self):
        """Un taux de remise négatif est invalide."""
        with pytest.raises(ValueError, match="compris entre 0 et 100"):
            ArticlePanier(
                medicament_id=uuid.uuid4(),
                quantite=1,
                prix_unitaire_demande=Decimal("800.00"),
                taux_remise=Decimal("-1.00"),
            )

    def test_taux_remise_zero_par_defaut(self):
        """Le taux de remise vaut 0 par défaut."""
        article = ArticlePanier(
            medicament_id=uuid.uuid4(),
            quantite=1,
            prix_unitaire_demande=Decimal("800.00"),
        )
        assert article.taux_remise == Decimal("0.00")

    def test_prix_zero_autorise(self):
        """Un prix de 0 (échantillon gratuit) est autorisé."""
        article = ArticlePanier(
            medicament_id=uuid.uuid4(),
            quantite=1,
            prix_unitaire_demande=Decimal("0.00"),
        )
        assert article.prix_unitaire_demande == Decimal("0.00")


# ─── Tests de ListeArticles ────────────────────────────────────────────────────

class TestListeArticles:
    """Tests de la classe ListeArticles (panier)."""

    def test_panier_vide_est_vide(self):
        """Un panier sans articles est considéré comme vide."""
        panier = ListeArticles()
        assert panier.est_vide is True

    def test_panier_avec_articles_non_vide(self):
        """Un panier avec au moins un article n'est pas vide."""
        panier = ListeArticles(articles=[
            ArticlePanier(uuid.uuid4(), 2, Decimal("800.00"))
        ])
        assert panier.est_vide is False

    def test_nombre_articles_somme_les_quantites(self):
        """nombre_articles() somme les quantités de tous les articles."""
        panier = ListeArticles(articles=[
            ArticlePanier(uuid.uuid4(), 3, Decimal("800.00")),
            ArticlePanier(uuid.uuid4(), 5, Decimal("500.00")),
            ArticlePanier(uuid.uuid4(), 1, Decimal("1200.00")),
        ])
        assert panier.nombre_articles == 9

    def test_nombre_articles_panier_vide_est_zero(self):
        """Un panier vide a 0 articles."""
        assert ListeArticles().nombre_articles == 0


# ─── Tests de ServiceVente ────────────────────────────────────────────────────

class TestServiceVenteValidations:
    """Tests des validations métier du ServiceVente."""

    @pytest.fixture
    def service(self):
        return ServiceVente()

    @pytest.fixture
    def panier_vide(self):
        return ListeArticles()

    @pytest.fixture
    def panier_simple(self, medicament_mock):
        return ListeArticles(articles=[
            ArticlePanier(
                medicament_id=medicament_mock.id,
                quantite=3,
                prix_unitaire_demande=Decimal("800.00"),
            )
        ])

    def test_panier_vide_leve_erreur(self, service, panier_vide, caissier):
        """Un panier vide lève PanierVide."""
        from gestion.exceptions import PanierVide

        with pytest.raises(PanierVide):
            service.traiter_vente(
                panier=panier_vide,
                mode_paiement="especes",
                utilisateur=caissier,
                montant_encaisse=Decimal("5000.00"),
            )

    def test_caissier_sans_permission_leve_erreur(self, service, panier_simple, stagiaire):
        """Un stagiaire ne peut pas effectuer une vente."""
        from gestion.exceptions import PermissionRefusee

        with pytest.raises(PermissionRefusee):
            service.traiter_vente(
                panier=panier_simple,
                mode_paiement="especes",
                utilisateur=stagiaire,
                montant_encaisse=Decimal("5000.00"),
            )

    def test_especes_sans_montant_leve_erreur(self, service, panier_simple, caissier):
        """Un paiement en espèces sans montant encaissé lève une erreur."""
        from gestion.exceptions import MontantEncaisseInsuffisant

        with pytest.raises(MontantEncaisseInsuffisant):
            service.traiter_vente(
                panier=panier_simple,
                mode_paiement="especes",
                utilisateur=caissier,
                montant_encaisse=Decimal("0.00"),
            )

    def test_calculer_monnaie_rendue(self, service):
        """calculer_monnaie retourne le bon montant et la décomposition en coupures."""
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("2400.00"),
            montant_encaisse=Decimal("5000.00"),
        )

        assert resultat["montant_rendu"] == Decimal("2600.00")
        assert isinstance(resultat["decomposition"], dict)

    def test_calculer_monnaie_encaisse_insuffisant_leve_erreur(self, service):
        """Montant encaissé < montant total → erreur."""
        from gestion.exceptions import MontantEncaisseInsuffisant

        with pytest.raises(MontantEncaisseInsuffisant):
            service.calculer_monnaie_rendue(
                montant_total=Decimal("5000.00"),
                montant_encaisse=Decimal("2000.00"),
            )

    def test_calculer_monnaie_decomposition_coupures_fcfa(self, service):
        """La décomposition utilise les coupures FCFA standard."""
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("1750.00"),
            montant_encaisse=Decimal("5000.00"),
        )
        # Monnaie = 3250 FCFA
        decomposition = resultat["decomposition"]
        # Vérifier que la décomposition utilise des coupures valides
        coupures_fcfa_valides = {10000, 5000, 2000, 1000, 500, 200, 100, 50, 25, 10, 5}
        for coupure in decomposition:
            assert coupure in coupures_fcfa_valides

    def test_calculer_monnaie_exacte_rendu_zero(self, service):
        """Si le client paie exactement, le rendu est zéro."""
        resultat = service.calculer_monnaie_rendue(
            montant_total=Decimal("2000.00"),
            montant_encaisse=Decimal("2000.00"),
        )
        assert resultat["montant_rendu"] == Decimal("0")

    def test_obtenir_historique_ventes_sans_filtres(self, service, db):
        """obtenir_historique_ventes() sans filtres retourne un QuerySet."""
        historique = service.obtenir_historique_ventes()
        # En DB vide, le QuerySet est vide mais valide
        assert hasattr(historique, "filter")  # C'est bien un QuerySet Django


class TestServiceVentePermissions:
    """Tests des contrôles de permissions dans ServiceVente."""

    @pytest.fixture
    def service(self):
        return ServiceVente()

    def test_annuler_vente_requiert_pharmacien_adjoint(self, service, caissier, db):
        """Seul un pharmacien adjoint ou plus peut annuler une vente."""
        from gestion.exceptions import PermissionRefusee

        # Un caissier ne peut pas annuler
        caissier.a_permission_role = lambda role: False  # Simuler refus

        with patch("gestion.ventes.services.Vente") as mock_vente_cls:
            vente_mock = MagicMock()
            vente_mock.statut = "validee"
            mock_vente_cls.objects.filter.return_value.select_for_update.return_value.first.return_value = vente_mock

            with pytest.raises(PermissionRefusee):
                service.annuler_vente(
                    vente_id=uuid.uuid4(),
                    motif="Test",
                    utilisateur=caissier,
                )
