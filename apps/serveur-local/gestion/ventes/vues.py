"""
gestion/ventes/vues.py
Vues DRF pour les ventes et clôtures de caisse.

ÉTAPE 7 — Ajout de l'action avoir() :
  POST /api/ventes/{id}/avoir/ — crée un avoir (retour client) pour une vente existante.

ÉTAPE 10 — Ajout ordonnance_id dans create() :
  Le payload de vente peut maintenant inclure ordonnance_id (optionnel).
  Si le médicament est contrôlé et ordonnance_id absent → erreur métier.

ÉTAPE 11 — Complétion POS :
  create() : accepte reference_mobile_money + client_id (création vente)
  annuler() : vérifie que la clôture du jour n'est pas faite avant d'autoriser
  Endpoint monnaie() : POST /ventes/{id}/monnaie/

ÉTAPE 14 — Avoir via ServiceAvoir :
  La logique avoir est déléguée à gestion.ventes.avoir.ServiceAvoir.
"""

import logging
from decimal import Decimal, InvalidOperation

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import EstAuthentifie, EstCaissier, EstPharmacienAdjoint
from gestion.ventes.services import ServiceVente, _verifier_cloture_ouverte
from gestion.ventes.models import Vente, ClotureCaisse

logger = logging.getLogger("pharmapp.ventes.vues")

MODES_PAIEMENT_VALIDES = {"especes", "mobile_money", "assurance", "credit", "cheque"}


def _valider_panier(panier: list) -> list:
    """Valide chaque article du panier sans accès DB."""
    erreurs = []
    for idx, article in enumerate(panier):
        quantite = article.get("quantite")
        try:
            q = int(quantite)
            if q <= 0:
                erreurs.append(f"Article {idx+1} : la quantité doit être strictement positive.")
        except (TypeError, ValueError):
            erreurs.append(f"Article {idx+1} : 'quantite' doit être un entier.")

        taux_remise = article.get("taux_remise", "0")
        try:
            t = Decimal(str(taux_remise))
            if not (Decimal("0") <= t <= Decimal("100")):
                erreurs.append(f"Article {idx+1} : le taux de remise doit être entre 0 et 100.")
        except InvalidOperation:
            erreurs.append(f"Article {idx+1} : 'taux_remise' doit être un nombre décimal.")

        prix = article.get("prix_unitaire_demande", "0")
        try:
            p = Decimal(str(prix))
            if p < Decimal("0"):
                erreurs.append(f"Article {idx+1} : le prix unitaire ne peut pas être négatif.")
        except InvalidOperation:
            erreurs.append(f"Article {idx+1} : 'prix_unitaire_demande' doit être un nombre.")

    return erreurs


