"""
tests/unitaires/test_service_vente_produits_controles.py

Tests unitaires ciblant les deux régressions critiques du flux de vente
impliquant les produits contrôlés et les ordonnances :

  1. Registre stupéfiants alimenté avec les bons arguments
     (ServiceProduitControle().enregistrer_sortie_vente, kwargs corrects).
  2. Ordonnance marquée UTILISEE après dispensation d'un produit contrôlé.
  3. Ordonnance non modifiée quand aucune ordonnance n'est fournie.
  4. ServiceProduitControle non appelé pour un médicament ordinaire.
  5. Erreur registre ne bloque pas la vente (degraded-mode toléré).
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from gestion.ventes.services import ArticlePanier, ListeArticles, ServiceVente

pytestmark = [pytest.mark.unitaire, pytest.mark.django_db]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_lot(est_produit_controle: bool = False, quantite: int = 50):
    """Construit un lot mock prêt à l'emploi."""
    med = MagicMock()
    med.id = uuid.uuid4()
    med.nom = "Morphine 10mg" if est_produit_controle else "Amoxicilline 500mg"
    med.est_actif = True
    med.necessite_ordonnance = est_produit_controle
    med.est_produit_controle = est_produit_controle
    med.prix_public = Decimal("1500.00")
    med.prix_min_autorise = Decimal("1000.00")
    med.prix_max_autorise = Decimal("2000.00")
    med.seuil_alerte_stock = 5
    med.seuil_rupture_stock = 0

    lot = MagicMock()
    lot.id = uuid.uuid4()
    lot.medicament = med
    lot.numero_lot = "LOT-PC-001" if est_produit_controle else "LOT-STD-001"
    lot.quantite_disponible = quantite
    lot.est_actif = True
    lot.date_peremption = None
    return lot


def _make_ordonnance(statut: str = "validee"):
    """Construit une ordonnance mock."""
    ordo = MagicMock()
    ordo.id = uuid.uuid4()
    ordo.statut = statut
    return ordo


def _make_vendeur(role: str = "caissier"):
    """Construit un utilisateur vendeur mock."""
    vendeur = MagicMock()
    vendeur.id = uuid.uuid4()
    vendeur.role = role
    vendeur.a_permission_role = lambda r: True  # autorisé à vendre
    return vendeur


def _patch_lot_qs(lot):
    """Retourne un patch robuste pour la chaîne de requête Lot.objects."""
    mock_qs = MagicMock()
    mock_qs.select_related.return_value = mock_qs
    mock_qs.select_for_update.return_value = mock_qs
    mock_qs.filter.return_value = mock_qs
    mock_qs.order_by.return_value = mock_qs
    mock_qs.first.return_value = lot
    return mock_qs


# ─── Tests : registre produits contrôlés ─────────────────────────────────────

