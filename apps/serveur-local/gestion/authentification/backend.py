"""
gestion/authentification/backend.py

Backend d'authentification personnalisé PharmApp.

Comportement :
    - Résiste à l'énumération (temps constant, message générique).
    - Verrouille les comptes après N échecs (paramétrable).
    - Réinitialise le compteur sur succès.
    - Journalise chaque tentative dans `pharmapp.securite`.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.utils import timezone

logger = logging.getLogger("pharmapp.securite")


class BackendPharmApp(BaseBackend):
    """Authentification email + mot de passe avec anti-brute-force."""

    def authenticate(self, request, email: str | None = None, password: str | None = None, **kwargs):
        from gestion.authentification.models import UtilisateurPharmacien

        # Accepte aussi le nom d'argument standard Django (`username`).
        email = (email or kwargs.get("username") or "").strip().lower()
        if not email or not password:
            return None

        try:
            user = UtilisateurPharmacien.objects.get(email__iexact=email)
        except UtilisateurPharmacien.DoesNotExist:
            # CORRECTIF (audit 2026-07-21) : empêche l'énumération en
            # égalisant le temps de réponse, sans dépendre d'un hash Argon2
            # pré-encodé dont le format n'était pas garanti valide (risque
            # d'exception non interceptée par Django selon la version
            # d'argon2-cffi, cassant systématiquement la connexion pour
            # tout email inconnu). UtilisateurPharmacien().set_password()
            # exécute un vrai hachage Argon2id du mot de passe fourni —
            # c'est l'idiome standard utilisé par ModelBackend de Django
            # pour ce même besoin — sans jamais dépendre d'un format figé.
            UtilisateurPharmacien().set_password(password)
            logger.warning("auth_echec_email_inconnu", extra={"email": email})
            return None

        # Compte verrouillé : refuser sans révéler d'info.
        if user.est_verrouille:
            if user.verrouille_jusqu_au and user.verrouille_jusqu_au <= timezone.now():
                # Déverrouillage automatique après expiration.
                user.reinitialiser_echecs_connexion()
            else:
                logger.warning(
                    "auth_echec_compte_verrouille",
                    extra={"user_id": str(user.id), "email": user.email},
                )
                return None

        if not user.est_actif:
            logger.warning("auth_echec_compte_desactive", extra={"user_id": str(user.id)})
            return None

        if not user.check_password(password):
            user.incrementer_echec_connexion()
            logger.warning(
                "auth_echec_mot_de_passe",
                extra={
                    "user_id": str(user.id),
                    "email": user.email,
                    "tentatives": user.tentatives_connexion_echouees,
                },
            )
            return None

        user.reinitialiser_echecs_connexion()
        logger.info("auth_succes", extra={"user_id": str(user.id), "email": user.email})
        return user

    def get_user(self, user_id):
        from gestion.authentification.models import UtilisateurPharmacien

        try:
            return UtilisateurPharmacien.objects.get(pk=user_id)
        except UtilisateurPharmacien.DoesNotExist:
            return None