class VueVente(viewsets.ModelViewSet):
    """CRUD des ventes."""

    permission_classes = [EstCaissier]

    def get_queryset(self):
        qs = ServiceVente().obtenir_historique_ventes()
        client_id = self.request.query_params.get("client")
        if client_id:
            qs = qs.filter(client_id=client_id)
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        debut = self.request.query_params.get("debut")
        if debut:
            qs = qs.filter(cree_le__date__gte=debut)
        fin = self.request.query_params.get("fin")
        if fin:
            qs = qs.filter(cree_le__date__lte=fin)
        return qs

    def get_serializer_class(self):
        from gestion.ventes.serialiseurs import VenteSerialiseur
        return VenteSerialiseur

    def create(self, request, *args, **kwargs):
        from gestion.ventes.serialiseurs import VenteSerialiseur
        from gestion.exceptions import (
            PermissionRefusee, PanierVide, ModePaiementInvalide,
            MontantEncaisseInsuffisant, StockInsuffisant,
        )

        panier = request.data.get("panier", [])
        if not panier:
            return Response(
                {"panier": ["Le panier ne peut pas être vide."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        erreurs_panier = _valider_panier(panier)
        if erreurs_panier:
            return Response(
                {"panier": erreurs_panier},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mode_paiement = request.data.get("mode_paiement", "")
        if mode_paiement not in MODES_PAIEMENT_VALIDES:
            return Response(
                {"mode_paiement": [f"'{mode_paiement}' n'est pas un mode de paiement valide."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Étape 11 : validation référence Mobile Money ──────────────────────
        reference_mobile_money = (request.data.get("reference_mobile_money") or "").strip()
        if mode_paiement == "mobile_money" and not reference_mobile_money:
            return Response(
                {"reference_mobile_money": ["La référence de transaction est obligatoire pour Mobile Money."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if mode_paiement == "especes":
            try:
                montant_encaisse = Decimal(str(request.data.get("montant_encaisse", "0")))
            except InvalidOperation:
                montant_encaisse = Decimal("0")
            if montant_encaisse <= 0:
                return Response(
                    {"montant_encaisse": ["Le montant encaissé doit être supérieur à zéro."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            try:
                montant_encaisse = Decimal(str(request.data.get("montant_encaisse", "0")))
            except InvalidOperation:
                montant_encaisse = Decimal("0")

        # Résoudre le client (optionnel)
        client = None
        client_id = request.data.get("client_id") or request.data.get("client")
        if client_id:
            try:
                from gestion.clients.models import Client
                client = Client.objects.get(pk=client_id)
            except Client.DoesNotExist:
                return Response(
                    {"client_id": [f"Client introuvable (ID={client_id})."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as exc:
                logger.error("Résolution client pk=%s échouée : %s", client_id, exc, exc_info=True)
                return Response(
                    {"client_id": ["Erreur lors de la résolution du client."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Étape 11 : vérification plafond crédit ────────────────────────────
        # DT-021 (corrigé) : la vérification de plafond est maintenant effectuée
        # à l'intérieur de ServiceVente.traiter_vente() via select_for_update() sur
        # le client, dans le même bloc transaction.atomic(). Ce pré-contrôle dans la
        # vue est conservé uniquement comme garde-fou rapide (évite un aller-retour
        # complet vers le service pour une erreur évidente), mais la vérification
        # définitive et atomique se fait dans le service.
        if mode_paiement == "credit" and client:
            if not client.credit_autorise:
                return Response(
                    {"erreur": f"Le crédit n'est pas autorisé pour le client {client.nom_complet}."},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            try:
                montant_total_pre = sum(
                    Decimal(str(a.get("prix_unitaire_demande", "0"))) * int(a.get("quantite", 1))
                    * (1 - Decimal(str(a.get("taux_remise", "0"))) / 100)
                    for a in panier
                )
                # Pré-vérification optimiste (sans verrou) — le service revalide
                # de façon atomique avec select_for_update() pour éviter la race
                # condition sur les ventes simultanées.
                if client.encours_credit + montant_total_pre > client.plafond_credit:
                    return Response(
                        {
                            "erreur": (
                                f"Dépassement du plafond de crédit. "
                                f"Encours : {client.encours_credit} FCFA, "
                                f"Plafond : {client.plafond_credit} FCFA."
                            )
                        },
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
            except Exception as exc:
                # Erreur de calcul dans la pré-vérification crédit :
                # on refuse la vente pour éviter un dépassement silencieux.
                logger.error(
                    "Erreur calcul plafond crédit client=%s : %s",
                    getattr(client, "id", client_id), exc, exc_info=True,
                )
                return Response(
                    {"erreur": "Impossible de vérifier le plafond de crédit. Réessayez."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Résoudre l'ordonnance (optionnel — étape 10)
        ordonnance_id = request.data.get("ordonnance_id")

        try:
            resultat = ServiceVente().traiter_vente(
                panier=panier,
                mode_paiement=mode_paiement,
                montant_encaisse=montant_encaisse,
                vendeur=request.user,
                client=client,
                ordonnance_id=ordonnance_id,
                adresse_ip=request.META.get("REMOTE_ADDR", ""),
            )

            # ── Étape 11 : sauvegarder référence Mobile Money ─────────────────
            vente = resultat.facture
            if reference_mobile_money and mode_paiement == "mobile_money":
                vente.reference_mobile_money = reference_mobile_money
                vente.save(update_fields=["reference_mobile_money"])

            return Response(
                VenteSerialiseur(vente).data,
                status=status.HTTP_201_CREATED,
            )

        except PanierVide as exc:
            return Response({"panier": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except ModePaiementInvalide as exc:
            return Response({"mode_paiement": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except MontantEncaisseInsuffisant as exc:
            return Response({"montant_encaisse": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except StockInsuffisant as exc:
            return Response({"stock": [str(exc)]}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except PermissionRefusee as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            logger.error("Erreur inattendue lors de la création de vente : %s", exc, exc_info=True)
            return Response(
                {"erreur": "Erreur interne lors du traitement de la vente."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], permission_classes=[EstAuthentifie])
    def annuler(self, request, pk=None):
        """
        Annule une vente.
        POST /api/ventes/{id}/annuler/
        Body : { "motif": "..." }

        Étape 11 : L'annulation est refusée si la clôture du jour est déjà faite.
        """
        from gestion.exceptions import (
            PermissionRefusee, VenteDejaAnnulee, DelaiAnnulationDepasse,
        )

        # L'existence de la vente prime sur la validation du corps : une vente
        # inconnue doit répondre 404, jamais 400 (ne pas divulguer la forme
        # attendue du payload sur une ressource inexistante).
        if not Vente.objects.filter(id=pk).exists():
            return Response(
                {"erreur": "Vente introuvable."}, status=status.HTTP_404_NOT_FOUND
            )

        if not EstPharmacienAdjoint().has_permission(request, self):
            return Response(
                {"erreur": "Permission insuffisante pour annuler une vente."},
                status=status.HTTP_403_FORBIDDEN,
            )

        motif = request.data.get("motif", "").strip()
        if not motif:
            return Response(
                {"motif": ["Le motif d'annulation est obligatoire."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Vérifier que la clôture du jour n'est pas faite ──────────────────
        if not _verifier_cloture_ouverte():
            return Response(
                {
                    "erreur": (
                        "L'annulation n'est plus possible : la clôture de caisse de la journée "
                        "a déjà été effectuée. Pour un remboursement, créez un avoir "
                        "(POST /ventes/{id}/avoir/)."
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            vente = ServiceVente().annuler_vente(
                vente_id=pk,
                motif=motif,
                utilisateur=request.user,
                adresse_ip=request.META.get("REMOTE_ADDR", ""),
            )
            from gestion.ventes.serialiseurs import VenteSerialiseur
            return Response(VenteSerialiseur(vente).data)
        except PermissionRefusee as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except VenteDejaAnnulee as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_409_CONFLICT)
        except DelaiAnnulationDepasse as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ValueError as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="monnaie")
    def monnaie(self, request, pk=None):
        """
        Calcule la monnaie à rendre pour une vente.
        POST /api/ventes/{id}/monnaie/
        Body : { "montant_encaisse": 10000 }
        """
        from gestion.exceptions import MontantEncaisseInsuffisant

        vente = Vente.objects.filter(id=pk).first()
        if not vente:
            return Response({"erreur": "Vente introuvable."}, status=status.HTTP_404_NOT_FOUND)

        try:
            montant_encaisse = Decimal(str(request.data.get("montant_encaisse", "0")))
        except InvalidOperation:
            return Response(
                {"erreur": "montant_encaisse invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultat = ServiceVente().calculer_monnaie_rendue(
                montant_total=vente.montant_total,
                montant_encaisse=montant_encaisse,
            )
            return Response(resultat)
        except MontantEncaisseInsuffisant as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path="avoir",
        permission_classes=[EstPharmacienAdjoint],
    )
    def avoir(self, request, pk=None):
        """
        Crée un avoir pour une vente existante.
        POST /api/ventes/{id}/avoir/
        Body : { "lignes": [{"ligne_id": "uuid", "quantite": 1}], "motif": "string" }

        Étape 14 : Délégué à ServiceAvoir.creer_avoir().
        Un avoir est possible même après clôture (contrairement à l'annulation).
        """
        from gestion.exceptions import PermissionRefusee
        from gestion.ventes.avoir import ServiceAvoir

        lignes = request.data.get("lignes", [])
        motif = request.data.get("motif", "").strip()

        if not motif:
            return Response(
                {"motif": ["Le motif est obligatoire."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not lignes:
            return Response(
                {"lignes": ["Au moins une ligne est requise."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            vente_avoir = ServiceAvoir().creer_avoir(
                vente_origine_id=pk,
                lignes_retour=lignes,
                motif=motif,
                utilisateur=request.user,
                adresse_ip=request.META.get("REMOTE_ADDR", ""),
            )
            from gestion.ventes.serialiseurs import VenteSerialiseur
            return Response(
                {
                    "vente_avoir": VenteSerialiseur(vente_avoir).data,
                    "message": (
                        f"Avoir {vente_avoir.numero} créé. "
                        f"Montant : {abs(vente_avoir.montant_total)} FCFA. "
                        f"Stock remis à jour."
                    ),
                },
                status=status.HTTP_201_CREATED,
            )
        except PermissionRefusee as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="recu")
    def recu(self, request, pk=None):
        """
        Génère le DTO reçu pour une vente et incrémente nb_impressions.
        GET /api/ventes/{id}/recu/
        """
        from gestion.ventes.recu import ServiceRecu
        try:
            dto = ServiceRecu().generer_recu(vente_id=pk)
            return Response(dto)
        except ValueError as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class VueClotureCaisse(viewsets.ModelViewSet):
    """Gestion des clôtures de caisse."""

    permission_classes = [EstPharmacienAdjoint]

    def get_queryset(self):
        from gestion.ventes.models import ClotureCaisse
        return ClotureCaisse.objects.select_related("caissier", "validee_par").order_by("-date_cloture")

    def get_serializer_class(self):
        from gestion.ventes.serialiseurs import ClotureCaisseSerialiseur
        return ClotureCaisseSerialiseur