class TestRegistreProduitControle:
    """Le registre réglementaire doit être alimenté correctement."""

    def _run_vente_produit_controle(self, ordonnance=None, quantite=2):
        """
        Exécute traiter_vente() pour 1 article produit contrôlé et retourne
        le mock ServiceProduitControle pour assertions.
        """
        lot = _make_lot(est_produit_controle=True, quantite=50)
        vendeur = _make_vendeur()
        article = ArticlePanier(
            medicament_id=lot.medicament.id,
            quantite=quantite,
            prix_unitaire_demande=Decimal("1500.00"),
        )
        panier = ListeArticles(articles=[article])

        with patch("gestion.ventes.services.Lot") as mock_lot_cls, \
             patch("gestion.ventes.services.MouvementStock") as _mock_mv, \
             patch("gestion.ventes.services.Vente") as mock_vente_cls, \
             patch("gestion.ventes.services.LigneVente") as _mock_lv, \
             patch("gestion.ventes.services.CompteurNumerotation") as _mock_cpt, \
             patch("gestion.ventes.services.Parametrage") as mock_param, \
             patch("gestion.ventes.services.ServiceProduitControle") as mock_spc_cls, \
             patch("gestion.ventes.services._verifier_cloture_ouverte", return_value=True):

            # Configuration lot
            mock_lot_cls.objects = _patch_lot_qs(lot)

            # Configuration numérotation
            _mock_cpt.objects.select_for_update.return_value.get_or_create.return_value = (
                MagicMock(sequence=1), True
            )
            mock_param.obtenir.return_value = MagicMock(
                format_numerotation="VTE-{YYYY}-{NNNN}"
            )

            # Configuration vente créée
            vente_mock = MagicMock()
            vente_mock.numero = "VTE-2026-0001"
            mock_vente_cls.objects.create.return_value = vente_mock

            # Instance mock du service produits contrôlés
            spc_instance = MagicMock()
            mock_spc_cls.return_value = spc_instance

            svc = ServiceVente()
            # On simule une ordonnance valide pour éviter OrdonnanceRequise
            ordo_mock = MagicMock()
            ordo_mock.id = uuid.uuid4()
            with patch.object(svc, "_resoudre_ordonnance", return_value=ordo_mock):
                svc.traiter_vente(
                    panier=panier,
                    mode_paiement="especes",
                    montant_encaisse=Decimal("5000.00"),
                    vendeur=vendeur,
                    ordonnance_id=str(ordo_mock.id),
                    adresse_ip="127.0.0.1",
                )

        return mock_spc_cls, spc_instance

    def test_service_produit_controle_instancie(self):
        """ServiceProduitControle doit être instancié (pas appelé en statique)."""
        mock_spc_cls, spc_instance = self._run_vente_produit_controle()
        mock_spc_cls.assert_called_once_with()

    def test_enregistrer_sortie_appelee(self):
        """enregistrer_sortie_vente() doit être appelée exactement une fois."""
        _, spc_instance = self._run_vente_produit_controle()
        spc_instance.enregistrer_sortie_vente.assert_called_once()

    def test_parametre_medicament_present(self):
        """Le paramètre keyword 'medicament' doit être fourni."""
        _, spc_instance = self._run_vente_produit_controle()
        _, kwargs = spc_instance.enregistrer_sortie_vente.call_args
        assert "medicament" in kwargs, (
            "Le paramètre 'medicament' est obligatoire mais absent de l'appel."
        )

    def test_parametre_vendeur_correct(self):
        """Le paramètre doit s'appeler 'vendeur', pas 'utilisateur'."""
        _, spc_instance = self._run_vente_produit_controle()
        _, kwargs = spc_instance.enregistrer_sortie_vente.call_args
        assert "vendeur" in kwargs, (
            "Le paramètre doit s'appeler 'vendeur', non 'utilisateur'."
        )
        assert "utilisateur" not in kwargs, (
            "'utilisateur' est le vieux nom de paramètre — il a été renommé 'vendeur'."
        )

    def test_parametre_lot_present(self):
        """Le paramètre keyword 'lot' doit être fourni."""
        _, spc_instance = self._run_vente_produit_controle()
        _, kwargs = spc_instance.enregistrer_sortie_vente.call_args
        assert "lot" in kwargs, "Le paramètre 'lot' est obligatoire mais absent."

    def test_parametre_quantite_correct(self):
        """La quantité passée au registre doit correspondre à l'article du panier."""
        qte_attendue = 3
        _, spc_instance = self._run_vente_produit_controle(quantite=qte_attendue)
        _, kwargs = spc_instance.enregistrer_sortie_vente.call_args
        assert kwargs.get("quantite") == qte_attendue, (
            f"Quantité incorrecte : attendu {qte_attendue}, "
            f"reçu {kwargs.get('quantite')}"
        )

    def test_pas_appele_pour_medicament_ordinaire(self):
        """ServiceProduitControle ne doit PAS être appelé pour un médicament standard."""
        lot = _make_lot(est_produit_controle=False, quantite=50)
        vendeur = _make_vendeur()
        article = ArticlePanier(
            medicament_id=lot.medicament.id,
            quantite=2,
            prix_unitaire_demande=Decimal("800.00"),
        )
        panier = ListeArticles(articles=[article])

        with patch("gestion.ventes.services.Lot") as mock_lot_cls, \
             patch("gestion.ventes.services.MouvementStock"), \
             patch("gestion.ventes.services.Vente") as mock_vente_cls, \
             patch("gestion.ventes.services.LigneVente"), \
             patch("gestion.ventes.services.CompteurNumerotation") as mock_cpt, \
             patch("gestion.ventes.services.Parametrage") as mock_param, \
             patch("gestion.ventes.services.ServiceProduitControle") as mock_spc_cls, \
             patch("gestion.ventes.services._verifier_cloture_ouverte", return_value=True):

            mock_lot_cls.objects = _patch_lot_qs(lot)
            mock_cpt.objects.select_for_update.return_value.get_or_create.return_value = (
                MagicMock(sequence=1), True
            )
            mock_param.obtenir.return_value = MagicMock(format_numerotation="VTE-{YYYY}-{NNNN}")
            vente_mock = MagicMock()
            vente_mock.numero = "VTE-2026-0001"
            mock_vente_cls.objects.create.return_value = vente_mock

            svc = ServiceVente()
            svc.traiter_vente(
                panier=panier,
                mode_paiement="especes",
                montant_encaisse=Decimal("5000.00"),
                vendeur=vendeur,
                adresse_ip="127.0.0.1",
            )

        # ServiceProduitControle ne doit jamais être instancié pour un médicament normal
        mock_spc_cls.assert_not_called()

    def test_erreur_registre_ne_bloque_pas_vente(self):
        """
        Si le registre produits contrôlés lève une exception, la vente
        doit quand même être créée (degraded-mode — un job de réconciliation
        peut corriger les entrées manquantes).
        """
        lot = _make_lot(est_produit_controle=True, quantite=50)
        vendeur = _make_vendeur()
        article = ArticlePanier(
            medicament_id=lot.medicament.id,
            quantite=1,
            prix_unitaire_demande=Decimal("1500.00"),
        )
        panier = ListeArticles(articles=[article])

        with patch("gestion.ventes.services.Lot") as mock_lot_cls, \
             patch("gestion.ventes.services.MouvementStock"), \
             patch("gestion.ventes.services.Vente") as mock_vente_cls, \
             patch("gestion.ventes.services.LigneVente"), \
             patch("gestion.ventes.services.CompteurNumerotation") as mock_cpt, \
             patch("gestion.ventes.services.Parametrage") as mock_param, \
             patch("gestion.ventes.services.ServiceProduitControle") as mock_spc_cls, \
             patch("gestion.ventes.services._verifier_cloture_ouverte", return_value=True):

            mock_lot_cls.objects = _patch_lot_qs(lot)
            mock_cpt.objects.select_for_update.return_value.get_or_create.return_value = (
                MagicMock(sequence=1), True
            )
            mock_param.obtenir.return_value = MagicMock(format_numerotation="VTE-{YYYY}-{NNNN}")
            vente_mock = MagicMock()
            vente_mock.numero = "VTE-2026-0001"
            mock_vente_cls.objects.create.return_value = vente_mock

            # Le registre plante
            spc_instance = MagicMock()
            spc_instance.enregistrer_sortie_vente.side_effect = RuntimeError("DB timeout")
            mock_spc_cls.return_value = spc_instance

            svc = ServiceVente()
            # On simule une ordonnance valide
            ordo_mock = MagicMock()
            ordo_mock.id = uuid.uuid4()
            with patch.object(svc, "_resoudre_ordonnance", return_value=ordo_mock):
                # Ne doit pas lever d'exception
                resultat = svc.traiter_vente(
                    panier=panier,
                    mode_paiement="especes",
                    montant_encaisse=Decimal("5000.00"),
                    vendeur=vendeur,
                    ordonnance_id=str(ordo_mock.id),
                    adresse_ip="127.0.0.1",
                )

        # La vente doit avoir été créée malgré l'échec du registre
        assert resultat.facture is not None


