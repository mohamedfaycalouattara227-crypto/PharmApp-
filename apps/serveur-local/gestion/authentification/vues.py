"""
gestion/authentification/vues.py
Vues DRF pour l'authentification : connexion, déconnexion, profil, gestion utilisateurs.

ÉTAPE 9 — Ajouts :
  - VueUtilisateur.suspendre() : suspend/réactive un compte
  - Protection : un titulaire ne peut pas se suspendre lui-même

ÉTAPE 12 — Sécurité fonctionnelle (CDC §4.1 + §7) :
  - VueConnexion.post() : comptage des tentatives échouées + verrouillage automatique
    Si authentification échoue → nb_tentatives_echec += 1
    Si >= TENTATIVES_CONNEXION_MAX (défaut 5) → est_verrouille = True
    Si succès → reinitialiser_echecs_connexion()
    Le seuil est lu depuis settings.TENTATIVES_CONNEXION_MAX (configurable par env).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.permissions import EstAuthentifie, EstTitulaire
from api.throttling import ThrottleConnexion

logger = logging.getLogger("pharmapp.auth")


class VueConnexion(APIView):
    """
    Endpoint de connexion — retourne un JWT via cookie httpOnly.

    Anti-brute-force (double couche) :
      1. ThrottleConnexion (5/min par IP) au niveau HTTP.
      2. Verrouillage applicatif après N échecs consécutifs (TENTATIVES_CONNEXION_MAX).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ThrottleConnexion]

    def post(self, request):
        email = request.data.get("email", "").strip()
        # Le client interne envoie `mot_de_passe` ; les clients standards (et
        # les suites de conformité) envoient `password`. Les deux sont acceptés.
        mot_de_passe = request.data.get("mot_de_passe") or request.data.get("password") or ""
        adresse_ip = request.META.get("REMOTE_ADDR", "")

        if not email or not mot_de_passe:
            return Response(
                {"erreur": "email et mot_de_passe sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "@" not in email or len(email) > 254 or len(mot_de_passe) > 256:
            return Response(
                {"erreur": "Format d'email ou longueur invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ASVS V2.2.1 — égaliser le temps de réponse pour empêcher l'énumération
        # d'utilisateurs par timing (le hash Argon2 prend ~100ms même si l'email
        # est inconnu). NOTE (audit 2026-07-21) : gestion.authentification.
        # backend.BackendPharmApp applique désormais sa propre contre-mesure
        # (set_password() sur instance jetable) sur le chemin normal
        # authenticate(). Ce bloc reste une seconde couche de défense en
        # profondeur pour le cas DoesNotExist ci-dessous — volontairement
        # conservé, sans effet indésirable puisque _DUMMY_HASH est un hash
        # Argon2id correctement formé.
        from django.contrib.auth.hashers import check_password
        # Hash Argon2id valide (mot de passe : chaîne aléatoire jamais utilisée).
        _DUMMY_HASH = (
            "argon2$argon2id$v=19$m=102400,t=2,p=8$"
            "YWFhYWFhYWFhYWFhYWFhYQ$c3RhbmRhcmRkdW1teWhhc2gxMjM0NTY3ODkwMTIzNA"
        )
        def _timing_safe_check():
            try:
                check_password(mot_de_passe, _DUMMY_HASH)
            except Exception:
                pass

        # ── Étape 12 : pré-vérification verrouillage avant authenticate() ──────
        # On cherche d'abord l'utilisateur pour vérifier son état et incrémenter
        # les tentatives en cas d'échec — sans révéler si l'email existe ou non.
        from gestion.authentification.models import UtilisateurPharmacien
        tentatives_max = getattr(settings, "TENTATIVES_CONNEXION_MAX", 5)

        utilisateur = authenticate(request, email=email, password=mot_de_passe)

        if utilisateur is None:
            # Incrémenter le compteur d'échecs si le compte existe
            try:
                u = UtilisateurPharmacien.objects.get(email__iexact=email)
                u.tentatives_connexion_echouees = (
                    getattr(u, "tentatives_connexion_echouees", 0) + 1
                )
                # Verrouillage automatique après N tentatives
                if u.tentatives_connexion_echouees >= tentatives_max:
                    u.est_verrouille = True
                    u.verrouille_jusqu_au = (
                        timezone.now()
                        + timedelta(
                            minutes=getattr(settings, "DUREE_BLOCAGE_COMPTE_MINUTES", 30)
                        )
                    )
                    u.save(update_fields=[
                        "tentatives_connexion_echouees",
                        "est_verrouille",
                        "verrouille_jusqu_au",
                    ])
                    logger.warning(
                        "compte_verrouille: email=%s ip=%s apres=%d tentatives",
                        email, adresse_ip, u.tentatives_connexion_echouees,
                    )
                    # CORRECTIF (audit 2026-07-21) : journalisation dans le
                    # journal d'audit réglementaire (JournalAudit), en plus
                    # du log applicatif ci-dessus. Auparavant, aucune
                    # connexion — réussie ou échouée — n'était jamais
                    # écrite dans JournalAudit : le gestionnaire
                    # _sur_connexion existait mais n'était jamais déclenché
                    # (aucun bus.publier(EvenementConnexion) en production).
                    try:
                        from gestion.audit.services import ServiceAudit
                        ServiceAudit().journaliser_connexion(
                            email=email, succes=False, adresse_ip=adresse_ip,
                            raison_echec=f"Compte verrouillé après {tentatives_max} tentatives",
                        )
                    except Exception as exc:
                        logger.warning("Audit : journalisation verrouillage échouée : %s", exc)
                    return Response(
                        {
                            "erreur": (
                                f"Compte verrouillé après {tentatives_max} tentatives échouées. "
                                "Contactez l'administrateur pour le déverrouiller."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
                else:
                    u.save(update_fields=["tentatives_connexion_echouees"])
            except UtilisateurPharmacien.DoesNotExist:
                _timing_safe_check()  # ASVS V2.2.1 : timing constant

            logger.info(
                "connexion_echouee: email=%s ip=%s",
                email, adresse_ip,
            )
            # CORRECTIF (audit 2026-07-21) : voir commentaire équivalent
            # ci-dessus (cas verrouillage). Message générique volontaire —
            # ne révèle jamais si l'email existe ou non.
            try:
                from gestion.audit.services import ServiceAudit
                ServiceAudit().journaliser_connexion(
                    email=email, succes=False, adresse_ip=adresse_ip,
                    raison_echec="Identifiants incorrects ou compte inexistant",
                )
            except Exception as exc:
                logger.warning("Audit : journalisation échec connexion échouée : %s", exc)
            return Response(
                {"erreur": "Identifiants incorrects ou compte inexistant."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # ── Vérifications post-authentification ───────────────────────────────
        if not utilisateur.est_actif:
            return Response(
                {"erreur": "Compte désactivé. Contactez votre administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if getattr(utilisateur, "est_verrouille", False):
            # Vérifier si la durée de blocage est écoulée (déverrouillage automatique)
            verrouille_jusqu = getattr(utilisateur, "verrouille_jusqu_au", None)
            if verrouille_jusqu and timezone.now() > verrouille_jusqu:
                utilisateur.est_verrouille = False
                utilisateur.tentatives_connexion_echouees = 0
                utilisateur.verrouille_jusqu_au = None
                utilisateur.save(update_fields=[
                    "est_verrouille", "tentatives_connexion_echouees", "verrouille_jusqu_au"
                ])
            else:
                return Response(
                    {"erreur": "Compte verrouillé — trop de tentatives échouées. "
                               "Contactez votre administrateur."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # ── Connexion réussie ─────────────────────────────────────────────────
        import secrets
        refresh = RefreshToken.for_user(utilisateur)
        utilisateur.reinitialiser_echecs_connexion()

        logger.info(
            "connexion_reussie: utilisateur_id=%s email=%s ip=%s",
            utilisateur.id, utilisateur.email, adresse_ip,
        )
        # CORRECTIF (audit 2026-07-21) : voir commentaire équivalent ci-dessus.
        try:
            from gestion.audit.services import ServiceAudit
            ServiceAudit().journaliser_connexion(
                email=utilisateur.email, succes=True,
                utilisateur=utilisateur, adresse_ip=adresse_ip,
            )
        except Exception as exc:
            logger.warning("Audit : journalisation connexion réussie échouée : %s", exc)

        reponse = Response({
            "role": utilisateur.role,
            "nom_complet": utilisateur.nom_complet,
        })
        from api.authentication import poser_cookies_session
        poser_cookies_session(
            reponse,
            access=str(refresh.access_token),
            refresh=str(refresh),
            csrf=secrets.token_urlsafe(32),
        )
        return reponse


class VueDeconnexion(APIView):
    """Endpoint de déconnexion — invalide le refresh token et efface les cookies."""

    permission_classes = [EstAuthentifie]

    def post(self, request):
        from api.authentication import COOKIE_REFRESH, effacer_cookies_session
        try:
            refresh_token = request.data.get("refresh") or request.COOKIES.get(COOKIE_REFRESH)
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception as exc:
            # Token déjà révoqué ou mal formé — la déconnexion se poursuit quand même.
            logger.warning("deconnexion_blacklist_echec: %s", type(exc).__name__)
        reponse = Response({"message": "Déconnexion réussie."})
        effacer_cookies_session(reponse)
        return reponse


class VueProfil(APIView):
    """Retourne le profil de l'utilisateur connecté."""

    permission_classes = [EstAuthentifie]

    def get(self, request):
        u = request.user
        return Response({
            "id": str(u.id),
            "email": u.email,
            "prenom": u.prenom,
            "nom": u.nom,
            "nom_complet": u.nom_complet,
            "role": u.role,
            "role_display": u.get_role_display(),
            "telephone": u.telephone,
            "numero_ordre": u.numero_ordre,
            "est_actif": u.est_actif,
            "derniere_connexion_reussie": (
                u.derniere_connexion_reussie.isoformat()
                if u.derniere_connexion_reussie else None
            ),
        })


class VueUtilisateur(viewsets.ModelViewSet):
    """CRUD utilisateurs (titulaire+)."""

    permission_classes = [EstTitulaire]

    def get_queryset(self):
        from gestion.authentification.models import UtilisateurPharmacien
        return UtilisateurPharmacien.objects.all().order_by("nom", "prenom")

    def get_serializer_class(self):
        from gestion.authentification.serialiseurs import UtilisateurSerialiseur
        return UtilisateurSerialiseur

    @action(detail=True, methods=["post"], url_path="suspendre")
    def suspendre(self, request, pk=None):
        """
        Suspend ou réactive un compte utilisateur.
        POST /api/auth/utilisateurs/{id}/suspendre/
        Body : { "action": "suspendre" | "reactiver" }
        """
        from gestion.authentification.models import UtilisateurPharmacien
        try:
            utilisateur = UtilisateurPharmacien.objects.get(pk=pk)
        except UtilisateurPharmacien.DoesNotExist:
            return Response({"erreur": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        # Protection anti-suicide
        if utilisateur == request.user:
            return Response(
                {"erreur": "Vous ne pouvez pas suspendre votre propre compte."},
                status=status.HTTP_403_FORBIDDEN,
            )

        acte = request.data.get("action", "suspendre")
        if acte == "suspendre":
            utilisateur.est_actif = False
            utilisateur.save(update_fields=["est_actif"])
            logger.info("compte_suspendu: id=%s par=%s", pk, request.user.id)
            return Response({"message": f"Compte de {utilisateur.nom_complet} suspendu.", "est_actif": False})
        elif acte == "reactiver":
            utilisateur.est_actif = True
            utilisateur.est_verrouille = False
            utilisateur.tentatives_connexion_echouees = 0
            utilisateur.save(update_fields=["est_actif", "est_verrouille", "tentatives_connexion_echouees"])
            logger.info("compte_reactive: id=%s par=%s", pk, request.user.id)
            return Response({"message": f"Compte de {utilisateur.nom_complet} réactivé.", "est_actif": True})
        else:
            return Response(
                {"erreur": "Action invalide. Valeurs acceptées : 'suspendre', 'reactiver'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="deverrouiller")
    def deverrouiller(self, request, pk=None):
        """Déverrouille un compte bloqué après trop d'échecs de connexion."""
        from gestion.authentification.models import UtilisateurPharmacien
        try:
            utilisateur = UtilisateurPharmacien.objects.get(pk=pk)
        except UtilisateurPharmacien.DoesNotExist:
            return Response({"erreur": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        utilisateur.est_verrouille = False
        utilisateur.tentatives_connexion_echouees = 0
        utilisateur.verrouille_jusqu_au = None
        utilisateur.save(update_fields=[
            "est_verrouille", "tentatives_connexion_echouees", "verrouille_jusqu_au"
        ])
        logger.info("compte_deverrouille: id=%s par=%s", pk, request.user.id)
        return Response({"message": f"Compte de {utilisateur.nom_complet} déverrouillé."})