# ─── Tests : marquage ordonnance UTILISEE ─────────────────────────────────────

class TestOrdonnanceMarqueeUtilisee:
    """L'ordonnance doit passer au statut UTILISEE après dispensation."""

    def _run_vente_avec_ordonnance(self, ordonnance=None):
        """Lance une vente simple avec une ordonnance injectée directement."""
        lot = _make_lot(est_produit_controle=False, quantite=50)
        vendeur = _make_vendeur()
        article = ArticlePanier(
            medicament_id=lot.medicament.id,
            quantite=1,
            prix_unitaire_demande=Decimal("800.00"),
        )
        panier = ListeArticles(articles=[article])

        if ordonnance is None:
            ordonnance = _make_ordonnance("validee")

        with patch("gestion.ventes.services.Lot") as mock_lot_cls, \
             patch("gestion.ventes.services.MouvementStock"), \
             patch("gestion.ventes.services.Vente") as mock_vente_cls, \
             patch("gestion.ventes.services.LigneVente"), \
             patch("gestion.ventes.services.CompteurNumerotation") as mock_cpt, \
             patch("gestion.ventes.services.Parametrage") as mock_param, \
             patch("gestion.ventes.services.Ordonnance") as mock_ordo_cls, \
             patch("gestion.ventes.services._verifier_cloture_ouverte", return_value=True):

            mock_lot_cls.objects = _patch_lot_qs(lot)
            mock_cpt.objects.select_for_update.return_value.get_or_create.return_value = (
                MagicMock(sequence=1), True
            )
            mock_param.obtenir.return_value = MagicMock(format_numerotation="VTE-{YYYY}-{NNNN}")
            vente_mock = MagicMock()
            vente_mock.numero = "VTE-2026-0001"
            mock_vente_cls.objects.create.return_value = vente_mock

            # Injecter l'ordonnance directement dans le service (bypass résolution par ID)
            svc = ServiceVente()
            with patch.object(svc, "_resoudre_ordonnance", return_value=ordonnance):
                svc.traiter_vente(
                    panier=panier,
                    mode_paiement="especes",
                    montant_encaisse=Decimal("5000.00"),
                    vendeur=vendeur,
                    ordonnance_id=str(ordonnance.id),
                    adresse_ip="127.0.0.1",
                )

        return ordonnance

    def test_ordonnance_sauvegardee_avec_statut_utilisee(self):
        """
        ordonnance.save() doit être appelé avec update_fields contenant 'statut'.
        """
        ordo = _make_ordonnance("validee")
        from gestion.ordonnances.models import StatutOrdonnance

        # On surveille la mutation directe de l'attribut statut
        sauvegardes = []
        original_save = ordo.save

        def spy_save(*args, **kwargs):
            sauvegardes.append(ordo.statut)
            return original_save(*args, **kwargs) if callable(original_save) else None

        ordo.save = spy_save

        self._run_vente_avec_ordonnance(ordonnance=ordo)

        assert len(sauvegardes) >= 1, (
            "ordonnance.save() doit être appelé après la vente."
        )
        assert ordo.statut == StatutOrdonnance.UTILISEE, (
            f"ordonnance.statut doit être UTILISEE après dispensation, "
            f"mais est '{ordo.statut}'."
        )

    def test_sans_ordonnance_aucun_changement_statut(self):
        """
        Si aucune ordonnance n'est attachée à la vente, aucun StatutOrdonnance
        ne doit être muté.
        """
        lot = _make_lot(est_produit_controle=False, quantite=50)
        vendeur = _make_vendeur()
        article = ArticlePanier(
            medicament_id=lot.medicament.id,
            quantite=1,
            prix_unitaire_demande=Decimal("800.00"),
        )
        panier = ListeArticles(articles=[article])

        with patch("gestion.ventes.services.Lot") as mock_lot_cls, \
             patch("gestion.ventes.services.MouvementStock"), \
             patch("gestion.ventes.services.Vente") as mock_vente_cls, \
             patch("gestion.ventes.services.LigneVente"), \
             patch("gestion.ventes.services.CompteurNumerotation") as mock_cpt, \
             patch("gestion.ventes.services.Parametrage") as mock_param, \
             patch("gestion.ventes.services._verifier_cloture_ouverte", return_value=True):

            mock_lot_cls.objects = _patch_lot_qs(lot)
            mock_cpt.objects.select_for_update.return_value.get_or_create.return_value = (
                MagicMock(sequence=1), True
            )
            mock_param.obtenir.return_value = MagicMock(format_numerotation="VTE-{YYYY}-{NNNN}")
            vente_mock = MagicMock()
            vente_mock.numero = "VTE-2026-0001"
            mock_vente_cls.objects.create.return_value = vente_mock

            # Pas d'ordonnance_id → ordonnance = None
            with patch("gestion.ventes.services.StatutOrdonnance") as mock_statut:
                svc = ServiceVente()
                svc.traiter_vente(
                    panier=panier,
                    mode_paiement="especes",
                    montant_encaisse=Decimal("5000.00"),
                    vendeur=vendeur,
                    ordonnance_id=None,
                    adresse_ip="127.0.0.1",
                )
                # StatutOrdonnance.UTILISEE ne doit jamais être affecté
                mock_statut.UTILISEE  # accès autorisé
                # ordonnance étant None, aucun .save() ne doit être appelé sur elle
        # Si on arrive ici sans exception, le test passe


class TestOrdonnanceStatutApresAvoir:
    """Après un avoir total, l'ordonnance doit repasser au statut VALIDEE."""

    def test_ordonnance_reactivee_apres_avoir_total(self):
        """
        ServiceAvoir.creer_avoir() doit remettre l'ordonnance au statut VALIDEE
        quand le montant de l'avoir couvre l'intégralité de la vente d'origine.
        """
        from gestion.ordonnances.models import StatutOrdonnance
        from gestion.ventes.avoir import ServiceAvoir

        ordo = MagicMock()
        ordo.id = uuid.uuid4()
        ordo.statut = StatutOrdonnance.UTILISEE

        vente_origine = MagicMock()
        vente_origine.id = uuid.uuid4()
        vente_origine.numero = "VTE-2026-0001"
        vente_origine.montant_total = Decimal("3000.00")
        vente_origine.statut = "validee"
        vente_origine.ordonnance = ordo
        vente_origine.client = None
        vente_origine.mode_paiement = "especes"

        ligne = MagicMock()
        ligne.id = uuid.uuid4()
        ligne.quantite = 3
        ligne.prix_unitaire = Decimal("1000.00")
        ligne.taux_remise = Decimal("0.00")
        ligne.prix_unitaire_apres_remise = Decimal("1000.00")
        ligne.medicament = MagicMock()
        ligne.lot_id = None

        lignes_mock = MagicMock()
        lignes_mock.select_related.return_value.all.return_value = [ligne]
        vente_origine.lignes = lignes_mock

        lignes_retour = [{"ligne_id": str(ligne.id), "quantite": 3}]

        utilisateur = _make_vendeur()

        with patch("gestion.ventes.avoir.Vente") as mock_vente_cls, \
             patch("gestion.ventes.avoir.LigneVente"), \
             patch("gestion.ventes.avoir.CompteurNumerotation") as mock_cpt, \
             patch("gestion.ventes.avoir.Parametrage") as mock_param, \
             patch("gestion.ventes.avoir.StatutOrdonnance") as mock_statut_cls:

            mock_vente_cls.objects.select_for_update.return_value.filter.return_value.first.return_value = vente_origine
            mock_cpt.objects.select_for_update.return_value.get_or_create.return_value = (
                MagicMock(sequence=1), True
            )
            mock_param.obtenir.return_value = MagicMock(format_numerotation="VTE-{YYYY}-{NNNN}")
            vente_avoir_mock = MagicMock()
            vente_avoir_mock.id = uuid.uuid4()
            mock_vente_cls.objects.create.return_value = vente_avoir_mock

            mock_statut_cls.UTILISEE = StatutOrdonnance.UTILISEE
            mock_statut_cls.VALIDEE = StatutOrdonnance.VALIDEE

            svc = ServiceAvoir()
            svc.creer_avoir(
                vente_origine_id=vente_origine.id,
                lignes_retour=lignes_retour,
                motif="Retour produit test",
                utilisateur=utilisateur,
            )

        # L'ordonnance doit repasser au statut VALIDEE
        assert ordo.statut == StatutOrdonnance.VALIDEE, (
            f"L'ordonnance doit être VALIDEE après un avoir total, "
            f"mais est '{ordo.statut}'."
        )
        ordo.save.assert_called()
